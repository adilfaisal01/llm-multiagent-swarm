"""Hermetic tests for inline-citation synthesis (swarm/synthesis.py).

Mocks the LLM call so no Ollama/network is touched. Verifies [N] marker
extraction, hallucinated-marker dropping, the Sources section, and the
graceful no-markers fallback.

Run with:
    python3 -m unittest discover tests/
    pytest tests/
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from swarm.synthesis import _append_sources_section, _extract_citations, synthesize

_SOURCES = [
    {"url": "https://a.gov/x", "domain": "a.gov", "credibility": 0.9, "title": "Gov page"},
    {"url": "https://b.com/y", "domain": "b.com", "credibility": 0.5, "title": "Blog"},
    {"url": "https://c.edu/z", "domain": "c.edu", "credibility": 0.8, "title": "Edu page"},
]

_RESULT = {
    "num_workers": 2,
    "research_mode": "objective",
    "workers": [
        {"name": "Vera", "model": "m", "angle": "a", "duration_s": 1, "search_rounds": 1,
         "response": "Paris is the capital [1]"},
        {"name": "Cyrus", "model": "m", "angle": "a", "duration_s": 1, "search_rounds": 1,
         "response": "2M people [2]"},
    ],
    "scratchpad": {
        "findings": [("Vera", "https://a.gov/x", "Paris is capital", "general", "high")],
        "top_sources": _SOURCES,
    },
}


class TestCitationExtraction(unittest.TestCase):
    """swarm/synthesis.py — _extract_citations / _append_sources_section."""

    def test_extracts_valid_markers(self):
        cits, cleaned = _extract_citations("Paris [1] and [3].", _SOURCES)
        self.assertEqual(len(cits), 2)
        self.assertEqual(cits[0]["url"], "https://a.gov/x")
        self.assertEqual(cits[1]["url"], "https://c.edu/z")
        self.assertEqual(cleaned, "Paris [1] and [3].")

    def test_drops_hallucinated_markers(self):
        cits, cleaned = _extract_citations("Paris [1] and [99].", _SOURCES)
        self.assertEqual(len(cits), 1)
        self.assertNotIn("[99]", cleaned)
        self.assertIn("[1]", cleaned)

    def test_no_markers_returns_empty(self):
        cits, cleaned = _extract_citations("No citations here.", _SOURCES)
        self.assertEqual(cits, [])
        self.assertEqual(cleaned, "No citations here.")

    def test_duplicate_marker_cited_once(self):
        cits, _ = _extract_citations("Paris [1] again [1].", _SOURCES)
        self.assertEqual(len(cits), 1)

    def test_sources_section_appended(self):
        cits, cleaned = _extract_citations("Paris [1].", _SOURCES)
        out = _append_sources_section(cleaned, cits)
        self.assertIn("## Sources", out)
        self.assertIn("1. https://a.gov/x — a.gov (★★★)", out)


class TestSynthesize(unittest.TestCase):
    """swarm/synthesis.py — synthesize() end to end with mocked LLM."""

    def test_returns_cited_synthesis(self):
        def fake_call(model, messages, **kw):
            return "Paris is the capital [1]. It has 2M people [3]."

        with patch("swarm.synthesis.call_llm", side_effect=fake_call):
            out = synthesize("Q", _RESULT, "m")
        self.assertIn("[1]", out["synthesis"])
        self.assertIn("[3]", out["synthesis"])
        self.assertEqual(out["sources_used"], 2)
        self.assertEqual(out["sources_total"], 3)
        self.assertEqual(len(out["citations"]), 2)
        self.assertIn("## Sources", out["synthesis"])

    def test_graceful_fallback_when_no_markers(self):
        """No [N] markers → prose kept as-is, sources still listed."""
        def fake_call(model, messages, **kw):
            return "Paris is the capital of France."

        with patch("swarm.synthesis.call_llm", side_effect=fake_call):
            out = synthesize("Q", _RESULT, "m")
        self.assertEqual(out["synthesis"], "Paris is the capital of France.")
        self.assertEqual(out["citations"], [])
        self.assertEqual(out["sources_used"], 0)
        self.assertEqual(out["sources_total"], 3)

    def test_streaming_forwards_chunks(self):
        chunks = []

        def fake_call(model, messages, **kw):
            if kw.get("stream"):
                for c in ["Paris", " is", " capital", " [1]"]:
                    kw["stream_cb"](c, "synthesis")
            return "Paris is capital [1]."

        with patch("swarm.synthesis.call_llm", side_effect=fake_call):
            out = synthesize("Q", _RESULT, "m", stream_cb=lambda c, p: chunks.append(c))
        self.assertEqual(chunks, ["Paris", " is", " capital", " [1]"])
        self.assertIn("[1]", out["synthesis"])

    def test_llm_error_returns_error_dict(self):
        def fake_call(model, messages, **kw):
            return "[LLM error: boom]"

        with patch("swarm.synthesis.call_llm", side_effect=fake_call):
            out = synthesize("Q", _RESULT, "m")
        self.assertTrue(out["synthesis"].startswith("[Synthesis error"))
        self.assertEqual(out["citations"], [])


if __name__ == "__main__":
    unittest.main()
