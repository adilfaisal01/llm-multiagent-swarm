"""Orchestrator — spawns workers, manages scratchpad, collects results.

The orchestrator:
1. Creates a write-only scratchpad
2. Builds worker configs from team/angles
3. Spawns workers in a ThreadPoolExecutor
4. Collects results and scratchpad data
5. Destroys the scratchpad
"""

import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .scratchpad import Scratchpad
from . import tools
from .worker import run_worker
from .synthesis import synthesize as run_synthesis


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
    tools._SCRATCHPAD = Scratchpad()

    # Build worker configs
    workers = []
    for i in range(num_workers):
        if mix and team:
            member = team[i % len(team)]
            w_model = member["model"]
            angle = member["angle"]
            if top_angle:
                angle = f"{top_angle} — {angle}"
            workers.append({
                "name": member["name"],
                "model": w_model,
                "angle": angle,
                "prompt": member.get("prompt", ""),
            })
        else:
            m = model or default_worker or "gpt-oss:120b-cloud"
            angle = angles[i % len(angles)] if angles else "General research"
            if top_angle:
                angle = f"{top_angle} — {angle}"
            workers.append({
                "name": f"Worker {i+1}",
                "model": m,
                "angle": angle,
                "prompt": "",
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
    print(f"{'─'*55}\n", file=out)

    results = []
    with ThreadPoolExecutor(max_workers=num_workers) as ex:
        futures = {
            ex.submit(run_worker, i + 1, goal, w["name"], w["model"],
                      w["angle"], w.get("prompt", ""),
                      ollama_base, fallback_models): i
            for i, w in enumerate(workers)
        }
        for f in as_completed(futures):
            r = f.result()
            results.append(r)
            ok = "OK" if r["status"] == "ok" else "ERR"
            print(f"   [{ok}] {r['name']} ({r['model'].split(':')[0]}) — "
                  f"{r['duration_s']}s, {r['search_rounds']} searches — "
                  f"{len(r['response'])} chars", file=out)

    results.sort(key=lambda x: x["worker_id"])

    # Collect scratchpad summary
    scratch_summary = tools._SCRATCHPAD.get_summary()
    scratch_findings = tools._SCRATCHPAD.get_all_findings()
    scratch_sources = tools._SCRATCHPAD.get_all_sources()
    tools._SCRATCHPAD.close()
    tools._SCRATCHPAD = None

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
