"""GitHub search tool — search GitHub repositories, issues, and code."""
from __future__ import annotations
import json
import os
import urllib.parse
import urllib.request
from swarm.cache import cache_enabled, cache_key, get_cache
from swarm.scratchpad import get_scratchpad
from .base import BaseTool

_GITHUB_API = "https://api.github.com/search"
_DEFAULT_TYPES = ("repositories", "issues", "code")


class GithubSearch(BaseTool):
    """Search GitHub for repositories, issues, or code.

    Uses the GitHub Search API. Public searches work without a key
    (rate-limited); set ``GITHUB_TOKEN`` for higher limits. Returns up to 5
    matches with a one-line description. Result URLs are auto-logged to the
    shared scratchpad.
    """

    name = "github_search"
    description = (
        "Search GitHub for open-source repositories, issues, or code. Use when "
        "researching software projects, finding libraries or implementations, "
        "or tracking bugs/feature discussions."
    )
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query (e.g. 'zig machine learning')",
            },
            "type": {
                "type": "string",
                "description": "What to search: 'repositories', 'issues', or 'code' (default 'repositories')",
            },
            "max_results": {
                "type": "number",
                "description": "Max results to return (default 5)",
            },
        },
        "required": ["query"],
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        """Execute a GitHub search.

        Args:
            args: Tool arguments. ``query`` is required; ``type`` selects the
                search scope (repositories/issues/code); ``max_results`` caps
                the returned results (default 5).
            worker_name: Name of the worker making the call, used for
                scratchpad attribution.

        Returns:
            Formatted results, or an error string starting with ``Error:`` /
            ``[GithubSearch error:`` on failure.
        """
        query = args.get("query", "")
        if not query:
            return "Error: no query provided"
        search_type = args.get("type", "repositories")
        if search_type not in _DEFAULT_TYPES:
            return f"Error: unsupported type '{search_type}' (choose from {', '.join(_DEFAULT_TYPES)})"
        max_results = max(1, min(int(args.get("max_results", 5)), 10))

        key = cache_key("github", f"{search_type}|{query}|{max_results}")
        cache = get_cache() if cache_enabled() else None
        if cache:
            cached = cache.get(key)
            if cached is not None:
                result = cached
            else:
                result = self._search(query, search_type, max_results)
                if not result.startswith("[GithubSearch error"):
                    cache.set(key, result)
        else:
            result = self._search(query, search_type, max_results)

        sp = get_scratchpad()
        if sp:
            sp.add_finding(worker_name, f"GitHub search ({search_type}): {query}", "", "code", "medium")
            for url in _urls_from(result):
                sp.add_source(worker_name, url, url, "")
        return result

    def _search(self, query: str, search_type: str, max_results: int) -> str:
        """Hit the GitHub Search API and format results."""
        params = urllib.parse.urlencode({"q": query, "per_page": max_results})
        url = f"{_GITHUB_API}?{params}"
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "SwarmWorker/1.0"}
        token = os.environ.get("GITHUB_TOKEN", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        except Exception as e:
            return f"[GithubSearch error: {e}]"

        items = data.get("items", [])
        if not items:
            return f"No GitHub {search_type} found."

        output = []
        for item in items[:max_results]:
            if search_type == "repositories":
                output.append(
                    f"- {item.get('full_name', '')}: {item.get('description') or 'no description'}\n"
                    f"  ⭐ {item.get('stargazers_count', 0)} | {item.get('html_url', '')}"
                )
            elif search_type == "issues":
                repo = item.get("repository_url", "").rsplit("/", 1)[-1]
                output.append(
                    f"- {repo}#{item.get('number', '')}: {item.get('title', '')} "
                    f"[{item.get('state', '')}]\n  {item.get('html_url', '')}"
                )
            else:
                repo = item.get("repository", {}).get("full_name", "")
                output.append(
                    f"- {item.get('path', '')} in {repo}\n  {item.get('html_url', '')}"
                )
        return "\n\n".join(output)


def _urls_from(result: str) -> list[str]:
    """Extract GitHub URLs from a formatted result string."""
    urls = []
    for line in result.split("\n"):
        if "github.com/" in line:
            start = line.index("github.com/")
            url = line[start:].strip().rstrip("| ,.;")
            if not url.startswith("http"):
                url = f"https://{url}"
            urls.append(url)
    return urls


TOOLS = [GithubSearch()]
BUNDLES = ["code", "research", "all"]
