"""Tool registry — discover, load, and execute tools for workers.

Usage:
    from swarm.tools.registry import ToolRegistry

    registry = ToolRegistry()
    registry.discover()

    # Get all tools
    all_tools = registry.get_tools()

    # Get Ollama-format tool definitions
    ollama_tools = registry.get_ollama_tools()

    # Execute a tool call
    result = registry.execute(tool_call, worker_name="Vera")

    # Get tools for a skill (delegates to the SkillRegistry)
    vision_tools = registry.get_tools_for_bundle("vision")
"""

from __future__ import annotations
import importlib
import inspect
import os
import pkgutil
from typing import Any

from .base import BaseTool


class ToolRegistry:
    """Holds all discovered tools and provides lookup/execution.

    Tool bundles are now defined by skills (swarm/skills/). The registry
    delegates skill→tools resolution to a SkillRegistry when one is wired in
    via set_skill_registry(); otherwise it falls back to the legacy hardcoded
    bundle map for backward compatibility.
    """

    _LEGACY_BUNDLES: dict[str, list[str]] = {
        "search": ["web_search", "web_extract"],
        "vision": ["read_image", "web_search", "web_extract", "scratchpad_add"],
        "code": ["python_exec", "web_search", "web_extract", "scratchpad_add"],
        "files": ["read_file", "read_image", "web_search", "web_extract", "scratchpad_add"],
        "scratchpad": ["scratchpad_add"],
        "default": ["web_search", "web_extract", "scratchpad_add"],
    }

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._skill_registry = None

    def set_skill_registry(self, skill_registry):
        """Wire a SkillRegistry so bundle lookups resolve through skills."""
        self._skill_registry = skill_registry

    def register(self, tool: BaseTool):
        """Register a single tool instance."""
        if not tool.name:
            raise ValueError("Tool must have a name")
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_ollama_tools(self) -> list[dict]:
        """Return tool definitions in Ollama function-calling format."""
        return [t.to_ollama_tool() for t in self._tools.values()]

    def get_ollama_tools_for_bundle(self, bundle_name: str) -> list[dict]:
        """Return Ollama-format tools for a named bundle/skill."""
        return [t.to_ollama_tool() for t in self.get_tools_for_bundle(bundle_name)]

    def get_tools_for_bundle(self, bundle_name: str) -> list[BaseTool]:
        """Return tool instances for a named bundle/skill.

        Resolves through the wired SkillRegistry when available; otherwise
        falls back to the legacy hardcoded bundle map.
        """
        if self._skill_registry is not None:
            return self._skill_registry.tools_for(bundle_name)
        names = self._LEGACY_BUNDLES.get(bundle_name, [])
        return [self._tools[n] for n in names if n in self._tools]

    def execute(self, fn_name: str, args: dict, worker_name: str = "") -> str:
        """Execute a tool by name."""
        tool = self._tools.get(fn_name)
        if not tool:
            return f"Unknown tool: {fn_name}"
        try:
            return tool.run(args, worker_name=worker_name)
        except Exception as e:
            return f"[Tool error: {e}]"

    def discover(self, package_path: str | None = None):
        """Auto-discover all tool modules in the tools package.

        Each module should define a list TOOLS = [Tool1(), Tool2(), ...]
        """
        base = os.path.dirname(os.path.abspath(__file__))
        for importer, modname, ispkg in pkgutil.iter_modules([base]):
            if modname in ("base", "registry", "__init__"):
                continue
            try:
                mod = importlib.import_module(f"swarm.tools.{modname}")
                if hasattr(mod, "TOOLS"):
                    for tool in mod.TOOLS:
                        if isinstance(tool, BaseTool):
                            self.register(tool)
            except Exception as e:
                print(f"  [WARN] Failed to load tool module {modname}: {e}")

    def get_bundle_names(self) -> list[str]:
        """Return known bundle/skill names (legacy map or wired skills)."""
        if self._skill_registry is not None:
            return self._skill_registry.names()
        return list(self._LEGACY_BUNDLES.keys())

    def __repr__(self) -> str:
        return f"<ToolRegistry: {len(self._tools)} tools>"