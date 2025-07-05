# SPDX-License-Identifier: MIT
#
# Copyright (c) [2025] [Your Name]
#
# This software is licensed under the MIT License.
# See the LICENSE file in the project root for the full license text.

"""
Recursive Agents MCP Server
===========================

An MCP server that exposes Recursive Agents' thinking methodology as:
- Resources: Protocol and templates for other agents to learn from
- Tools: Functions that perform recursive thinking and analysis
- Prompts: Pre-built patterns for using RA effectively

This server can also discover and use other MCP servers during its
critique phase, making it a "thinking layer" for the MCP ecosystem.
"""

from mcp import FastMCP
import logging
from pathlib import Path
import sys

# Add parent directory to path to import recursive_agents
sys.path.append(str(Path(__file__).parent.parent.parent))

from mcp_server.resources import register_resources
from mcp_server.tools import register_tools
from mcp_server.prompts import register_prompts

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize the MCP server
mcp = FastMCP(
    "Recursive Agents MCP",
    description="A thinking layer for AI - exposing Recursive Agents' critique-revision methodology"
)

# Register all components
logger.info("Registering resources...")
register_resources(mcp)

logger.info("Registering tools...")
register_tools(mcp)

logger.info("Registering prompts...")
register_prompts(mcp)

def main():
    """Main entry point for the MCP server"""
    logger.info("Starting Recursive Agents MCP server...")
    mcp.run()

if __name__ == "__main__":
    main()