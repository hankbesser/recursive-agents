# =====================================================================
# Critique Phase Tool (token streaming) 
# =====================================================================
from fastmcp import Context
import asyncio
import secrets
from typing import Dict, Tuple
from datetime import datetime
from schema.inputs import CritiqueDraftInput, CritiqueCompleteInput
from schema.outputs import CritiqueOutput, CritiqueServerOutput, CritiqueClientOutput, CritiqueCompleteOutput
from schema.common import (
    ExecutionMode, RequestMetadata, SessionMetadata, 
    IterationMetadata, Phase
)
from services.companion_manager import session_manager
from services.streaming_manager import StreamingManager, BaseTokenCallback

# ---------- Critique helpers and globals  ---------------------------------------------------

MAX_DRAFT_WINDOW = 3        # how many previous drafts to surface
def last_n_drafts(companion, query: str, n: int = MAX_DRAFT_WINDOW) -> str:
    """
    Return baseline draft + up to (n-1) recent revisions from current slot.
    Always includes the original draft as reference point.
    """
    # Get current slot
    if not companion.run_log:
        return ""
    
    current_slot = companion.run_log[-1]
    if current_slot["query"] != query:
        return ""  # Shouldn't happen with new architecture
    
    drafts = []
    
    # Always include baseline draft first
    drafts.append(f"[ORIGINAL BASELINE]\n{current_slot['draft']}")
    
    # Add recent revisions (presented as drafts)
    revisions = current_slot.get("revision", [])
    if revisions:
        # Take the last (n-1) revisions since we already have the baseline
        recent_revisions = revisions[-(n-1):] if len(revisions) > (n-1) else revisions
        
        for i, rev in enumerate(recent_revisions):
            # Calculate the actual revision number
            revision_num = len(revisions) - len(recent_revisions) + i + 1
            drafts.append(f"[ITERATION {revision_num}]\n{rev}")
    
    return "\n\n---\n\n".join(drafts)

# tracks pending client-side draft operations
PENDING_CRITIQUES: Dict[Tuple[str, str], str] = {}  # (session_id, draft_hash) -> nonce
def _get_draft_hash(draft: str) -> str:
    """Create consistent hash of draft content for nonce validation.
    We hash the draft (not the query) because critique is based on
    the draft's feedback. This ensures each unique draft gets its
    own nonce for critique operations.
    """
    import hashlib
    return hashlib.sha256(draft.encode()).hexdigest()[:16]  # First 16 chars
# ---------------------------------------------------------------------

async def tool_critique(params: CritiqueDraftInput, ctx: Context) -> CritiqueOutput:
    """Generate critique using a persistent BaseCompanion instance.
    
    Server maintains companion objects with conversation history and run_log.
    Client can execute with own model, then sync state via tool_critique_complete.
    
    Key difference from typical MCP tools:
    - Companion instance persists between calls with full state
    - Client-side execution updates server-side memory through completion pattern
    - Same memory structure regardless of execution location
    
    Memory accessible via:
    - resource://sessions/{session_id}/{companion_type}/history
    - resource://sessions/{session_id}/{companion_type}/run_log
    """
    
    # Get session_id from FastMCP context (fallback to params if needed)
    session_id = ctx.session_id if ctx.session_id else params.session_id
    if not session_id:
        session_id = session_manager.get_or_create_session()
    
    # Get companion with full sampling config
    comp = session_manager.get_companion(session_id, params.companion_type, params.sampling)
    cfg = params.sampling                 
    # -------------------------------------------------
    # Sampling preference management 
    # -------------------------------------------------
    # Get current slot - middleware ensures draft exists
    row = comp.run_log[-1] if comp.run_log else None
    # Note: PhaseValidationMiddleware already verified draft exists
    
    # --- autofill query and latest "draft" (which could be the last revision)
    # Get the query and working draft from run_log
    params.query = row["query"]
    # Determine what we're critiquing (latest revision or original draft)
    revisions = row.get("revision", [])
    if revisions:
        params.draft = revisions[-1]  # Critique the latest revision
        draft_source = f"revision #{len(revisions)}"
    else:
        params.draft = row["draft"]   # Critique the original draft
        draft_source = "original draft"
    critiques = row.get("critique", [])
    
    # Re-critiquing same content - show overwrite warning
    # critiques can NEVER be more than revisions + 1
    # and if there more critiques than revisions 
    # we know are attempting to overwrite the last critique
    if critiques and len(critiques) > len(revisions):
        choice = await ctx.elicit(
            f"⚠️ **Critique Already Exists**\n\n"
            f"You are attempting to overwrite critique #{len(critiques)} of the {draft_source} for\n\n"
            f"Query: \"{row['query'][:100]}...\"\n\n"
            f"Would you like to continue?",
            response_type=["overwrite", "cancel"]
        )
        if choice.action != "accept" or choice.data == "cancel":
            raise ValueError("Critique cancelled by user")
        
        
        # Info message about what's being critique is being overwritten
        await ctx.report_progress(
            message=f"📝 Overwriting critique #{len(critiques)} based on {draft_source}  "
        )
    else:
        # Info message about what's being crtiqued
        await ctx.report_progress(
            message=f"📝 Creating critique #{len(critiques)+1} based on {draft_source} "
        )
    # --------------------------------------------------------

    # ── CLIENT-SIDE SAMPLING ───────────────────────────
    window_raw = last_n_drafts(comp, params.query)  # text of last 3 (or n) drafts for critique to see
    window     = ( "Earlier drafts (oldest → newest):\n"
               + window_raw ) if window_raw else ""
    
    # add context  
    if cfg.execution_mode == ExecutionMode.CLIENT:
        sys_t = comp.TEMPLATES["critique_sys"]
        usr_t = comp.TEMPLATES["critique_user"].format(
            user_input=params.query, 
            draft=params.draft,
            prev_drafts=window
        )
        
        # Generate nonce for this critique operation
        nonce = secrets.token_urlsafe(16)        # 96-bit
        draft_hash = _get_draft_hash(params.draft)

        # Store in pending operations
        PENDING_CRITIQUES[(session_id, draft_hash)] = nonce

        # Progress notificatione
        await ctx.report_progress(
            message=f"→ Client-side critique requested (nonce: {nonce[:4]}...)"
        )

        # Return prompts and metadata for client-side generation
        return CritiqueClientOutput(
            system=sys_t,
            user=usr_t,
            session_id=session_id,
            nonce=nonce,
            use_client_sampling=True,  # Keep for backward compatibility
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
            model=cfg.model,
            metadata={
                "execution_mode": cfg.execution_mode.value,
                "model_preferences": cfg.model_preferences,
                **(cfg.metadata or {})
            }
        )
    # ──────────────────────────────────────────────────────────
    

    # ── SERVER-SIDE SAMPLING──────────────────────────────────
    # Server executes the critique chain with streaming

    # Capture event loop for thread-safe streaming
    current_loop = asyncio.get_running_loop()
    
    # Create streaming manager with bounded queue
    # This prevents memory issues if tokens arrive faster than we can send them
    stream_mgr = StreamingManager()
    
    # Create callback for LangChain → MCP streaming bridge with proper event loop handling
    callback = BaseTokenCallback(stream_mgr, current_loop, phase="critique")
    
    # Attach callback to the critique chain
    chain = comp.crit_chain.with_config(callbacks=[callback])
    
    # Execute with streaming
    # Use context manager to ensure cleanup even if errors occur
    async with stream_mgr.stream_handler():
        # Start chain execution in background
        run_task = asyncio.create_task(
            chain.ainvoke({
                "user_input": params.query, 
                "draft": params.draft,
                "prev_drafts": window 
            })
        )
        
        # Stream tokens as they arrive, with automatic timeout handling
        # This prevents hanging if the LLM stops producing tokens
        async for tok in stream_mgr.stream_tokens():
            await ctx.report_progress(progress=0, total=None, message=tok)
        
        # Wait for chain completion and get crtitique
        crit_msg = await run_task
        critique = crit_msg.content
    # ────────────────────────────────────────────────────────────
    
    # Check for streaming errors and report if any occurred
    error_summary = callback.get_error_summary()
    if error_summary:
        await ctx.report_progress(
            progress=0,
            total=None,
            message=f"\n{error_summary}\n"
        )
    
    # ---------- run_log handling ---------------------
    # Append or overwrite to critique array
    if len(critiques) > len(revisions):
        row["critique"][-1] = critique  # Overwrite
    else:
        row["critique"].append(critique)  # Append new

    # Update the sampling info to reflect the latest operation
    row["sampling"] = cfg.model_dump()
    
    # Get the model variant used (from cfg or row)
    variant = cfg.model or row.get("variant", "server-default")
    
    # Build metadata
    
    # Request metadata from FastMCP context
    request_meta = RequestMetadata(
        request_id=ctx.request_id,
        client_id=ctx.client_id,
        session_id=session_id,
        progress_token=ctx.request_context.meta.progressToken if ctx.request_context.meta else None
    )
    
    # Session metadata
    session_meta = session_manager.get_session_metadata(session_id)
    
    # Iteration metadata
    iteration_number = len(row.get("critique", []))
    
    # Get convergence signals from middleware via proper FastMCP pattern
    convergence_signals = ctx.get_state("convergence_signals") or []
    # Extract messages from convergence signals for hints
    convergence_hints = [signal.get("message", "") for signal in convergence_signals if isinstance(signal, dict)]
    
    # Get phase tracking for elapsed time
    phase_tracking = ctx.get_state("phase_tracking") or {}
    elapsed_ms = int(phase_tracking.get("phase_timings", {}).get(f"critique_{iteration_number}", 0) * 1000) if phase_tracking else None
    
    iteration_meta = IterationMetadata(
        iteration_number=iteration_number,
        phase=Phase.CRITIQUE,
        similarity_score=None,  # Not applicable for critique
        convergence_hints=convergence_hints,
        elapsed_ms=elapsed_ms
    )
    
    return CritiqueServerOutput(
        critique=critique,
        session_id=session_id,
        execution_mode=ExecutionMode.SERVER,
        model_used=variant,
        timestamp=datetime.now().isoformat(),
        request_metadata=request_meta,
        session_metadata=session_meta,
        iteration_metadata=iteration_meta
    )

# =====================================================================
# Critique Completion Handler (Client-Side Only)
# =====================================================================
async def tool_critique_complete(params: CritiqueCompleteInput, ctx: Context) -> CritiqueCompleteOutput:
    """Complete client-side critique generation with proper array handling.
    
    This handler validates the nonce to ensure the critique operation is
    legitimate, then updates memory data structures identically to server-side
    execution. Supports both append and overwrite based on whether we're
    re-critiquing with the same draft.
    """
    
    # Validate nonce
    draft_hash = _get_draft_hash(params.draft)
    key = (params.session_id, draft_hash)
    # Read the pending nonce without removing it yet
    nonce = PENDING_CRITIQUES.get(key)  

    if nonce is None:
        raise ValueError(f"No pending critique for session {params.session_id}")
    if params.nonce != nonce:
        raise ValueError("Nonce mismatch")
    
    # Remove from pending only after successful check
    PENDING_CRITIQUES.pop(key)
    
    # Log completion into the existing slot
    comp = session_manager.get_companion(params.session_id, params.companion_type)
    # Get current slot to apply same append or overwrite logic as server-side
    row = comp.run_log[-1]
    critiques = row.get("critique", [])
    revisions = row.get("revision", [])
    # ---------- run_log handling ---------------------
    # Append or overwrite to critique array
    if len(critiques) > len(revisions):
        row["critique"][-1] = params.critique  # Overwrite
    else:
        row["critique"].append(params.critique)  # Append new

    
    
    # Store sampling metadata in consistent format
    row["sampling"] = {"client_side": True,
                       "metadata": params.metadata or {}}

    # Report successful completion with nonce for audit trail
    await ctx.report_progress(
        message=f"✓ Client critique logged (nonce {params.nonce[:4]}…)"
    )

    return CritiqueCompleteOutput(
        status="logged",
        session_id=params.session_id
    )