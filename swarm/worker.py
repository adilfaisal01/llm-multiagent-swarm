"""Worker agent loop — runs a single research agent with tool access.

Each worker gets its own conversation context and runs independently.
Workers can call web_search, web_extract, and scratchpad_add.
"""

import json
import os
import time
import urllib.request

from . import tools


def run_worker(task_id: int, goal: str, worker_name: str,
               model_name: str, angle: str, prompt_template: str = "",
               ollama_base: str = "http://localhost:11434",
               fallback_models: list = None) -> dict:
    """Run a single worker agent with tool access.

    Returns a dict with worker_id, name, model, duration_s, search_rounds,
    response, and status.
    """
    if fallback_models is None:
        fallback_models = []

    if prompt_template:
        system_prompt = prompt_template.replace("{goal}", goal).replace("{angle}", angle)
    else:
        system_prompt = (
            f"You are {worker_name}, a focused research agent.\n\n"
            f"MAIN QUESTION: {goal}\n\n"
            f"YOUR ANGLE: {angle}\n\n"
            "You have web_search, web_extract, and scratchpad_add tools.\n\n"
            "WORKFLOW:\n"
            "1. Use web_search to find current information on your angle.\n"
            "2. For EACH search result, call scratchpad_add to log the raw facts, "
            "quotes, numbers, and source URLs you find. This is how the orchestrator "
            "collects all raw data across the team.\n"
            "3. After collecting data, write your report.\n\n"
            "IMPORTANT: You MUST call scratchpad_add for every significant finding. "
            "Log the raw data first, then write your analysis. "
            "Be factual with names, dates, and numbers."
        )

    start = time.time()
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": "Research your assigned angle on this topic. Use web_search to find current information.",
        },
    ]

    search_rounds = 0
    for _ in range(3):
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "tools": tools.TOOLS,
            "options": {"num_predict": 4096},
        }
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{ollama_base}/api/chat",
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
            result_content = tools.execute_tool(tc, worker_name)
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
                f"{ollama_base}/api/chat",
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
        for fb_model in fallback_models:
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
                    f"{ollama_base}/api/chat",
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
