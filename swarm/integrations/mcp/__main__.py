"""MCP server entry point — python3 -m swarm.integrations.mcp."""

import sys

from .server import main

if __name__ == "__main__":
    sys.exit(main())
