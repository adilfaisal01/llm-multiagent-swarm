"""Output formatting and file saving for swarm results.

Separated from the CLI so the library can be used without
the terminal output side effects.
"""

import json
import re
import sys
import time
from pathlib import Path


def print_summary(result: dict, *, file=None):
    """Print a human-readable summary of swarm results to a stream."""
    out = file or sys.stdout

    # Synthesis first — the boss's take
    synthesis = result.get("synthesis", "")
    if synthesis and not synthesis.startswith("[Synthesis error"):
        print(f"\n{'─'*55}", file=out)
        print(f"  🎯 ORCHESTRATOR'S TAKE", file=out)
        print(f"{'─'*55}", file=out)
        print(f"  {synthesis[:1200]}", file=out)
        if len(synthesis) > 1200:
            print(f"  ... ({len(synthesis)} chars total)", file=out)
        print("", file=out)

    print(f"\n{'─'*55}", file=out)
    print(f"  ALL WORKERS DONE — {result['wall_time_s']}s total", file=out)
    print(f"{'─'*55}", file=out)

    for w in result["workers"]:
        label = f"{w['name']} ({w['model'].split(':')[0]}, {w['duration_s']}s, {w['search_rounds']} searches)"
        print(f"\n  --- {label} ---", file=out)
        print(f"  {w['response'][:600]}", file=out)
        if len(w["response"]) > 600:
            print(f"  ... ({len(w['response'])} chars total)", file=out)

    print(f"\n{'─'*55}", file=out)
    print(f"  Swarm done! I'll synthesize these into a unified take.", file=out)
    print(f"{'─'*55}", file=out)

    # Show scratchpad summary
    sp = result.get("scratchpad", {}).get("summary", {})
    if sp and sp.get("total_findings", 0) > 0:
        print(f"\n  📋 Scratchpad: {sp['total_findings']} findings from {sp['workers_with_findings']} workers", file=out)
        print(f"     {sp['total_sources']} sources ({sp['unique_urls']} unique URLs)", file=out)
        print(f"{'─'*55}", file=out)


OUTPUT_DIR = Path("swarm_outputs")


def save_markdown(result: dict, goal: str, filepath: str | None = None) -> str:
    """Save full research output to a markdown file.

    Args:
        result: The swarm result dict from run_swarm().
        goal: The original research question (used for filename).
        filepath: Optional explicit path. Auto-generated if not provided.

    Returns:
        The path to the saved file.
    """
    if not filepath:
        OUTPUT_DIR.mkdir(exist_ok=True)
        safe_name = re.sub(r'[^a-zA-Z0-9]+', '_', goal.strip()[:60]).strip('_')
        if not safe_name:
            safe_name = "swarm_output"
        filepath = OUTPUT_DIR / f"swarm_{safe_name}_{int(time.time())}.md"

    with open(filepath, "w") as f:
        f.write(f"# Swarm Research: {goal}\n\n")
        f.write(f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Wall time:** {result['wall_time_s']}s  \n")
        f.write(f"**Workers:** {result['num_workers']}  \n")
        f.write(f"**Models:** {', '.join(result['models'])}\n\n")

        # Orchestrator synthesis at the top of the file
        synthesis = result.get("synthesis", "")
        if synthesis and not synthesis.startswith("[Synthesis error"):
            f.write("---\n\n")
            f.write("## 🎯 Orchestrator's Take\n\n")
            f.write(f"{synthesis}\n\n")

        f.write("---\n\n")
        f.write("## Raw Worker Reports\n\n")

        for w in result["workers"]:
            f.write(f"### {w['name']} ({w['model']})\n\n")
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

    return filepath


def format_json(result: dict) -> str:
    """Return swarm result as a pretty-printed JSON string."""
    return json.dumps(result, indent=2)