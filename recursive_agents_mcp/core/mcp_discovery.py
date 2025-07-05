# SPDX-License-Identifier: MIT

"""
MCP Discovery and Client
========================

Handles discovery of other MCP servers and provides a client
interface for executing their tools.
"""

from typing import Dict, Any, List, Optional
import logging
from mcp import Client as MCPClient

logger = logging.getLogger(__name__)


class MCPDiscoveryClient:
    """
    Client for discovering and using other MCP servers.
    
    This would integrate with the actual MCP discovery protocol
    to find available servers and their capabilities.
    """
    
    def __init__(self):
        self.discovered_servers = {}
        self.available_tools = {}
        self.mcp_client = None
        
    async def initialize(self):
        """Initialize the MCP client for discovery"""
        try:
            self.mcp_client = MCPClient()
            await self.mcp_client.initialize()
            logger.info("MCP discovery client initialized")
        except Exception as e:
            logger.error(f"Failed to initialize MCP client: {e}")
            
    async def discover_servers(self) -> Dict[str, Any]:
        """
        Discover available MCP servers through the host client.
        
        When running in Claude Desktop or similar hosts, the host
        manages all MCP server connections. We just ask what's available.
        """
        if not self.mcp_client:
            logger.warning("No MCP client available for discovery")
            return {}
            
        try:
            # Ask the host what MCP servers are connected
            # The host (Claude) knows about all configured servers
            available_servers = await self.mcp_client.get_available_servers()
            
            # Transform into our format
            self.discovered_servers = {}
            for server_id, server_info in available_servers.items():
                self.discovered_servers[server_id] = {
                    "name": server_info.get("name", server_id),
                    "description": server_info.get("description", ""),
                    # No endpoint needed - host manages connections
                }
            
            logger.info(f"Discovered {len(self.discovered_servers)} MCP servers via host")
            return self.discovered_servers
            
        except Exception as e:
            logger.error(f"Server discovery failed: {e}")
            # Fallback to no external servers
            return {}
        
    async def list_available_tools(self) -> Dict[str, Any]:
        """
        List all available tools from ALL connected MCP servers.
        
        In a host like Claude Desktop, this returns tools from:
        - Our own server (recursive-agents)
        - Any other configured MCP servers (github, websearch, etc.)
        
        Returns:
            Dict mapping tool names to their metadata
        """
        if not self.mcp_client:
            logger.warning("No MCP client for tool discovery")
            return {}
            
        try:
            # The MCP host aggregates ALL tools from ALL servers
            # We get a unified view of everything available
            all_tools = await self.mcp_client.list_tools()
            
            # Transform to our internal format
            self.available_tools = {}
            for tool_name, tool_info in all_tools.items():
                self.available_tools[tool_name] = {
                    "description": tool_info.get("description", ""),
                    "parameters": tool_info.get("inputSchema", {}).get("properties", {}),
                    # The host tracks which server provides which tool
                    "server": tool_info.get("server_id", "unknown")
                }
            
            logger.info(f"Discovered {len(self.available_tools)} total tools across all MCP servers")
            
            # Log tool categories for debugging
            servers = set(t["server"] for t in self.available_tools.values())
            logger.debug(f"Tools from servers: {servers}")
            
            return self.available_tools
            
        except Exception as e:
            logger.error(f"Tool discovery failed: {e}")
            return {}
        
    async def execute_tool(
        self, 
        tool_name: str, 
        parameters: Dict[str, Any]
    ) -> Any:
        """
        Execute a tool through the MCP host.
        
        The host (Claude Desktop) handles routing to the correct
        MCP server - we don't need to know which server provides
        which tool.
        
        Args:
            tool_name: Name of the tool to execute
            parameters: Parameters to pass to the tool
            
        Returns:
            Tool execution result
        """
        if not self.mcp_client:
            raise RuntimeError("No MCP client available")
            
        if tool_name not in self.available_tools:
            # Re-discover in case new tools were added
            await self.list_available_tools()
            if tool_name not in self.available_tools:
                raise ValueError(f"Unknown tool: {tool_name}")
        
        try:
            logger.info(f"Executing tool: {tool_name}")
            logger.debug(f"Parameters: {parameters}")
            
            # The host routes this to the correct MCP server
            result = await self.mcp_client.call_tool(
                tool_name=tool_name,
                arguments=parameters
            )
            
            logger.info(f"Tool {tool_name} executed successfully")
            return result
            
        except Exception as e:
            logger.error(f"Tool execution failed for {tool_name}: {e}")
            raise
            
    async def close(self):
        """Clean up client connections"""
        if self.mcp_client:
            await self.mcp_client.close()
            logger.info("MCP discovery client closed")