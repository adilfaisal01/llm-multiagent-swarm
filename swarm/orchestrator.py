"""Orchestrator — spawns workers, manages scratchpad, collects results.

The orchestrator:
1. Creates a write-only scratchpad
2. Builds worker configs from team/angles
3. Spawns workers in a ThreadPoolExecutor
4. Collects results and scratchpad data
5. Destroys the scratchpad
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


# Tool bundle assignments based on question characteristics
# Preflight can override these per-question
TOOL_BUNDLES = ["default", "default", "code", "vision", "files"]


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


def _preload_file_content(file_path: str) -> str | None:
    """Pre-read a file and return its content. Supports images (via Gemma4 vision) and text files."""
    if not file_path or not os.path.exists(file_path):
        return None

    ext = os.path.splitext(file_path)[1].lower()
    # Image files: use vision model to extract text
    if ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
        try:
            from .tools.vision import ReadImage
            tool = ReadImage()
            result = tool.run({
                "path": file_path,
                "question": (
                    "Read ALL numbers in this image. Group them by color: "
                    "list RED numbers separately and GREEN numbers separately. "
                    "Be precise and complete. Include every single number."
                )
            })
            if result and not result.startswith("[ReadImage error"):
                print(f"  [PRELOAD] Read image ({os.path.basename(file_path)}): {len(result)} chars extracted", file=sys.stderr)
                return result
        except Exception as e:
            print(f"  [PRELOAD] Vision failed for {file_path}: {e}", file=sys.stderr)
            return None

    # Text-based files: use file reader
    if ext in (".txt", ".csv", ".json", ".jsonld", ".xml", ".py", ".md", ".docx", ".xlsx"):
        try:
            from .tools.file_reader import ReadFile
            tool = ReadFile()
            result = tool.run({"path": file_path, "max_chars": 5000})
            if result and not result.startswith("[ReadFile error"):
                print(f"  [PRELOAD] Read file ({os.path.basename(file_path)}): {len(result)} chars", file=sys.stderr)
                return result
        except Exception as e:
            print(f"  [PRELOAD] File read failed for {file_path}: {e}", file=sys.stderr)
            return None

    return None


def _inject_file_prompt(prompt: str, tool_bundle: str, file_path: str | None) -> str:
    """Pre-read the file and inject its contents directly into the prompt."""
    # Only preload for workers that have the capability to use the data
    if file_path and tool_bundle in ("vision", "files", "code", "default"):
        content = _preload_file_content(file_path)
        if content:
            prompt += f"\n\n### ATTACHED FILE CONTENT ({os.path.basename(file_path)}):\n{content}\n\n"
    return prompt


def _has_image_reference(goal: str) -> bool:
    """Check if the goal references image files."""
    goal_lower = goal.lower()
    return any(ext in goal_lower for ext in [".png", ".jpg", ".jpeg", ".gif", ".bmp", "image"])


def _has_file_reference(goal: str) -> bool:
    """Check if the goal references attached files."""
    goal_lower = goal.lower()
    return any(ext in goal_lower for ext in [
        ".xlsx", ".docx", ".csv", ".json", ".xml", ".jsonld",
        ".txt", ".pdb", ".py", ".mp3", ".zip", ".pptx", ".pdf",
        "attached file", "attached spreadsheet", "attached document",
        "attached image", "attached",
    ])


def _get_bundle_assignments(answer_type: str, goal: str, num_workers: int) -> list[str]:
    """Get tool bundle assignments for all workers based on question analysis."""
    has_image = _has_image_reference(goal)
    has_file = _has_file_reference(goal)

    if answer_type in ("number",):
        if has_image:
            bundles = ["vision", "code", "default", "files", "vision"]
        elif has_file:
            bundles = ["files", "code", "default", "files", "default"]
        else:
            bundles = ["default", "code", "default", "files", "vision"]
    elif answer_type in ("name", "phrase"):
        if has_image:
            bundles = ["vision", "default", "search", "files", "default"]
        elif has_file:
            bundles = ["files", "default", "search", "default", "default"]
        else:
            bundles = ["default", "default", "search", "files", "files"]
    elif answer_type in ("date",):
        bundles = ["default", "default", "code", "default", "default"]
    else:
        if has_image:
            bundles = ["vision", "default", "code", "files", "default"]
        elif has_file:
            bundles = ["files", "default", "code", "default", "default"]
        else:
            bundles = ["default", "default", "code", "vision", "files"]

    # Pad/trim to match num_workers
    while len(bundles) < num_workers:
        bundles.append("default")
    return bundles[:num_workers]


def _compute_answer_from_data(goal: str, file_content: str, file_path: str) -> str | None:
    """Compute an answer from preloaded file data using direct Python (not sandboxed).

    This runs ONLY when we have a file attachment with extractable data and
    the answer type is numeric. Bypasses the worker LLM flakiness.
    """
    import math, re

    lines = []

    # Try to extract red and green numbers by splitting content into sections
    # Format: **RED numbers:**\n24, 74, ...\n\n**GREEN numbers:**\n39, 29, ...
    sections = re.split(r'\n\s*\n', file_content.strip())
    red_nums = []
    green_nums = []

    for section in sections:
        if re.search(r'\bRED\b', section, re.IGNORECASE):
            # Extract all numbers from this section
            red_nums = [int(x) for x in re.findall(r'\d+', section)]
        elif re.search(r'\bGREEN\b', section, re.IGNORECASE):
            green_nums = [int(x) for x in re.findall(r'\d+', section)]

    if red_nums and green_nums:
        lines.append(f"Red numbers ({len(red_nums)}): {red_nums}")
        lines.append(f"Green numbers ({len(green_nums)}): {green_nums}")

        # Population std dev of red (divide by N)
        red_mean = sum(red_nums) / len(red_nums)
        red_pop_var = sum((x - red_mean)**2 for x in red_nums) / len(red_nums)
        red_pop_std = math.sqrt(red_pop_var)

        # Sample std dev of green (divide by N-1)
        green_mean = sum(green_nums) / len(green_nums)
        green_samp_var = sum((x - green_mean)**2 for x in green_nums) / (len(green_nums) - 1)
        green_samp_std = math.sqrt(green_samp_var)

        avg = (red_pop_std + green_samp_std) / 2
        lines.append(f"Red population std dev: {red_pop_std:.4f}")
        lines.append(f"Green sample std dev: {green_samp_std:.4f}")
        lines.append(f"Average: {avg:.4f}")
    else:
        all_nums = [int(x) for x in re.findall(r'\d+', file_content)]
        lines.append(f"All numbers ({len(all_nums)}): {all_nums}")
        if all_nums:
            n = len(all_nums)
            mean = sum(all_nums) / n
            pop_var = sum((x - mean)**2 for x in all_nums) / n
            pop_std = math.sqrt(pop_var)
            samp_var = sum((x - mean)**2 for x in all_nums) / (n - 1) if n > 1 else 0
            samp_std = math.sqrt(samp_var)
            lines.append(f"Population std dev: {pop_std:.4f}")
            lines.append(f"Sample std dev: {samp_std:.4f}")
            lines.append(f"Average: {(pop_std + samp_std) / 2:.4f}")

    return "\n".join(lines)


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
    print(f"  [PREFLIGHT] Answer type: {answer_type} | {len(strategies)} strategies", file=sys.stderr)

    # Determine tool bundles for each worker
    bundle_assignments = _get_bundle_assignments(answer_type, goal, num_workers)
    file_path_in_goal = _extract_file_path(goal)

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
    print(f"{'─'*55}\n", file=out)

    results = []
    with ThreadPoolExecutor(max_workers=num_workers) as ex:
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
        # Check if we can pre-compute an answer from attached file data
        computed_answer = None
        if file_path_in_goal and answer_type == "number":
            file_content = _preload_file_content(file_path_in_goal)
            if file_content:
                computed_answer = _compute_answer_from_data(goal, file_content, file_path_in_goal)

        if computed_answer:
            # Inject directly into results and synthesis
            result["_computed"] = computed_answer
            synthesis_text = computed_answer
            syn_elapsed = 0
            result["synthesis"] = synthesis_text
            result["synthesis_model"] = "orchestrator"
            result["synthesis_time_s"] = 0
            print(f"\n  🔢 Orchestrator computed answer: {computed_answer[:200]}", file=out)
        else:
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