"""Skill model + registry for the swarm.

A skill is a capability pack: a folder under swarm/skills/<name>/ with a
SKILL.md file. The frontmatter (YAML, delimited by ---) declares metadata and
which tools the skill grants; the markdown body becomes the worker's behavior
rules.

Frontmatter fields:
    name               — skill identifier (required)
    description        — one-line summary shown to preflight (required)
    triggers           — keyword hints passed to preflight (optional)
    tools              — tool NAMES resolved against the ToolRegistry (optional)
    recommended_model  — suggested model for this skill (optional)
    team               — relative path to a team.json (optional, full-pack skills)
    mode               — "parallel" or "pipeline" (optional)
    version, category, tags, trigger, related_skills, platforms
                       — Hermes-style metadata, parsed but not used by swarm

The YAML subset parser is intentionally minimal (scalars + string arrays).
It keeps the frontmatter valid YAML so Hermes and other harnesses can read it,
without adding a PyYAML dependency.
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..tools.base import BaseTool
    from ..tools.registry import ToolRegistry

# Directory where skill folders live, relative to this package.
_SKILLS_DIR = Path(__file__).parent

# Fields that are Hermes-style metadata (parsed, not used by swarm).
_HERMES_FIELDS = ("version", "category", "tags", "trigger", "related_skills", "platforms")


def _warn(msg: str) -> None:
    print(f"  [WARN] {msg}", file=sys.stderr)


def _parse_scalar(value: str) -> str:
    """Parse a YAML scalar into a plain string (strip quotes)."""
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _parse_list(value: str) -> list[str]:
    """Parse a YAML inline list like [a, b, c] or a comma-separated string."""
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    items = [item.strip() for item in value.split(",") if item.strip()]
    return [_parse_scalar(item) for item in items]


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter delimited by --- lines.

    Returns:
        (frontmatter dict, body text). Empty dict if no frontmatter found.
    """
    if not text.startswith("---"):
        return {}, text
    lines = text.splitlines()
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text

    header = lines[1:end]
    body = "\n".join(lines[end + 1:]).strip()
    data: dict = {}
    for line in header:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value.startswith("["):
            data[key] = _parse_list(value)
        else:
            data[key] = _parse_scalar(value)
    return data, body


@dataclass
class Skill:
    """A capability pack: metadata + tool names + worker behavior rules."""

    name: str
    description: str
    triggers: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    recommended_model: str | None = None
    team_path: str | None = None
    mode: str | None = None
    prompt: str = ""
    # Hermes-style metadata (parsed, not used by swarm)
    version: str | None = None
    category: str | None = None
    tags: list[str] = field(default_factory=list)
    trigger: str | None = None
    related_skills: list[str] = field(default_factory=list)
    platforms: list[str] = field(default_factory=list)

    @classmethod
    def from_skill_file(cls, path: Path) -> "Skill":
        """Parse a SKILL.md file into a Skill."""
        text = path.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(text)
        name = frontmatter.get("name", path.parent.name)
        if not isinstance(name, str) or not name:
            raise ValueError(f"skill name must be a non-empty string, got {name!r}")
        description = frontmatter.get("description", "")
        if not isinstance(description, str):
            description = str(description)
        return cls(
            name=name,
            description=description,
            triggers=frontmatter.get("triggers", []),
            tools=frontmatter.get("tools", []),
            recommended_model=frontmatter.get("recommended_model"),
            team_path=frontmatter.get("team"),
            mode=frontmatter.get("mode"),
            prompt=body,
            version=frontmatter.get("version"),
            category=frontmatter.get("category"),
            tags=frontmatter.get("tags", []),
            trigger=frontmatter.get("trigger"),
            related_skills=frontmatter.get("related_skills", []),
            platforms=frontmatter.get("platforms", []),
        )

    def description_for_llm(self) -> str:
        """One-line description with trigger hints, for the preflight prompt."""
        line = f'"{self.name}": {self.description}'
        if self.triggers:
            line += f" (triggers: {', '.join(self.triggers)})"
        if self.recommended_model:
            line += f" Best model: {self.recommended_model}."
        return line


class SkillRegistry:
    """Discovers and holds skills; resolves tool names against a ToolRegistry."""

    def __init__(self, tool_registry: "ToolRegistry | None" = None):
        self._skills: dict[str, Skill] = {}
        self._tool_registry = tool_registry

    def set_tool_registry(self, tool_registry: "ToolRegistry") -> None:
        self._tool_registry = tool_registry

    def discover(self, root: str | Path | None = None) -> None:
        """Walk root (default swarm/skills/) for */SKILL.md files."""
        base = Path(root) if root else _SKILLS_DIR
        if not base.is_dir():
            _warn(f"Skills directory not found: {base}")
            return
        for skill_dir in sorted(base.iterdir()):
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            try:
                skill = Skill.from_skill_file(skill_file)
            except Exception as e:
                _warn(f"Malformed frontmatter in {skill_file}: {e}, skipping skill")
                continue
            if not skill.name:
                _warn(f"Skill {skill_dir.name} has no name, skipping")
                continue
            self._skills[skill.name] = skill

    def get(self, name: str) -> Skill | None:
        return self._skills.get(name)

    def all(self) -> list[Skill]:
        return list(self._skills.values())

    def names(self) -> list[str]:
        return sorted(self._skills.keys())

    def descriptions_for_llm(self) -> str:
        """Block of skill descriptions for the preflight prompt."""
        return "\n".join(s.description_for_llm() for s in sorted(self._skills.values(), key=lambda s: s.name))

    def tools_for(self, skill_name: str) -> list["BaseTool"]:
        """Resolve a skill's tool names to BaseTool instances.

        Unknown tool names are dropped with a warning; the skill stays usable
        with whatever tools remain.
        """
        skill = self._skills.get(skill_name)
        if skill is None:
            return []
        if self._tool_registry is None:
            return []
        resolved = []
        for name in skill.tools:
            tool = self._tool_registry.get(name)
            if tool is None:
                _warn(f"Skill '{skill_name}' references unknown tool '{name}', dropping it")
                continue
            resolved.append(tool)
        return resolved

    def ollama_tools_for(self, skill_name: str) -> list[dict]:
        """Ollama-format tool definitions for a skill."""
        return [t.to_ollama_tool() for t in self.tools_for(skill_name)]

    def load_team(self, skill_name: str) -> dict | None:
        """Load a skill's team.json if the frontmatter declares one."""
        skill = self._skills.get(skill_name)
        if skill is None or not skill.team_path:
            return None
        team_file = _SKILLS_DIR / skill_name / skill.team_path
        if not team_file.exists():
            _warn(f"No team.json for skill '{skill_name}' (expected {team_file}), using preflight team")
            return None
        try:
            with open(team_file) as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            _warn(f"Malformed team.json for skill '{skill_name}': {e}, using preflight team")
            return None

    def __repr__(self) -> str:
        return f"<SkillRegistry: {len(self._skills)} skills>"


# Global default registry, populated once.
_DEFAULT_SKILL_REGISTRY: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """Get or create the global skill registry (wired to the tool registry)."""
    global _DEFAULT_SKILL_REGISTRY
    if _DEFAULT_SKILL_REGISTRY is None:
        from ..tools import get_registry
        _DEFAULT_SKILL_REGISTRY = SkillRegistry(get_registry())
        _DEFAULT_SKILL_REGISTRY.discover()
    return _DEFAULT_SKILL_REGISTRY


def reset_skill_registry():
    """Reset the global skill registry (for testing)."""
    global _DEFAULT_SKILL_REGISTRY
    _DEFAULT_SKILL_REGISTRY = None
