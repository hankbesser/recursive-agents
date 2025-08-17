# resources/session_resources.py
"""
Session-based resources for direct memory access.

These resources allow clients to read session state directly without
going through tools, reducing response payload size and enabling
better client-side caching.
"""

from typing import Dict, Any, Optional
from services.companion_manager import session_manager


async def resource_session_run_log(
    session_id: str,
    companion_type: str = "generic",
    slot_index: Optional[int] = None
) -> Dict[str, Any]:
    """Get run_log data for a session.
    
    URI: resource://sessions/{session_id}/{companion_type}/run_log
    Or:  resource://sessions/{session_id}/{companion_type}/run_log/{slot_index}
    """
    comp = session_manager.get_companion(session_id, companion_type)
    
    if slot_index is not None:
        # Specific slot requested
        if 0 <= slot_index < len(comp.run_log):
            return {
                "slot_index": slot_index,
                "slot": comp.run_log[slot_index],
                "total_slots": len(comp.run_log)
            }
        else:
            return {
                "error": f"Slot {slot_index} not found",
                "total_slots": len(comp.run_log)
            }
    
    # Return all slots
    return {
        "run_log": comp.run_log,
        "total_slots": len(comp.run_log),
        "current_slot": comp.run_log[-1] if comp.run_log else None
    }


async def resource_session_current_phase(
    session_id: str,
    companion_type: str = "generic"
) -> Dict[str, Any]:
    """Get current phase position for a session.
    
    URI: resource://sessions/{session_id}/{companion_type}/phase
    
    This resource analyzes the run_log and returns the current phase position,
    making it easy for clients to understand where they are in the iteration.
    """
    comp = session_manager.get_companion(session_id, companion_type)
    
    if not comp.run_log:
        return {
            "phase": "initial",
            "next_action": "draft",
            "iteration": 0,
            "can_critique": False,
            "can_revise": False
        }
    
    current_slot = comp.run_log[-1]
    critiques = current_slot.get("critique", [])
    revisions = current_slot.get("revision", [])
    
    # Determine phase position
    if not current_slot.get("draft"):
        phase = "needs_draft"
        next_action = "draft"
    elif len(critiques) == len(revisions):
        phase = "balanced"
        next_action = "critique_or_finalize"
    elif len(critiques) > len(revisions):
        phase = "needs_revision"
        next_action = "revise"
    else:
        phase = "unknown"
        next_action = "unknown"
    
    return {
        "phase": phase,
        "next_action": next_action,
        "iteration": max(len(critiques), len(revisions)),
        "critiques_count": len(critiques),
        "revisions_count": len(revisions),
        "can_critique": bool(current_slot.get("draft")) and len(critiques) == len(revisions),
        "can_revise": len(critiques) > len(revisions),
        "query": current_slot.get("query", "")
    }
