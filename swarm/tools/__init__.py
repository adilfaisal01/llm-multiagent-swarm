"""Modular tool system for swarm workers.

Each tool is a module in swarm/tools/ with a TOOLS list and optional BUNDLES list.
The registry auto-discovers all tools and provides bundle-based filtering.
"""
from .registry import ToolRegistry

# Global default registry, populated once
_DEFAULT_REGISTRY: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Get or create the global tool registry."""
    global _DEFAULT_REGISTRY
    if _DEFAULT_REGISTRY is None:
        _DEFAULT_REGISTRY = ToolRegistry()
        _DEFAULT_REGISTRY.discover()
    return _DEFAULT_REGISTRY


def reset_registry():
    """Reset the global registry (for testing)."""
    global _DEFAULT_REGISTRY
    _DEFAULT_REGISTRY = None