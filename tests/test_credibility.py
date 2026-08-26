"""Hermetic tests for AI-based probabilistic credibility (swarm/credibility.py).

Mocks the LLM judge so no Ollama/network is touched. Verifies the Bayesian
combining math, JSON extraction, and graceful fallback on LLM failure.

Run with:
    python3 -m unittest discover tests/
    pytest tests/
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from swarm.credibility import (
    _extract_judgments,
    ai_score_sources,
    combine_probabilities,
)

_SOURCES = [
    {"url": "https://a.gov/x", "domain": "a.gov", "title": "Gov", "snippet": "s",
     "corroboration": 3, "first_seen": "2026-08-01 00:00:00"},
    {"url": "https://b.com/y", "domain": "b.com", "title": "Blog", "snippet": "s",
     "corroboration": 1, "first_seen": "2026-08-01 00:00:00"},
]


class TestCombineProbabilities(unittest.TestCase):
    """swarm/credibility.py — combine_probabilities."""

    def test_confidence_zero_returns_prior(self):
        self.assertEqual(combine_probabilities(0.5, 0.9, 0.0), 0.5)

    def test_confidence_one_returns_llm(self):
        self.assertEqual(combine_probabilities(0.5, 0.9, 1.0), 0.9)

    def test_blend_between(self):
        p = combine_probabilities(0.5, 0.9, 0.5)
        self.assertGreater(p, 0.5)
        self.assertLess(p, 0.9)

    def test_llm_downgrades_high_prior(self):
        p = combine_probabilities(0.65, 0.3, 0.8)
        self.assertLess(p, 0.65)

    def test_clamps_extremes(self):
        self.assertEqual(combine_probabilities(0.0, 1.0, 0.5), 0.5)
        self.assertGreaterEqual(combine_probabilities(0.0, 1.0, 0.9), 0.0)
        self.assertLessEqual(combine_probabilities(0.0, 1.0, 0.9), 1.0)


class TestExtractJudgments(unittest.TestCase):
    """swarm/credibility.py — _extract_judgments."""

    def test_parses_plain_json(self):
        text = '[{"url": "https://a.gov/x", "probability": 0.9, "confidence": 0.8, "reason": "gov"}]'
        out = _extract_judgments(text)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["url"], "https://a.gov/x")
        self.assertEqual(out[0]["probability"], 0.9)

    def test_parses_markdown_fenced_json(self):
        text = '```json\n[{"url": "u", "probability": 0.7, "confidence": 0.6, "reason": "r"}]\n```'
        out = _extract_judgments(text)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["probability"], 0.7)

    def test_tolerates_noise_around_json(self):
        text = 'Here you go:\n[{"url": "u", "probability": 0.5, "confidence": 0.5, "reason": "r"}]\nHope that helps.'
        out = _extract_judgments(text)
        self.assertEqual(len(out), 1)

    def test_clamps_out_of_range(self):
        text = '[{"url": "u", "probability": 1.5, "confidence": -0.2, "reason": "r"}]'
        out = _extract_judgments(text)
        self.assertEqual(out[0]["probability"], 1.0)
        self.assertEqual(out[0]["confidence"], 0.0)

    def test_garbage_returns_empty(self):
        self.assertEqual(_extract_judgments("not json at all"), [])


class TestAiScoreSources(unittest.TestCase):
    """swarm/credibility.py — ai_score_sources."""

    def test_combines_prior_and_llm(self):
        def fake_call(model, messages, **kw):
            return ('[{"url": "https://a.gov/x", "probability": 0.95, "confidence": 0.9, "reason": "authoritative"},'
                    ' {"url": "https://b.com/y", "probability": 0.3, "confidence": 0.8, "reason": "low quality"}]')

        with patch("swarm.credibility.call_llm", side_effect=fake_call):
            out = ai_score_sources(_SOURCES, model="m")

        a = out["https://a.gov/x"]
        b = out["https://b.com/y"]
        self.assertGreater(a["posterior"], a["prior"])  # LLM boosts gov source
        self.assertLess(b["posterior"], b["prior"])     # LLM downgrades blog
        self.assertEqual(a["llm_probability"], 0.95)
        self.assertEqual(a["confidence"], 0.9)
        self.assertEqual(a["reason"], "authoritative")

    def test_llm_failure_falls_back_to_prior(self):
        def fail(model, messages, **kw):
            return "[LLM error: boom]"

        with patch("swarm.credibility.call_llm", side_effect=fail):
            out = ai_score_sources(_SOURCES, model="m")

        for url, meta in out.items():
            self.assertEqual(meta["posterior"], meta["prior"])
            self.assertIsNone(meta["llm_probability"])

    def test_missing_judgment_keeps_prior(self):
        def partial(model, messages, **kw):
            return '[{"url": "https://a.gov/x", "probability": 0.9, "confidence": 0.9, "reason": "r"}]'

        with patch("swarm.credibility.call_llm", side_effect=partial):
            out = ai_score_sources(_SOURCES, model="m")

        self.assertIn("https://a.gov/x", out)
        self.assertIn("https://b.com/y", out)
        self.assertEqual(out["https://b.com/y"]["posterior"], out["https://b.com/y"]["prior"])

    def test_empty_sources_returns_empty(self):
        self.assertEqual(ai_score_sources([], model="m"), {})


if __name__ == "__main__":
    unittest.main()
