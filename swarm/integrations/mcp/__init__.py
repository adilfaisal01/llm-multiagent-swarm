"""MCP server — expose the swarm as a Model Context Protocol tool.

Any MCP client (Claude Desktop, Cursor, opencode, etc.) can call
``swarm_research`` to run a full multi-agent research swarm and get back
the cited, hardened result.

Requires the optional ``mcp`` extra:

    pip install -e ".[mcp]"

Run the server (stdio transport):

    python3 -m swarm.integrations.mcp
    # or, if installed as a console script:
    swarm-mcp
"""

from .server import run_mcp_server, main

__all__ = ["run_mcp_server", "main"]
