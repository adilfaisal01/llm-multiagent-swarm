"""Skill system — capability packs for swarm workers.

A skill is a self-contained folder under swarm/skills/<name>/ containing a
SKILL.md file with YAML frontmatter (name, description, triggers, tools,
recommended_model, optional team/mode) and a markdown body that becomes the
worker's behavior rules.

Skills reference tools by name — all tool implementations live in swarm/tools/.
"""
from ._base import Skill, SkillRegistry, get_skill_registry, reset_skill_registry

__all__ = ["Skill", "SkillRegistry", "get_skill_registry", "reset_skill_registry"]
