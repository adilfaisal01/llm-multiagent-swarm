"""Provider resolution — maps model tags to endpoints, keys, and headers.

Model tags carry a ``provider/name`` shape (e.g. ``openai/gpt-4o``,
``ollama/deepseek-v4-flash:cloud``). The provider prefix selects a block
from the config ``providers`` dict; the remainder is the model name sent
to the API. Bare tags with no ``/`` fall back to the ``ollama`` provider.

Also exposes LiteLLM detection so ``swarm/llm.py`` can dispatch to the
optional ``litellm`` transport when installed.
"""

from __future__ import annotations

import os

DEFAULT_OLLAMA_BASE = "http://localhost:11434/v1"

_litellm_available: bool | None = None


def resolve_endpoint(model_tag: str, config: dict | None = None) -> tuple[str, str, dict, str | None]:
    """Resolve a model tag to (base_url, api_model, headers, api_key).

    Args:
        model_tag: ``provider/name`` or a bare tag (bare → ``ollama``).
        config: Loaded swarm config dict. May contain a ``providers``
            block mapping provider names to ``{base_url, api_key_env}``.

    Returns:
        ``(base_url, api_model, headers, api_key)`` where ``headers``
        includes ``Authorization: Bearer`` when an API key resolves.
    """
    provider, name = _split_tag(model_tag)
    prov_cfg = ((config or {}).get("providers") or {}).get(provider) or {}

    base_url = prov_cfg.get("base_url") or _default_base_url(provider)
    api_key = _resolve_api_key(prov_cfg.get("api_key_env"))

    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    return base_url, name, headers, api_key


def has_litellm() -> bool:
    """True if the optional ``litellm`` package is importable (cached)."""
    global _litellm_available
    if _litellm_available is None:
        try:
            import litellm  # noqa: F401
            _litellm_available = True
        except ImportError:
            _litellm_available = False
    return _litellm_available


def should_use_litellm(config: dict | None = None, model_tag: str = "") -> bool:
    """Whether to route through LiteLLM for a call.

    Honors an explicit ``use_litellm`` bool in config; otherwise auto-
    detects (True when litellm is installed).
    """
    cfg = config or {}
    explicit = cfg.get("use_litellm")
    if explicit is not None:
        return bool(explicit)
    return has_litellm()


def _split_tag(model_tag: str) -> tuple[str, str]:
    """Split ``provider/name`` → (provider, name); bare tag → (ollama, tag)."""
    if "/" in model_tag:
        provider, name = model_tag.split("/", 1)
        return provider, name
    return "ollama", model_tag


def _default_base_url(provider: str) -> str:
    """Default base URL for a provider when config omits it."""
    if provider == "ollama":
        raw = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        if not raw.startswith("http"):
            raw = f"http://{raw}"
        return raw.rstrip("/") + "/v1"
    return DEFAULT_OLLAMA_BASE


def _resolve_api_key(env_name: str | None) -> str | None:
    """Read an API key from the named env var, else None."""
    if not env_name:
        return None
    return os.environ.get(env_name) or None
