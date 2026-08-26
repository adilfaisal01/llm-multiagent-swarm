"""High-level runner — the library entry point for the swarm.

Usage as a library:
    from swarm.runner import run_swarm

    result = run_swarm("What is the capital of France?", mix=True)
    print(result["workers"][0]["response"][:200])
"""

import os
import sys

from . import config as cfg
from .complexity import estimate_complexity
from .orchestrator import orchestrate


def run_swarm(
    goal: str,
    *,
    workers: int | None = None,
    auto: bool = False,
    mix: bool = False,
    model: str | None = None,
    angle: str | None = None,
    config_path: str | None = None,
    skill: str | None = None,
    json_mode: bool = False,
    ollama_host: str | None = None,
    synthesize: bool = True,
    progress_callback=None,
    stream_callback=None,
    ai_credibility: bool = True,
) -> dict:
    """Run the swarm and return results.

    This is the main library entry point. Handles config loading,
    complexity estimation, and orchestration in one call.

    Args:
        goal: Research question.
        workers: Number of workers (1-5). If None and auto=False, defaults to 3.
        auto: Auto-estimate worker count from query complexity.
        mix: Use mixed models (Vera/Cyrus/Romy/Ash/Zara).
        model: Model for uniform mode (ignored if mix=True).
        angle: Optional top-level angle prepended to all workers.
        config_path: Path to JSON config file. Defaults to SWARM_CONFIG env or swarm_config.json.
        skill: Named skill from swarm/skills/. Loads its team.json if present.
        json_mode: Return JSON-serializable output.
        ollama_host: Ollama base URL. Defaults to OLLAMA_HOST env or http://localhost:11434.
        progress_callback: Optional callable(event, payload) for live UI updates.
        stream_callback: Optional callable(chunk, phase) receiving streamed
            tokens from preflight and synthesis (phase in {"preflight",
            "synthesis"}).
        ai_credibility: If True, an LLM judge refines source credibility
            scores into Bayesian posteriors (default True).

    Returns:
        Dict with keys: goal, num_workers, models, wall_time_s, workers, scratchpad.
    """
    # Resolve Ollama URL
    ollama_raw = ollama_host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    ollama_base = f"http://{ollama_raw}" if not ollama_raw.startswith("http") else ollama_raw

    # Load config
    config_path = config_path or cfg.CONFIG_PATH
    loaded_config = cfg.load_swarm_config(config_path)
    defaults = cfg.get_defaults(loaded_config)

    # If a skill is named, load its team.json (if it ships one) as the config
    skill_team = None
    if skill:
        from .skills import get_skill_registry
        skill_team = get_skill_registry().load_team(skill)
        if skill_team:
            loaded_config = skill_team
            defaults = cfg.get_defaults(loaded_config)
            if not mix:
                mix = True
                print(f"  [INFO] Skill '{skill}' ships a team — enabling --mix to use it", file=sys.stderr)
        else:
            print(f"  [INFO] Skill '{skill}' has no team.json — using preflight-generated team", file=sys.stderr)
    elif loaded_config and loaded_config.get("skill"):
        # --config JSON may declare a skill: use its prompt body + tools with the JSON's team
        from .skills import get_skill_registry
        cfg_skill = loaded_config.get("skill")
        if cfg_skill and get_skill_registry().get(cfg_skill) is None:
            print(f"  [WARN] Config references unknown skill '{cfg_skill}', ignoring", file=sys.stderr)
            cfg_skill = None
        skill = cfg_skill

    # Pull goal and angle from config if not set
    if not goal:
        goal = loaded_config.get("goal", "") if loaded_config else ""
    if not angle:
        angle = loaded_config.get("angle", "") if loaded_config else ""

    if not goal or not goal.strip():
        print("  [ERROR] --goal cannot be empty. Swarm needs a question to research!", file=sys.stderr)
        sys.exit(1)

    # Determine worker count
    if workers is not None:
        num_workers = min(max(workers, 1), 5)
    elif auto:
        est_model = defaults["worker_models"].get("deepseek", "deepseek-v4-flash:cloud")
        num_workers = estimate_complexity(goal, model=est_model, ollama_base=ollama_base)
        print(f"  [AUTO] Estimated complexity: {num_workers}/5 workers (model: {est_model.split(':')[0]})", file=sys.stderr)
    elif skill_team:
        # Skill ships a team — default to the full team size (concurrency is
        # capped at 5 in the orchestrator; extra workers queue up).
        num_workers = len(skill_team["team"])
        print(f"  [INFO] Skill '{skill}' ships {num_workers} workers — using full team "
              f"(max 5 run concurrently, rest queue)", file=sys.stderr)
    elif mix:
        # Mixed team — default to the full team size so all 5 workers run.
        num_workers = len(defaults["team"])
        print(f"  [INFO] --mix with no --workers — using full team of {num_workers}",
              file=sys.stderr)
    else:
        num_workers = 3

    # Resolve model
    resolved_model: str | None = None
    if model:
        resolved_model = defaults["worker_models"].get(model, model)

    # Run the swarm
    result = orchestrate(
        goal=goal,
        num_workers=num_workers,
        model=resolved_model,
        mix=mix,
        json_mode=json_mode,
        top_angle=angle or "",
        team=defaults["team"],
        angles=defaults["angles"],
        default_worker=defaults["default_worker"],
        fallback_models=defaults["fallback_models"],
        ollama_base=ollama_base,
        synthesize=synthesize,
        synthesis_model=defaults["worker_models"].get("deepseek", "deepseek-v4-flash:cloud"),
        skill=skill,
        progress_callback=progress_callback,
        stream_callback=stream_callback,
        credible_domains=defaults["credible_domains"],
        retry_cfg=defaults["retry"],
        model_costs=defaults["model_costs"],
        ai_credibility=ai_credibility,
    )

    return result
