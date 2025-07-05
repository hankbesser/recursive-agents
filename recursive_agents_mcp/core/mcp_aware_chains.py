# SPDX-License-Identifier: MIT

"""
MCP-Aware Chains for Recursive Agents
=====================================

Extends BaseCompanion to be aware of other MCP servers during
the critique phase. This allows the critique to identify when
external data or tools would improve the analysis and automatically
use them.
"""

from typing import Dict, Any, List, Optional
import logging
import asyncio
from recursive_agents.core.chains import BaseCompanion, cosine_from_embeddings
from langchain_core.messages import HumanMessage, AIMessage
from recursive_agents.template_load_utils import build_templates
from .data_tools import DataTools

logger = logging.getLogger(__name__)

# MCP-aware critique template
MCP_AWARE_CRITIQUE_TEMPLATE = """You are reviewing a draft analysis to identify improvements.

Beyond standard critique, you should also identify when external data or tools would strengthen the analysis. If you identify such needs, specify them clearly using this format:

[MCP_NEED: tool_type="<type>", query="<what to look for>", reason="<why this would help>"]

For example:
[MCP_NEED: tool_type="database", query="customer churn data last quarter", reason="would provide concrete numbers to support the retention analysis"]

Provide your regular critique first, then identify any external data needs."""


class MCPAwareCompanion(BaseCompanion):
    """
    Extension of BaseCompanion that can discover and use other MCP
    servers during its critique phase.
    """
    
    def __init__(
        self,
        use_external_tools=True,
        tool_timeout=30,
        **kwargs
    ):
        """
        Initialize MCP-aware companion with data tools.
        
        Args:
            use_external_tools: Whether to use data tools during critique
            tool_timeout: Timeout for external tool calls (seconds)
            **kwargs: Passed to BaseCompanion
        """
        super().__init__(**kwargs)
        self.use_external_tools = use_external_tools
        self.tool_timeout = tool_timeout
        self.data_tools = DataTools()
        
    async def discover_tools(self):
        """Discover available MCP tools from connected servers"""
        if not self.mcp_client or not self.use_external_tools:
            return {}
            
        try:
            # This would use actual MCP discovery protocol
            # For now, returning example structure
            tools = await self.mcp_client.list_available_tools()
            self.discovered_tools = tools
            logger.info(f"Discovered {len(tools)} MCP tools")
            return tools
        except Exception as e:
            logger.warning(f"Tool discovery failed: {e}")
            return {}
    
    def parse_mcp_needs(self, critique: str) -> List[Dict[str, str]]:
        """
        Parse critique for MCP_NEED markers.
        
        Returns:
            List of dicts with tool_type, query, reason
        """
        needs = []
        lines = critique.split('\n')
        
        for line in lines:
            if '[MCP_NEED:' in line and ']' in line:
                try:
                    # Extract content between brackets
                    start = line.index('[MCP_NEED:') + 10
                    end = line.index(']', start)
                    need_str = line[start:end]
                    
                    # Parse key-value pairs
                    need = {}
                    for pair in need_str.split(', '):
                        if '=' in pair:
                            key, value = pair.split('=', 1)
                            need[key.strip()] = value.strip('"')
                    
                    if 'tool_type' in need and 'query' in need:
                        needs.append(need)
                        
                except Exception as e:
                    logger.debug(f"Failed to parse MCP_NEED: {e}")
                    
        return needs
    
    async def execute_data_tool(self, tool_type: str, query: str) -> Optional[str]:
        """
        Execute a data tool and return its result.
        
        Args:
            tool_type: Type of tool (web_search, database, etc.)
            query: Query/parameters for the tool
            
        Returns:
            Tool output or None if failed
        """
        try:
            result = await asyncio.wait_for(
                self.data_tools.execute_tool(tool_type, query=query),
                timeout=self.tool_timeout
            )
            
            # Format results for inclusion in critique
            if isinstance(result, list) and len(result) > 0:
                # For search results, format nicely
                formatted = []
                for item in result[:3]:  # Top 3 results
                    formatted.append(f"- {item.get('title', '')}: {item.get('snippet', '')}")
                return "\n".join(formatted)
            else:
                return str(result)
                
        except asyncio.TimeoutError:
            logger.warning(f"Tool {tool_type} timed out")
            return None
        except Exception as e:
            logger.warning(f"Tool {tool_type} failed: {e}")
            return None
    
    async def enhance_revision_with_tools(
        self, 
        draft: str, 
        critique: str, 
        mcp_needs: List[Dict[str, str]]
    ) -> str:
        """
        Enhance the revision by executing identified data tools.
        
        Returns:
            Additional context to include in revision
        """
        if not mcp_needs or not self.use_external_tools:
            return ""
            
        tool_results = []
        
        for need in mcp_needs:
            tool_type = need.get('tool_type', '')
            query = need.get('query', '')
            reason = need.get('reason', '')
            
            # Map critique needs to our data tools
            if tool_type in ['web_search', 'search', 'web']:
                logger.info(f"Using web search for: {query}")
                result = await self.execute_data_tool('web_search', query)
                if result:
                    tool_results.append(
                        f"\n[Web Search Results]:\n{result}\n"
                        f"(Retrieved because: {reason})\n"
                    )
            elif tool_type in ['database', 'db', 'sql']:
                logger.info(f"Using database query for: {query}")
                result = await self.execute_data_tool('database', query)
                if result:
                    tool_results.append(
                        f"\n[Database Query Results]:\n{result}\n"
                        f"(Retrieved because: {reason})\n"
                    )
            else:
                # Try web search as default
                logger.info(f"Unknown tool type '{tool_type}', using web search")
                result = await self.execute_data_tool('web_search', query)
                if result:
                    tool_results.append(
                        f"\n[Search Results for {tool_type}]:\n{result}\n"
                        f"(Retrieved because: {reason})\n"
                    )
        
        if tool_results:
            return "\n---\nAdditional Context from Data Tools:\n" + "\n".join(tool_results)
        return ""
    
    async def mcp_aware_loop(self, user_input: str) -> str:
        """
        Extended loop that can use MCP tools during critique phase.
        
        This is an async version of the standard loop that discovers
        and uses external tools when the critique identifies needs.
        """
        # No need to discover tools - we have built-in data tools
        
        # Clear run log for fresh start
        self.run_log.clear()
        
        # Initial draft (same as original)
        draft = self.init_chain.invoke(
            {"user_input": user_input, "history": self.history}
        ).content
        
        if self.verbose:
            logger.debug(f"Initial draft: {draft[:200]}...")
        
        prev = None
        prev_emb = None
        
        # Critique and revision cycles
        for i in range(1, self.max_loops + 1):
            # Get critique (potentially with MCP awareness)
            critique = self.crit_chain.invoke(
                {"user_input": user_input, "draft": draft}
            ).content
            
            if self.verbose:
                logger.debug(f"Critique #{i}: {critique[:200]}...")
            
            # Check for early exit
            if any(p in critique.lower() for p in ("no further improvements", "minimal revisions")):
                self.run_log.append({"draft": draft, "critique": critique, "revision": draft})
                break
            
            # Parse MCP needs from critique
            mcp_needs = self.parse_mcp_needs(critique)
            
            # Get external data if needed
            external_context = ""
            if mcp_needs and self.use_external_tools:
                external_context = await self.enhance_revision_with_tools(
                    draft, critique, mcp_needs
                )
            
            # Create enhanced revision input
            revision_input = {
                "user_input": user_input,
                "draft": draft,
                "critique": critique + external_context
            }
            
            # Get revision
            revised = self.rev_chain.invoke(revision_input).content
            
            # Similarity check (same as original)
            if prev is None:
                sim = None
            else:
                if prev_emb is None:
                    prev_emb = self._emb.embed_query(prev)
                cur_emb = self._emb.embed_query(revised)
                sim = cosine_from_embeddings(prev_emb, cur_emb)
            
            if self.verbose and sim is not None:
                logger.debug(f"Revision #{i} similarity: {sim:.3f}")
            
            # Check convergence
            if sim is not None and sim >= self.similarity_threshold:
                self.run_log.append({
                    "draft": draft,
                    "critique": critique,
                    "revision": revised,
                    "mcp_tools_used": [n['tool_type'] for n in mcp_needs] if mcp_needs else []
                })
                draft = revised
                break
            
            # Continue iteration
            self.run_log.append({
                "draft": draft,
                "critique": critique,
                "revision": revised,
                "mcp_tools_used": [n['tool_type'] for n in mcp_needs] if mcp_needs else []
            })
            prev = draft
            if 'cur_emb' in locals():
                prev_emb = cur_emb
            draft = revised
        
        # Update history
        self.history.extend([HumanMessage(user_input), AIMessage(draft)])
        
        if self.clear_history:
            self.history.clear()
        
        return draft if not self.return_transcript else (draft, self.run_log)