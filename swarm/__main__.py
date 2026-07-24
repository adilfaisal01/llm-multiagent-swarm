"""Swarm v2 — CLI entry point.

Usage:
  python3 -m swarm --goal "What is the capital of France?" --mix
  python3 -m swarm --goal "Quantum computing on cryptography" --auto
  python3 -m swarm --goal "Topic" --model qwen --workers 3

As a library:
  from swarm.runner import run_swarm
  result = run_swarm("Your question", mix=True)
"""

import argparse
import sys

from .output import format_json, print_summary, save_markdown
from .runner import run_swarm


def main(argv=None):
    ap = argparse.ArgumentParser(description="Swarm v2 with web search and mixed models")
    ap.add_argument("--goal", default=None,
                    help="Research question (optional if config file has 'goal' field)")
    ap.add_argument("--angle", default=None,
                    help="Optional top-level angle to prepend to all workers (or from config)")
    ap.add_argument("--workers", type=int, default=None,
                    help="Number of workers (default: 3, or auto-estimated with --auto)")
    ap.add_argument("--auto", action="store_true",
                    help="Auto-estimate worker count based on query complexity")
    ap.add_argument("--model", default=None,
                    help="Model for uniform mode")
    ap.add_argument("--mix", action="store_true",
                    help="Mix different models per worker (Vera/Cyrus/Romy/etc)")
    ap.add_argument("--config", default=None,
                    help="Path to JSON config file (default: swarm_config.json)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--synthesize", action="store_true", default=True,
                    help="Orchestrator synthesizes all worker reports into a unified answer")
    ap.add_argument("--no-synthesize", action="store_false", dest="synthesize",
                    help="Skip the synthesis step")
    ap.add_argument("--tui", action="store_true",
                    help="Launch the persistent Textual TUI instead of a single CLI run")
    args = ap.parse_args(argv)

    if args.tui:
        from .tui import run_tui
        run_tui()
        return

    goal = args.goal or ""
    if not goal.strip():
        print("  [ERROR] --goal cannot be empty. Swarm needs a question to research!", file=sys.stderr)
        sys.exit(1)

    # Run the swarm via the library entry point
    result = run_swarm(
        goal=goal,
        workers=args.workers,
        auto=args.auto,
        mix=args.mix,
        model=args.model,
        angle=args.angle,
        config_path=args.config,
        json_mode=args.json,
        synthesize=args.synthesize,
    )

    # Output
    if args.json:
        # JSON goes to stdout so piping works (e.g. | python3 -c "import json...")
        print(format_json(result))
    else:
        # Human-readable goes to stdout
        print_summary(result)
        # Auto-save to markdown
        filepath = save_markdown(result, result["goal"])
        print(f"\n  💾 Saved to {filepath}")


if __name__ == "__main__":
    main()
