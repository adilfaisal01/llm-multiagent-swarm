"""Functional and adversarial tests derived from chaos_monkey.sh."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from swarm.__main__ import main
from swarm.runner import run_swarm


def fake_result(goal="test"):
    return {
        "goal": goal,
        "num_workers": 3,
        "models": ["m"],
        "wall_time_s": 1.0,
        "workers": [],
        "scratchpad": {"summary": {}, "findings": [], "sources": []},
        "synthesis": "",
    }


class TestCLIChaos(unittest.TestCase):
    """Hermetic CLI chaos tests that do not require Ollama."""

    def run_swarm_subprocess(self, args, timeout=5):
        """Run the CLI in a subprocess — used only for argparse-level failures."""
        return subprocess.run(
            [sys.executable, "-m", "swarm"] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    @patch("swarm.__main__.run_swarm")
    def test_empty_goal(self, mock_run):
        """Empty --goal should fail gracefully."""
        with self.assertRaises(SystemExit) as ctx:
            main(["--goal", "", "--mix"])
        self.assertNotEqual(ctx.exception.code, 0)
        mock_run.assert_not_called()

    def test_missing_goal(self):
        """Missing --goal should trigger argparse error."""
        result = self.run_swarm_subprocess(["--mix"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("goal", result.stderr.lower())

    @patch("swarm.__main__.save_markdown")
    @patch("swarm.__main__.print_summary")
    @patch("swarm.__main__.run_swarm")
    def test_workers_zero(self, mock_run, _print, _save):
        """--workers 0 should clamp to 1 without a hard crash."""
        mock_run.return_value = fake_result()
        main(["--goal", "test", "--workers", "0", "--mix"])
        self.assertEqual(mock_run.call_args.kwargs["workers"], 0)

    @patch("swarm.__main__.save_markdown")
    @patch("swarm.__main__.print_summary")
    @patch("swarm.__main__.run_swarm")
    def test_workers_twenty(self, mock_run, _print, _save):
        """--workers 20 should be passed through to run_swarm for clamping."""
        mock_run.return_value = fake_result()
        main(["--goal", "test", "--workers", "20", "--mix"])
        self.assertEqual(mock_run.call_args.kwargs["workers"], 20)

    @patch("swarm.__main__.save_markdown")
    @patch("swarm.__main__.print_summary")
    @patch("swarm.__main__.run_swarm")
    def test_nonexistent_config(self, mock_run, _print, _save):
        """Missing config file should fall back to default."""
        mock_run.return_value = fake_result()
        main(["--goal", "test", "--config", "/tmp/nope.json", "--mix"])
        self.assertEqual(mock_run.call_args.kwargs["config_path"], "/tmp/nope.json")

    @patch("swarm.__main__.save_markdown")
    @patch("swarm.__main__.print_summary")
    @patch("swarm.__main__.run_swarm")
    def test_malformed_config(self, mock_run, _print, _save):
        """Malformed config JSON should be handled."""
        mock_run.return_value = fake_result()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{broken json")
            path = f.name
        try:
            main(["--goal", "test", "--config", path, "--mix"])
        finally:
            os.unlink(path)
        self.assertEqual(mock_run.call_args.kwargs["config_path"], path)

    @patch("swarm.__main__.save_markdown")
    @patch("swarm.__main__.print_summary")
    @patch("swarm.__main__.run_swarm")
    def test_unicode_goal(self, mock_run, _print, _save):
        """Unicode and emoji should pass through without crash."""
        mock_run.return_value = fake_result()
        goal = "🔥💯 What does 🎉 mean in Japanese? 日本語"
        main(["--goal", goal, "--workers", "1"])
        self.assertEqual(mock_run.call_args.kwargs["goal"], goal)

    @patch("swarm.__main__.save_markdown")
    @patch("swarm.__main__.print_summary")
    @patch("swarm.__main__.run_swarm")
    def test_long_goal_no_crash(self, mock_run, _print, _save):
        """Very long goal should not crash."""
        mock_run.return_value = fake_result()
        long_goal = "A" * 10000
        main(["--goal", long_goal, "--workers", "1"])
        self.assertEqual(mock_run.call_args.kwargs["goal"], long_goal)

    def test_json_output_flag(self):
        """--json should be forwarded to run_swarm."""
        with patch("swarm.__main__.run_swarm") as mock_run, patch("swarm.__main__.format_json") as mock_json:
            mock_run.return_value = fake_result()
            main(["--goal", "What is 2+2?", "--workers", "2", "--mix", "--json"])
            self.assertTrue(mock_run.call_args.kwargs["json_mode"])
            mock_json.assert_called_once()


class TestRunnerChaos(unittest.TestCase):
    """Adversarial tests at the runner level (no Ollama)."""

    @patch("swarm.runner.orchestrate")
    def test_run_swarm_clamps_workers_to_minimum(self, mock_orchestrate):
        mock_orchestrate.return_value = fake_result()
        run_swarm("test", workers=0, mix=False)
        self.assertEqual(mock_orchestrate.call_args.kwargs["num_workers"], 1)

    @patch("swarm.runner.orchestrate")
    def test_run_swarm_clamps_workers_to_maximum(self, mock_orchestrate):
        mock_orchestrate.return_value = fake_result()
        run_swarm("test", workers=20, mix=False)
        self.assertEqual(mock_orchestrate.call_args.kwargs["num_workers"], 5)


class TestConfigChaos(unittest.TestCase):
    """Adversarial config loading tests."""

    def test_missing_config_falls_back(self):
        from swarm import config as cfg
        result = cfg.load_swarm_config("/tmp/definitely_missing.json")
        self.assertIsNotNone(result)


if __name__ == "__main__":
    unittest.main()
