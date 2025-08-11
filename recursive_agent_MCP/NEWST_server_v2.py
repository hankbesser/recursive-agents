# recursive_agent_MCP/NEWEST_server_v2.py
# =============================================================================
# FastMCP 2.10 wrapper for Recursive Agents (BaseCompanion)
#   • draft   • critique   • revise   • loop     (token‑level streaming)
#   • resource://protocol_context  (read‑only)
# =============================================================================
# ── FastMCP 2.10 -------------------------------------------------------------
from fastmcp import FastMCP      
from contextlib import asynccontextmanager
from services.companion_manager import session_manager
from tools.tools_registry import register_all_tools
from resources.resources_registry import register_all_resources
from middleware.phase_validation import PhaseValidationMiddleware
from middleware.phase_metrics import PhaseMetricsMiddleware


@asynccontextmanager
async def companion_lifespan(server: FastMCP):
    """Manage session lifecycle and cleanup tasks."""
    # Start the cleanup task
    await session_manager.start_cleanup_task()
    
    try:
        # Yield control to FastMCP
        yield {}
    finally:
        # Shutdown and clean up all sessions
        await session_manager.shutdown()

# ── FastMCP server object ----------------------------------------------------
mcp = FastMCP("RecursiveAgent-MCP-v2", lifespan=companion_lifespan)

# ── Middleware Registration --------------------------------------------------
# Add middleware to enhance the three-phase reasoning system.
# Middleware executes in the order added: first middleware runs first.
# 1. Validation runs first to ensure phase rules are followed
mcp.add_middleware(PhaseValidationMiddleware())
# 2. Metrics middleware tracks real metrics (replaces PhaseIntelligence)
mcp.add_middleware(PhaseMetricsMiddleware())

# ── Tool Registration --------------------------------------------------------
# Register all tools with the MCP server using the registry pattern.
# This approach avoids circular imports while maintaining clean separation
# between tool implementation and MCP protocol handling.
#
# The registration process:
# 1. register_all_tools() iterates through TOOL_REGISTRY (defined in tools_registry.py)
# 2. For each tool, it calls mcp.tool() which returns a decorator function
# 3. That decorator is immediately applied to the tool function
# 4. FastMCP internally stores the decorated function in its tool registry
#
# Why the decorator pattern is needed:
# The mcp.tool() decorator performs crucial operations:
#   - Protocol Wrapping: Wraps async functions to handle JSON-RPC protocol
#   - Schema Validation: Uses Pydantic schemas to validate inputs before execution
#   - Error Handling: Catches exceptions and converts them to MCP error responses
#   - Discovery Registration: Adds tools to internal registry for tools/list discovery
#   - Context Injection: Handles the ctx: Context parameter injection for MCP features
#
# This registration must happen after the MCP instance is created but before
# the server starts running.
register_all_tools(mcp)

# ── Resource Registration ----------------------------------------------------
# Register all resources with the MCP server using the same registry pattern
# as tools. This maintains consistency and clean separation.
#
# Resources in MCP are read-only data sources that clients can access via
# resource:// URIs. Unlike tools which perform actions, resources provide
# information that can be loaded into the LLM's context.
#
# The registration process mirrors tool registration:
# 1. register_all_resources() iterates through RESOURCE_REGISTRY
# 2. For each resource, it calls mcp.resource() which returns a decorator
# 3. That decorator is applied to the resource function
# 4. FastMCP internally stores the resource for resources/list discovery
#
# Currently we have one resource:
#   - resource://protocol_context: The strategic decomposition protocol
#
# This must happen after MCP instance creation but before server starts.
register_all_resources(mcp)

# Initialize metrics resources with the intelligence middleware
from resources.metrics_resources import set_intelligence_middleware
set_intelligence_middleware(intelligence_middleware)

# ── run ----------------------------------------------------------------------
if __name__ == "__main__":
    mcp.run(host="0.0.0.0", port=8000, transport="http") 
    # if terminal only
    # mcp.run() if launch from Claude CLI you usually don’t want HTTP; drop the kwargs entirely   