# SPDX-License-Identifier: MIT

"""
MCP Prompts for Recursive Agents
================================

Pre-built prompt templates that guide users in effectively
using RA's thinking methodology through MCP.
"""

def register_prompts(mcp):
    """Register all RA prompts with the MCP server"""
    
    @mcp.prompt("recursive_analysis")
    async def recursive_analysis_prompt():
        """
        Basic recursive analysis using the three-phase methodology.
        Guides the user to think through draft, critique, and revision.
        """
        return {
            "name": "Recursive Analysis",
            "description": "Analyze a problem using RA's three-phase thinking methodology",
            "arguments": [
                {
                    "name": "problem",
                    "description": "The problem or question to analyze deeply",
                    "required": True
                },
                {
                    "name": "domain", 
                    "description": "Analysis perspective: generic, marketing, bug_triage, or strategy",
                    "required": False,
                    "default": "generic"
                }
            ],
            "prompt": """I'll analyze this problem using recursive thinking methodology.

First, I'll use the think_recursively tool to perform a deep analysis through multiple critique-revision cycles.

Problem: {{problem}}
Domain: {{domain}}

Let me analyze this systematically..."""
        }
    
    @mcp.prompt("multi_perspective_synthesis")  
    async def multi_perspective_prompt():
        """
        Analyze from multiple perspectives and synthesize insights.
        Useful for complex problems requiring diverse viewpoints.
        """
        return {
            "name": "Multi-Perspective Synthesis",
            "description": "Analyze a problem from multiple domain perspectives and synthesize",
            "arguments": [
                {
                    "name": "problem",
                    "description": "The complex problem requiring multiple perspectives",
                    "required": True
                },
                {
                    "name": "domains",
                    "description": "Comma-separated list of domains (e.g., 'marketing,bug_triage')",
                    "required": False,
                    "default": "marketing,bug_triage"
                }
            ],
            "prompt": """I'll analyze this problem from multiple perspectives to get a comprehensive understanding.

Problem: {{problem}}

I'll examine this from these perspectives: {{domains}}

Then I'll synthesize these viewpoints into a unified strategy. This multi-perspective approach often reveals hidden connections and comprehensive solutions."""
        }
    
    @mcp.prompt("debug_with_history")
    async def debug_with_history_prompt():
        """
        Analyze a problem and show the complete thinking process.
        Useful for understanding how the AI reaches its conclusions.
        """
        return {
            "name": "Debug Analysis with History", 
            "description": "Analyze and show the complete thinking process",
            "arguments": [
                {
                    "name": "problem",
                    "description": "The problem to analyze with full transparency",
                    "required": True
                },
                {
                    "name": "domain",
                    "description": "Domain for analysis",
                    "required": False,
                    "default": "generic"
                }
            ],
            "prompt": """I'll analyze this problem and show you my complete thinking process.

Problem: {{problem}}

I'll use the think_with_details tool to capture not just the final answer, but also:
- Each critique phase
- How the analysis evolved
- Why it converged when it did

This transparency helps you understand the reasoning path."""
        }
    
    @mcp.prompt("learn_ra_methodology")
    async def learn_methodology_prompt():
        """
        Learn about RA's thinking methodology by examining the protocol and templates.
        Educational prompt for understanding the system.
        """
        return {
            "name": "Learn RA Methodology",
            "description": "Understand how Recursive Agents' thinking methodology works",
            "arguments": [
                {
                    "name": "domain",
                    "description": "Domain to explore (generic, marketing, bug_triage, strategy)",
                    "required": False,
                    "default": "generic"
                }
            ],
            "prompt": """I'll help you understand Recursive Agents' thinking methodology.

Let me access the strategic problem decomposition protocol and show you how the three-phase process works:

1. Initial Decomposition - mapping the visible territory
2. Pattern Compression - seeking hidden architectures  
3. Structural Synthesis - revealing deep structure

I'll also show you the {{domain}} templates to see how this methodology is applied in practice."""
        }
    
    @mcp.prompt("iterative_refinement")
    async def iterative_refinement_prompt():
        """
        Guide through manual iterative refinement of an analysis.
        Interactive approach to thinking improvement.
        """
        return {
            "name": "Iterative Refinement Guide",
            "description": "Manually guide through critique and refinement cycles",
            "arguments": [
                {
                    "name": "initial_analysis",
                    "description": "Your initial analysis or draft to refine",
                    "required": True
                },
                {
                    "name": "focus_area",
                    "description": "Specific aspect to focus critique on",
                    "required": False
                }
            ],
            "prompt": """Let's refine your analysis through structured critique.

Initial Analysis: {{initial_analysis}}
{% if focus_area %}Focus Area: {{focus_area}}{% endif %}

I'll help you:
1. Identify gaps and weaknesses in the current analysis
2. Suggest specific improvements
3. Guide the revision process

This manual approach helps you internalize the recursive thinking methodology."""
        }