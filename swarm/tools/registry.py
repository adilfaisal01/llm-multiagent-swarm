"""Tool registry — discover, load, and bundle tools for workers.

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

    # Get a bundle by skill name
    vision_tools = registry.get_bundle("vision")
    code_tools = registry.get_bundle("code")
"""

from __future__ import annotations
import importlib
import inspect
import os
import pkgutil
from typing import Any

from .base import BaseTool


class ToolRegistry:
    """Holds all discovered tools and provides lookup/execution."""

    def __init__(self):
        self._tools: dict[str, BaseTool] = {}
        self._bundles: dict[str, list[str]] = {
            "all": [],  # special: every tool
            "search": ["web_search", "web_extract"],
            "vision": ["read_image", "web_search", "web_extract", "scratchpad_add"],
            "code": ["python_exec", "web_search", "web_extract", "scratchpad_add"],
            "files": ["read_file", "read_image", "web_search", "web_extract", "scratchpad_add"],
            "scratchpad": ["scratchpad_add"],
            "default": ["web_search", "web_extract", "scratchpad_add"],
        }

    def register(self, tool: BaseTool):
        """Register a single tool instance."""
        if not tool.name:
            raise ValueError("Tool must have a name")
        self._tools[tool.name] = tool
        if "all" in self._bundles:
            if tool.name not in self._bundles["all"]:
                self._bundles["all"].append(tool.name)

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def get_tools(self) -> list[BaseTool]:
        return list(self._tools.values())

    def get_ollama_tools(self) -> list[dict]:
        """Return tool definitions in Ollama function-calling format."""
        return [t.to_ollama_tool() for t in self._tools.values()]

    def get_ollama_tools_for_bundle(self, bundle_name: str) -> list[dict]:
        """Return Ollama-format tools for a named bundle."""
        names = self._bundles.get(bundle_name, [])
        return [self._tools[n].to_ollama_tool() for n in names if n in self._tools]

    def get_tools_for_bundle(self, bundle_name: str) -> list[BaseTool]:
        """Return tool instances for a named bundle."""
        names = self._bundles.get(bundle_name, [])
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
                            # Auto-bundle: if module has a BUNDLE list, add to those bundles
                            if hasattr(mod, "BUNDLES"):
                                for b in mod.BUNDLES:
                                    if b in self._bundles:
                                        if tool.name not in self._bundles[b]:
                                            self._bundles[b].append(tool.name)
            except Exception as e:
                print(f"  [WARN] Failed to load tool module {modname}: {e}")

    def define_bundle(self, name: str, tool_names: list[str]):
        """Define or override a bundle."""
        self._bundles[name] = tool_names

    def get_bundle_names(self) -> list[str]:
        return list(self._bundles.keys())

    def __repr__(self) -> str:
        return f"<ToolRegistry: {len(self._tools)} tools, {len(self._bundles)} bundles>"