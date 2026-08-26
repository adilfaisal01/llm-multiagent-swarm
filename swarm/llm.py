"""Shared Ollama chat helper — retry/backoff, streaming, and cost accounting.

Centralizes the repeated ``requests``-style chat calls that used to live in
worker.py, synthesis.py, and preflight.py. Behavior is identical to the old
call sites when no retry is triggered and streaming is off, so this is a
drop-in replacement.

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
from dataclasses import dataclass, field


@dataclass
class RunCost:
    """Accumulated token + wall-time accounting for a run.

    All fields default to 0 so missing Ollama response fields never raise.
    ``estimated_cost_usd`` is only nonzero when the caller supplies model
    cost rates (config ``model_costs``); otherwise it stays 0.
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
    if isinstance(exc, (urllib.error.URLError, TimeoutError, ConnectionError, OSError)):
        return True
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code >= 500 or exc.code == 429
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
    ollama_base: str = "http://localhost:11434",
    stream: bool = False,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    tools: list | None = None,
    timeout: int = 120,
    purpose: str = "chat",
    retry_cfg: dict | None = None,
    cost: RunCost | None = None,
    model_rates: dict | None = None,
    stream_cb=None,
) -> str:
    """Call the Ollama chat API with retry/backoff and optional streaming.

    Args:
        model: Full Ollama model tag (e.g. ``deepseek-v4-flash:cloud``).
        messages: Chat messages list (system/user/assistant/tool).
        stream: If True, yield chunks via ``stream_cb`` and return the
            accumulated text. If False, return the full text.
        stream_cb: Optional ``callable(chunk: str, phase: str)`` invoked for
            each streamed chunk. ``phase`` is the ``purpose`` value.
        cost: Optional RunCost accumulator. Populated with token usage.
        model_rates: Optional {input_per_1k, output_per_1k} for cost estimation.
        retry_cfg: Optional {max_attempts, base_delay, max_delay}.

    Returns:
        The model's text content (empty string on unrecoverable failure).
    """
    policy = _retry_policy(retry_cfg)
    payload = {
        "model": model,
        "messages": messages,
        "stream": stream,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if tools:
        payload["tools"] = tools

    data = json.dumps(payload).encode()
    last_exc: Exception | None = None
    start = time.time()

    for attempt in range(1, policy["max_attempts"] + 1):
        req = urllib.request.Request(
            f"{ollama_base}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
        )
        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if stream:
                    text = _read_stream(resp, stream_cb, purpose)
                else:
                    result = json.loads(resp.read())
                    text = result.get("message", {}).get("content", "") or ""
                    if cost is not None:
                        cost.add(
                            prompt=result.get("prompt_eval_count", 0),
                            completion=result.get("eval_count", 0),
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
    """Consume an Ollama NDJSON streaming response, forwarding chunks."""
    chunks = []
    for line in resp:
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        piece = obj.get("message", {}).get("content", "")
        if piece:
            chunks.append(piece)
            if stream_cb:
                stream_cb(piece, purpose)
    return "".join(chunks)
