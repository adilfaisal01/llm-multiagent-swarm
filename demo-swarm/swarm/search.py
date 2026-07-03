"""Search backends for the swarm.

Supported backends:
- searxng: Self-hosted SearXNG instance (default)
- ddgs: DuckDuckGo HTML endpoint (no API key needed)
- google: Google Custom Search JSON API (requires GOOGLE_API_KEY + GOOGLE_CX)
"""

import json
import os
import re
import urllib.parse
import urllib.request

SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8080")
SEARCH_TIMEOUT = int(os.environ.get("SEARCH_TIMEOUT", "15"))
SEARCH_API_KEY = os.environ.get("SEARCH_API_KEY", "")


def search_searxng(query: str) -> str:
    """Search via SearXNG instance."""
    try:
        url = f"{SEARXNG_URL}/search?q={urllib.parse.quote(query)}&format=json&language=en"
        req = urllib.request.Request(url, headers={"User-Agent": "SwarmWorker/1.0"})
        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as resp:
            data = json.loads(resp.read())
            results = data.get("results", [])
            if not results:
                return "No search results found."
            output = []
            for r in results[:5]:
                title = r.get("title", "")
                snippet = r.get("content", "")
                link = r.get("url", "")
                output.append(f"- {title}: {snippet[:200]}\n  {link}")
            return "\n".join(output)
    except Exception as e:
        return f"[Search error: {e}]"


def search_ddg(query: str) -> str:
    """Search via DuckDuckGo HTML endpoint (no API key needed)."""
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            snippets = re.findall(
                r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
                r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                html, re.DOTALL
            )
            if not snippets:
                return "No search results found."
            output = []
            for link, title, snippet in snippets[:5]:
                clean_title = re.sub(r"<[^>]+>", "", title).strip()
                clean_snippet = re.sub(r"<[^>]+>", "", snippet).strip()
                output.append(f"- {clean_title}: {clean_snippet[:200]}\n  {link}")
            return "\n".join(output)
    except Exception as e:
        return f"[Search error: {e}]"


def search_google(query: str) -> str:
    """Search via Google Custom Search JSON API."""
    api_key = SEARCH_API_KEY
    cx = os.environ.get("GOOGLE_CX", "")
    if not api_key or not cx:
        return "[Search error: GOOGLE_API_KEY and GOOGLE_CX required]"
    try:
        url = (f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cx}"
               f"&q={urllib.parse.quote(query)}&num=5")
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as resp:
            data = json.loads(resp.read())
            items = data.get("items", [])
            if not items:
                return "No search results found."
            output = []
            for item in items[:5]:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                output.append(f"- {title}: {snippet[:200]}\n  {link}")
            return "\n".join(output)
    except Exception as e:
        return f"[Search error: {e}]"


BACKENDS = {
    "searxng": search_searxng,
    "ddgs": search_ddg,
    "google": search_google,
}
