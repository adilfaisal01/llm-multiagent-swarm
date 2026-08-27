"""Shared LLM chat helper — retry/backoff, streaming, and cost accounting.

Centralizes the repeated chat calls that used to live in worker.py,
synthesis.py, and preflight.py. Speaks the OpenAI-compatible
``/v1/chat/completions`` protocol, which covers OpenAI, Anthropic (compat
layer), Ollama (``/v1``), Groq, Together, DeepSeek, OpenRouter, vLLM, etc.

When the optional ``litellm`` package is installed (``pip install -e
".[providers]"``), calls route through it for native provider support and
normalized tool calls; otherwise a stdlib urllib implementation is used.

Usage:
    from swarm.llm import call_llm, RunCost

    cost = RunCost()
    text = call_llm("deepseek-v4-flash:cloud", messages, purpose="synthesis",
                    cost=cost, stream_cb=lambda chunk, phase: print(chunk))
    print(cost.completion_tokens)
"""

from __future__ import annotations

import json
import random
import time
import urllib.error
import urllib.request
import warnings
from dataclasses import dataclass, field

from .providers import resolve_endpoint, should_use_litellm

SAFETY_CAP = 32768


@dataclass
class RunCost:
    """Accumulated token + wall-time accounting for a run.

    All fields default to 0 so missing response fields never raise.
    ``estimated_cost_usd`` is only nonzero when the caller supplies model
    cost rates (config ``model_costs``) or the LiteLLM path computes it;
    otherwise it stays 0.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    estimated_cost_usd: float = 0.0
    calls: int = 0

    def add(self, prompt: int = 0, completion: int = 0, seconds: float = 0.0,
            rates: dict | None = None):
        """Accumulate one call's usage. ``rates`` is {input_per_1k, output_per_1k}."""
        self.prompt_tokens += int(prompt or 0)
        self.completion_tokens += int(completion or 0)
        self.seconds += float(seconds or 0.0)
        self.calls += 1
        if rates:
            in_rate = float(rates.get("input_per_1k", 0.0))
            out_rate = float(rates.get("output_per_1k", 0.0))
            self.estimated_cost_usd += (
                (self.prompt_tokens / 1000.0) * in_rate
                + (self.completion_tokens / 1000.0) * out_rate
            )

    def to_dict(self) -> dict:
        """JSON-serializable summary for the run result dict."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.prompt_tokens + self.completion_tokens,
            "seconds": round(self.seconds, 2),
            "calls": self.calls,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
        }


def _retry_policy(retry_cfg: dict | None) -> dict:
    """Normalize a retry config dict to {max_attempts, base_delay, max_delay}."""
    cfg = retry_cfg or {}
    return {
        "max_attempts": int(cfg.get("max_attempts", 3)),
        "base_delay": float(cfg.get("base_delay", 0.5)),
        "max_delay": float(cfg.get("max_delay", 4.0)),
    }


def _should_retry(exc: Exception) -> bool:
    """True if the exception is transient (network / 5xx / timeout)."""
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code >= 500 or exc.code == 429
    if isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError, OSError)):
        return True
    # LiteLLM raises its own exception types; treat rate-limit / connection /
    # timeout as transient.
    try:
        from litellm.exceptions import APIConnectionError, RateLimitError, Timeout
        if isinstance(exc, (RateLimitError, APIConnectionError, Timeout)):
            return True
    except ImportError:
        pass
    return False


def _retry_after_seconds(exc: Exception) -> float | None:
    """Honor Retry-After on 429 responses, else None."""
    if isinstance(exc, urllib.error.HTTPError) and exc.code == 429:
        try:
            return float(exc.headers.get("Retry-After", ""))
        except (ValueError, TypeError):
            return None
    return None


def _backoff_delay(attempt: int, policy: dict, retry_after: float | None) -> float:
    """Exponential backoff with jitter, capped at max_delay."""
    if retry_after is not None:
        return min(retry_after, policy["max_delay"])
    base = policy["base_delay"] * (2 ** (attempt - 1))
    return min(base + random.uniform(0, base * 0.25), policy["max_delay"])


def call_llm(
    model: str,
    messages: list,
    *,
    config: dict | None = None,
    ollama_base: str | None = None,
    stream: bool = False,
    temperature: float = 0.3,
    max_tokens: int | None = None,
    tools: list | None = None,
    timeout: int = 120,
    purpose: str = "chat",
    retry_cfg: dict | None = None,
    cost: RunCost | None = None,
    model_rates: dict | None = None,
    stream_cb=None,
    return_message: bool = False,
) -> str | dict:
    """Call an OpenAI-compatible chat API with retry/backoff and streaming.

    Args:
        model: Model tag, ``provider/name`` (e.g. ``openai/gpt-4o``) or a
            bare tag (e.g. ``deepseek-v4-flash:cloud`` → ollama provider).
        messages: Chat messages list (system/user/assistant/tool).
        config: Loaded swarm config dict. May contain a ``providers`` block
            (``{base_url, api_key_env}`` per provider) and ``use_litellm``.
        ollama_base: Deprecated. If set, overrides the resolved endpoint
            with an ollama-style base URL (``/v1`` appended).
        stream: If True, yield chunks via ``stream_cb`` and return the
            accumulated text. If False, return the full text.
        stream_cb: Optional ``callable(chunk: str, phase: str)`` invoked for
            each streamed chunk. ``phase`` is the ``purpose`` value.
        cost: Optional RunCost accumulator. Populated with token usage.
        model_rates: Optional {input_per_1k, output_per_1k} for cost estimation.
        max_tokens: Upper bound on output tokens. ``None`` applies a 32768-token
            safety cap, letting the model use its natural default without
            unbounded output; an explicit value overrides the cap.
        retry_cfg: Optional {max_attempts, base_delay, max_delay}.
        return_message: If True, return the full message dict (including
            ``tool_calls``) instead of just the text content. On failure
            still returns the ``[LLM error: ...]`` string.

    Returns:
        The model's text content (empty string on unrecoverable failure),
        or the full message dict when ``return_message`` is True.
    """
    base_url, api_model, headers, api_key = resolve_endpoint(model, config or {})

    if ollama_base is not None:
        warnings.warn(
            "ollama_base is deprecated; use config={'providers': {...}}",
            DeprecationWarning,
            stacklevel=2,
        )
        base_url = ollama_base.rstrip("/") + "/v1"

    if should_use_litellm(config, model):
        return _call_via_litellm(
            api_model, messages, base_url=base_url, api_key=api_key,
            headers=headers, stream=stream, temperature=temperature,
            max_tokens=max_tokens, tools=tools, timeout=timeout,
            purpose=purpose, retry_cfg=retry_cfg, cost=cost,
            model_rates=model_rates, stream_cb=stream_cb,
            return_message=return_message,
        )
    return _call_native(
        api_model, messages, base_url=base_url, headers=headers,
        stream=stream, temperature=temperature, max_tokens=max_tokens,
        tools=tools, timeout=timeout, purpose=purpose, retry_cfg=retry_cfg,
        cost=cost, model_rates=model_rates, stream_cb=stream_cb,
        return_message=return_message,
    )


def _call_native(
    model: str,
    messages: list,
    *,
    base_url: str,
    headers: dict,
    stream: bool,
    temperature: float,
    max_tokens: int | None,
    tools: list | None,
    timeout: int,
    purpose: str,
    retry_cfg: dict | None,
    cost: RunCost | None,
    model_rates: dict | None,
    stream_cb,
    return_message: bool,
) -> str | dict:
    """OpenAI-compatible chat via stdlib urllib (no external deps)."""
    policy = _retry_policy(retry_cfg)
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "temperature": temperature,
        "max_tokens": SAFETY_CAP if max_tokens is None else max_tokens,
    }
    if tools:
        payload["tools"] = tools

    data = json.dumps(payload).encode()
    url = f"{base_url.rstrip('/')}/chat/completions"
    last_exc: Exception | None = None
    start = time.time()

    for attempt in range(1, policy["max_attempts"] + 1):
        req = urllib.request.Request(url, data=data, headers=headers)
        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if stream:
                    text = _read_stream(resp, stream_cb, purpose)
                else:
                    result = json.loads(resp.read())
                    if return_message:
                        return result["choices"][0]["message"]
                    text = result["choices"][0]["message"].get("content", "") or ""
                    if cost is not None:
                        usage = result.get("usage", {})
                        cost.add(
                            prompt=usage.get("prompt_tokens", 0),
                            completion=usage.get("completion_tokens", 0),
                            seconds=time.time() - start,
                            rates=model_rates,
                        )
                return text
        except Exception as e:
            last_exc = e
            if not _should_retry(e):
                break
            if attempt < policy["max_attempts"]:
                delay = _backoff_delay(attempt, policy, _retry_after_seconds(e))
                time.sleep(delay)

    if cost is not None:
        cost.add(seconds=time.time() - start, rates=model_rates)
    return f"[LLM error: {last_exc}]" if last_exc else ""


def _read_stream(resp, stream_cb, purpose: str) -> str:
    """Consume an OpenAI SSE streaming response, forwarding chunks."""
    chunks = []
    for line in resp:
        line = line.strip()
        if not line or not line.startswith(b"data:"):
            continue
        data = line[5:].strip()
        if data == b"[DONE]":
            break
        try:
            obj = json.loads(data)
        except json.JSONDecodeError:
            continue
        delta = obj.get("choices", [{}])[0].get("delta", {}).get("content", "")
        if delta:
            chunks.append(delta)
            if stream_cb:
                stream_cb(delta, purpose)
    return "".join(chunks)


def _call_via_litellm(
    model: str,
    messages: list,
    *,
    base_url: str,
    api_key: str | None,
    headers: dict,
    stream: bool,
    temperature: float,
    max_tokens: int | None,
    tools: list | None,
    timeout: int,
    purpose: str,
    retry_cfg: dict | None,
    cost: RunCost | None,
    model_rates: dict | None,
    stream_cb,
    return_message: bool,
) -> str | dict:
    """LiteLLM transport — implemented in a later commit."""
    raise RuntimeError(
        "litellm transport not yet implemented; install with: pip install -e .[providers]"
    )
