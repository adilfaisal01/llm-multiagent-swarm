"""Functional tests for CLI argument validation without Ollama."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from swarm.__main__ import main


class TestArgumentValidation(unittest.TestCase):
    """Check that argparse behavior matches expectations."""

    @patch("swarm.__main__.run_swarm")
    @patch("swarm.__main__.print_summary")
    @patch("swarm.__main__.save_markdown")
    def test_main_parses_common_args(self, mock_save, mock_print, mock_run):
        mock_run.return_value = {"goal": "test", "num_workers": 3, "wall_time_s": 1.0}
        main(["--goal", "test", "--mix", "--workers", "3"])
        mock_run.assert_called_once()
        kwargs = mock_run.call_args.kwargs
        self.assertEqual(kwargs["goal"], "test")
        self.assertEqual(kwargs["mix"], True)
        self.assertEqual(kwargs["workers"], 3)
        mock_print.assert_called_once()

    @patch("swarm.__main__.run_swarm")
    def test_main_exits_on_empty_goal(self, mock_run):
        """main() should exit when given an empty goal."""
        with self.assertRaises(SystemExit) as ctx:
            main(["--goal", "", "--mix"])
        self.assertNotEqual(ctx.exception.code, 0)
        mock_run.assert_not_called()

    @patch("swarm.tui.run_tui")
    def test_tui_flag_routes_to_tui(self, mock_tui):
        with patch("swarm.__main__.run_swarm") as mock_run:
            main(["--tui"])
            mock_tui.assert_called_once()
            mock_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
