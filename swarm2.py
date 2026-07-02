#!/usr/bin/env python3
"""
Swarm v2 — Grok-style workers with full tool access via Ollama /api/chat.

Each worker can call web_search and web_extract independently.
Orchestrator provides the tool runtime.

--mix flag assigns different models per worker (like Grok's team).
Uniform mode (default) uses same model for all.

USAGE:
  python3 swarm2.py --goal "Iran war economic impacts" --mix
  python3 swarm2.py --goal "Topic" --model gemma --workers 4
  python3 swarm2.py --goal "Fable 5 shutdown" --mix --json
"""

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed

OLLAMA_BASE = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
SEARCH_BACKEND = os.environ.get("SEARCH_BACKEND", "searxng")
SEARXNG_URL = os.environ.get("SEARXNG_URL", "http://localhost:8080")
SEARCH_API_KEY = os.environ.get("SEARCH_API_KEY", "")
SEARCH_TIMEOUT = int(os.environ.get("SEARCH_TIMEOUT", "15"))
CONFIG_PATH = os.environ.get("SWARM_CONFIG", "swarm_config.json")


# ─── Config loader ───────────────────────────────────────────────────────────

def load_swarm_config(path: str = CONFIG_PATH) -> dict:
    """Load swarm configuration from JSON file."""
    if not os.path.exists(path):
        print(f"  [INFO] Config not found at {path}, using defaults", file=sys.stderr)
        return {}

    with open(path) as f:
        cfg = json.load(f)

    # Resolve model aliases to full tags
    models = cfg.get("models", {})
    for member in cfg.get("team", []):
        alias = member.get("model", "")
        if alias in models:
            member["_model_tag"] = models[alias]
        else:
            member["_model_tag"] = alias

    return cfg


# ─── Load config ─────────────────────────────────────────────────────────────

def load_swarm_config(path: str = CONFIG_PATH) -> dict:
    """Load swarm configuration from JSON file."""
    if not os.path.exists(path):
        print(f"  [INFO] Config not found at {path}, using defaults", file=sys.stderr)
        return {}

    with open(path) as f:
        cfg = json.load(f)

    # Resolve model aliases to full tags
    models = cfg.get("models", {})
    for member in cfg.get("team", []):
        alias = member.get("model", "")
        if alias in models:
            member["_model_tag"] = models[alias]
        else:
            member["_model_tag"] = alias

    return cfg


CONFIG = load_swarm_config()

# Build WORKER_MODELS from config, fall back to hardcoded defaults
WORKER_MODELS = CONFIG.get("models", {}) or {
    "ministral": "ministral-3:14b-cloud",
    "nemotron": "nemotron-3-nano:30b-cloud",
    "nemotron-super": "nemotron-3-super:cloud",
    "gpt-oss": "gpt-oss:120b-cloud",
    "gemma": "gemma4:31b-cloud",
    "qwen": "qwen3.5:397b-cloud",
    "deepseek": "deepseek-v4-flash:cloud",
    "flash": "deepseek-v4-flash:cloud",
}
MODEL_LIST = list(WORKER_MODELS.keys())
DEFAULT_WORKER = WORKER_MODELS.get(
    CONFIG.get("default_model", ""),
    WORKER_MODELS.get("gpt-oss", "gpt-oss:120b-cloud"),
)

# Build TEAM from config, fall back to hardcoded defaults
raw_team = CONFIG.get("team", [])
if raw_team:
    TEAM = []
    for m in raw_team:
        TEAM.append({
            "name": m.get("name", "Worker"),
            "model": m.get("_model_tag", m.get("model", DEFAULT_WORKER)),
            "prompt": m.get("prompt", ""),
            "angle": m.get("angle", ""),
        })
else:
    TEAM = [
        {"name": "Vera",  "model": WORKER_MODELS.get("gpt-oss", "gpt-oss:120b-cloud"),  "prompt": "", "angle": "Cover ORIGINS and HISTORY. Timeline, background, how it started."},
        {"name": "Cyrus", "model": WORKER_MODELS.get("nemotron", "nemotron-3-nano:30b-cloud"), "prompt": "", "angle": "Cover KEY PLAYERS and MONEY. Who is involved, who benefits, amounts at stake."},
        {"name": "Romy",  "model": WORKER_MODELS.get("qwen", "qwen3.5:397b-cloud"),      "prompt": "", "angle": "Cover IMPLICATIONS and FUTURE. Second-order effects, where this is heading."},
        {"name": "Ash",   "model": WORKER_MODELS.get("deepseek", "deepseek-v4-flash:cloud"), "prompt": "", "angle": "Cover CONTROVERSIES and CRITICISMS. What opponents and skeptics say."},
        {"name": "Zara",  "model": WORKER_MODELS.get("gpt-oss", "gpt-oss:120b-cloud"),  "prompt": "", "angle": "Cover TECHNICAL DETAILS. How it actually works under the hood."},
    ]

ANGLES = CONFIG.get("angles", []) or [
    "Cover ORIGINS and HISTORY. Timeline, background, how it started.",
    "Cover KEY PLAYERS and MONEY. Who is involved, who benefits, amounts at stake.",
    "Cover IMPLICATIONS and FUTURE. Second-order effects, where this is heading.",
    "Cover CONTROVERSIES and CRITICISMS. What opponents and skeptics say.",
    "Cover TECHNICAL DETAILS. How it actually works under the hood.",
]

FALLBACK_MODELS = CONFIG.get("fallback_models", []) or [
    "gpt-oss:120b-cloud",
    "nemotron-3-nano:30b-cloud",
]

# ─── Tool definitions for Ollama ────────────────────────────────────────────

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information. Use this to find recent news, facts, and data.",
            "parameters": {
                "type": "object",
                "required": ["query"],
                "properties": {
                    "query": {"type": "string", "description": "Web search query"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_extract",
            "description": "Read the full content of a web page or article.",
            "parameters": {
                "type": "object",
                "required": ["url"],
                "properties": {
                    "url": {"type": "string", "description": "The URL to read"}
                },
            },
        },
    },
]

# ─── Search backends ─────────────────────────────────────────────────────────

def search_searxng(query: str) -> str:
    """Search via SearXNG instance."""
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


def search_ddg(query: str) -> str:
    """Search via DuckDuckGo HTML endpoint (no API key needed)."""
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # Extract result snippets from DDG HTML
            snippets = re.findall(
                r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
                r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>',
                html, re.DOTALL
            )
            if not snippets:
                return "No search results found."
            output = []
            for link, title, snippet in snippets[:5]:
                clean_title = re.sub(r"<[^>]+>", "", title).strip()
                clean_snippet = re.sub(r"<[^>]+>", "", snippet).strip()
                output.append(f"- {clean_title}: {clean_snippet[:200]}\n  {link}")
            return "\n".join(output)
    except Exception as e:
        return f"[Search error: {e}]"


def search_google(query: str) -> str:
    """Search via Google Custom Search JSON API."""
    api_key = SEARCH_API_KEY
    cx = os.environ.get("GOOGLE_CX", "")
    if not api_key or not cx:
        return "[Search error: GOOGLE_API_KEY and GOOGLE_CX required]"
    try:
        url = (f"https://www.googleapis.com/customsearch/v1?key={api_key}&cx={cx}"
               f"&q={urllib.parse.quote(query)}&num=5")
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as resp:
            data = json.loads(resp.read())
            items = data.get("items", [])
            if not items:
                return "No search results found."
            output = []
            for item in items[:5]:
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                link = item.get("link", "")
                output.append(f"- {title}: {snippet[:200]}\n  {link}")
            return "\n".join(output)
    except Exception as e:
        return f"[Search error: {e}]"


SEARCH_BACKENDS = {
    "searxng": search_searxng,
    "ddgs": search_ddg,
    "google": search_google,
}


# ─── Tool execution ─────────────────────────────────────────────────────────

def execute_tool(tool_call: dict) -> str:
    fn_name = tool_call.get("function", {}).get("name", "")
    args = tool_call.get("function", {}).get("arguments", {})

    if fn_name == "web_search":
        query = args.get("query", "")
        if not query:
            return "Error: no query provided"
        backend = SEARCH_BACKENDS.get(SEARCH_BACKEND)
        if not backend:
            return f"[Search error: unknown backend '{SEARCH_BACKEND}']"
        return backend(query)

    elif fn_name == "web_extract":
        url = args.get("url", "")
        if not url:
            return "Error: no URL provided"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "SwarmWorker/1.0"})
            with urllib.request.urlopen(req, timeout=SEARCH_TIMEOUT) as resp:
                text = resp.read().decode("utf-8", errors="ignore")
                clean = re.sub(r"<[^>]+>", " ", text)
                clean = re.sub(r"\s+", " ", clean).strip()
                return clean[:3000]
        except Exception as e:
            return f"[Extract error: {e}]"

    return f"Unknown tool: {fn_name}"


# ─── Worker agent loop ──────────────────────────────────────────────────────

def run_worker(task_id: int, goal: str, worker_name: str,
               model_name: str, angle: str, prompt_template: str = "") -> dict:
    if prompt_template:
        system_prompt = prompt_template.replace("{goal}", goal).replace("{angle}", angle)
    else:
        system_prompt = (
            f"You are {worker_name}, a focused research agent.\n\n"
            f"MAIN QUESTION: {goal}\n\n"
            f"YOUR ANGLE: {angle}\n\n"
            "You have web_search and web_extract tools. Search for current info, "
            "then write your report. Be factual with names, dates, numbers."
        )

    start = time.time()
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": f"Research your assigned angle on this topic. Use web_search to find current information.",
        },
    ]

    search_rounds = 0
    for _ in range(3):
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "tools": TOOLS,
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
                "worker_id": task_id,
                "name": worker_name,
                "model": model_name,
                "duration_s": round(time.time() - start, 1),
                "search_rounds": search_rounds,
                "response": f"[ERROR: {e}]",
                "status": "error",
            }

        messages.append(msg)
        tool_calls = msg.get("tool_calls", [])

        if not tool_calls:
            break

        for tc in tool_calls:
            result_content = execute_tool(tc)
            messages.append({
                "role": "tool",
                "tool_name": tc["function"]["name"],
                "content": result_content[:5000],
            })
        search_rounds += 1

    content = msg.get("content", "") or ""
    
    # Force synthesis: if tool rounds exhausted and no content, push for a final answer
    if not content and search_rounds >= 3:
        for attempt, prompt in enumerate([
            "Synthesize your findings into a final answer now. Do not search again. Just respond with what you know.",
            "STOP SEARCHING. You have enough information. Write your final answer NOW. One paragraph. Go."
        ]):
            messages.append({
                "role": "user",
                "content": prompt
            })
            payload = {
                "model": model_name,
                "messages": messages,
                "stream": False,
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
                    content = msg.get("content", "") or ""
                if content:
                    break
            except Exception:
                content = "(no response)"
    
    if not content:
        # Both force-synthesis attempts failed. Try swapping to a known-working model.
        for fb_model in FALLBACK_MODELS:
            if fb_model == model_name:
                continue
            try:
                fb_payload = {
                    "model": fb_model,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": f"Answer this question concisely: {goal}"}
                    ],
                    "stream": False,
                    "options": {"num_predict": 1024},
                }
                fb_data = json.dumps(fb_payload).encode()
                fb_req = urllib.request.Request(
                    f"{OLLAMA_BASE}/api/chat",
                    data=fb_data,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(fb_req, timeout=60) as resp:
                    fb_result = json.loads(resp.read())
                    fb_content = fb_result.get("message", {}).get("content", "") or ""
                if fb_content:
                    content = f"[FALLBACK: {fb_model}] {fb_content}"
                    break
            except Exception:
                continue
    
    if not content:
        content = "(no response)"
    elapsed = time.time() - start
    return {
        "worker_id": task_id,
        "name": worker_name,
        "model": model_name,
        "duration_s": round(elapsed, 1),
        "search_rounds": search_rounds,
        "response": content,
        "status": "ok",
    }


# ─── Orchestrator ───────────────────────────────────────────────────────────

def orchestrate(goal: str, num_workers: int = 5, model: str = None,
                mix: bool = False) -> dict:
    # Build worker configs
    workers = []
    for i in range(num_workers):
        if mix:
            member = TEAM[i % len(TEAM)]
            w_model = WORKER_MODELS[member["model"]]
            workers.append({
                "name": member["name"],
                "model": w_model,
                "angle": member["angle"],
            })
        else:
            m = model or DEFAULT_WORKER
            workers.append({
                "name": f"Worker {i+1}",
                "model": m,
                "angle": ANGLES[i % len(ANGLES)],
            })

    models_used = list(set(w["model"] for w in workers))
    print(f"\n{'─'*55}")
    print(f"  🐝 SWARM v2")
    print(f"  Workers: {num_workers} | Models: {', '.join(models_used)}")
    if mix:
        names = [f"{w['name']}({w['model'].split(':')[0]})" for w in workers]
        print(f"  Team: {', '.join(names)}")
    print(f"  Goal: {goal[:100]}")
    print(f"{'─'*55}\n")

    results = []
    with ThreadPoolExecutor(max_workers=num_workers) as ex:
        futures = {
            ex.submit(run_worker, i + 1, goal, w["name"], w["model"], w["angle"], w.get("prompt", "")): i
            for i, w in enumerate(workers)
        }
        for f in as_completed(futures):
            r = f.result()
            results.append(r)
            ok = "OK" if r["status"] == "ok" else "ERR"
            print(f"   [{ok}] {r['name']} ({r['model'].split(':')[0]}) — "
                  f"{r['duration_s']}s, {r['search_rounds']} searches — "
                  f"{len(r['response'])} chars")

    results.sort(key=lambda x: x["worker_id"])
    return {
        "goal": goal,
        "num_workers": num_workers,
        "models": models_used,
        "wall_time_s": round(sum(r["duration_s"] for r in results), 1),
        "workers": results,
    }


# ─── CLI ────────────────────────────────────────────────────────────────────

def main():
    global CONFIG, WORKER_MODELS, MODEL_LIST, DEFAULT_WORKER, TEAM, ANGLES, FALLBACK_MODELS
    ap = argparse.ArgumentParser(description="Swarm v2 with web search and mixed models")
    ap.add_argument("--goal", required=True)
    ap.add_argument("--workers", type=int, default=5)
    ap.add_argument("--model", default=None,
                    help=f"Model for uniform mode: {', '.join(MODEL_LIST)}")
    ap.add_argument("--mix", action="store_true",
                    help="Mix different models per worker (Vera/Cyrus/Romy/etc)")
    ap.add_argument("--config", default=None,
                    help="Path to YAML config file (default: swarm_config.yaml or $SWARM_CONFIG)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    model = WORKER_MODELS.get(args.model, args.model) if args.model else None
    args.workers = min(max(args.workers, 1), 5)

    # Reload config if --config was passed
    if args.config:
        new_cfg = load_swarm_config(args.config)
        if new_cfg:
            CONFIG = new_cfg
            WORKER_MODELS = CONFIG.get("models", {}) or WORKER_MODELS
            MODEL_LIST = list(WORKER_MODELS.keys())
            DEFAULT_WORKER = WORKER_MODELS.get(
                CONFIG.get("default_model", ""),
                WORKER_MODELS.get("gpt-oss", "gpt-oss:120b-cloud"),
            )
            raw_team = CONFIG.get("team", [])
            if raw_team:
                TEAM = []
                for m in raw_team:
                    TEAM.append({
                        "name": m.get("name", "Worker"),
                        "model": m.get("_model_tag", m.get("model", DEFAULT_WORKER)),
                        "prompt": m.get("prompt", ""),
                        "angle": m.get("angle", ""),
                    })
            ANGLES = CONFIG.get("angles", []) or ANGLES
            FALLBACK_MODELS = CONFIG.get("fallback_models", []) or FALLBACK_MODELS

    result = orchestrate(args.goal, args.workers, model, args.mix)

    print(f"\n{'─'*55}")
    print(f"  ALL WORKERS DONE — {result['wall_time_s']}s total")
    print(f"{'─'*55}")

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


if __name__ == "__main__":
    main()