"""Organized test runner — groups results by suite and prints a clean, colored summary.

Usage:
    python3 tests/summary_runner.py
    python3 tests/summary_runner.py tests.test_skills tests.test_prompts

Runs the given unittest modules (default: all hermetic suites under tests/),
captures per-test output, and prints a grouped summary:

    PASS tests.test_skills  (33 ✓, 0 ✗, 0 skipped)
      TestFrontmatterParser
        ✓ test_parses_scalars_and_lists
      TestParallelRunnerQueue
        ✓ test_six_workers_all_complete_with_five_concurrent

    FAIL tests.test_argparse  (4 ✓, 1 ✗, 0 skipped)
      TestArgumentValidation
        ✓ test_main_parses_common_args
        ✗ test_tui_flag_routes_to_tui
            → AttributeError: module 'swarm' has no attribute 'tui'

    FAIL tests.test_tui  (import error)
      Module
        ✗ ModuleNotFoundError: No module named 'textual'

Colors: green for pass, red for fail/error, yellow for skip. Colors are
auto-disabled when stdout is not a TTY. Modules that cannot import (e.g.
missing optional deps) are shown as a FAIL suite entry instead of aborting.
"""

from __future__ import annotations

import importlib
import io
import sys
import traceback
import unittest
from pathlib import Path

# Ensure the project root is on sys.path so `tests` is importable
ROOT = str(Path(__file__).resolve().parent.parent)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
DIM = "\033[2m"
RESET = "\033[0m"


def _color(text: str, code: str) -> str:
    if not sys.stdout.isatty():
        return text
    return f"{code}{text}{RESET}"


def _one_line_reason(err) -> str:
    """Reduce an unittest err tuple (exc_type, exc_value, tb) to one line."""
    lines = traceback.format_exception_only(err[0], err[1])
    for line in lines:
        s = line.strip()
        if s:
            return s.splitlines()[0]
    return f"{err[0].__name__}: {err[1]}"


def _suite_of(test) -> str:
    return test.__class__.__name__


def run_module(module_name: str) -> tuple[dict[str, dict[str, tuple[str, str]]], str]:
    """Run one test module, capturing stdout/stderr.

    Returns (results, raw_output) where results maps
    suite name -> {test name: (status, reason)} with status in
    ok/failed/skipped/error. reason is "" for ok/skipped.
    """
    suite = unittest.defaultTestLoader.loadTestsFromName(module_name)
    results: dict[str, dict[str, tuple[str, str]]] = {}

    def _record(test, status, reason=""):
        results.setdefault(_suite_of(test), {})[test._testMethodName] = (status, reason)

    class QuietResult(unittest.TestResult):
        def addSuccess(self, test):
            _record(test, "ok")

        def addFailure(self, test, err):
            _record(test, "failed", _one_line_reason(err))

        def addSkip(self, test, reason):
            _record(test, "skipped")

        def addError(self, test, err):
            _record(test, "error", _one_line_reason(err))

    buf = io.StringIO()
    result = QuietResult()
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout = buf
    sys.stderr = buf
    try:
        suite.run(result)
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    return results, buf.getvalue()


def _print_test(name: str, status: str, reason: str) -> None:
    if status == "ok":
        print(f"      {_color('✓', GREEN)} {name}")
    elif status == "skipped":
        print(f"      {_color('⏭', YELLOW)} {name}")
    else:
        print(f"      {_color('✗', RED)} {name}")
        if reason:
            print(f"          {_color('→ ' + reason, DIM)}")


def _print_module_fail(mod: str, summary: str) -> None:
    print(f"{_color('FAIL', RED)} {mod}  ({summary})")


def _print_suite(name: str) -> None:
    print(f"    {_color(name, DIM)}")


def main() -> int:
    modules = sys.argv[1:] or [
        "tests.test_argparse",
        "tests.test_chaos",
        "tests.test_e2e",
        "tests.test_prompts",
        "tests.test_skills",
        "tests.test_tui",
    ]

    print(_color("⚙  SWARM TEST SUMMARY", DIM))
    print()

    grand_ok = grand_fail = grand_skip = 0

    for mod in modules:
        try:
            importlib.import_module(mod)
        except Exception as e:
            reason = _one_line_reason((type(e), e, None))
            _print_module_fail(mod, "import error")
            _print_suite("Module")
            _print_test("import", "error", reason)
            grand_fail += 1
            print()
            continue

        results, _raw = run_module(mod)
        n_ok = sum(1 for s in results.values() for v in s.values() if v[0] == "ok")
        n_fail = sum(1 for s in results.values() for v in s.values() if v[0] in ("failed", "error"))
        n_skip = sum(1 for s in results.values() for v in s.values() if v[0] == "skipped")
        grand_ok += n_ok
        grand_fail += n_fail
        grand_skip += n_skip

        status_label = _color("PASS", GREEN) if n_fail == 0 else _color("FAIL", RED)
        print(f"{status_label} {mod}  ({n_ok} ✓, {n_fail} ✗, {n_skip} skipped)")

        for suite, tests in results.items():
            _print_suite(suite)
            for name, (status_, reason) in tests.items():
                _print_test(name, status_, reason)
        print()

    total = grand_ok + grand_fail + grand_skip
    result = _color("PASS", GREEN) if grand_fail == 0 else _color("FAIL", RED)
    print(_color("─" * 44, DIM))
    print(f"{result}  {grand_ok} passed | {grand_fail} failed | {grand_skip} skipped | {total} total")
    print(_color("─" * 44, DIM))

    return 1 if grand_fail else 0


if __name__ == "__main__":
    sys.exit(main())