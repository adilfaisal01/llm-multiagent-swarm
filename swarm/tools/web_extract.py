"""Web extract tool — fetch and extract text from a URL."""
from __future__ import annotations
import re
import urllib.request
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
            req = urllib.request.Request(url, headers={"User-Agent": "SwarmWorker/1.0"})
            timeout = 15
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
                clean = re.sub(r"<[^>]+>", " ", text)
                clean = re.sub(r"\s+", " ", clean).strip()
                result = clean[:3000]
            sp = get_scratchpad()
            if sp:
                sp.add_source(worker_name, url, url, result[:200])
                sp.add_finding(worker_name, f"Extracted: {url}", url, "extract", "medium")
            return result
        except Exception as e:
            return f"[Extract error: {e}]"


TOOLS = [WebExtract()]
BUNDLES = ["search", "default", "all"]