#!/usr/bin/env python3
"""
Hard query benchmark: Parallel swarm vs Sequential single-agent.
Same query, same 5 angles, same models. Measures wall time.
"""

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

OLLAMA_RAW = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_BASE = f"http://{OLLAMA_RAW}" if not OLLAMA_RAW.startswith("http") else OLLAMA_RAW
SEARCH_BACKEND = os.environ.get("SEARCH_BACKEND", "searxng")
SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8080")
SEARCH_TIMEOUT = int(os.environ.get("SEARCH_TIMEOUT", "15"))

GOAL = "Analyze the impact of quantum computing on cryptography"

ANGLES = [
    "Cover ORIGINS and HISTORY. Timeline, background, how it started.",
    "Cover KEY PLAYERS and MONEY. Who is involved, who benefits, amounts at stake.",
    "Cover IMPLICATIONS and FUTURE. Second-order effects, where this is heading.",
    "Cover CONTROVERSIES and CRITICISMS. What opponents and skeptics say.",
    "Cover TECHNICAL DETAILS. How it actually works under the hood.",
]

TEAM = [
    {"name": "Vera", "model": "qwen3.5:397b-cloud", "angle": ANGLES[0]},
    {"name": "Cyrus", "model": "qwen3.5:397b-cloud", "angle": ANGLES[1]},
    {"name": "Romy", "model": "qwen3.5:397b-cloud", "angle": ANGLES[2]},
    {"name": "Ash", "model": "qwen3.5:397b-cloud", "angle": ANGLES[3]},
    {"name": "Zara", "model": "qwen3.5:397b-cloud", "angle": ANGLES[4]},
]

def search_web(query: str) -> str:
    try:
        url = f"{SEARXNG_URL}/search?q={urllib.parse.quote(query)}&format=json&language=en"
        req = urllib.request.Request(url, headers={"User-Agent": "SwarmWorker/1.0"})
        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as resp:
            data = json.loads(resp.read())
            results = data.get("results", [])
            if not results:
                return "No search results found."
            output = []
            for r in results[:5]:
                title = r.get("title", "")
                snippet = r.get("content", "")
                link = r.get("url", "")
                output.append(f"- {title}: {snippet[:200]}\n  {link}")
            return "\n".join(output)
    except Exception as e:
        return f"[Search error: {e}]"

def extract_url(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SwarmWorker/1.0"})
        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as resp:
            text = resp.read().decode("utf-8", errors="ignore")
            import re
            clean = re.sub(r"<[^>]+>", " ", text)
            clean = re.sub(r"\s+", " ", clean).strip()
            return clean[:3000]
    except Exception as e:
        return f"[Extract error: {e}]"

def run_worker(worker_id: int, goal: str, name: str, model: str, angle: str) -> dict:
    system_prompt = (
        f"You are {name}, a focused research agent.\n\n"
        f"MAIN QUESTION: {goal}\n\n"
        f"YOUR ANGLE: {angle}\n\n"
        "You have web_search and web_extract tools. "
        "Search for current info, then write your report. "
        "Be factual with names, dates, numbers."
    )
    start = time.time()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": "Research your assigned angle on this topic. Use web_search to find current information."},
    ]
    search_rounds = 0
    for _ in range(3):
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "web_search",
                        "description": "Search the web for current information",
                        "parameters": {
                            "type": "object",
                            "properties": {"query": {"type": "string", "description": "Search query"}},
                            "required": ["query"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "web_extract",
                        "description": "Extract content from a URL",
                        "parameters": {
                            "type": "object",
                            "properties": {"url": {"type": "string", "description": "URL to extract"}},
                            "required": ["url"],
                        },
                    },
                },
            ],
            "options": {"num_predict": 4096},
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{OLLAMA_BASE}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                result = json.loads(resp.read())
                msg = result.get("message", {})
        except Exception as e:
            return {
                "worker_id": worker_id, "name": name, "model": model,
                "duration_s": round(time.time() - start, 1),
                "search_rounds": search_rounds,
                "response": f"[ERROR: {e}]", "status": "error",
            }
        messages.append(msg)
        tool_calls = msg.get("tool_calls", [])
        if not tool_calls:
            break
        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            args = tc["function"].get("arguments", {})
            if fn_name == "web_search":
                result_content = search_web(args.get("query", ""))
            elif fn_name == "web_extract":
                result_content = extract_url(args.get("url", ""))
            else:
                result_content = f"Unknown tool: {fn_name}"
            messages.append({
                "role": "tool",
                "tool_name": fn_name,
                "content": result_content[:5000],
            })
        search_rounds += 1
    content = msg.get("content", "") or ""
    if not content:
        content = "(no response)"
    elapsed = time.time() - start
    return {
        "worker_id": worker_id, "name": name, "model": model,
        "duration_s": round(elapsed, 1),
        "search_rounds": search_rounds,
        "response": content, "status": "ok",
    }

def benchmark_parallel():
    print(f"\n{'='*60}")
    print(f"  BENCHMARK: PARALLEL SWARM (HARD QUERY)")
    print(f"  Goal: {GOAL}")
    print(f"  Workers: 5 (ThreadPoolExecutor)")
    print(f"{'='*60}\n")
    total_start = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {
            ex.submit(run_worker, i, GOAL, m["name"], m["model"], m["angle"]): i
            for i, m in enumerate(TEAM)
        }
        for f in as_completed(futures):
            r = f.result()
            results.append(r)
            ok = "OK" if r["status"] == "ok" else "ERR"
            print(f"   [{ok}] {r['name']} ({r['model'].split(':')[0]}) — "
                  f"{r['duration_s']}s, {r['search_rounds']} searches — "
                  f"{len(r['response'])} chars")
    results.sort(key=lambda x: x["worker_id"])
    wall_time = round(time.time() - total_start, 1)
    total_model_time = round(sum(r["duration_s"] for r in results), 1)
    print(f"\n  ─────────────────────────────────────")
    print(f"  Wall time:  {wall_time}s")
    print(f"  Model time: {total_model_time}s")
    print(f"  Speedup:    {round(total_model_time / wall_time, 1)}x")
    print(f"  Total chars: {sum(len(r['response']) for r in results)}")
    print(f"  ─────────────────────────────────────")
    return {"wall_time": wall_time, "model_time": total_model_time, "results": results}

def benchmark_sequential():
    print(f"\n{'='*60}")
    print(f"  BENCHMARK: SEQUENTIAL (HARD QUERY)")
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
    print(f"\n  ─────────────────────────────────────")
    print(f"  Wall time:  {wall_time}s")
    print(f"  Model time: {total_model_time}s")
    print(f"  Speedup:    {round(total_model_time / wall_time, 1)}x")
    print(f"  Total chars: {sum(len(r['response']) for r in results)}")
    print(f"  ─────────────────────────────────────")
    return {"wall_time": wall_time, "model_time": total_model_time, "results": results}

if __name__ == "__main__":
    print("=" * 60)
    print("  HARD QUERY BENCHMARK: Parallel vs Sequential")
    print("  Query: Analyze the impact of quantum computing on cryptography")
    print("=" * 60)
    seq = benchmark_sequential()
    par = benchmark_parallel()
    print(f"\n{'='*60}")
    print(f"  HARD QUERY RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"  {'Metric':<25} {'Sequential':<15} {'Parallel':<15} {'Speedup':<10}")
    print(f"  {'-'*25} {'-'*15} {'-'*15} {'-'*10}")
    print(f"  {'Wall time':<25} {seq['wall_time']:<15}s {par['wall_time']:<15}s "
          f"{round(seq['wall_time'] / par['wall_time'], 1)}x")
    print(f"  {'Model time (sum)':<25} {seq['model_time']:<15}s {par['model_time']:<15}s "
          f"{round(seq['model_time'] / par['model_time'], 1)}x")
    print(f"  {'Total chars':<25} {sum(len(r['response']) for r in seq['results']):<15} "
          f"{sum(len(r['response']) for r in par['results']):<15}")
    print(f"{'='*60}")
