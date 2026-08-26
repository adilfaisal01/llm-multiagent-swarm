"""Generic HTTP request tool — call any REST API from a worker."""
from __future__ import annotations
import json
import urllib.request
from swarm.cache import cache_enabled, cache_key, get_cache
from swarm.scratchpad import get_scratchpad
from .base import BaseTool

_METHODS = ("GET", "POST", "PUT", "DELETE", "HEAD", "PATCH")
_MAX_BODY = 5000


class HttpRequest(BaseTool):
    """Make a generic HTTP request to a REST API.

    Lets workers query any public or keyless API (weather, exchange rates,
    geocoding, public data endpoints, etc.). Returns the response body
    (truncated). Safe for research use — workers only GET by default.
    """

    name = "http_request"
    description = (
        "Make a raw HTTP request to a URL. Use when you need data from a "
        "specific API or endpoint that no other tool covers. GET is the "
        "default; the response body is returned truncated."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Full URL to request",
            },
            "method": {
                "type": "string",
                "description": "HTTP method, default GET",
            },
            "headers": {
                "type": "object",
                "description": "Optional request headers as a JSON object",
            },
            "body": {
                "type": "string",
                "description": "Optional request body (sent as-is for POST/PUT)",
            },
        },
        "required": ["url"],
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        """Execute an HTTP request.

        Args:
            args: Tool arguments. ``url`` is required; ``method`` defaults to
                GET; ``headers`` (dict) and ``body`` (string) are optional.
            worker_name: Name of the worker making the call, used for
                scratchpad attribution.

        Returns:
            The response body (truncated), or an error string starting with
            ``Error:`` / ``[HttpRequest error:`` on failure.
        """
        url = args.get("url", "")
        if not url:
            return "Error: no URL provided"
        if not url.startswith(("http://", "https://")):
            return "Error: URL must start with http:// or https://"
        method = args.get("method", "GET").upper()
        if method not in _METHODS:
            return f"Error: unsupported method '{method}'"
        headers = args.get("headers") or {}
        if not isinstance(headers, dict):
            return "Error: headers must be a JSON object"
        body = args.get("body", "")

        key = cache_key("http", f"{method}|{url}|{json.dumps(headers, sort_keys=True)}")
        cache = get_cache() if cache_enabled() else None
        if cache:
            cached = cache.get(key)
            if cached is not None:
                result = cached
            else:
                result = self._request(url, method, headers, body)
                if not result.startswith("[HttpRequest error"):
                    cache.set(key, result)
        else:
            result = self._request(url, method, headers, body)

        sp = get_scratchpad()
        if sp:
            sp.add_finding(worker_name, f"HTTP {method}: {url}", "", "web", "medium")
        return result

    def _request(self, url: str, method: str, headers: dict, body: str) -> str:
        """Perform the HTTP call and return a truncated body."""
        data = body.encode("utf-8") if body else None
        merged = {"User-Agent": "SwarmWorker/1.0", **headers}
        req = urllib.request.Request(url, data=data, headers=merged, method=method)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", errors="ignore")
        except Exception as e:
            return f"[HttpRequest error: {e}]"

        if len(raw) > _MAX_BODY:
            return f"{raw[:_MAX_BODY]}\n... (body truncated, {len(raw)} chars total)"
        return raw or "(empty response)"


TOOLS = [HttpRequest()]
BUNDLES = ["research", "code", "all"]
