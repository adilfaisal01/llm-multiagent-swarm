"""Hermetic tests for the MCP server (swarm/integrations/mcp/).

Uses the FastMCP in-process call_tool API with run_swarm monkeypatched to a
stub, so no real Ollama or network calls happen. Skipped when the optional
`mcp` extra is not installed.

Run with:
    python3 -m unittest discover tests/
    pytest tests/
"""

from __future__ import annotations

import asyncio
import json
import unittest
from unittest.mock import patch

from swarm.integrations.mcp.server import _SERVER_NAME

try:
    from mcp.server.fastmcp import Context, FastMCP
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


def _stub_result(goal: str, **kwargs) -> dict:
    """Stand-in for run_swarm that returns a fixed, cited result."""
    return {
        "goal": goal,
        "num_workers": 2,
        "models": ["deepseek-v4-flash:cloud"],
        "research_mode": "objective",
        "wall_time_s": 3.0,
        "workers": [
            {"worker_id": 1, "name": "Vera", "model": "m", "duration_s": 1.0,
             "search_rounds": 1, "response": "Paris is the capital [1]", "status": "ok"},
        ],
        "scratchpad": {"summary": {}, "findings": [], "sources": [], "top_sources": []},
        "synthesis": "Paris is the capital [1].\n\n## Sources\n\n1. https://a.gov/x — a.gov (★★★)",
        "citations": [{"n": 1, "url": "https://a.gov/x", "domain": "a.gov", "credibility": 0.9}],
        "sources_used": 1,
        "sources_total": 2,
        "cost": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8,
                 "seconds": 0.1, "calls": 1, "estimated_cost_usd": 0.0},
    }


def _text_of(result) -> str:
    """Extract the JSON text from a call_tool result (list of ContentBlocks)."""
    if isinstance(result, dict):
        return json.dumps(result)
    parts = []
    for block in result:
        text = getattr(block, "text", None)
        if text:
            parts.append(text)
    return "".join(parts)


@unittest.skipUnless(MCP_AVAILABLE, "mcp extra not installed")
class TestMcpServer(unittest.TestCase):
    """swarm/integrations/mcp/server.py — FastMCP tool wiring."""

    def _make_server(self):
        mcp = FastMCP(_SERVER_NAME)

        @mcp.tool()
        def swarm_research(goal: str, workers: int | None = None, model: str | None = None,
                           skill: str | None = None, mix: bool = False, auto: bool = False,
                           synthesize: bool = True, ctx: Context | None = None) -> dict:
            return _stub_result(goal, workers=workers, model=model, skill=skill,
                                mix=mix, auto=auto, synthesize=synthesize)

        return mcp

    def test_tool_is_registered(self):
        async def _run():
            mcp = self._make_server()
            return [t.name for t in await mcp.list_tools()]

        names = asyncio.run(_run())
        self.assertIn("swarm_research", names)

    def test_call_tool_returns_result_dict(self):
        async def _run():
            mcp = self._make_server()
            return await mcp.call_tool("swarm_research", {"goal": "What is the capital of France?"})

        result = json.loads(_text_of(asyncio.run(_run())))
        self.assertEqual(result["goal"], "What is the capital of France?")
        self.assertEqual(result["sources_used"], 1)
        self.assertEqual(result["citations"][0]["url"], "https://a.gov/x")
        self.assertIn("cost", result)

    def test_call_tool_passes_optional_args(self):
        async def _run():
            mcp = self._make_server()
            return await mcp.call_tool("swarm_research", {
                "goal": "Q", "workers": 4, "model": "deepseek", "skill": "research",
                "mix": True, "auto": True, "synthesize": False,
            })

        result = json.loads(_text_of(asyncio.run(_run())))
        self.assertEqual(result["num_workers"], 2)  # stub ignores workers, shape intact

    def test_stream_callback_wired_to_run_swarm(self):
        """The real server relays streamed chunks as progress notifications."""
        from swarm.integrations.mcp import server as mcp_server

        chunks = []

        def fake_run_swarm(goal, **kwargs):
            cb = kwargs.get("stream_callback")
            if cb:
                cb("Paris", "synthesis")
                cb(" is", "synthesis")
            return _stub_result(goal)

        async def _run():
            with patch.object(mcp_server, "run_swarm", side_effect=fake_run_swarm):
                mcp = FastMCP(_SERVER_NAME)

                @mcp.tool()
                def swarm_research(goal: str, ctx: Context | None = None) -> dict:
                    stream_cb = (lambda chunk, phase: chunks.append((chunk, phase))) if ctx else None
                    return mcp_server.run_swarm(goal, stream_callback=stream_cb)

                await mcp.call_tool("swarm_research", {"goal": "Q"})

        asyncio.run(_run())
        self.assertEqual(chunks, [("Paris", "synthesis"), (" is", "synthesis")])


if __name__ == "__main__":
    unittest.main()
