"""Scratchpad tool — write findings to the shared scratchpad."""
from __future__ import annotations
from swarm.scratchpad import get_scratchpad
from .base import BaseTool


class ScratchpadAdd(BaseTool):
    name = "scratchpad_add"
    description = (
        "Save a raw finding to the shared scratchpad (write-only, "
        "agents never read from it). Use this to log facts, quotes, "
        "numbers, and source URLs for the orchestrator to synthesize later."
    )
    parameters = {
        "type": "object",
        "properties": {
            "finding": {"type": "string", "description": "The raw finding, fact, quote, or number"},
            "source_url": {"type": "string", "description": "URL where this finding came from"},
            "category": {
                "type": "string",
                "description": "Category: 'timeline', 'money', 'players', 'impact', 'technical', 'controversy', or 'general'",
            },
            "confidence": {
                "type": "string",
                "description": "Confidence: 'high', 'medium', or 'low'",
            },
        },
        "required": ["finding"],
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        finding = args.get("finding", "")
        source_url = args.get("source_url", "")
        category = args.get("category", "general")
        confidence = args.get("confidence", "medium")
        sp = get_scratchpad()
        if sp and finding:
            sp.add_finding(worker_name, finding, source_url, category, confidence)
            return f"[Scratchpad: saved finding ({category}, {confidence})]"
        return "[Scratchpad: not available]"


TOOLS = [ScratchpadAdd()]
BUNDLES = ["scratchpad", "default", "all"]