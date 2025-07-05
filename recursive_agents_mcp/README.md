# Recursive Agents MCP Server

An MCP (Model Context Protocol) server that exposes Recursive Agents' three-phase thinking methodology to any MCP-compatible AI system.

## What This Does

This MCP server makes Recursive Agents' powerful critique-revision thinking process available as:

- **Resources**: Read the strategic problem decomposition protocol and templates
- **Tools**: Execute recursive thinking with any domain (marketing, engineering, strategy)  
- **Prompts**: Pre-built patterns for effective analysis

The server can also discover and use OTHER MCP servers during its critique phase, making it a "thinking layer" that intelligently orchestrates external tools.

## Installation

```bash
# From the recursive-agents-mcp directory
pip install -e .
```

## Usage

### Start the MCP Server

```bash
python -m mcp_server.server
```

### Configure Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "recursive-agents": {
      "command": "python",
      "args": ["-m", "mcp_server.server"],
      "cwd": "/path/to/recursive-agents-mcp"
    }
  }
}
```

## Available Resources

- `/recursive_agents/protocol` - The strategic problem decomposition protocol
- `/recursive_agents/templates/{domain}/{type}` - Domain-specific templates
- `/recursive_agents/capabilities` - Dynamic list of available features

## Available Tools

### think_recursively
Analyze any problem using the three-phase methodology:
```
think_recursively(problem="Why did sales drop?", domain="marketing")
```

### think_with_details  
Get analysis with full thinking history:
```
think_with_details(problem="Bug in auth system", include_critique=True)
```

### synthesize_perspectives
Analyze from multiple viewpoints:
```
synthesize_perspectives(problem="Customer complaints", domains=["marketing", "bug_triage"])
```

## MCP-Aware Critique

When configured with MCP discovery, the critique phase can identify needs for external data and automatically query other MCP servers (databases, GitHub, web search, etc.) to enhance the analysis.

## Architecture

```
mcp_server/
├── server.py       # Main MCP server
├── resources.py    # Protocol and templates
├── tools.py        # Thinking tools
└── prompts.py      # Usage patterns

core/
├── mcp_aware_chains.py    # Extended companion
└── mcp_discovery.py       # MCP client
```

## License

MIT License - see LICENSE file for details.