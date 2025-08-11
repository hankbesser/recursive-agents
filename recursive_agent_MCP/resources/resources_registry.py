"""
Resource Registration Module for Recursive Agents MCP Server
===========================================================

This module handles the registration of all MCP resources with the FastMCP server.
It follows the same pattern as tool registration to avoid circular imports while
maintaining clean separation between resource implementation and MCP protocol handling.

Resources in MCP are read-only data sources that clients can access. Unlike tools
which perform actions, resources provide information that can be loaded into the
LLM's context.

The registration process:
1. Import resource functions (without decorators)
2. Register each resource with the MCP server instance
"""

from typing import List, Tuple, Callable
import logging

from fastmcp import FastMCP

# Import resource implementations
from .protocol_resource import resource_protocol_context
from .template_resources import (
    resource_template_by_path,
    resource_templates_by_phase,
    resource_templates_by_domain,
    resource_all_templates,
    resource_template_domains
)
from .memory_resources import (
    resource_history,
    resource_run_log,
    resource_full_prompt
)
from .metrics_resources import (
    resource_global_metrics,
    resource_companion_metrics,
    resource_learning_suggestions,
    set_intelligence_middleware
)
from .session_resources import (
    resource_session_run_log,
    resource_session_current_phase,
    resource_session_suggestions
)



# Set up logging for registration debugging
logger = logging.getLogger(__name__)


# Resource registry configuration
# Static resources: (uri, name, function, description)
RESOURCES: List[Tuple[str, str, Callable, str]] = [
    (
        "resource://protocol",
        "protocol",
        resource_protocol_context,
        "The strategic problem decomposition protocol that guides companion analysis"
    ),
    (
        "resource://templates/all",
        "all_templates",
        resource_all_templates,
        "Get all templates with metadata"
    ),
    (
        "resource://templates/domains",
        "template_domains", 
        resource_template_domains,
        "List all available template domains"
    ),
]

# Template resources: (uri_pattern, name, function, description)
TEMPLATE_RESOURCES: List[Tuple[str, str, Callable, str]] = [
    (
        "resource://templates/{domain}/{type}/{phase}",
        "template_by_path",
        resource_template_by_path,
        "Access specific template by domain/type/phase"
    ),
    (
        "resource://templates/{phase}/{type}",
        "templates_by_phase",
        resource_templates_by_phase,
        "Get all templates for a specific phase and type"
    ),
    (
        "resource://templates/{domain}/all",
        "templates_by_domain",
        resource_templates_by_domain,
        "Get all templates for a specific domain"
    ),
]

# Dynamic memory resources: (uri_pattern, name, function, description)
DYNAMIC_RESOURCES: List[Tuple[str, str, Callable, str]] = [
    (
        "resource://sessions/{session_id}/{ctype}/history", 
        "history",
        resource_history, 
        "Paginated conversation history"
    ),
    (
        "resource://sessions/{session_id}/{ctype}/run_log", 
        "run_log",
        resource_run_log, 
        "Paginated per-turn run-log"
    ),
    (
        "resource://sessions/{session_id}/{ctype}/full_prompt", 
        "full_prompt",
        resource_full_prompt, 
        "Rendered prompt for deterministic replay"),
]

# Session state resources: (uri_pattern, name, function, description)
SESSION_RESOURCES: List[Tuple[str, str, Callable, str]] = [
    (
        "resource://sessions/{session_id}/{companion_type}/run_log",
        "session_run_log",
        resource_session_run_log,
        "Direct access to session run_log data"
    ),
    (
        "resource://sessions/{session_id}/{companion_type}/phase",
        "session_current_phase",
        resource_session_current_phase,
        "Current phase position and available actions"
    ),
    (
        "resource://sessions/{session_id}/{companion_type}/suggestions",
        "session_suggestions",
        resource_session_suggestions,
        "AI-generated suggestions for next actions"
    ),
]

# Metrics resources: (uri, name, function, description)
METRICS_RESOURCES: List[Tuple[str, str, Callable, str]] = [
    (
        "resource://metrics/global",
        "global_metrics",
        resource_global_metrics,
        "Aggregated learning metrics across all sessions"
    ),
    (
        "resource://metrics/companion/{companion_type}",
        "companion_metrics",
        resource_companion_metrics,
        "Metrics for a specific companion type"
    ),
    (
        "resource://metrics/suggestions",
        "learning_suggestions",
        resource_learning_suggestions,
        "AI-powered suggestions based on learned patterns"
    ),
]

# Combine for backward compatibility
RESOURCE_REGISTRY = RESOURCES + TEMPLATE_RESOURCES + DYNAMIC_RESOURCES + SESSION_RESOURCES + METRICS_RESOURCES 


def register_all_resources(mcp: FastMCP) -> int:
    """
    Register all resources with the MCP server.
    
    This function applies the MCP resource decorator to each resource function,
    which enables:
    - URI-based access pattern (resource://...)
    - Read-only data exposure
    - Resource discovery via resources/list
    - Consistent error handling
    
    Args:
        mcp: The FastMCP server instance to register resources with
        
    Returns:
        int: Number of resources successfully registered
        
    Raises:
        RuntimeError: If resource registration fails
    """
    registered_count = 0
    
    logger.info(f"Starting resource registration for {len(RESOURCE_REGISTRY)} resources")
    
    for uri, name, resource_func, description in RESOURCE_REGISTRY:
        try:
            # Apply the resource decorator
            mcp.resource(
                uri=uri,
                name=name,
                description=description
            )(resource_func)
            
            registered_count += 1
            logger.debug(f"Registered resource '{name}' at {uri}")
            
        except Exception as e:
            error_msg = f"Failed to register resource '{name}': {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    
    logger.info(f"Successfully registered {registered_count} resources")
    return registered_count


def get_resource_uris() -> List[str]:
    """Get list of all available resource URIs."""
    return [uri for uri, _, _, _ in RESOURCE_REGISTRY]


def get_resource_info() -> List[dict]:
    """Get detailed information about all registered resources."""
    return [
        {
            "uri": uri,
            "name": name,
            "description": desc
        }
        for uri, name, _, desc in RESOURCE_REGISTRY
    ]

