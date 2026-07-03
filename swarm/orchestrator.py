"""Orchestrator — spawns workers, manages scratchpad, collects results.

The orchestrator:
1. Creates a write-only scratchpad
2. Builds worker configs from team/angles
3. Preflight: analyzes question → assigns tool bundles via LLM
4. Spawns workers (parallel or pipeline mode based on dependencies)
5. Collects results and scratchpad data
6. Destroys the scratchpad
"""

import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .scratchpad import Scratchpad, set_scratchpad, get_scratchpad
from .worker import run_worker
from .synthesis import synthesize as run_synthesis
from .preflight import analyze_question, build_worker_prompt
from .tools import get_registry


def _get_tool_names_for_bundle(bundle_name: str) -> list[str]:
    """Get the tool names for a bundle from the registry."""
    reg = get_registry()
    return list(reg._bundles.get(bundle_name, []))


def _extract_file_path(goal: str) -> str | None:
    """Extract file path from [ATTACHED TYPE: /path/to/file] markers in goal."""
    match = re.search(r'\[ATTACHED [^\]]+: ([^\]]+)\]', goal)
    if match:
        return match.group(1).strip()
    return None


def _inject_file_prompt(prompt: str, tool_bundle: str, file_path: str | None) -> str:
    """Tell the worker about the file — let them use their tools to read it."""
    if file_path and tool_bundle in ("vision", "files", "code"):
        basename = os.path.basename(file_path)
        prompt += (
            f"\n\n### ATTACHED FILE\n"
            f"Path: {file_path}\n"
            f"Name: {basename}\n"
            f"You MUST use your available tools to read this file.\n"
            f"Do not guess the content. Do not write from memory. Use the tool.\n"
        )
    return prompt


def _run_workers_parallel(workers, goal, ollama_base, fallback_models, out):
    """Run all workers in parallel via ThreadPoolExecutor."""
    results = []
    with ThreadPoolExecutor(max_workers=len(workers)) as ex:
        futures = {
            ex.submit(run_worker, i + 1, goal, w["name"], w["model"],
                      w["angle"], w.get("prompt", ""),
                      ollama_base, fallback_models, w.get("tool_bundle", "default")): i
            for i, w in enumerate(workers)
        }
        for f in as_completed(futures):
            r = f.result()
            results.append(r)
            ok = "OK" if r["status"] == "ok" else "ERR"
            print(f"   [{ok}] {r['name']} ({r['model'].split(':')[0]}) — "
                  f"{r['duration_s']}s — bundle: {r.get('tool_bundle', 'default')} — "
                  f"{len(r['response'])} chars", file=out)
    results.sort(key=lambda x: x["worker_id"])
    return results


def _run_workers_pipeline(workers, depends_on, goal, ollama_base, fallback_models, out):
    """Run workers sequentially, passing previous outputs down the chain."""
    results = []
    completed = {}
    remaining = list(range(len(workers)))

    while remaining:
        for i in list(remaining):
            dep = depends_on[i] if i < len(depends_on) else None
            if dep is None or dep in completed:
                w = workers[i]
                prompt = w["prompt"]

                # Inject previous worker's output if this worker depends on it
                if dep is not None and dep in completed:
                    dep_result = completed[dep]
                    dep_output = dep_result.get("response", "")
                    prompt += (
                        f"\n\n### PREVIOUS WORKER OUTPUT ({dep_result['name']}):\n"
                        f"{dep_output[:3000]}\n\n"
                        f"Use this data for your assigned task.\n"
                    )
                    w["prompt"] = prompt

                print(f"  ▶️  Running {w['name']} (bundle: {w['tool_bundle']}, depends_on: {dep})...", file=out)
                r = run_worker(
                    i + 1, goal, w["name"], w["model"],
                    w["angle"], w["prompt"],
                    ollama_base, fallback_models, w.get("tool_bundle", "default"),
                )
                results.append(r)
                completed[i] = r
                remaining.remove(i)
                ok = "OK" if r["status"] == "ok" else "ERR"
                print(f"   [{ok}] {r['name']} ({r['model'].split(':')[0]}) — "
                      f"{r['duration_s']}s — bundle: {r.get('tool_bundle', 'default')} — "
                      f"{len(r['response'])} chars", file=out)

    results.sort(key=lambda x: x["worker_id"])
    return results


def orchestrate(goal: str, num_workers: int = 5, model: str = None,
                mix: bool = False, json_mode: bool = False,
                top_angle: str = "",
                team: list = None, angles: list = None,
                default_worker: str = None,
                fallback_models: list = None,
                ollama_base: str = "http://localhost:11434",
                synthesize: bool = True,
                synthesis_model: str | None = None) -> dict:
    """Run the swarm and return results with scratchpad data."""
    if team is None:
        team = []
    if angles is None:
        angles = []
    if fallback_models is None:
        fallback_models = []

    # Create the write-only scratchpad for raw findings
    sp = Scratchpad()
    set_scratchpad(sp)

    # Preflight: orchestrator analyzes the question and generates strategies
    print(f"  [PREFLIGHT] Analyzing question for strategy…", file=sys.stderr)
    preflight_model = synthesis_model or default_worker or "gpt-oss:120b-cloud"
    preflight = analyze_question(goal, model=preflight_model, ollama_base=ollama_base, num_workers=num_workers)
    strategies = preflight["strategies"]
    answer_type = preflight["answer_type"]
    bundle_assignments = preflight.get("bundles", ["default"] * num_workers)
    execution_mode = preflight.get("mode", "parallel")
    depends_on = preflight.get("depends_on", [None] * num_workers)
    print(f"  [PREFLIGHT] Answer type: {answer_type} | Mode: {execution_mode} | {len(strategies)} strategies", file=sys.stderr)
    print(f"  [PREFLIGHT] Assigned bundles: {', '.join(bundle_assignments)}", file=sys.stderr)
    if execution_mode == "pipeline":
        deps_str = ", ".join(str(d) if d is not None else "-" for d in depends_on)
        print(f"  [PREFLIGHT] Pipeline deps: {deps_str}", file=sys.stderr)
    file_path_in_goal = _extract_file_path(goal)
    if file_path_in_goal:
        print(f"  [PREFLIGHT] File attachment detected: {os.path.basename(file_path_in_goal)}", file=sys.stderr)

    # Build worker configs from preflight strategies
    workers = []
    for i in range(num_workers):
        strategy = strategies[i] if i < len(strategies) else strategies[0]
        tool_bundle = bundle_assignments[i]
        tool_names = _get_tool_names_for_bundle(tool_bundle)

        if mix and team:
            member = team[i % len(team)]
            w_model = member["model"]
            w_name = member["name"]
        else:
            w_model = model or default_worker or "gpt-oss:120b-cloud"
            w_name = f"Worker {i+1}"

        prompt = build_worker_prompt(goal, strategy, answer_type, w_name, tool_bundle=tool_bundle)
        if top_angle:
            prompt += f"\n\nADDITIONAL CONTEXT: {top_angle}"
        prompt = _inject_file_prompt(prompt, tool_bundle, file_path_in_goal)
        prompt += f"\n\nAVAILABLE TOOLS: {', '.join(tool_names)}\n"

        workers.append({
            "name": w_name,
            "model": w_model,
            "angle": strategy["search_plan"],
            "prompt": prompt,
            "tool_bundle": tool_bundle,
        })

    models_used = list(set(w["model"] for w in workers))
    out = sys.stderr if json_mode else sys.stdout
    print(f"\n{'─'*55}", file=out)
    print(f"  🐝 SWARM v2", file=out)
    print(f"  Workers: {num_workers} | Models: {', '.join(models_used)}", file=out)
    if mix:
        names = [f"{w['name']}({w['model'].split(':')[0]})" for w in workers]
        print(f"  Team: {', '.join(names)}", file=out)
    print(f"  Goal: {goal[:100]}", file=out)
    print(f"  Bundles: {', '.join(bundle_assignments)}", file=out)
    if execution_mode == "pipeline":
        print(f"  Mode: pipeline 🔗", file=out)
    else:
        print(f"  Mode: parallel ⚡", file=out)
    print(f"{'─'*55}\n", file=out)

    # Execute workers in the right mode
    if execution_mode == "pipeline":
        results = _run_workers_pipeline(workers, depends_on, goal, ollama_base, fallback_models, out)
    else:
        results = _run_workers_parallel(workers, goal, ollama_base, fallback_models, out)

    # Collect scratchpad summary
    scratch_summary = sp.get_summary()
    scratch_findings = sp.get_all_findings()
    scratch_sources = sp.get_all_sources()
    sp.close()
    set_scratchpad(None)

    result = {
        "goal": goal,
        "num_workers": num_workers,
        "models": models_used,
        "wall_time_s": round(sum(r["duration_s"] for r in results), 1),
        "workers": results,
        "scratchpad": {
            "summary": scratch_summary,
            "findings": scratch_findings,
            "sources": scratch_sources,
        },
    }

    # ─── Orchestrator synthesis: the boss reads the room ───
    if synthesize:
        syn_model = synthesis_model or (default_worker or "gpt-oss:120b-cloud")
        print(f"\n  🎯 Orchestrator synthesizing... (model: {syn_model.split(':')[0]})", file=out)
        syn_start = time.time()
        synthesis_text = run_synthesis(goal, result, model=syn_model, ollama_base=ollama_base)
        syn_elapsed = round(time.time() - syn_start, 1)
        result["synthesis"] = synthesis_text
        result["synthesis_model"] = syn_model
        result["synthesis_time_s"] = syn_elapsed
        if not synthesis_text.startswith("[Synthesis error"):
            print(f"  ✅ Orchestrator synthesis done ({syn_elapsed}s, {len(synthesis_text)} chars)", file=out)
        else:
            print(f"  ⚠️  Orchestrator synthesis failed ({syn_elapsed}s)", file=out)
    else:
        result["synthesis"] = ""
        result["synthesis_model"] = ""
        result["synthesis_time_s"] = 0

    return result