from typing import Dict, Any, List, Optional
from services.companion_manager import session_manager
from .protocol_resource import get_protocol_context

def _paginate(lst: List[Any], offset: int, limit: Optional[int]) -> List[Any]:
    if limit is None:
        return lst[offset:]
    return lst[offset: offset + limit]

async def resource_history(session_id: str,
                           companion_type: str = "generic",
                           offset: int = 0,
                           limit: Optional[int] = None) -> Dict[str, Any]:
    comp = session_manager.get_companion(session_id, companion_type)
    payload = [m.dict() for m in comp.history]   # serialize LangChain messages
    return {
        "history": _paginate(payload, offset, limit),
        "total": len(payload),
        "offset": offset
    }

async def resource_run_log(session_id: str,
                           companion_type: str = "generic",
                           offset: int = 0,
                           limit: Optional[int] = None) -> Dict[str, Any]:
    comp = session_manager.get_companion(session_id, companion_type)
    return {
        "run_log": _paginate(comp.run_log, offset, limit),
        "total": len(comp.run_log),
        "offset": offset
    }

async def resource_full_prompt(session_id: str,
                               companion_type: str = "generic",
                               turn: int = -1) -> Dict[str, Any]:
    comp = session_manager.get_companion(session_id, companion_type)
    # use the latest user message by default
    user_input = comp.history[turn].content if comp.history else ""
    prompt = comp.init_chain.prompt.format(
        user_input=user_input,
        history=comp.history
    )
    return {"full_prompt": prompt,
            "protocol_context": get_protocol_context(),   # for completeness 
            "turn": turn, 
            "session_id": session_id}