#!/usr/bin/env python3
"""Test draft tool from terminal."""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directories to path
project_root = Path(__file__).parent.parent.parent
mcp_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
if str(mcp_root) not in sys.path:
    sys.path.insert(0, str(mcp_root))

from fastmcp import Client
from NEWST_server_v2 import mcp



async def test_draft_companion_types():
    """Test that different companions give different perspectives."""

    query = "Our mobile app crashes when users upload photos"

    async with Client(mcp) as client:
        # Test each companion type
        for companion_type in ["generic", "marketing"]: #, "bug_triage", "strategy"]:
            print(f"\n{'='*60}")
            print(f"Testing {companion_type} companion...")

            result = await client.call_tool("draft", {
                "params": {
                    "query": query,
                    "companion_type": companion_type
                }
            })

            # Extract the response from CallToolResult
            if result.content and len(result.content) > 0:
                content = result.content[0]
                if hasattr(content, 'text'):
                    data = json.loads(content.text)
                    print("\nDraft Response preview:")
                    print(f"{data['answer'][:150]}...")


if __name__ == "__main__":
    # Run the async function
    asyncio.run(test_draft_companion_types())