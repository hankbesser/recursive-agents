# =====================================================================
# Revision Phase Tool (single-pass, server + client)
# =====================================================================
from fastmcp import Context
import asyncio
import secrets
from typing import Dict, Tuple
from datetime import datetime
from schema.inputs import ReviseInput, ReviseCompleteInput
from schema.outputs import ReviseOutput, ReviseServerOutput, ReviseClientOutput, ReviseCompleteOutput
from schema.common import (
    ExecutionMode, RequestMetadata, SessionMetadata, 
    IterationMetadata, Phase
)
from services.companion_manager import session_manager
from services.streaming_manager import StreamingManager, BaseTokenCallback
from langchain_core.messages import AIMessage

# ---------- Revision helpers and globals -------------------------------------

# tracks pending client-side revision operations
PENDING_REVISIONS: Dict[Tuple[str, str], str] = {}  # (session_id, critique_hash) -> nonce
def _get_critique_hash(critique: str) -> str:
    """Create consistent hash of critique content for nonce validation.
    We hash the critique (not the draft) because revision is based on
    the critique's feedback. This ensures each unique critique gets its
    own nonce for revision operations.
    """
    import hashlib
    return hashlib.sha256(critique.encode()).hexdigest()[:16]  # First 16 chars
# ---------------------------------------------------------------------

async def tool_revise(params: ReviseInput, ctx: Context) -> ReviseOutput:
    """Generate revision using a persistent BaseCompanion instance.
    
    Server maintains companion objects with conversation history and run_log.
    Client can execute with own model, then sync state via tool_revise_complete.
    
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
    # Get current slot - middleware ensures both draft and critique exist
    row = comp.run_log[-1] if comp.run_log else None
    # Note: PhaseValidationMiddleware already verified draft and critique exist
    
    # Get the critique array (we know it exists from middleware validation)
    critiques = row.get("critique", [])
    
    # --- autofill query, latest "draft" (which could be the last revision) and latest critique
    params.query = row["query"]
    params.critique = critiques[-1]
    # Determine what we're revising
    revisions = row.get("revision", [])
    if len(critiques)>1:
        params.draft = revisions[-1]  # Revise based the latest revision ("draft")
        draft_source    = f"revision #{len(critiques)-1}"
        critique_source = f"critique #{len(critiques)}"
        revision_number = len(revisions) + 1
    else:
        params.draft = row["draft"]   # Revise the original draft
        draft_source = "original draft"
        critique_source = "critique #1"
        revision_number = 1
    
    
    # Re-revising same content - show overwrite warning
    # revisions can NEVER be more than critiques
    # and if there are the same amount of critiques and revisions 
    # we know are atempting to overwrite last revision 
    if critiques and len(critiques) == len(revisions):
        choice = await ctx.elicit(
            f"⚠️ **Revision Already Exists**\n\n"
            f"You are attempting to overwrite revision #{len(revisions)} based on {critique_source} and {draft_source} for\n\n"
            f"Query: \"{row['query'][:100]}...\"\n\n"
            f"Would you like to continue?",
            response_type=["overwrite", "cancel"]
        )
        if choice.action != "accept" or choice.data == "cancel":
            raise ValueError("Revision cancelled by user")
        
        # Info message about what's being revision is being overwritten
        await ctx.report_progress(
            message=f"📝 Overwriting revision #{len(revisions)} based on {critique_source} and {draft_source} "
        )
    else:
        # Info message about what's being revised
        await ctx.report_progress(
            message=f"📝 Creating revision #{revision_number} based on {critique_source} and {draft_source} "
        )
    # -----------------------------------------------------------------

    # ── CLIENT-SIDE SAMPLING -----------------------------------------
    if cfg.execution_mode == ExecutionMode.CLIENT:
        sys_t = comp.TEMPLATES["revision_sys"]
        usr_t = comp.TEMPLATES["revision_user"].format(
            user_input=params.query,
            draft=params.draft,
            critique=params.critique
        )
        # Generate nonce for this revision operation
        nonce = secrets.token_urlsafe(16)        # 96-bit
        critique_hash = _get_critique_hash(params.critique)
        
        # Store in pending operations
        PENDING_REVISIONS[(session_id, critique_hash)] = nonce
        
        # Progress notification
        await ctx.report_progress(
            message=f"→ Client-side revision requested (nonce: {nonce[:4]}...)"
        )
        
        # Return prompts and metadata for client-side generation
        return ReviseClientOutput(
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
    # -----------------------------------------------------------------

    # ── SERVER-SIDE SAMPLING──────────────────────────────────
    # Server executes the revision chain with streaming

    # Capture event loop for thread-safe streaming
    current_loop = asyncio.get_running_loop()
    
    # Create streaming manager with bounded queue
    # This prevents memory issues if tokens arrive faster than we can send them
    stream_mgr = StreamingManager()
    
    # Create callback for LangChain → MCP streaming bridge with proper event loop handling
    callback = BaseTokenCallback(stream_mgr, current_loop, phase="revision")
    
    # Attach callback to the revision chain
    chain = comp.rev_chain.with_config(callbacks=[callback])


    # Execute with streaming
    # Use context manager to ensure cleanup even if errors occur
    async with stream_mgr.stream_handler():
        run_task = asyncio.create_task(
            chain.ainvoke({
                "user_input": params.query,
                "draft":      params.draft,
                "critique":   params.critique
            })
        )

        # Stream tokens as they arrive, with automatic timeout handling
        # This prevents hanging if the LLM stops producing tokens
        async for tok in stream_mgr.stream_tokens():
            await ctx.report_progress(progress=0, total=None, message=tok)
        
        # Wait for chain completion and get revision
        rev_msg  = await run_task
        revision = rev_msg.content
    # ────────────────────────────────────────────────────────────

    # Check for streaming errors and report if any occurred
    error_summary = callback.get_error_summary()
    if error_summary:
        await ctx.report_progress(
            progress=0,
            total=None,
            message=f"\n{error_summary}\n"
        )

    
    # Update history - replace last AI message with new revision
    comp.history[-1] = AIMessage(revision)

    # ---------- run_log handling-----------------------------------
     # Append or overwrite to revision array
    if len(critiques) == len(revisions):
        row["revision"][-1] = revision  # Overwrite
    else:
        row["revision"].append(revision)  # Append new

    # Update the sampling info to reflect the latest operation
    row["sampling"] = cfg.model_dump()
    
    # Calculate similarity score in server mode with 2+ revisions
    revisions_after = row["revision"]
    
    # Check if user wants similarity calculation
    # Default to True in server mode with 2+ revisions
    should_calculate_similarity = params.calculate_similarity
    if should_calculate_similarity is None:
        # Default: True for server mode with 2+ revisions
        should_calculate_similarity = (execution_mode == ExecutionMode.SERVER and len(revisions_after) >= 2)
    
    if should_calculate_similarity and execution_mode == ExecutionMode.SERVER and len(revisions_after) >= 2:
        try:
            # Compare last two revisions for convergence
            prev_revision = revisions_after[-2]
            curr_revision = revisions_after[-1]
            
            # Use the companion's calculate_similarity method
            # This requires chain_V2.py with the public method
            if hasattr(comp, 'calculate_similarity'):
                similarity_score = comp.calculate_similarity(prev_revision, curr_revision)
                
                # Store similarity score in the run_log slot
                row["similarity_score"] = similarity_score
                
                # Log for debugging
                logger.debug(f"Similarity between revisions: {similarity_score:.4f}")
                
                # Check if we've reached convergence threshold
                if similarity_score >= comp.similarity_threshold:
                    logger.info(f"Convergence detected: {similarity_score:.4f} >= {comp.similarity_threshold}")
            else:
                logger.warning("Companion doesn't have calculate_similarity method - using chains.py instead of chain_V2.py?")
        except Exception as e:
            logger.error(f"Failed to calculate similarity: {e}")
            # Don't fail the whole revision, just skip similarity
    
    # Save the session after modifications
    session_manager.mark_companion_modified(session_id)
    # -----------------------------------------------------------------

    # Progress notification for server-side completion
    await ctx.report_progress(message="✓ Server's Revision complete")

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
    iteration_number = len(row.get("revision", []))
    
    # Check if we have similarity score from middleware (future enhancement)
    similarity_score = ctx.get_state("similarity_score")
    
    # Get convergence signals from middleware via proper FastMCP pattern
    convergence_signals = ctx.get_state("convergence_signals") or []
    # Extract messages from convergence signals for hints
    convergence_hints = [signal.get("message", "") for signal in convergence_signals if isinstance(signal, dict)]
    
    # Get phase tracking for elapsed time
    phase_tracking = ctx.get_state("phase_tracking") or {}
    elapsed_ms = int(phase_tracking.get("phase_timings", {}).get(f"revise_{iteration_number}", 0) * 1000) if phase_tracking else None
    
    # Get suggestions from middleware
    suggestions = ctx.get_state("suggestions") or {}
    # Add suggestion message to convergence hints if available
    if suggestions.get("message"):
        convergence_hints.append(suggestions["message"])
    
    iteration_meta = IterationMetadata(
        iteration_number=iteration_number,
        phase=Phase.REVISION,
        similarity_score=similarity_score,
        convergence_hints=convergence_hints,
        elapsed_ms=elapsed_ms
    )
    
    return ReviseServerOutput(
        revision=revision,
        session_id=session_id,
        execution_mode=ExecutionMode.SERVER,
        model_used=variant,
        timestamp=datetime.now().isoformat(),
        request_metadata=request_meta,
        session_metadata=session_meta,
        iteration_metadata=iteration_meta
    )

# =====================================================================
# Revision Completion Handler (Client-Side Only)
# =====================================================================
async def tool_revise_complete(params: ReviseCompleteInput, ctx: Context) -> ReviseCompleteOutput:
    """Complete client-side revision generation with proper array handling.
    
    This handler validates the nonce to ensure the revision operation is
    legitimate, then updates memory data structures identically to server-side
    execution. Supports both append and overwrite based on whether we're
    re-revising with the same critique.
    """
    
    # Validate nonce
    critique_hash = _get_critique_hash(params.critique)
    key = (params.session_id, critique_hash)
    # Read the pending nonce without removing it yet
    nonce = PENDING_REVISIONS.get(key)
    
    if nonce is None:
        raise ValueError(f"No pending revision for session {params.session_id}")
    if params.nonce != nonce:
        raise ValueError("Nonce mismatch")
    
    # Remove from pending only after successful check
    PENDING_REVISIONS.pop(key)
    
    # Log completion into the existing slot
    comp = session_manager.get_companion(params.session_id, params.companion_type)
    # Get current slot to apply same append or overwrite logic as server-side
    row = comp.run_log[-1]
    critiques = row.get("critique", [])
    revisions = row.get("revision", [])
    
    # Update history - replace last AI message with new revision
    comp.history[-1] = AIMessage(params.revision)
    
    # ---------- run_log handling ---------------------
    # Append or overwrite to revision array
    if len(critiques) == len(revisions):
        row["revision"][-1] = params.revision  # Overwrite
    else:
        row["revision"].append(params.revision)  # Append new
    
    # Store sampling metadata in consistent format
    row["sampling"] = {"client_side": True,
                       "metadata": params.metadata or {}}
    
    # Report successful completion with nonce for audit trail
    await ctx.report_progress(
        message=f"✓ Client revision logged (nonce {params.nonce[:4]}…)"
    )
    
    return ReviseCompleteOutput(
        status="logged",
        session_id=params.session_id
    )
