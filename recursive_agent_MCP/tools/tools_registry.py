"""
Tool Registration Module for Recursive Agents MCP Server
========================================================

This module handles the registration of all MCP tools with the FastMCP server.
It uses a registration pattern to avoid circular imports while maintaining
clean separation between tool implementation and MCP protocol handling.

The registration process:
1. Import tool functions (without decorators)
2. Import their corresponding input schemas
3. Register each tool with the MCP server instance
"""

from typing import Dict, List, Tuple, Callable, Any
import logging

from fastmcp import FastMCP

# Import tool implementations
from .draft import tool_draft, tool_draft_complete
from .critique import tool_critique, tool_critique_complete
from .revise import tool_revise, tool_revise_complete

# Set up logging for registration debugging
logger = logging.getLogger(__name__)


# Tool registry configuration
# Each tuple contains: (name, function, description)
TOOL_REGISTRY: List[Tuple[str, Callable, str, Dict[str, Any]]] = [
(
    "draft",
    tool_draft,
    "Generate initial draft analysis. ALWAYS the first tool to call for any query. "
    "Creates new memory slot for: new queries, different server models, or switching to client execution. "
    "Will elicit: 1) execution preference (server/client), 2) query confirmation/collection. "
    "Blank query reuses previous query for continued iteration. "
    "BLOCKS draft creation if revisions exist (preserves iteration integrity). "
    "If client execution chosen, you MUST call draft_complete afterward.",
    {
    "idempotentHint": False,    # Different results each time
    "openWorldHint": True       # They call external LLMs
    }

),
(
    "draft_complete",
    tool_draft_complete,
    "REQUIRED after client-side draft execution to sync results back to server. "
    "Validates nonce and updates conversation state. "
    "Only call this if you chose client execution in draft tool. "
    "Do NOT call for server-side execution.",
    {
    "idempotentHint": True,     # Same nonce = same result
    "openWorldHint": False      # No external calls, just work with data 
    }
    
),
(
    "critique",
    tool_critique,
    "Analyze and critique to identify improvements. "
    "SECOND STEP in reasoning process. REQUIRES existing draft in session. "
    "Critiques the LATEST content (original draft OR most recent revision). "
    "Shows context window: baseline draft + up to 2 recent revisions for comparison. "
    "Can overwrite last critique if re-critiquing same content. "
    "If client execution chosen, you MUST call critique_complete afterward.",
    {
    "idempotentHint": False,    # Different results each time
    "openWorldHint": True       # They call external LLMs
    }
),
(
    "critique_complete",
    tool_critique_complete,
    "REQUIRED after client-side critique execution to sync results back to server. "
    "Validates nonce and updates conversation state. "
    "Only call this if you chose client execution in critique tool. "
    "Do NOT call for server-side execution.",
    {
    "idempotentHint": True,     # Same nonce = same result
    "openWorldHint": False      # No external calls, just works with data 
    }
),
(
    "revise",
    tool_revise,
    "Generate improved version based on critique feedback. "
    "THIRD STEP in reasoning process. REQUIRES both draft AND critique exist. "
    "Revises based on critique count: if only 1 critique, revises original draft; if multiple critiques, revises latest revision. "
    "Uses the LATEST critique to guide improvements. "
    "To continue iterating: run critique again after revision, then revise again. "
    "If client execution chosen, you MUST call revise_complete afterward.",
    {
    "idempotentHint": False,    # Different results each time
    "openWorldHint": True       # They call external LLMs
    }
),
(
    "revise_complete",
    tool_revise_complete,
    "REQUIRED after client-side revision execution to sync results back to server. "
    "Validates nonce and updates conversation state. "
    "Only call this if you chose client execution in revision tool. "
    "Do NOT call for server-side execution.",
    {
    "idempotentHint": True,     # Same nonce = same result
    "openWorldHint": False      # No external calls, just works with data 
    }
),
]


def register_all_tools(mcp: FastMCP) -> int:
    """
    Register all Recursive Agents tools with the MCP server.
    
    This function applies the MCP tool decorator to each tool function,
    which enables:
    - Automatic JSON-RPC protocol handling
    - Input validation via Pydantic schemas
    - Tool discovery via tools/list
    - Error handling and response formatting
    
    Args:
        mcp: The FastMCP server instance to register tools with
        
    Returns:
        int: Number of tools successfully registered
        
    Raises:
        RuntimeError: If tool registration fails
    """
    registered_count = 0
    
    logger.info(f"Starting tool registration for {len(TOOL_REGISTRY)} tools")
    
    for tool_name, tool_func, description, annotations in TOOL_REGISTRY:
        try:
            # The decorator pattern: mcp.tool() returns a decorator function
            # We immediately apply it to our tool function
            mcp.tool(
                name=tool_name,
                description=description,
                annotations=annotations
            )(tool_func)
            
            registered_count += 1
            
        except Exception as e:
            error_msg = f"Failed to register tool '{tool_name}': {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    logger.info(f"Successfully registered {registered_count} tools")
    return registered_count


def get_tool_names() -> List[str]:
    """Get list of all available tool names."""
    return [name for name, _, _, _ in TOOL_REGISTRY]


def get_tool_info() -> List[dict]:
    """Get detailed information about all registered tools."""
    return [
        {
            "name": name,
            "description": desc,
            "annotations": annotations 
        }
        for name, _, desc, annotations in TOOL_REGISTRY
    ]