from pathlib import Path
# ── protocol_context hot‑reload ---------------------------------------------
TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"
_protocol_cache: dict[str, tuple[str, float]] = {}          # {path: (text, mtime)}


def get_protocol_context() -> str:
    """Protocol context caching for MCP resource exposure.
    This module handles the protocol_context.txt file that is exposed as an MCP
    resource (resource://protocol_context). This is different from internal 
    templates (which includes to protocol_context.txt) used by companions.
    """

    pc_path = TEMPLATE_DIR / "protocol_context.txt"
    
    # Check if file exists, return default if not
    if not pc_path.exists():
        default_protocol = """MINIMAL RECURSIVE ANALYSIS PROTOCOL

Approach each problem through iterative refinement:
1. Initial Analysis - Map the visible elements and relationships
2. Critique Phase - Identify gaps, inconsistencies, or areas needing depth  
3. Revision Phase - Integrate critique to produce enhanced understanding

Key principle: Each iteration should reveal deeper layers of the problem.
Stop when new iterations produce minimal new insights."""
        return default_protocol
    
    try:
        mtime = pc_path.stat().st_mtime
        cached = _protocol_cache.get(str(pc_path))
        if cached and cached[1] == mtime:
            return cached[0]
        text = pc_path.read_text(encoding="utf-8")
        _protocol_cache[str(pc_path)] = (text, mtime)
        return text
    except Exception as e:
        # If any error reading file, return a default
        return f"Error loading protocol: {str(e)}. Using fallback."


# ── Resource -----------------------------------------------------------------
async def resource_protocol_context() -> str:
    """Return the current protocol context for MCP resource exposure."""
    return get_protocol_context()