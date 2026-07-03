#!/usr/bin/env python3
"""Benchmark: Worker count scaling + Mix vs Uniform.

Tests fundamental architecture claims:
1. Does more workers actually add value? (1 vs 3 vs 5)
2. Does mixing models beat uniform? (mix vs single model)

Uses the swarm library directly.
"""

import time
from swarm.runner import run_swarm

GOAL = "What are the environmental and economic impacts of nuclear fusion energy?"
RESULTS = {}


def run_config(label: str, workers: int, mix: bool, model: str | None = None):
    """Run one benchmark configuration and record results."""
    print(f"\n{'='*65}")
    print(f"  {label}")
    print(f"  Workers: {workers} | Mix: {mix} | Model: {model or 'auto'}")
    print(f"{'='*65}")

    start = time.time()
    result = run_swarm(
        GOAL,
        workers=workers,
        mix=mix,
        model=model,
        synthesize=True,
    )
    wall = round(time.time() - start, 1)

    # Collect stats
    total_chars = sum(len(w["response"]) for w in result["workers"])
    avg_duration = round(sum(w["duration_s"] for w in result["workers"]) / len(result["workers"]), 1)
    total_rounds = sum(w["search_rounds"] for w in result["workers"])
    scratch_findings = result.get("scratchpad", {}).get("summary", {}).get("total_findings", 0)
    unique_sources = result.get("scratchpad", {}).get("summary", {}).get("unique_urls", 0)
    synthesis_chars = len(result.get("synthesis", ""))
    worker_chars = [len(w["response"]) for w in result["workers"]]
    worker_names = [w["name"] for w in result["workers"]]

    RESULTS[label] = {
        "workers": workers,
        "mix": mix,
        "model": model,
        "wall_time_s": wall,
        "total_chars": total_chars,
        "avg_duration_s": avg_duration,
        "total_search_rounds": total_rounds,
        "scratch_findings": scratch_findings,
        "unique_sources": unique_sources,
        "synthesis_chars": synthesis_chars,
        "worker_chars": worker_chars,
        "worker_names": worker_names,
    }

    # Print per-worker summary
    for i, w in enumerate(result["workers"]):
        ok = "OK" if w["status"] == "ok" else "ERR"
        print(f"   [{ok}] {w['name']} ({w['model'].split(':')[0]}) — {w['duration_s']}s, {w['search_rounds']} searches, {len(w['response'])} chars")
    print(f"  ───────────────────────────────────────")
    print(f"  Wall: {wall}s | Total chars: {total_chars} | Scratchpad: {scratch_findings} findings, {unique_sources} sources")
    syn_status = "✅" if result.get("synthesis") and not result["synthesis"].startswith("[Synthesis error") else "❌"
    print(f"  Synthesis: {syn_status} ({synthesis_chars} chars)")


def print_results_table():
    """Print a comparison table of all configurations."""
    print(f"\n\n{'='*65}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*65}")

    header = f"  {'Config':<45} {'Wall':<8} {'Chars':<8} {'Findings':<10} {'Rounds':<8} {'Synth':<6}"
    print(header)
    print(f"  {'-'*45} {'-'*8} {'-'*8} {'-'*10} {'-'*8} {'-'*6}")

    for label, r in RESULTS.items():
        print(f"  {label:<45} {r['wall_time_s']:<8}s {r['total_chars']:<8} {r['scratch_findings']:<10} {r['total_search_rounds']:<8} {r['synthesis_chars']:<6}")

    # Worker count scaling analysis
    print(f"\n\n─── WORKER COUNT SCALING ───")
    scale_results = {k: v for k, v in RESULTS.items() if not v["mix"]}
    base = None
    for label, r in sorted(scale_results.items(), key=lambda x: x[1]["workers"]):
        if base is None:
            base = r
            print(f"  1 worker: {r['total_chars']} chars, {r['scratch_findings']} findings")
        else:
            char_pct = round(r["total_chars"] / base["total_chars"] * 100)
            finding_pct = round(r["scratch_findings"] / base["scratch_findings"] * 100) if base["scratch_findings"] else 0
            wall_ratio = round(r["wall_time_s"] / base["wall_time_s"], 1)
            print(f"  {r['workers']} workers: {r['total_chars']} chars ({char_pct}% of 1), {r['scratch_findings']} findings ({finding_pct}% of 1), wall {wall_ratio}x")

    # Mix vs uniform comparison
    print(f"\n\n─── MIX VS UNIFORM ───")
    mix_results = {k: v for k, v in RESULTS.items() if v["mix"]}
    uniform_results = {k: v for k, v in RESULTS.items() if not v["mix"]}
    if mix_results and uniform_results:
        for label_m, r_m in mix_results.items():
            for label_u, r_u in uniform_results.items():
                if r_m["workers"] == r_u["workers"]:
                    char_diff = round((r_m["total_chars"] - r_u["total_chars"]) / r_u["total_chars"] * 100)
                    finding_diff = round((r_m["scratch_findings"] - r_u["scratch_findings"]) / r_u["scratch_findings"] * 100) if r_u["scratch_findings"] else 0
                    print(f"  Mix vs Uniform ({r_m['workers']} workers):")
                    print(f"    Mix     — {r_m['total_chars']} chars, {r_m['scratch_findings']} findings, {r_m['wall_time_s']}s")
                    print(f"    Uniform — {r_u['total_chars']} chars, {r_u['scratch_findings']} findings, {r_u['wall_time_s']}s")
                    print(f"    Diff: {char_diff:+.0f}% chars, {finding_diff:+.0f}% findings")


if __name__ == "__main__":
    print("=" * 65)
    print("  BENCHMARK: Worker Count Scaling + Mix vs Uniform")
    print("  Query: What are the environmental and economic impacts of nuclear fusion energy?")
    print("=" * 65)

    # ─── 1. Worker count scaling (uniform model) ───
    run_config("1. 1 worker (uniform gpt-oss)", workers=1, mix=False, model="gpt-oss:120b-cloud")
    run_config("2. 3 workers (uniform gpt-oss)", workers=3, mix=False, model="gpt-oss:120b-cloud")
    run_config("3. 5 workers (uniform gpt-oss)", workers=5, mix=False, model="gpt-oss:120b-cloud")

    # ─── 2. Mix vs Uniform comparison ───
    run_config("4. 5 workers (mix)", workers=5, mix=True)
    run_config("5. 3 workers (mix)", workers=3, mix=True)

    print_results_table()