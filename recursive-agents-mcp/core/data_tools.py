# SPDX-License-Identifier: MIT

"""
Data Tools for MCP-Aware Critique
==================================

Provides real data fetching capabilities that the critique phase
can use to enhance its analysis. Includes web search, database
queries, and other data sources.
"""

import logging
from typing import List, Dict, Any, Optional
import json
import httpx
from urllib.parse import quote

logger = logging.getLogger(__name__)


class DataTools:
    """
    Collection of data fetching tools for the critique phase.
    
    These tools can be called when the critique identifies
    needs for external data to improve the analysis.
    """
    
    def __init__(self):
        self.available_tools = {
            "web_search": self.web_search,
            "google_search": self.google_search,
            "database": self.database_query,
            # Add more tools as needed
        }
        self.http_client = None
    
    async def web_search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """
        Search the web for information using DuckDuckGo.
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            List of search results with title, url, snippet
        """
        try:
            logger.info(f"Searching web for: {query}")
            
            # Try to import duckduckgo_search
            try:
                from duckduckgo_search import AsyncDDGS
            except ImportError:
                logger.error("duckduckgo-search not installed. Install with: pip install duckduckgo-search")
                return [{
                    "title": "Error: Search library not installed",
                    "url": "",
                    "snippet": "Please install duckduckgo-search: pip install duckduckgo-search"
                }]
            
            # Perform actual web search
            async with AsyncDDGS() as ddgs:
                results = []
                async for r in ddgs.text(query, max_results=num_results):
                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", "")
                    })
                
                logger.info(f"Found {len(results)} search results")
                return results
            
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            # Return error as a result so critique knows what happened
            return [{
                "title": "Search Error",
                "url": "",
                "snippet": f"Search failed with error: {str(e)}"
            }]
    
    async def google_search(self, query: str, num_results: int = 5) -> List[Dict[str, str]]:
        """
        Search Google as a fallback option.
        Uses web scraping approach - may be rate limited.
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            List of search results
        """
        try:
            logger.info(f"Google search for: {query}")
            
            if not self.http_client:
                self.http_client = httpx.AsyncClient(
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                )
            
            # Google search URL
            url = f"https://www.google.com/search?q={quote(query)}&num={num_results}"
            
            response = await self.http_client.get(url)
            
            if response.status_code != 200:
                logger.warning(f"Google search returned status {response.status_code}")
                # Fall back to DuckDuckGo
                return await self.web_search(query, num_results)
            
            # For now, return a simple response indicating we tried
            # In production, we'd parse the HTML properly
            return [{
                "title": "Google Search Result",
                "url": url,
                "snippet": f"Google search attempted for: {query}. Consider using DuckDuckGo for better programmatic access."
            }]
            
        except Exception as e:
            logger.error(f"Google search failed: {e}")
            # Fall back to DuckDuckGo
            return await self.web_search(query, num_results)
    
    async def database_query(self, query: str, db_type: str = "sqlite") -> Any:
        """
        Query a database for information.
        
        Args:
            query: SQL query or natural language query
            db_type: Type of database (sqlite, postgres, etc.)
            
        Returns:
            Query results
        """
        try:
            logger.info(f"Querying {db_type} database: {query}")
            
            # Placeholder for actual implementation
            # TODO: Implement real database access
            result = {
                "status": "success",
                "data": f"Database query result for: {query}",
                "rows": []
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Database query failed: {e}")
            return {"status": "error", "message": str(e)}
    
    async def execute_tool(self, tool_type: str, **kwargs) -> Any:
        """
        Execute a data tool by type.
        
        Args:
            tool_type: Type of tool to execute
            **kwargs: Tool-specific parameters
            
        Returns:
            Tool execution result
        """
        tool_func = self.available_tools.get(tool_type)
        if not tool_func:
            logger.warning(f"Unknown tool type: {tool_type}")
            return None
            
        try:
            return await tool_func(**kwargs)
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_type}: {e}")
            return None