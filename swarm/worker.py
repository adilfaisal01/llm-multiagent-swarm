"""Worker agent loop — runs a single research agent with tool access.

Each worker gets its own conversation context and runs independently.
Workers get tool bundles assigned by preflight based on the question.
"""

from __future__ import annotations
import json
import time

from .llm import call_llm
from .prompts import render_prompt
from .tools import get_registry


def run_worker(
    task_id: int,
    goal: str,
    worker_name: str,
    model_name: str,
    angle: str,
    prompt_template: str = "",
    config: dict | None = None,
    fallback_models: list | None = None,
    tool_bundle: str = "default",
    progress=None,
    retry_cfg: dict | None = None,
    cost=None,
    model_rates: dict | None = None,
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
        system_prompt = render_prompt(
            "default_worker",
            worker_name=worker_name,
            goal=goal,
            angle=angle,
            tools=", ".join(tool_names),
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
    msg: dict = {"role": "assistant", "content": "", "tool_calls": []}
    for _ in range(max_rounds):
        content = call_llm(
            model_name,
            messages,
            config=config,
            tools=ollama_tools,
            temperature=0.3,
            purpose="worker",
            retry_cfg=retry_cfg,
            cost=cost,
            model_rates=model_rates,
            return_message=True,
        )
        if isinstance(content, str) and content.startswith("[LLM error"):
            return {
                "worker_id": task_id,
                "name": worker_name,
                "model": model_name,
                "duration_s": round(time.time() - start, 1),
                "search_rounds": search_rounds,
                "response": f"[ERROR: {content}]",
                "status": "error",
                "tool_bundle": tool_bundle,
            }

        # content is the full message dict when return_message=True
        msg = content if isinstance(content, dict) else {"role": "assistant", "content": content, "tool_calls": []}
        messages.append(msg)
        tool_calls = msg.get("tool_calls", [])

        if not tool_calls:
            break

        for tc in tool_calls:
            fn_name = tc["function"]["name"]
            raw_args = tc["function"].get("arguments", "{}")
            if isinstance(raw_args, str):
                args = json.loads(raw_args) if raw_args else {}
            else:
                args = raw_args
            progress("worker_tool_call", {
                "worker_id": task_id,
                "name": worker_name,
                "tool": fn_name,
                "bundle": tool_bundle,
                "args": args,
            })
            result_content = registry.execute(
                fn_name,
                args,
                worker_name=worker_name,
            )
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", ""),
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
        for prompt in [
            "Synthesize your findings into a final answer now. Do not search again. Just respond with what you know.",
            "STOP SEARCHING. You have enough information. Write your final answer NOW. One paragraph. Go."
        ]:
            messages.append({"role": "user", "content": prompt})
            content = call_llm(
                model_name,
                messages,
                config=config,
                temperature=0.3,
                purpose="worker_force",
                retry_cfg=retry_cfg,
                cost=cost,
                model_rates=model_rates,
            )
            if content and not content.startswith("[LLM error"):
                break
        if not content or content.startswith("[LLM error"):
            content = "(no response)"

    if not content:
        for fb_model in fallback_models:
            if fb_model == model_name:
                continue
            fb_content = call_llm(
                fb_model,
                [
                    {"role": "system", "content": render_prompt("fallback_system")},
                    {"role": "user", "content": render_prompt("fallback_user", goal=goal)}
                ],
                config=config,
                temperature=0.3,
                max_tokens=1024,
                timeout=60,
                purpose="worker_fallback",
                retry_cfg=retry_cfg,
                cost=cost,
                model_rates=model_rates,
            )
            if fb_content and not fb_content.startswith("[LLM error"):
                content = f"[FALLBACK: {fb_model}] {fb_content}"
                break

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