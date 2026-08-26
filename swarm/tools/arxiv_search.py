"""arXiv search tool — search academic papers via the arXiv API."""
from __future__ import annotations
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from swarm.cache import cache_enabled, cache_key, get_cache
from swarm.scratchpad import get_scratchpad
from .base import BaseTool

_ARXIV_API = "https://export.arxiv.org/api/query"
_ATOM_NS = "{http://www.w3.org/2005/Atom}"


class ArxivSearch(BaseTool):
    """Search arXiv for academic papers (preprints, papers, math, CS, physics).

    Queries the public arXiv API (no key required) and returns up to 5 paper
    titles with authors, date, and abstract excerpts. Each paper's abs page
    is auto-logged as a source to the shared scratchpad.
    """

    name = "arxiv_search"
    description = (
        "Search arXiv for academic papers and preprints on a topic. Use when "
        "you need scholarly sources: research findings, methods, math, CS, "
        "or physics results."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (e.g. 'transformer attention' or 'title:GPT')",
            },
            "max_results": {
                "type": "number",
                "description": "Max papers to return (default 5)",
            },
        },
        "required": ["query"],
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        """Execute an arXiv search.

        Args:
            args: Tool arguments. ``query`` is required; ``max_results``
                caps the returned papers (default 5).
            worker_name: Name of the worker making the call, used for
                scratchpad attribution.

        Returns:
            Formatted paper results, or an error string starting with
            ``Error:`` / ``[ArxivSearch error:`` on failure.
        """
        query = args.get("query", "")
        if not query:
            return "Error: no query provided"
        max_results = max(1, min(int(args.get("max_results", 5)), 10))

        key = cache_key("arxiv", f"{query}|{max_results}")
        cache = get_cache() if cache_enabled() else None
        if cache:
            cached = cache.get(key)
            if cached is not None:
                result = cached
            else:
                result = self._search(query, max_results)
                if not result.startswith("[ArxivSearch error"):
                    cache.set(key, result)
        else:
            result = self._search(query, max_results)

        sp = get_scratchpad()
        if sp:
            sp.add_finding(worker_name, f"arXiv search: {query}", "", "research", "high")
            for abs_url in _abs_urls_from(result):
                sp.add_source(worker_name, abs_url, abs_url, "")
        return result

    def _search(self, query: str, max_results: int) -> str:
        """Hit the arXiv Atom API and format up to max_results papers."""
        params = urllib.parse.urlencode({
            "search_query": f"all:{query}",
            "start": 0,
            "max_results": max_results,
        })
        url = f"{_ARXIV_API}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "SwarmWorker/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml_text = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            return f"[ArxivSearch error: {e}]"

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            return f"[ArxivSearch error: malformed response: {e}]"

        entries = root.findall(f"{_ATOM_NS}entry")
        if not entries:
            return "No arXiv papers found."

        output = []
        for entry in entries[:max_results]:
            title = _tag_text(entry, "title")
            summary = _tag_text(entry, "summary")
            published = _tag_text(entry, "published")[:10]
            link = entry.find(f"{_ATOM_NS}id")
            abs_url = link.text.strip() if link is not None and link.text else ""
            output.append(
                f"- {title} ({published})\n"
                f"  {summary[:200]}\n  {abs_url}"
            )
        return "\n\n".join(output)


def _tag_text(entry, name: str) -> str:
    """Return the cleaned text of a child tag (whitespace-collapsed)."""
    node = entry.find(f"{_ATOM_NS}{name}")
    if node is None or node.text is None:
        return ""
    return " ".join(node.text.split())


def _abs_urls_from(result: str) -> list[str]:
    """Extract arXiv abs URLs from a formatted result string."""
    urls = []
    for line in result.split("\n"):
        line = line.strip()
        if line.startswith("http://arxiv.org/abs/") or line.startswith("https://arxiv.org/abs/"):
            urls.append(line)
    return urls


TOOLS = [ArxivSearch()]
BUNDLES = ["research", "academic", "all"]
