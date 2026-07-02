"""Tool definitions and execution for swarm workers.

Tools are exposed to Ollama as function-calling tools.
execute_tool() routes tool calls to the appropriate handler.
"""

import os
import re
import urllib.request

from . import search
from .scratchpad import Scratchpad

# Set by orchestrator before spawning workers
_SCRATCHPAD: Scratchpad = None  # type: ignore[assignment]

# ─── Tool definitions for Ollama ────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_extract",
            "description": "Extract content from a URL",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to extract"}
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scratchpad_add",
            "description": "Save a raw finding to the shared scratchpad (write-only, agents never read from it). Use this to log facts, quotes, numbers, and source URLs for the orchestrator to synthesize later.",
            "parameters": {
                "type": "object",
                "properties": {
                    "finding": {"type": "string", "description": "The raw finding, fact, quote, or number"},
                    "source_url": {"type": "string", "description": "URL where this finding came from"},
                    "category": {"type": "string", "description": "Category: 'timeline', 'money', 'players', 'impact', 'technical', 'controversy', or 'general'"},
                    "confidence": {"type": "string", "description": "Confidence: 'high', 'medium', or 'low'"},
                },
                "required": ["finding"],
            },
        },
    },
]


def execute_tool(tool_call: dict, worker_name: str = "unknown") -> str:
    """Execute a tool call from an agent and return the result string."""
    fn_name = tool_call.get("function", {}).get("name", "")
    args = tool_call.get("function", {}).get("arguments", {})

    if fn_name == "web_search":
        query = args.get("query", "")
        if not query:
            return "Error: no query provided"
        backend = search.BACKENDS.get(os.environ.get("SEARCH_BACKEND", "searxng"))
        if not backend:
            return f"[Search error: unknown backend]"
        result = backend(query)
        # Auto-log search results to scratchpad
        if _SCRATCHPAD:
            _SCRATCHPAD.add_finding(worker_name, f"Search: {query}", "", "search", "high")
            for line in result.split("\n"):
                line = line.strip()
                if line.startswith("- ") and "http" in line:
                    parts = line.rsplit("  ", 1)
                    if len(parts) == 2:
                        url = parts[-1].strip()
                        snippet = parts[0][2:].strip()
                        _SCRATCHPAD.add_source(worker_name, url, snippet[:200], snippet[:200])
        return result

    elif fn_name == "web_extract":
        url = args.get("url", "")
        if not url:
            return "Error: no URL provided"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SwarmWorker/1.0"})
            timeout = int(os.environ.get("SEARCH_TIMEOUT", "15"))
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
                clean = re.sub(r"<[^>]+>", " ", text)
                clean = re.sub(r"\s+", " ", clean).strip()
                result = clean[:3000]
            if _SCRATCHPAD:
                _SCRATCHPAD.add_source(worker_name, url, url, result[:200])
                _SCRATCHPAD.add_finding(worker_name, f"Extracted: {url}", url, "extract", "medium")
            return result
        except Exception as e:
            return f"[Extract error: {e}]"

    elif fn_name == "scratchpad_add":
        finding = args.get("finding", "")
        source_url = args.get("source_url", "")
        category = args.get("category", "general")
        confidence = args.get("confidence", "medium")
        if _SCRATCHPAD and finding:
            _SCRATCHPAD.add_finding(worker_name, finding, source_url, category, confidence)
            return f"[Scratchpad: saved finding ({category}, {confidence})]"
        return "[Scratchpad: not available]"

    return f"Unknown tool: {fn_name}"
