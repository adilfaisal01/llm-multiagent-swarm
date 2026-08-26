"""Web extract tool — fetch and extract text from a URL."""
from __future__ import annotations
import re
import urllib.request
from swarm.cache import cache_enabled, cache_key, get_cache
from swarm.scratchpad import get_scratchpad
from .base import BaseTool


class WebExtract(BaseTool):
    """Fetch a URL and extract its text content.

    Downloads the page, strips HTML tags, collapses whitespace, and returns
    the first 3000 characters. The URL and a finding are auto-logged to the
    shared scratchpad.
    """

    name = "web_extract"
    description = "Extract content from a URL"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "URL to extract"}
        },
        "required": ["url"],
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        """Extract text from a URL.

        Args:
            args: Tool arguments. Must contain ``url``.
            worker_name: Name of the worker making the call, used for
                scratchpad attribution.

        Returns:
            Cleaned page text (up to 3000 chars), or an error string
            starting with ``Error:`` / ``[Extract error:`` on failure.
        """
        url = args.get("url", "")
        if not url:
            return "Error: no URL provided"

        try:
            # Cache lookup: identical URL extracts skip the network call.
            cache = get_cache() if cache_enabled() else None
            if cache:
                key = cache_key("extract", url)
                cached = cache.get(key)
                if cached is not None:
                    result = cached
                else:
                    result = _fetch(url)
                    if not result.startswith("[Extract error"):
                        cache.set(key, result)
            else:
                result = _fetch(url)
        except Exception as e:
            return f"[Extract error: {e}]"

        sp = get_scratchpad()
        if sp:
            sp.add_source(worker_name, url, url, result[:200])
            sp.add_finding(worker_name, f"Extracted: {url}", url, "extract", "medium")
        return result


def _fetch(url: str) -> str:
    """Download a URL and return cleaned text (up to 3000 chars)."""
    req = urllib.request.Request(url, headers={"User-Agent": "SwarmWorker/1.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        text = resp.read().decode("utf-8", errors="ignore")
        clean = re.sub(r"<[^>]+>", " ", text)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean[:3000]


TOOLS = [WebExtract()]
BUNDLES = ["search", "default", "all"]