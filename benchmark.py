#!/usr/bin/env python3
"""Benchmark: Parallel swarm vs Sequential single-agent.

Uses the swarm library (from swarm import run_swarm) instead of
duplicating the worker loop. Measures wall time for both modes.
"""

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from swarm.runner import run_swarm
from swarm.worker import run_worker


GOAL = "What is the capital of France?"

TEAM = [
    {"name": "Vera",  "model": "gpt-oss:120b-cloud", "angle": "Cover ORIGINS and HISTORY. Timeline, background, how it started."},
    {"name": "Cyrus", "model": "gpt-oss:120b-cloud", "angle": "Cover KEY PLAYERS and MONEY. Who is involved, who benefits, amounts at stake."},
    {"name": "Romy",  "model": "gpt-oss:120b-cloud", "angle": "Cover IMPLICATIONS and FUTURE. Second-order effects, where this is heading."},
    {"name": "Ash",   "model": "gpt-oss:120b-cloud", "angle": "Cover CONTROVERSIES and CRITICISMS. What opponents and skeptics say."},
    {"name": "Zara",  "model": "gpt-oss:120b-cloud", "angle": "Cover TECHNICAL DETAILS. How it actually works under the hood."},
]


def benchmark_parallel():
    """Run the swarm in parallel via run_swarm()."""
    print(f"\n{'='*60}")
    print(f"  BENCHMARK: PARALLEL SWARM")
    print(f"  Goal: {GOAL}")
    print(f"  Workers: 5 (ThreadPoolExecutor via swarm library)")
    print(f"{'='*60}\n")

    start = time.time()
    result = run_swarm(GOAL, workers=5, mix=False, model="gpt-oss:120b-cloud")
    wall_time = round(time.time() - start, 1)

    for w in result["workers"]:
        ok = "OK" if w["status"] == "ok" else "ERR"
        print(f"   [{ok}] {w['name']} ({w['model'].split(':')[0]}) — "
              f"{w['duration_s']}s, {w['search_rounds']} searches — "
              f"{len(w['response'])} chars")

    total_model_time = round(sum(w["duration_s"] for w in result["workers"]), 1)
    total_chars = sum(len(w["response"]) for w in result["workers"])

    print(f"\n  ─────────────────────────────────────")
    print(f"  Wall time:  {wall_time}s")
    print(f"  Model time: {total_model_time}s (sum of individual)")
    print(f"  Speedup:    {round(total_model_time / wall_time, 1)}x")
    print(f"  Total chars: {total_chars}")
    print(f"  ─────────────────────────────────────")

    return {"wall_time": wall_time, "model_time": total_model_time, "total_chars": total_chars}


def benchmark_sequential():
    """Run all 5 workers one at a time using run_worker directly."""
    print(f"\n{'='*60}")
    print(f"  BENCHMARK: SEQUENTIAL (Claude-like)")
    print(f"  Goal: {GOAL}")
    print(f"  Workers: 5 (one at a time)")
    print(f"{'='*60}\n")

    total_start = time.time()
    results = []
    for i, m in enumerate(TEAM):
        r = run_worker(i, GOAL, m["name"], m["model"], m["angle"])
        results.append(r)
        ok = "OK" if r["status"] == "ok" else "ERR"
        print(f"   [{ok}] {r['name']} ({r['model'].split(':')[0]}) — "
              f"{r['duration_s']}s, {r['search_rounds']} searches — "
              f"{len(r['response'])} chars")

    wall_time = round(time.time() - total_start, 1)
    total_model_time = round(sum(r["duration_s"] for r in results), 1)
    total_chars = sum(len(r["response"]) for r in results)

    print(f"\n  ─────────────────────────────────────")
    print(f"  Wall time:  {wall_time}s")
    print(f"  Model time: {total_model_time}s (sum of individual)")
    print(f"  Speedup:    {round(total_model_time / wall_time, 1)}x")
    print(f"  Total chars: {total_chars}")
    print(f"  ─────────────────────────────────────")

    return {"wall_time": wall_time, "model_time": total_model_time, "total_chars": total_chars}


if __name__ == "__main__":
    print("=" * 60)
    print("  SWARM BENCHMARK: Parallel vs Sequential")
    print("  Same query, same 5 angles, same models")
    print("=" * 60)

    seq = benchmark_sequential()
    par = benchmark_parallel()

    print(f"\n{'='*60}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Metric':<25} {'Sequential':<15} {'Parallel':<15} {'Speedup':<10}")
    print(f"  {'-'*25} {'-'*15} {'-'*15} {'-'*10}")
    print(f"  {'Wall time':<25} {seq['wall_time']:<15}s {par['wall_time']:<15}s "
          f"{round(seq['wall_time'] / par['wall_time'], 1)}x")
    print(f"  {'Model time (sum)':<25} {seq['model_time']:<15}s {par['model_time']:<15}s "
          f"{round(seq['model_time'] / par['model_time'], 1)}x")
    print(f"  {'Total chars':<25} {seq['total_chars']:<15} {par['total_chars']:<15}")
    print(f"{'='*60}")