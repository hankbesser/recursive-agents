# SPDX-License-Identifier: MIT

"""
MCP Tools for Recursive Agents
==============================

Executable tools that perform recursive thinking and analysis.
These tools use RA's three-phase methodology internally while
presenting simple interfaces to MCP clients.
"""

from typing import Dict, Any, List, Optional
import json
import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Import RA components
from recursive_agents.base import (
    GenericCompanion, 
    MarketingCompanion, 
    BugTriageCompanion, 
    StrategyCompanion
)
from recursive_agents.template_load_utils import build_templates
from core.mcp_aware_chains import MCPAwareCompanion

# Companion mapping
COMPANION_MAP = {
    "generic": GenericCompanion,
    "marketing": MarketingCompanion,
    "bug_triage": BugTriageCompanion,
    "strategy": StrategyCompanion
}

# Store session histories for retrieval
SESSION_HISTORIES = {}

def register_tools(mcp):
    """Register all RA tools with the MCP server"""
    
    @mcp.tool()
    async def think_recursively(
        problem: str, 
        domain: str = "generic",
        max_loops: int = 3,
        temperature: float = 0.7
    ) -> str:
        """
        Analyze a problem using Recursive Agents' three-phase thinking.
        
        The analysis will go through draft -> critique -> revision cycles
        until convergence or max_loops is reached.
        
        Args:
            problem: The problem or question to analyze
            domain: Analysis perspective (generic, marketing, bug_triage, strategy)
            max_loops: Maximum critique-revision cycles (1-5)
            temperature: LLM temperature for creativity vs focus (0.0-1.0)
            
        Returns:
            The refined analysis after recursive thinking
        """
        if domain not in COMPANION_MAP:
            return f"Unknown domain: {domain}. Available: {list(COMPANION_MAP.keys())}"
        
        # Create companion with specified parameters
        companion_class = COMPANION_MAP[domain]
        companion = companion_class(
            temperature=temperature,
            max_loops=max_loops,
            clear_history=True,
            return_transcript=True
        )
        
        # Run the analysis
        try:
            # Run in thread pool since companions aren't async
            loop = asyncio.get_event_loop()
            result, run_log = await loop.run_in_executor(
                None, 
                companion.loop, 
                problem
            )
            
            # Store session for history retrieval
            session_id = f"{domain}_{datetime.now().isoformat()}"
            SESSION_HISTORIES[session_id] = {
                "problem": problem,
                "domain": domain,
                "result": result,
                "run_log": run_log,
                "iterations": len(run_log),
                "transcript": companion.transcript_as_markdown()
            }
            
            # Return result with session info
            return f"{result}\n\n---\n_Session ID: {session_id} | Iterations: {len(run_log)}_"
            
        except Exception as e:
            return f"Error during analysis: {str(e)}"
    
    @mcp.tool()
    async def think_with_details(
        problem: str,
        domain: str = "generic",
        include_critique: bool = True,
        include_metrics: bool = True
    ) -> Dict[str, Any]:
        """
        Get detailed recursive analysis including thinking process.
        
        Returns structured data with the final answer, critiques,
        revisions, and convergence metrics.
        
        Args:
            problem: The problem to analyze
            domain: Analysis perspective
            include_critique: Include critique/revision history
            include_metrics: Include convergence metrics
            
        Returns:
            Dictionary with analysis details
        """
        if domain not in COMPANION_MAP:
            return {"error": f"Unknown domain: {domain}"}
        
        companion_class = COMPANION_MAP[domain]
        companion = companion_class(
            clear_history=True,
            return_transcript=True
        )
        
        try:
            loop = asyncio.get_event_loop()
            result, run_log = await loop.run_in_executor(
                None,
                companion.loop,
                problem
            )
            
            response = {
                "final_answer": result,
                "domain": domain,
                "iterations": len(run_log)
            }
            
            if include_critique:
                response["thinking_process"] = companion.transcript_as_markdown()
                response["critiques"] = [step["critique"] for step in run_log]
            
            if include_metrics:
                response["metrics"] = {
                    "iterations": len(run_log),
                    "max_loops": companion.max_loops,
                    "converged": len(run_log) < companion.max_loops,
                    "similarity_threshold": companion.similarity_threshold
                }
            
            return response
            
        except Exception as e:
            return {"error": str(e)}
    
    @mcp.tool()
    async def think_with_live_data(
        problem: str,
        domain: str = "generic",
        enable_search: bool = True
    ) -> str:
        """
        Analyze using recursive thinking with access to live web data.
        
        The critique phase can search for current information to enhance
        the analysis with real-time data.
        
        Args:
            problem: The problem to analyze
            domain: Analysis perspective
            enable_search: Whether to allow web searches during critique
            
        Returns:
            Analysis enhanced with live data when relevant
        """
        try:
            # Use MCP-aware companion for live data access
            templates = build_templates(
                initial_sys=f"{domain}_initial_sys" if domain != "generic" else "generic_initial_sys",
                critique_sys="mcp_critique_sys"  # Use MCP-aware critique
            )
            
            companion = MCPAwareCompanion(
                templates=templates,
                use_external_tools=enable_search,
                clear_history=True,
                return_transcript=True
            )
            
            # Run the analysis with potential live data enhancement
            result, run_log = await companion.mcp_aware_loop(problem)
            
            # Check if any external data was used
            tools_used = []
            for step in run_log:
                if "mcp_tools_used" in step and step["mcp_tools_used"]:
                    tools_used.extend(step["mcp_tools_used"])
            
            # Add metadata about data sources
            if tools_used:
                result += f"\n\n---\n_Enhanced with live data from: {', '.join(set(tools_used))}_"
            
            return result
            
        except Exception as e:
            logger.error(f"Live data analysis failed: {e}")
            return f"Error during live data analysis: {str(e)}"
    
    @mcp.tool()
    async def synthesize_perspectives(
        problem: str,
        domains: List[str] = ["marketing", "bug_triage"],
        synthesize: bool = True
    ) -> Dict[str, str]:
        """
        Analyze a problem from multiple domain perspectives.
        
        Each domain performs its own recursive analysis, then optionally
        synthesizes all perspectives using the strategy companion.
        
        Args:
            problem: The problem to analyze
            domains: List of domains to analyze from
            synthesize: Whether to synthesize into unified strategy
            
        Returns:
            Dictionary with each domain's analysis and optional synthesis
        """
        results = {}
        
        # Validate domains
        valid_domains = [d for d in domains if d in COMPANION_MAP]
        if not valid_domains:
            return {"error": "No valid domains specified"}
        
        # Run each domain analysis in parallel
        tasks = []
        for domain in valid_domains:
            companion = COMPANION_MAP[domain](clear_history=True)
            task = asyncio.create_task(
                asyncio.get_event_loop().run_in_executor(
                    None,
                    companion.loop,
                    problem
                )
            )
            tasks.append((domain, task))
        
        # Collect results
        for domain, task in tasks:
            try:
                result = await task
                results[domain] = result
            except Exception as e:
                results[domain] = f"Error: {str(e)}"
        
        # Synthesize if requested
        if synthesize and len(results) > 1:
            synthesis_input = f"Problem: {problem}\n\n"
            for domain, analysis in results.items():
                synthesis_input += f"=== {domain.upper()} ANALYSIS ===\n{analysis}\n\n"
            synthesis_input += "Synthesize these perspectives into a unified strategy."
            
            strategy = StrategyCompanion(clear_history=True)
            try:
                synthesis_result = await asyncio.get_event_loop().run_in_executor(
                    None,
                    strategy.loop,
                    synthesis_input
                )
                results["synthesis"] = synthesis_result
            except Exception as e:
                results["synthesis"] = f"Synthesis error: {str(e)}"
        
        return results
    
    @mcp.tool()
    async def get_thinking_history(session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve the thinking history from a previous analysis session.
        
        Args:
            session_id: The session ID from a previous analysis.
                       If None, returns list of available sessions.
                       
        Returns:
            Session details or list of available sessions
        """
        if session_id is None:
            # Return list of available sessions
            sessions = []
            for sid, data in SESSION_HISTORIES.items():
                sessions.append({
                    "session_id": sid,
                    "domain": data["domain"],
                    "problem_preview": data["problem"][:100] + "...",
                    "iterations": data["iterations"]
                })
            return {"available_sessions": sessions}
        
        if session_id in SESSION_HISTORIES:
            return SESSION_HISTORIES[session_id]
        else:
            return {"error": f"Session not found: {session_id}"}