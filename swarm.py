#!/usr/bin/env python3
"""
Lightweight Swarm — Grok-style multi-agent orchestration via Ollama cloud models.

ARCHITECTURE:
  Orchestrator (Sabrina/me)
    ├── Worker 1: angle 1 (origins/history)
    ├── Worker 2: angle 2 (money/players)
    └── Worker 3: angle 3 (implications)
              ↓
         All results → Orchestrator synthesizes unified answer

AVAILABLE WORKER MODELS:
  --model ministral   Ministral 3:14b (default) — clean, fast, no thinking mode
  --model nemotron    Nemotron 3 Nano 30b — NVIDIA agentic model
  --model gemma       Gemma 4 31b — fastest (0.22s!)
  --model deepseek    DeepSeek V4 Flash — has thinking mode
  --model flash       alias for deepseek

USAGE:
  python3 swarm.py --goal "Anthropic Fable 5 shutdown"
  python3 swarm.py --goal "Topic" --workers 5
  python3 swarm.py --goal "Topic" --model nemotron --json
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor, as_completed

OLLAMA_BASE = "http://localhost:11434"

WORKER_MODELS = {
    "ministral": "ministral-3:14b-cloud",
    "nemotron": "nemotron-3-nano:30b-cloud",
    "gemma": "gemma4:31b-cloud",
    "deepseek": "deepseek-v4-flash:cloud",
    "flash": "deepseek-v4-flash:cloud",
}

DEFAULT_WORKER = WORKER_MODELS["ministral"]


def call_ollama(model: str, prompt: str, system: str = "") -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": 512},
    }
    if system:
        payload["system"] = system

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{OLLAMA_BASE}/api/generate",
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            text = result.get("response") or result.get("thinking") or ""
            return text.strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        return f"[WORKER ERROR: HTTP {e.code} — {body[:200]}]"
    except Exception as e:
        return f"[WORKER ERROR: {e}]"


def run_worker(task_id: int, goal: str, system_prompt: str,
               model: str, sub_goal: str) -> dict:
    prompt = f"""You are a focused research agent contributing to a larger analysis.

MAIN RESEARCH QUESTION: {goal}

YOUR ASSIGNMENT: {sub_goal}

Report findings factually and concisely. Include specific names, dates,
numbers, and sources. Be thorough but direct."""

    start = time.time()
    response = call_ollama(model, prompt, system_prompt)
    elapsed = time.time() - start

    return {
        "worker_id": task_id,
        "model": model,
        "duration_s": round(elapsed, 1),
        "response": response,
        "status": "ok" if not response.startswith("[WORKER ERROR") else "error",
    }


ANGLES = [
    "Cover ORIGINS and HISTORY. Timeline, background, how it started.",
    "Cover KEY PLAYERS and MONEY. Who's involved, who benefits, amounts at stake.",
    "Cover IMPLICATIONS and FUTURE. Second-order effects, where this is heading.",
    "Cover CONTROVERSIES and CRITICISMS. What opponents and skeptics say.",
    "Cover TECHNICAL DETAILS. How it actually works under the hood.",
]


def orchestrate(goal: str, num_workers: int = 3, model: str = None,
                system_prompt: str = "", angles: list = None) -> dict:
    if model is None:
        model = DEFAULT_WORKER
    if angles is None:
        angles = ANGLES[:num_workers]
    while len(angles) < num_workers:
        angles.append(f"Cover a UNIQUE PERSPECTIVE on: {goal}")
    angles = angles[:num_workers]

    print(f"\n{'─'*50}")
    print(f"  SWARM: {num_workers} workers × {model}")
    print(f"  Goal: {goal[:100]}")
    print(f"{'─'*50}\n")

    results = []
    with ThreadPoolExecutor(max_workers=num_workers) as executor:
        futures = {
            executor.submit(run_worker, i + 1, goal, system_prompt, model, angles[i]): i + 1
            for i in range(num_workers)
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            badge = "✅" if result["status"] == "ok" else "❌"
            print(f"   {badge} Worker {result['worker_id']} — {result['duration_s']}s — {len(result['response'])} chars")

    results.sort(key=lambda r: r["worker_id"])
    return {
        "goal": goal,
        "num_workers": num_workers,
        "model": model,
        "wall_time_s": round(sum(r["duration_s"] for r in results), 1),
        "workers": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Lightweight multi-agent swarm")
    parser.add_argument("--goal", required=True, help="Research topic")
    parser.add_argument("--workers", type=int, default=3, help="Parallel workers (1-5)")
    parser.add_argument("--model", default=None,
                        help=f"Worker model: {', '.join(WORKER_MODELS.keys())} "
                             f"(default: ministral)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON")
    parser.add_argument("--system", default="", help="System prompt for workers")
    args = parser.parse_args()

    # Resolve model alias
    model = WORKER_MODELS.get(args.model, args.model)

    args.workers = min(max(args.workers, 1), 5)

    result = orchestrate(args.goal, args.workers, model, args.system)

    print(f"\n{'─'*50}")
    print(f"  ALL WORKERS DONE — {result['wall_time_s']}s total")
    print(f"{'─'*50}")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for w in result["workers"]:
            lbl = f"Worker {w['worker_id']} ({w['duration_s']}s)"
            print(f"\n  ─── {lbl} ───")
            print(f"  {w['response'][:600]}")
            if len(w["response"]) > 600:
                print(f"  ... ({len(w['response'])} chars total)")
        print(f"\n{'─'*50}")
        print(f"  Swarm complete! Feed results to orchestrator for synthesis.")
        print(f"{'─'*50}")


if __name__ == "__main__":
    main()