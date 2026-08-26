"""Hermetic tests for streaming (swarm/runner.py + swarm/orchestrator.py).

Mocks orchestrate to verify run_swarm wires stream_callback through, and
verifies the orchestrator's synthesis path forwards streamed chunks. No
Ollama/network calls.

Run with:
    python3 -m unittest discover tests/
    pytest tests/
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from swarm.runner import run_swarm


def _fake_result(**overrides):
    result = {
        "goal": "Q",
        "num_workers": 1,
        "models": ["m"],
        "research_mode": "objective",
        "wall_time_s": 1.0,
        "workers": [],
        "scratchpad": {"summary": {}, "findings": [], "sources": [], "top_sources": []},
        "synthesis": "Answer [1]",
        "citations": [{"n": 1, "url": "https://a.gov/x", "domain": "a.gov", "credibility": 0.9}],
        "sources_used": 1,
        "sources_total": 2,
        "cost": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2,
                 "seconds": 0.1, "calls": 1, "estimated_cost_usd": 0.0},
    }
    result.update(overrides)
    return result


class TestStreamingWiring(unittest.TestCase):
    """swarm/runner.py — stream_callback plumbing."""

    def test_stream_callback_forwarded_to_orchestrate(self):
        received = []

        def fake_orchestrate(**kwargs):
            received.append(kwargs.get("stream_callback"))
            return _fake_result()

        with patch("swarm.runner.orchestrate", side_effect=fake_orchestrate):
            run_swarm("Q", workers=1, stream_callback=lambda c, p: None)
        self.assertEqual(len(received), 1)
        self.assertIsNotNone(received[0])

    def test_no_stream_callback_defaults_to_none(self):
        received = []

        def fake_orchestrate(**kwargs):
            received.append(kwargs.get("stream_callback"))
            return _fake_result()

        with patch("swarm.runner.orchestrate", side_effect=fake_orchestrate):
            run_swarm("Q", workers=1)
        self.assertIsNone(received[0])

    def test_result_shape_unchanged_without_streaming(self):
        with patch("swarm.runner.orchestrate", return_value=_fake_result()):
            r = run_swarm("Q", workers=1)
        self.assertEqual(r["synthesis"], "Answer [1]")
        self.assertEqual(r["citations"][0]["url"], "https://a.gov/x")
        self.assertIn("cost", r)


class TestOrchestratorStreaming(unittest.TestCase):
    """swarm/orchestrator.py — synthesis stream_cb forwarding."""

    def test_synthesis_streams_chunks(self):
        from swarm.orchestrator import orchestrate

        chunks = []

        def fake_synthesis(goal, result, model, **kwargs):
            cb = kwargs.get("stream_cb")
            if cb:
                cb("Paris", "synthesis")
                cb(" is", "synthesis")
            return {
                "synthesis": "Paris is capital [1].",
                "citations": [{"n": 1, "url": "https://a.gov/x", "domain": "a.gov", "credibility": 0.9}],
                "sources_used": 1,
                "sources_total": 2,
            }

        with patch("swarm.orchestrator.analyze_question", return_value={
            "answer_type": "other", "research_mode": "objective", "mode": "parallel",
            "skills": ["default"], "depends_on": [None],
            "strategies": [{"worker_name": "W1", "search_plan": "s", "verification_hint": "v"}],
        }), patch("swarm.orchestrator._run_workers_parallel", return_value=[]), \
                patch("swarm.orchestrator.run_synthesis", side_effect=fake_synthesis):
            result = orchestrate(
                "Q", num_workers=1, synthesize=True,
                stream_callback=lambda c, p: chunks.append((c, p)),
            )

        self.assertEqual(chunks, [("Paris", "synthesis"), (" is", "synthesis")])
        self.assertEqual(result["sources_used"], 1)
        self.assertEqual(result["sources_total"], 2)
        self.assertIn("cost", result)

    def test_no_stream_callback_uses_non_streaming(self):
        from swarm.orchestrator import orchestrate

        def fake_synthesis(goal, result, model, **kwargs):
            self.assertIsNone(kwargs.get("stream_cb"))
            return {
                "synthesis": "Plain answer.",
                "citations": [],
                "sources_used": 0,
                "sources_total": 0,
            }

        with patch("swarm.orchestrator.analyze_question", return_value={
            "answer_type": "other", "research_mode": "objective", "mode": "parallel",
            "skills": ["default"], "depends_on": [None],
            "strategies": [{"worker_name": "W1", "search_plan": "s", "verification_hint": "v"}],
        }), patch("swarm.orchestrator._run_workers_parallel", return_value=[]), \
                patch("swarm.orchestrator.run_synthesis", side_effect=fake_synthesis):
            result = orchestrate("Q", num_workers=1, synthesize=True)

        self.assertEqual(result["synthesis"], "Plain answer.")


if __name__ == "__main__":
    unittest.main()
