"""Web search tool — search the web using configured backend."""
from __future__ import annotations
import os
from swarm import search
from swarm.scratchpad import get_scratchpad
from .base import BaseTool


class WebSearch(BaseTool):
    name = "web_search"
    description = "Search the web for current information"
    parameters = {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"}
        },
        "required": ["query"],
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        query = args.get("query", "")
        if not query:
            return "Error: no query provided"
        backend = search.BACKENDS.get(os.environ.get("SEARCH_BACKEND", "ddgs"))
        if not backend:
            return f"[Search error: unknown backend]"
        result = backend(query)
        sp = get_scratchpad()
        if sp:
            sp.add_finding(worker_name, f"Search: {query}", "", "search", "high")
            for line in result.split("\n"):
                line = line.strip()
                if line.startswith("- ") and "http" in line:
                    parts = line.rsplit("  ", 1)
                    if len(parts) == 2:
                        url = parts[-1].strip()
                        snippet = parts[0][2:].strip()
                        sp.add_source(worker_name, url, snippet[:200], snippet[:200])
        return result


TOOLS = [WebSearch()]
BUNDLES = ["search", "default", "all"]