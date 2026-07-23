"""Worker agent loop — runs a single research agent with tool access.

Each worker gets its own conversation context and runs independently.
Workers get tool bundles assigned by preflight based on the question.
"""

from __future__ import annotations
import json
import time
import urllib.request

from .tools import get_registry


def run_worker(
    task_id: int,
    goal: str,
    worker_name: str,
    model_name: str,
    angle: str,
    prompt_template: str = "",
    ollama_base: str = "http://localhost:11434",
    fallback_models: list | None = None,
    tool_bundle: str = "default",
    progress=None,
) -> dict:
    """Run a single worker agent with tool access.

    The worker is given a specific set of tools based on the
    tool_bundle (assigned by preflight). This lets different
    workers have different capabilities (vision, python, search, etc.).

    Args:
        progress: Optional callable(event, payload) for live UI updates.

    Returns a dict with worker_id, name, model, duration_s, search_rounds,
    response, and status.
    """
    if fallback_models is None:
        fallback_models = []
    if progress is None:
        progress = lambda *_: None

    # Load the tool registry and get bundle-specific tools
    registry = get_registry()
    ollama_tools = registry.get_ollama_tools_for_bundle(tool_bundle)
    tool_names = [t["function"]["name"] for t in ollama_tools]

    if prompt_template:
        system_prompt = prompt_template.replace("{goal}", goal).replace("{angle}", angle)
    else:
        system_prompt = (
            f"You are {worker_name}, a focused research agent.\n\n"
            f"MAIN QUESTION: {goal}\n\n"
            f"YOUR ANGLE: {angle}\n\n"
            f"AVAILABLE TOOLS: {', '.join(tool_names)}\n\n"
            f"WORKFLOW:\n"
            f"1. Use your tools to find information. Each tool has a specific purpose.\n"
            f"2. For EVERY finding, call scratchpad_add to log raw facts, quotes, "
            f"numbers, and source URLs.\n"
            f"3. After collecting data, write your final report.\n\n"
            f"IMPORTANT: You MUST call scratchpad_add for every significant finding. "
            f"Log the raw data first, then write your analysis. "
            f"Be factual with names, dates, and numbers."
        )

    start = time.time()
    progress("worker_start", {"worker_id": task_id, "name": worker_name, "bundle": tool_bundle, "model": model_name})
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": "Research your assigned angle on this topic. Use your tools to find current information.",
        },
    ]

    search_rounds = 0
    max_rounds = 5  # more rounds to allow tool use + synthesis
    for _ in range(max_rounds):
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "tools": ollama_tools,
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
                "tool_bundle": tool_bundle,
            }

        messages.append(msg)
        tool_calls = msg.get("tool_calls", [])

        if not tool_calls:
            break

        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            progress("worker_tool_call", {
                "worker_id": task_id,
                "name": worker_name,
                "tool": fn_name,
                "bundle": tool_bundle,
            })
            result_content = registry.execute(
                fn_name,
                tc["function"].get("arguments", {}),
                worker_name=worker_name,
            )
            messages.append({
                "role": "tool",
                "tool_name": fn_name,
                "content": result_content[:5000],
            })
            # If this is a read_image or python_exec result with real data,
            # we're likely done with search — nudge the model to produce text
            if fn_name in ("read_image", "python_exec", "read_file") and result_content and len(result_content) > 20:
                # Add a synthesis nudge after meaningful tool results
                messages.append({
                    "role": "user",
                    "content": "Now synthesize your findings into a FINAL ANSWER. State the answer clearly at the top of your response."
                })
                break  # exit tool loop but continue outer loop to get the synthesis
        search_rounds += 1
        if tool_calls and messages[-1]["role"] == "user":
            # We already added a synthesis prompt, continue to get the response
            continue

    content = msg.get("content", "") or ""

    # Force synthesis if tool rounds exhausted and no content
    if not content and search_rounds >= max_rounds:
        for attempt, prompt in enumerate([
            "Synthesize your findings into a final answer now. Do not search again. Just respond with what you know.",
            "STOP SEARCHING. You have enough information. Write your final answer NOW. One paragraph. Go."
        ]):
            messages.append({"role": "user", "content": prompt})
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
        "tool_bundle": tool_bundle,
        "tools_used": tool_names,
    }