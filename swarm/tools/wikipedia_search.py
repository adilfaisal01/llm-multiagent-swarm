"""Wikipedia search tool — search Wikipedia via the MediaWiki API."""
from __future__ import annotations
import json
import re
import urllib.parse
import urllib.request
from swarm.cache import cache_enabled, cache_key, get_cache
from swarm.scratchpad import get_scratchpad
from .base import BaseTool

_WIKI_API = "https://{lang}.wikipedia.org/w/api.php"


class WikipediaSearch(BaseTool):
    """Search Wikipedia for encyclopedic summaries of a topic.

    Queries the MediaWiki search API (no key required), returns up to 5
    article titles with snippets, and auto-logs each result article as a
    source to the shared scratchpad.
    """

    name = "wikipedia_search"
    description = (
        "Search Wikipedia for encyclopedic facts about a topic, person, "
        "place, or concept. Use when you need a reliable overview or to "
        "confirm basic facts, definitions, dates, or biographical details."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (e.g. 'quantum computing')",
            },
            "lang": {
                "type": "string",
                "description": "Language code, default 'en' (e.g. 'fr', 'de', 'es')",
            },
        },
        "required": ["query"],
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        """Execute a Wikipedia search.

        Args:
            args: Tool arguments. ``query`` is required; ``lang`` optionally
                selects a Wikipedia language edition (default ``en``).
            worker_name: Name of the worker making the call, used for
                scratchpad attribution.

        Returns:
            Formatted article results, or an error string starting with
            ``Error:`` / ``[WikipediaSearch error:`` on failure.
        """
        query = args.get("query", "")
        if not query:
            return "Error: no query provided"
        lang = args.get("lang", "en")

        key = cache_key("wikipedia", f"{lang}|{query}")
        cache = get_cache() if cache_enabled() else None
        if cache:
            cached = cache.get(key)
            if cached is not None:
                result = cached
            else:
                result = self._search(lang, query)
                if not result.startswith("[WikipediaSearch error"):
                    cache.set(key, result)
        else:
            result = self._search(lang, query)

        sp = get_scratchpad()
        if sp:
            sp.add_finding(worker_name, f"Wikipedia search: {query}", "", "web", "high")
            for title in _titles_from(result):
                url = _article_url(lang, title)
                sp.add_source(worker_name, url, title, "")
        return result

    def _search(self, lang: str, query: str) -> str:
        """Hit the MediaWiki search API and format up to 5 results."""
        params = urllib.parse.urlencode({
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": 5,
            "format": "json",
            "utf8": 1,
        })
        url = f"{_WIKI_API.format(lang=lang)}?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "SwarmWorker/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        except Exception as e:
            return f"[WikipediaSearch error: {e}]"

        results = data.get("query", {}).get("search", [])
        if not results:
            return "No Wikipedia results found."

        output = []
        for r in results[:5]:
            title = r.get("title", "")
            snippet = _strip_markup(r.get("snippet", ""))
            url = _article_url(lang, title)
            output.append(f"- {title}: {snippet[:200]}\n  {url}")
        return "\n".join(output)


def _strip_markup(text: str) -> str:
    """Strip HTML tags (e.g. <span class="searchmatch">) from a snippet."""
    return re.sub(r"<[^>]+>", "", text).strip()


def _article_url(lang: str, title: str) -> str:
    """Build the canonical article URL for a title."""
    slug = title.replace(" ", "_")
    return f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(slug)}"


def _titles_from(result: str) -> list[str]:
    """Extract article titles from a formatted result string for scratchpad."""
    titles = []
    for line in result.split("\n"):
        line = line.strip()
        if "wikipedia.org/wiki/" in line:
            slug = line.split("wikipedia.org/wiki/")[-1].strip()
            title = urllib.parse.unquote(slug).replace("_", " ")
            if title:
                titles.append(title)
    return titles


TOOLS = [WikipediaSearch()]
BUNDLES = ["search", "default", "all"]
