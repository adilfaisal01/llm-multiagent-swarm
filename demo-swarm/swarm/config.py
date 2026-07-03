"""Configuration loader and defaults for the swarm.

Loads from swarm_config.json with fallback to hardcoded defaults.
"""

import json
import os
import sys

CONFIG_PATH = os.environ.get("SWARM_CONFIG", "swarm_config.json")


def load_swarm_config(path: str = CONFIG_PATH) -> dict:
    """Load swarm configuration from JSON file."""
    if not os.path.exists(path):
        print(f"  [INFO] Config not found at {path}, using defaults", file=sys.stderr)
        return {}

    with open(path) as f:
        try:
            cfg = json.load(f)
        except json.JSONDecodeError as e:
            print(f"  [ERROR] Malformed config file {path}: {e}", file=sys.stderr)
            sys.exit(1)

    # Resolve model aliases to full tags
    models = cfg.get("models", {})
    for member in cfg.get("team", []):
        alias = member.get("model", "")
        if alias in models:
            member["_model_tag"] = models[alias]
        else:
            member["_model_tag"] = alias

    return cfg


def get_defaults(config: dict = None) -> dict:
    """Build default config dict from config file or hardcoded defaults."""
    if config is None:
        config = {}

    worker_models = config.get("models", {}) or {
        "ministral": "ministral-3:14b-cloud",
        "nemotron": "nemotron-3-nano:30b-cloud",
        "nemotron-super": "nemotron-3-super:cloud",
        "gpt-oss": "gpt-oss:120b-cloud",
        "gemma": "gemma4:31b-cloud",
        "qwen": "qwen3.5:397b-cloud",
        "deepseek": "deepseek-v4-flash:cloud",
        "flash": "deepseek-v4-flash:cloud",
    }

    default_worker = worker_models.get(
        config.get("default_model", ""),
        worker_models.get("gpt-oss", "gpt-oss:120b-cloud"),
    )

    raw_team = config.get("team", [])
    if raw_team:
        team = []
        for m in raw_team:
            team.append({
                "name": m.get("name", "Worker"),
                "model": m.get("_model_tag", m.get("model", default_worker)),
                "prompt": m.get("prompt", ""),
                "angle": m.get("angle", ""),
            })
    else:
        team = [
            {"name": "Vera",  "model": worker_models.get("gpt-oss", "gpt-oss:120b-cloud"),  "prompt": "", "angle": "Cover ORIGINS and HISTORY. Timeline, background, how it started."},
            {"name": "Cyrus", "model": worker_models.get("nemotron", "nemotron-3-nano:30b-cloud"), "prompt": "", "angle": "Cover KEY PLAYERS and MONEY. Who is involved, who benefits, amounts at stake."},
            {"name": "Romy",  "model": worker_models.get("qwen", "qwen3.5:397b-cloud"),      "prompt": "", "angle": "Cover IMPLICATIONS and FUTURE. Second-order effects, where this is heading."},
            {"name": "Ash",   "model": worker_models.get("deepseek", "deepseek-v4-flash:cloud"), "prompt": "", "angle": "Cover CONTROVERSIES and CRITICISMS. What opponents and skeptics say."},
            {"name": "Zara",  "model": worker_models.get("gpt-oss", "gpt-oss:120b-cloud"),  "prompt": "", "angle": "Cover TECHNICAL DETAILS. How it actually works under the hood."},
        ]

    angles = config.get("angles", []) or [
        "Cover ORIGINS and HISTORY. Timeline, background, how it started.",
        "Cover KEY PLAYERS and MONEY. Who is involved, who benefits, amounts at stake.",
        "Cover IMPLICATIONS and FUTURE. Second-order effects, where this is heading.",
        "Cover CONTROVERSIES and CRITICISMS. What opponents and skeptics say.",
        "Cover TECHNICAL DETAILS. How it actually works under the hood.",
    ]

    fallback_models = config.get("fallback_models", []) or [
        "gpt-oss:120b-cloud",
        "nemotron-3-nano:30b-cloud",
    ]

    return {
        "worker_models": worker_models,
        "model_list": list(worker_models.keys()),
        "default_worker": default_worker,
        "team": team,
        "angles": angles,
        "fallback_models": fallback_models,
    }
