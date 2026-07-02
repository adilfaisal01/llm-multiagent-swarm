"""Swarm v2 — CLI entry point.

Usage:
  python3 -m swarm --goal "What is the capital of France?" --mix
  python3 -m swarm --goal "Quantum computing on cryptography" --auto
  python3 -m swarm --goal "Topic" --model qwen --workers 3
"""

import argparse
import json
import os
import re
import sys
import time

from . import config as cfg
from .complexity import estimate_complexity
from .orchestrator import orchestrate


def main():
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
    args = ap.parse_args()

    # Load config
    config_path = args.config or cfg.CONFIG_PATH
    loaded_config = cfg.load_swarm_config(config_path)
    defaults = cfg.get_defaults(loaded_config)

    # Pull goal and angle from config if not set via CLI
    if not args.goal:
        args.goal = loaded_config.get("goal", "") if loaded_config else ""
    if not args.angle:
        args.angle = loaded_config.get("angle", "") if loaded_config else ""

    if not args.goal or not args.goal.strip():
        print("  [ERROR] --goal cannot be empty. Swarm needs a question to research!")
        sys.exit(1)

    # Ollama base URL (needed before worker count for auto-estimation)
    ollama_raw = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    ollama_base = f"http://{ollama_raw}" if not ollama_raw.startswith("http") else ollama_raw

    # Determine worker count
    if args.workers is not None:
        num_workers = min(max(args.workers, 1), 5)
    elif args.auto:
        # Use DeepSeek V4 Flash for semantic complexity estimation
        est_model = defaults["worker_models"].get("deepseek", "deepseek-v4-flash:cloud")
        num_workers = estimate_complexity(args.goal, model=est_model, ollama_base=ollama_base)
        print(f"  [AUTO] Estimated complexity: {num_workers}/5 workers (model: {est_model.split(':')[0]})", file=sys.stderr)
    else:
        num_workers = 3  # sensible default

    # Resolve model
    model = None
    if args.model:
        model = defaults["worker_models"].get(args.model, args.model)

    # Run the swarm
    result = orchestrate(
        goal=args.goal,
        num_workers=num_workers,
        model=model,
        mix=args.mix,
        json_mode=args.json,
        top_angle=args.angle or "",
        team=defaults["team"],
        angles=defaults["angles"],
        default_worker=defaults["default_worker"],
        fallback_models=defaults["fallback_models"],
        ollama_base=ollama_base,
    )

    out = sys.stderr if args.json else sys.stdout
    print(f"\n{'─'*55}", file=out)
    print(f"  ALL WORKERS DONE — {result['wall_time_s']}s total", file=out)
    print(f"{'─'*55}", file=out)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for w in result["workers"]:
            label = f"{w['name']} ({w['model'].split(':')[0]}, {w['duration_s']}s, {w['search_rounds']} searches)"
            print(f"\n  --- {label} ---")
            print(f"  {w['response'][:600]}")
            if len(w["response"]) > 600:
                print(f"  ... ({len(w['response'])} chars total)")
        print(f"\n{'─'*55}")
        print(f"  Swarm done! I'll synthesize these into a unified take.")
        print(f"{'─'*55}")

        # Show scratchpad summary
        sp = result.get("scratchpad", {}).get("summary", {})
        if sp and sp.get("total_findings", 0) > 0:
            print(f"\n  📋 Scratchpad: {sp['total_findings']} findings from {sp['workers_with_findings']} workers")
            print(f"     {sp['total_sources']} sources ({sp['unique_urls']} unique URLs)")
            print(f"{'─'*55}")

    # Auto-save full research to a markdown file
    safe_name = re.sub(r'[^a-zA-Z0-9]+', '_', args.goal.strip()[:60]).strip('_')
    if not safe_name:
        safe_name = "swarm_output"
    filename = f"swarm_{safe_name}_{int(time.time())}.md"
    with open(filename, "w") as f:
        f.write(f"# Swarm Research: {args.goal}\n\n")
        f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Wall time:** {result['wall_time_s']}s  \n")
        f.write(f"**Workers:** {result['num_workers']}  \n")
        f.write(f"**Models:** {', '.join(result['models'])}\n\n")
        f.write("---\n\n")
        for w in result["workers"]:
            f.write(f"## {w['name']} ({w['model']})\n\n")
            f.write(f"**Duration:** {w['duration_s']}s | **Searches:** {w['search_rounds']} | **Chars:** {len(w['response'])}\n\n")
            f.write(f"{w['response']}\n\n")
            f.write("---\n\n")

        # Add scratchpad findings
        sp = result.get("scratchpad", {})
        if sp.get("findings"):
            f.write("## 📋 Scratchpad Findings\n\n")
            f.write("| Worker | Category | Finding | Source |\n")
            f.write("|--------|----------|---------|--------|\n")
            for row in sp["findings"]:
                worker, src_url, finding, cat, conf = row
                src_short = src_url[:60] if src_url else "-"
                finding_short = finding[:100].replace("\n", " ")
                f.write(f"| {worker} | {cat} | {finding_short} | {src_short} |\n")
            f.write("\n")

        if sp.get("sources"):
            f.write("## 🔗 Sources Collected\n\n")
            for row in sp["sources"]:
                worker, url, title = row
                f.write(f"- [{title}]({url}) — {worker}\n")
            f.write("\n")
    print(f"\n  💾 Saved to {filename}", file=out)


if __name__ == "__main__":
    main()
