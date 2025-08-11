# recursive_agent_MCP/middleware/phase_validation.py
"""
Phase validation middleware for the three-phase reasoning system.

This middleware ensures proper phase transitions in the draft → critique → revise
cycle, preventing invalid operations like critiquing without a draft or revising
without a critique.
"""

from typing import Optional
from mcp import McpError
from mcp.types import ErrorData
from fastmcp.server.middleware import Middleware, MiddlewareContext, CallNext
from services.companion_manager import session_manager


class PhaseValidationMiddleware(Middleware):
    """Validates phase transitions in the three-phase reasoning system.
    
    Ensures:
    - Cannot critique without a draft
    - Cannot revise without a critique
    - Draft creation follows overwrite rules (no new draft if revisions exist)
    
    Runs BEFORE Pydantic validation, so handles raw arguments dict.
    """
    
    async def on_call_tool(self, context: MiddlewareContext, call_next: CallNext):
        """Validate phase transitions for draft, critique, and revise tools."""
        tool_name = context.message.name
        
        # Only validate our three phases
        if tool_name not in ["draft", "critique", "revise"]:
            return await call_next(context)
        
        # Extract from raw arguments (pre-Pydantic)
        args = context.message.arguments or {}
        companion_type = str(args.get("companion_type", "generic"))
        session_id = args.get("session_id")  # Might be None
        
        # Skip validation if we can't get context
        if not context.fastmcp_context:
            return await call_next(context)
        
        # Use context session_id if not provided
        if not session_id:
            session_id = context.fastmcp_context.session_id
        
        try:
            # Get companion state (without sampling_config since we're just validating)
            # Note: Tools will pass sampling_config when they actually execute
            comp = session_manager.get_companion(session_id, companion_type)
            current_slot = comp.run_log[-1] if comp.run_log else None
            
            # Phase-specific validation
            if tool_name == "critique":
                self._validate_critique_prerequisites(current_slot)
            elif tool_name == "revise":
                self._validate_revise_prerequisites(current_slot)
            elif tool_name == "draft":
                self._validate_draft_constraints(current_slot, args)
            
        except ValueError as e:
            # Convert to MCP error
            raise McpError(ErrorData(
                code=-32602,
                message=f"Phase validation failed: {str(e)}"
            ))
        
        # Validation passed, continue
        return await call_next(context)
    
    def _validate_critique_prerequisites(self, slot: Optional[dict]):
        """Critique requires a draft to exist."""
        if not slot or not slot.get("draft"):
            raise ValueError(
                "Cannot critique: No draft exists in current session. "
                "Please run the draft tool first."
            )
    
    def _validate_revise_prerequisites(self, slot: Optional[dict]):
        """Revise requires both draft and critique, with proper array balance."""
        if not slot or not slot.get("draft"):
            raise ValueError(
                "Cannot revise: No draft exists in current session. "
                "Please run the draft tool first."
            )
        
        critiques = slot.get("critique", [])
        if not critiques:
            raise ValueError(
                "Cannot revise: No critique exists. "
                "Please run the critique tool first."
            )
        
        # CRITICAL: Check array balance - can only revise if more critiques than revisions
        revisions = slot.get("revision", [])
        if len(critiques) <= len(revisions):
            raise ValueError(
                f"Cannot revise: Already have {len(revisions)} revision(s) for {len(critiques)} critique(s). "
                "You must run critique again before creating another revision. "
                "The system maintains balance: each critique gets one revision."
            )
    
    def _validate_draft_constraints(self, slot: Optional[dict], args: dict):
        """Draft has special overwrite protection rules."""
        if not slot:
            return  # First draft is always allowed
        
        # Extract query to check if it's the same
        query = args.get("query", "").strip()
        if not query:
            # Empty query means reuse previous - check will happen in tool
            query = slot.get("query", "")
        
        # Check if same query
        if query == slot.get("query", ""):
            # Same query - check if revisions exist
            revisions = slot.get("revision", [])
            if revisions:
                # This is the hard block - no user choice
                raise ValueError(
                    "Cannot create new draft: Revisions exist for this query. "
                    "Creating a new baseline draft would corrupt the iteration chain. "
                    "Each query gets exactly ONE baseline draft. "
                    "To start fresh, modify your query slightly (even adding a period)."
                )
        
        # Note: Overwrite warnings for existing drafts stay in the tool
        # This middleware only blocks the hard constraints