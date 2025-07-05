# SPDX-License-Identifier: MIT

"""
MCP Resources for Recursive Agents
==================================

Exposes RA's thinking methodology as readable resources:
- Protocol (strategic problem decomposition)
- Templates (by domain and type)
- Examples of thinking processes
- Dynamic capability listing
"""

from pathlib import Path
from typing import Dict, Any
import json

# Path to recursive-agents templates directory
TEMPLATES_DIR = Path(__file__).parent.parent.parent / "templates"

def register_resources(mcp):
    """Register all RA resources with the MCP server"""
    
    @mcp.resource("recursive_agents/protocol")
    async def get_protocol() -> str:
        """
        Get the Strategic Problem Decomposition Protocol.
        This protocol guides systematic discovery of hidden problem structures
        through iterative decomposition and pattern emergence.
        """
        protocol_path = TEMPLATES_DIR / "protocol_context.txt"
        if protocol_path.exists():
            return protocol_path.read_text(encoding='utf-8')
        return "Protocol file not found"
    
    @mcp.resource("recursive_agents/templates/{domain}/{template_type}")
    async def get_template(domain: str, template_type: str) -> str:
        """
        Get a specific template by domain and type.
        
        Domains: generic, marketing, bug_triage, strategy
        Types: initial_sys, critique_sys, revision_sys, critique_user, revision_user
        """
        # Map template request to actual filename
        if template_type in ["initial_sys"]:
            filename = f"{domain}_{template_type}.txt"
        else:
            # critique_sys, revision_sys, etc. are usually generic
            filename = f"generic_{template_type}.txt"
        
        template_path = TEMPLATES_DIR / filename
        if template_path.exists():
            return template_path.read_text(encoding='utf-8')
        return f"Template not found: {filename}"
    
    @mcp.resource("recursive_agents/templates/all/{domain}")
    async def get_all_domain_templates(domain: str) -> Dict[str, str]:
        """
        Get all templates for a specific domain as a JSON object.
        Useful for agents that want to implement the full methodology.
        """
        templates = {}
        
        # Get domain-specific initial_sys
        initial_path = TEMPLATES_DIR / f"{domain}_initial_sys.txt"
        if initial_path.exists():
            templates["initial_sys"] = initial_path.read_text(encoding='utf-8')
        
        # Get generic templates for other phases
        for template_type in ["critique_sys", "revision_sys", "critique_user", "revision_user"]:
            path = TEMPLATES_DIR / f"generic_{template_type}.txt"
            if path.exists():
                templates[template_type] = path.read_text(encoding='utf-8')
        
        return json.dumps(templates, indent=2)
    
    @mcp.resource("recursive_agents/examples/{domain}")
    async def get_example_thinking(domain: str) -> str:
        """
        Get an example of the thinking process for a domain.
        Returns a markdown-formatted example showing the three-phase loop.
        """
        # For now, return a structured example
        # In future, could load from actual saved examples
        example = f"""# {domain.title()} Thinking Example

## Initial Problem
"Our customer retention rate dropped 25% last quarter."

## Phase 1: Initial Draft
[Initial analysis identifying surface-level factors]

## Phase 2: Critique
"The draft identifies symptoms but misses underlying patterns. 
It needs data on timing, segments, and correlation with changes..."

## Phase 3: Revision
[Deeper analysis incorporating critique feedback, revealing root causes]

## Result
The three-phase process revealed that the retention drop concentrated 
in enterprise customers after a UI change that broke their workflows.
"""
        return example
    
    @mcp.resource("recursive_agents/capabilities")
    async def list_capabilities() -> Dict[str, Any]:
        """
        Dynamic resource showing current RA capabilities.
        Updates based on available companions and configuration.
        """
        capabilities = {
            "version": "0.1.0",
            "domains": ["generic", "marketing", "bug_triage", "strategy"],
            "features": {
                "recursive_thinking": True,
                "mcp_discovery": True,
                "streaming_support": True,
                "multi_domain_synthesis": True
            },
            "thinking_phases": {
                "1_initial_draft": "Map the visible territory",
                "2_critique": "Seek hidden architectures", 
                "3_revision": "Reveal deep structure"
            }
        }
        return json.dumps(capabilities, indent=2)