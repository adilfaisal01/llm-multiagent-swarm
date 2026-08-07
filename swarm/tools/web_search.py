"""Web search tool — search the web using configured backend."""
from __future__ import annotations
import os
from swarm import search
from swarm.scratchpad import get_scratchpad
from .base import BaseTool


class WebSearch(BaseTool):
    """Search the web using the configured backend.

    Runs the query through the backend selected by ``SEARCH_BACKEND``
    (default ``ddgs``) and auto-logs the query and any result URLs to the
    shared scratchpad.
    """

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
        """Execute a web search.

        Args:
            args: Tool arguments. Must contain ``query`` (the search string).
            worker_name: Name of the worker making the call, used for
                scratchpad attribution.

        Returns:
            Formatted search results, or an error string starting with
            ``Error:`` / ``[Search error:`` on failure.
        """
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
            lines = [ln.strip() for ln in result.split("\n")]
            for i, line in enumerate(lines):
                if not line.startswith("- ") or "http" in line:
                    continue
                url = ""
                if i + 1 < len(lines) and "http" in lines[i + 1]:
                    url = lines[i + 1]
                snippet = line[2:].strip()
                if url:
                    sp.add_source(worker_name, url, snippet[:200], snippet[:200])
        return result


TOOLS = [WebSearch()]
BUNDLES = ["search", "default", "all"]