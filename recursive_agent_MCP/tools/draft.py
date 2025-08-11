# =====================================================================
# Draft Phase Tool (Initial Generation with Token Streaming)
# =====================================================================
from fastmcp import Context
from langchain_core.messages import HumanMessage, AIMessage
import asyncio
import secrets
from typing import Dict, Tuple
from datetime import datetime
from schema.inputs import GenerateDraftInput, DraftCompleteInput
from schema.outputs import DraftOutput, DraftServerOutput, DraftClientOutput, DraftCompleteOutput
from schema.common import (
    ExecutionMode, RequestMetadata, SessionMetadata, 
    IterationMetadata, Phase
)
from services.companion_manager import session_manager
from services.streaming_manager import StreamingManager, BaseTokenCallback

# ---------- draft helpers and globals ----------------------------------------

def is_new_query(companion, q: str) -> bool:
    """
    Return True if <q> should begin a new run_log slot:
      • run_log is empty   - first ever query
      • q is non-empty AND differs from last slot's .query
    Empty <q> ("" / whitespace) is treated as 'iterate again'.
    """
    if not companion.run_log:
        return True
    return q and q != companion.run_log[-1]["query"]

MAX_PAIRS = 3        # <= 6 history messsages to trim
def trim_history(hist, max_pairs: int = MAX_PAIRS):
    """
    Keep only the newest <max_pairs> (Human, AI) pairs in-place.
    Works on the flat `comp.history` list.
    """
    excess = len(hist) - max_pairs * 2
    if excess > 0:
        del hist[:excess]

# tracks pending client-side draft operations
PENDING_DRAFTS: Dict[Tuple[str, str], str] = {}  # (session_id, query_hash) -> nonce
def _get_query_hash(query: str) -> str:
    """Create consistent hash of query content for nonce validation.
    We hash the query because the initial draft (the base draft) is based on
    the query. This ensures each unique query gets its
    own nonce for initial draft operations.
    """
    import hashlib
    return hashlib.sha256(query.encode()).hexdigest()[:16]  # First 16 chars

def norm(text: str) -> str:
    return " ".join(text.strip().split())
# ---------------------------------------------------------------------

async def tool_draft(params: GenerateDraftInput, ctx: Context) -> DraftOutput:
    """Generate an initial draft using a persistent BaseCompanion instance.
    
    Server maintains companion objects with conversation history and run_log.
    Client can execute with own model, then sync state via draft_complete.
    
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
    variant = cfg.model or "server-default"

    # --- autofill query from last slot (iterate-again case) -------
    row = comp.run_log[-1] if comp.run_log else None
    if row and not params.query.strip():          # user left query blank
        params.query = row["query"]               # reuse previous question
    # --------------------------------------------------------------
    
    # -------------------------------------------------
    # Execution mode preference management 
    # -------------------------------------------------
    # 1. persist/recall a cached preference, if any
    if hasattr(comp, "preferred_execution_mode"):
        cfg.execution_mode = comp.preferred_execution_mode
    
    # 2. If undecided, ask user for preference
    if cfg.execution_mode is None:
        side = await ctx.elicit(
            "Run the draft with **your** host's (client) model or the **server** model?",
            response_type=["client", "server"]
        )
        if side.action != "accept":
            raise ValueError("Draft generation cancelled by user")
        cfg.execution_mode = ExecutionMode.CLIENT if side.data == "client" else ExecutionMode.SERVER
        
        # Ask if preference should be remembered for session
        remember = await ctx.elicit(
            "Remember this choice for the rest of the session?",
            response_type=["yes", "no"]
        )
        if remember.action != "accept":
            raise ValueError("Draft generation cancelled by user")
        if remember.data == "yes":
            # Store preference on companion instance
            comp.preferred_execution_mode = cfg.execution_mode

    # 3. Query confirmation/collection - ALWAYS elicit
    if params.query.strip():
        # Query was provided - show preview and confirm
        query_preview = params.query[:100] + "..." if len(params.query) > 100 else params.query
        
        choice = await ctx.elicit(
            f"📝 **Draft Query Confirmation**\n\n"
            f"I'll draft a response for:\n"
            f"*\"{query_preview}\"*\n\n"
            f"Would you like to continue with this query or provide a different one?",
            response_type=["continue", "new query"]
        )
        
        if choice.action != "accept":
            raise ValueError("Draft generation cancelled by user")
        
        if choice.data == "new query":
            # Ask for the new query
            res = await ctx.elicit(
                "Please provide your question or problem to draft:",
                response_type=str
            )
            if res.action != "accept":
                raise ValueError("Draft generation cancelled by user")
            params.query = res.data
        # If "continue", we keep the existing params.query
        
    else:
        # No query provided - ask for it directly
        res = await ctx.elicit(
            "What would you like me to draft a response for?",
            response_type=str
        )
        if res.action != "accept":
            raise ValueError("Draft generation cancelled by user")
        params.query = res.data

    # 5. Check for overwrite warning (middleware handles hard blocks)
    last_slot = comp.run_log[-1] if comp.run_log else None
    if last_slot and not is_new_query(comp, params.query):
        # We're dealing with the same query, now check variant
        last_variant = last_slot.get("variant", "")
        current_variant = variant  # Already computed above
        same_variant = last_variant == current_variant
        
        if same_variant:
            # Note: PhaseValidationMiddleware already blocked if revisions exist
            
            # Check if there's already a draft (overwrite warning)
            has_draft = bool(last_slot.get("draft"))
            has_revision = len(last_slot.get("revision", [])) > 0
            
            if has_draft and not has_revision:
                # Give user a choice since this is a legitimate action
                choice = await ctx.elicit(
                    "⚠️ **Draft Overwrite Warning**\n\n"
                    "You already have a draft for this query and model variant.\n\n"
                    "Continuing will replace your existing draft. Since you haven't "
                    "created any revisions yet, this is allowed but will lose your "
                    "previous draft.\n\n"
                    "Do you want to overwrite the existing draft?",
                    response_type=["continue", "cancel"]
                )
                
                if choice.action != "accept" or choice.data == "cancel":
                    raise ValueError("Draft generation cancelled by user")
                # If they choose continue, the draft will be overwritten below
# -------------------------------------------
    

    # --------------------------------------------------------
    # ── CLIENT-SIDE SAMPLING PATH ───────────────────────────
    if cfg.execution_mode == ExecutionMode.CLIENT:
        # Get templates - initial_sys includes protocol injection
        sys_t = comp.TEMPLATES["initial_sys"]
        
        # IMPORTANT: the draft's init_chain is different from crit/rev chains!
        # init_chain expects: {user_input} and history via MessagesPlaceholder
        # The chain will format: SystemMessage + History + HumanMessage(user_input)
        # So we just return the system prompt and the raw query
        
        # Note: Client needs to handle history injection between system and user
        usr_t = params.query
        
        # Generate nonce for tracking this draft operation
        nonce = secrets.token_urlsafe(16)  # 128-bit security
        query_hash = _get_query_hash(params.query)
        
        # Store in pending operations
        PENDING_DRAFTS[(session_id, query_hash)] = nonce
        
        # Progress notification
        await ctx.report_progress(
            message=f"→ Client-side draft requested (nonce: {nonce[:4]}...)"
        )
        
        # Return prompts and metadata for client-side generation
        return DraftClientOutput(
            system=sys_t,
            user=usr_t,
            session_id=session_id,
            nonce=nonce,
            history_length=len(comp.history),
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
    # --------------------------------------------------------

    # --------------------------------------------------------
    # ── SERVER-SIDE SAMPLING PATH ──────────────────────────────
    # Server executes the draft chain with streaming
    
    # Capture event loop for thread-safe streaming
    current_loop = asyncio.get_running_loop()
    
    # Create streaming manager with bounded queue
    # This prevents memory issues if tokens arrive faster than we can send them
    stream_mgr = StreamingManager()
    
    # Create callback for LangChain → MCP streaming bridge with proper event loop handling
    callback = BaseTokenCallback(stream_mgr, current_loop, phase="draft")
    
    # Attach callback to the initial draft chain
    chain = comp.init_chain.with_config(callbacks=[callback])
    
    # Execute with streaming
    # Use context manager to ensure cleanup even if errors occur
    async with stream_mgr.stream_handler():
        # Start chain execution in background
        # Note: init_chain expects both user_input and history
        run_task = asyncio.create_task(
            chain.ainvoke({
                "user_input": params.query,
                "history": comp.history  # Include conversation context
            })
        )
        
        # Stream tokens as they arrive, with automatic timeout handling
        # This prevents hanging if the LLM stops producing tokens
        async for tok in stream_mgr.stream_tokens():
            await ctx.report_progress(progress=0, total=None, message=tok)
        
        # Wait for completion and get final draft
        draft_msg = await run_task
        draft = draft_msg.content
    # ────────────────────────────────────────────────────────────
    
    # Check for streaming errors and report if any occurred
    error_summary = callback.get_error_summary()
    if error_summary:
        await ctx.report_progress(
            progress=0,
            total=None,
            message=f"\n{error_summary}\n"
        )
    
    # --- decide slot strategy-------------
    last      = comp.run_log[-1] if comp.run_log else None
    new_slot  = (
        is_new_query(comp, params.query)          # query changed
        or not last                               # first ever
        or last.get("variant") != variant         # same query but new variant
    )
    # --------------------------------------------------------
    
    # ---------- Update conversation history ----------
    # Draft is the first phase that updates history
    # This maintains conversation continuity
    if new_slot:
        comp.history.extend([HumanMessage(params.query), AIMessage(draft)])
        # TRIM HERE - only when we add new pairs
        if len(comp.history) > MAX_PAIRS * 2:
            trim_history(comp.history)
    else:
        # iterate again → replace last assistant message only
        comp.history[-1] = AIMessage(draft)
        # No trim needed - size didn't change
    
    # ---------- run_log handling ---------------------
    # ---------- Initialize run_log for this iteration ----------
    # Create the first entry in run_log with draft
    # Critique and revision will update this same entry
    if new_slot:
        # create NEW slot
        comp.run_log.append({
            "query":     params.query,
            "draft":     draft,
            "variant":   variant,
            "critique":  [],  # intialize list of critique strings 
            "revision":  [],  # intialize list of revision strings
            "sampling":  cfg.model_dump(),
        })
    else:
        # reuse last slot (iteration)
        comp.run_log[-1]["draft"] = draft
        comp.run_log[-1]["sampling"] = cfg.model_dump()
        
    # Progress notification for server-side completion
    await ctx.report_progress(message="✓ Server's Draft complete")
    
    # Build metadata
    
    # Request metadata from FastMCP context
    request_meta = RequestMetadata(
        request_id=ctx.request_id,
        client_id=ctx.client_id,
        session_id=session_id,
        progress_token=ctx.request_context.meta.progressToken if ctx.request_context.meta else None
    )
    
    # Session metadata from session manager
    session = session_manager.sessions.get(session_id, {})
    session_meta = SessionMetadata(
        created_at=session.get("created_at", datetime.now()),
        last_accessed=session.get("last_accessed", datetime.now()),
        companion_types=list(session.get("companions", {}).keys()),
        total_iterations=sum(len(slot.get("critique", [])) for slot in comp.run_log),
        total_requests=len(comp.run_log),
        current_phase=Phase.DRAFT
    )
    
    # Get phase tracking for elapsed time (if middleware tracked it)
    phase_tracking = ctx.get_state("phase_tracking") or {}
    elapsed_ms = int(phase_tracking.get("phase_timings", {}).get("draft_0", 0) * 1000) if phase_tracking else None
    
    # Get any early suggestions from middleware
    suggestions = ctx.get_state("suggestions") or {}
    convergence_hints = []
    if suggestions.get("message"):
        convergence_hints.append(suggestions["message"])
    
    # Iteration metadata
    iteration_meta = IterationMetadata(
        iteration_number=1,  # Draft is always iteration 1
        phase=Phase.DRAFT,
        similarity_score=None,  # Not applicable for draft
        convergence_hints=convergence_hints,
        elapsed_ms=elapsed_ms
    )
    
    # Save the session after modifications
    session_manager.mark_companion_modified(session_id)
    
    return DraftServerOutput(
        draft=draft,
        session_id=session_id,
        execution_mode=ExecutionMode.SERVER,
        model_used=variant,
        timestamp=datetime.now().isoformat(),
        request_metadata=request_meta,
        session_metadata=session_meta,
        iteration_metadata=iteration_meta
    )

# =====================================================================
# Draft Completion Handler (Client-Side Only)
# =====================================================================
async def tool_draft_complete(params: DraftCompleteInput, ctx: Context) -> DraftCompleteOutput:
    """Complete client-side draft generation with deterministic logging.
    
    This function MUST be called after client-side draft generation to:
    1. Validate the operation via nonce
    2. Update conversation history
    3. Initialize run_log entry
    4. Maintain state consistency with server-side path
    
    The nonce system ensures:
    - No duplicate completions
    - No completions without matching draft request
    - Audit trail of all operations
    """
    variant = "client"  # All client-side executions use the same variant
    
    # Validate nonce to ensure this matches a pending operation
    query_hash = _get_query_hash(params.query)
    key = (params.session_id, query_hash)
    
    # Read nonce without removing (validate first)
    nonce = PENDING_DRAFTS.get(key)
    
    if nonce is None:
        raise ValueError(f"No pending draft for session {params.session_id}")
    if params.nonce != nonce:
        raise ValueError("Nonce mismatch - this draft completion is invalid")
    
    # Remove from pending only after validation passes
    PENDING_DRAFTS.pop(key)
    
    # Get companion instance to update state
    comp = session_manager.get_companion(params.session_id, params.companion_type)
    
    # --- decide slot strategy --------------------------------
    last      = comp.run_log[-1] if comp.run_log else None
    new_slot  = (
        is_new_query(comp, params.query)
        or not last
        or last.get("variant") != variant
    )

    # ---------- Update conversation history ----------
    # Draft is the first phase that updates history
    # This maintains conversation continuity
    if new_slot:
        comp.history.extend([HumanMessage(params.query), AIMessage(params.draft)])
        # TRIM HERE - only when we add new pairs
        if len(comp.history) > MAX_PAIRS * 2:
            trim_history(comp.history)
    else:
        # iterate again → replace last assistant message only
        comp.history[-1] = AIMessage(params.draft)
        # No trim needed - size didn't change

    # Initialize run_log entry (same structure as server-side)
    if new_slot:
        comp.run_log.append({
            "query":     params.query,
            "draft":     params.draft,
            "variant":   variant,
            "critique":  [],  # intialize list of critique strings 
            "revision":  [],  # intialize list of revision strings
            "sampling":  {"client_side": True,
                        "metadata":   params.metadata or {}},
        })
    else:
        comp.run_log[-1]["draft"]    = params.draft
        comp.run_log[-1]["sampling"] = {"client_side": True,
                                        "metadata":   params.metadata or {}}
    
    # Progress notification
    await ctx.report_progress(
        message=f"✓ Client draft logged (nonce {params.nonce[:4]}…)"
    )
    
    return DraftCompleteOutput(
        status="logged",
        session_id=params.session_id
    )