"""End-to-end swarm tests — require a live Ollama server.

These tests are NOT run by CI (GitHub Actions has no Ollama). They only
run locally when SWARM_E2E=1 is set:

    SWARM_E2E=1 python3 -m unittest tests.test_e2e -v

or via the Makefile:

    make test-e2e

Each test fires a real swarm run against Ollama at OLLAMA_HOST. Goals and
models are intentionally simple to keep cost and wall time low.
"""

from __future__ import annotations

import os
import unittest

from swarm.runner import run_swarm

_E2E_GUARD = "set SWARM_E2E=1 to run end-to-end tests (requires Ollama)"


@unittest.skipUnless(os.environ.get("SWARM_E2E"), _E2E_GUARD)
class TestSkillE2E(unittest.TestCase):
    """Verify full --skill runs use the shipped team."""

    def test_skill_research_runs_and_uses_team(self):
        result = run_swarm(
            "What is the capital of France?",
            skill="research",
            synthesize=False,
        )
        workers = result["workers"]
        self.assertEqual(len(workers), 5)
        names = {w["name"] for w in workers}
        self.assertEqual(names, {"Vera", "Cyrus", "Romy", "Ash", "Zara"})
        for w in workers:
            self.assertEqual(w["tool_bundle"], "research")

    def test_skill_reverse_engineering_runs_and_uses_team(self):
        result = run_swarm(
            "What is the capital of France?",
            skill="reverse-engineering",
            synthesize=False,
        )
        workers = result["workers"]
        self.assertEqual(len(workers), 5)
        names = {w["name"] for w in workers}
        self.assertEqual(names, {"Vera", "Cyrus", "Ash", "Zara", "Romy"})
        for w in workers:
            self.assertEqual(w["tool_bundle"], "reverse-engineering")


@unittest.skipUnless(os.environ.get("SWARM_E2E"), _E2E_GUARD)
class TestDefaultE2E(unittest.TestCase):
    """Verify the no--skill path still generates teams dynamically."""

    def test_default_skill_no_team_uses_preflight(self):
        result = run_swarm(
            "What is the capital of France?",
            mix=False,
            synthesize=False,
        )
        workers = result["workers"]
        self.assertEqual(len(workers), 3)
        for w in workers:
            self.assertTrue(w["name"].startswith("Worker"))
            self.assertIn(w["tool_bundle"], ("default", "search", "research"))

    def test_synthesis_present(self):
        result = run_swarm(
            "What is 2+2?",
            mix=False,
            synthesize=True,
        )
        synthesis = result.get("synthesis", "")
        self.assertTrue(synthesis)
        self.assertFalse(synthesis.startswith("[Synthesis error"))


if __name__ == "__main__":
    unittest.main()
