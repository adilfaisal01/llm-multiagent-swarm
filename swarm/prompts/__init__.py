"""Prompt loader — reads markdown prompt templates from swarm/prompts/."""

from __future__ import annotations

import importlib.resources
from pathlib import Path


# Directory where prompt markdown files live, relative to this package.
_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Load a raw markdown prompt file by name (e.g. 'preflight', 'worker').

    Args:
        name: Prompt file name without the .md extension.

    Returns:
        The prompt text, or an empty string if the file is missing.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        # Fallback: try package resources for installed wheels
        try:
            return importlib.resources.files(__package__).joinpath(f"{name}.md").read_text()
        except Exception:
            return ""
    return path.read_text()


def render_prompt(name: str, **kwargs) -> str:
    """Load and render a markdown prompt template.

    Args:
        name: Prompt file name without the .md extension.
        **kwargs: Variables to format into the template.

    Returns:
        The rendered prompt string.
    """
    template = load_prompt(name)
    if not template:
        raise FileNotFoundError(f"Prompt template not found: {name}.md")
    return template.format(**kwargs)
