"""Wayback Machine tool — find archived snapshots of URLs."""
from __future__ import annotations
import json
import urllib.parse
import urllib.request
from swarm.cache import cache_enabled, cache_key, get_cache
from swarm.scratchpad import get_scratchpad
from .base import BaseTool

_AVAILABILITY_API = "https://archive.org/wayback/available"
_CDX_API = "https://web.archive.org/cdx/search/cdx"


class WaybackMachine(BaseTool):
    """Find archived snapshots of a URL in the Wayback Machine.

    Returns the closest archived copy of a URL (and optionally a list of
    recent snapshots via the CDX API). Use when a page is dead, changed, or
    to see how a page looked at a point in history. The archived snapshot URL
    is auto-logged as a source.
    """

    name = "wayback_machine"
    description = (
        "Look up archived snapshots of a URL in the Wayback Machine. Use when "
        "a page is dead, content changed, or you need to see how a page looked "
        "at a specific time."
    )
    parameters = {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "The URL to look up",
            },
            "timestamp": {
                "type": "string",
                "description": "Optional target time (e.g. '20200101'), defaults to closest snapshot",
            },
        },
        "required": ["url"],
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        """Execute a Wayback Machine lookup.

        Args:
            args: Tool arguments. ``url`` is required; ``timestamp`` optionally
                targets a specific date (e.g. ``20200101``).
            worker_name: Name of the worker making the call, used for
                scratchpad attribution.

        Returns:
            The closest snapshot URL, or an error string starting with
            ``Error:`` / ``[WaybackMachine error:``.
        """
        url = args.get("url", "")
        if not url:
            return "Error: no URL provided"
        timestamp = args.get("timestamp", "")

        key = cache_key("wayback", f"{url}|{timestamp}")
        cache = get_cache() if cache_enabled() else None
        if cache:
            cached = cache.get(key)
            if cached is not None:
                result = cached
            else:
                result = self._lookup(url, timestamp)
                if not result.startswith("[WaybackMachine error"):
                    cache.set(key, result)
        else:
            result = self._lookup(url, timestamp)

        sp = get_scratchpad()
        if sp:
            sp.add_finding(worker_name, f"Wayback lookup: {url}", "", "web", "medium")
            snapshot = _first_url(result)
            if snapshot:
                sp.add_source(worker_name, snapshot, snapshot, "")
        return result

    def _lookup(self, url: str, timestamp: str) -> str:
        """Query the availability API for the closest snapshot."""
        params = urllib.parse.urlencode({"url": url, "timestamp": timestamp} if timestamp else {"url": url})
        api_url = f"{_AVAILABILITY_API}?{params}"
        req = urllib.request.Request(api_url, headers={"User-Agent": "SwarmWorker/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="ignore"))
        except Exception as e:
            return f"[WaybackMachine error: {e}]"

        snap = data.get("archived_snapshots", {}).get("closest", {})
        snapshot_url = snap.get("url", "")
        if not snapshot_url:
            return f"No archive found for {url}."
        when = snap.get("timestamp", "")
        return f"- Archived: {snapshot_url}\n  captured: {when}"


def _first_url(result: str) -> str:
    """Extract the first web.archive.org URL from a result string."""
    for line in result.split("\n"):
        line = line.strip()
        if "web.archive.org/" in line:
            start = line.index("web.archive.org/")
            url = line[start:].strip()
            if not url.startswith("http"):
                url = f"https://{url}"
            return url
    return ""


TOOLS = [WaybackMachine()]
BUNDLES = ["search", "research", "all"]
