"""AI-based probabilistic source credibility scoring.

The heuristic score in scratchpad.py becomes a Bayesian PRIOR. An LLM judge
provides its own probability estimate + confidence (the likelihood). The two
are combined via confidence-weighted log-odds pooling into a POSTERIOR
probability.

If the LLM call fails or returns unusable output, the prior is kept — output
is never worse than the heuristic baseline.

Usage:
    from swarm.credibility import ai_score_sources

    posteriors = ai_score_sources(sources, model="deepseek-v4-flash:cloud")
    # posteriors[url] = {"posterior": 0.83, "prior": 0.65, ...}
"""

from __future__ import annotations

import json
import math

from .llm import call_llm
from .scratchpad import score_source

_LOGIT_CLAMP = 0.01  # avoid log(0) / log(1)


def _logit(p: float) -> float:
    p = min(max(p, _LOGIT_CLAMP), 1 - _LOGIT_CLAMP)
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def combine_probabilities(prior: float, llm_prob: float, confidence: float) -> float:
    """Confidence-weighted log-odds pooling of prior and LLM estimate.

    confidence=0 → returns prior; confidence=1 → returns llm_prob; in between,
    the posterior is a weighted geometric blend of the two odds.
    """
    c = min(max(confidence, 0.0), 1.0)
    if c == 0.0:
        return round(prior, 3)
    if c == 1.0:
        return round(llm_prob, 3)
    logit = (1 - c) * _logit(prior) + c * _logit(llm_prob)
    return round(_sigmoid(logit), 3)


_JUDGE_SYSTEM = (
    "You are a source-credibility judge for a research system. "
    "Given a source, estimate the probability (0.0-1.0) that it is credible "
    "and reliable for research purposes, and your confidence in that estimate. "
    "Consider domain authority, whether it looks like a primary source, "
    "editorial quality, and how corroborated it is. "
    "Respond with ONLY valid JSON."
)

_JUDGE_PROMPT = """Rate the credibility of each source below.

For each source, output:
- "probability": float 0.0-1.0 — your estimate that the source is credible/reliable
- "confidence": float 0.0-1.0 — how confident you are in that estimate
- "reason": short one-line justification

SOURCES:
{sources}

Respond with ONLY a JSON array, one object per source, in the same order:
[{{"url": "...", "probability": 0.8, "confidence": 0.7, "reason": "..."}}]
"""


def _format_sources(sources: list[dict]) -> str:
    lines = []
    for i, s in enumerate(sources, start=1):
        lines.append(
            f"{i}. url: {s.get('url', '')}\n"
            f"   domain: {s.get('domain', '')}\n"
            f"   title: {(s.get('title') or '')[:120]}\n"
            f"   snippet: {(s.get('snippet') or '')[:200]}\n"
            f"   corroboration: {s.get('corroboration', 1)} (how many workers hit it)\n"
            f"   first_seen: {s.get('first_seen', '')}"
        )
    return "\n".join(lines)


def _extract_judgments(text: str) -> list[dict]:
    """Parse the LLM's JSON array, tolerating markdown fences and noise."""
    text = text.strip()
    if text.startswith("```"):
        lines = [l for l in text.splitlines() if not l.strip().startswith("```")]
        text = "\n".join(lines)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[")
        end = text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            return []
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return []
    if not isinstance(data, list):
        return []
    out = []
    for item in data:
        if not isinstance(item, dict):
            continue
        try:
            prob = float(item.get("probability", 0.5))
            conf = float(item.get("confidence", 0.5))
        except (TypeError, ValueError):
            continue
        out.append({
            "url": str(item.get("url", "")),
            "probability": min(max(prob, 0.0), 1.0),
            "confidence": min(max(conf, 0.0), 1.0),
            "reason": str(item.get("reason", "")),
        })
    return out


def _prior(s: dict) -> float:
    """Heuristic prior from scratchpad.score_source."""
    return score_source(
        s.get("url", ""),
        domain=s.get("domain", ""),
        corroboration=s.get("corroboration", 1),
        first_seen=s.get("first_seen", ""),
    )


def ai_score_sources(sources: list[dict], *, model: str,
                     config: dict | None = None,
                     retry_cfg: dict | None = None,
                     cost=None, model_rates: dict | None = None,
                     timeout: int = 120) -> dict[str, dict]:
    """Score a batch of sources with an LLM judge.

    Args:
        sources: list of dicts with url, domain, title, snippet,
            corroboration, first_seen.
        model: full Ollama model tag for the judge.

    Returns:
        dict mapping url → {posterior, prior, llm_probability, confidence, reason}.
        On LLM failure, posterior == prior for every source.
    """
    if not sources:
        return {}
    prompt = _JUDGE_PROMPT.format(sources=_format_sources(sources))
    text = call_llm(
        model,
        [
            {"role": "system", "content": _JUDGE_SYSTEM},
            {"role": "user", "content": prompt},
        ],
        config=config,
        temperature=0.2,
        max_tokens=2048,
        timeout=timeout,
        purpose="credibility",
        retry_cfg=retry_cfg,
        cost=cost,
        model_rates=model_rates,
    )
    if text.startswith("[LLM error"):
        return {
            s["url"]: {"posterior": _prior(s), "prior": _prior(s),
                       "llm_probability": None, "confidence": None,
                       "reason": "LLM judge failed; heuristic prior kept"}
            for s in sources
        }
    judgments = _extract_judgments(text)
    by_url = {j["url"]: j for j in judgments}
    out = {}
    for s in sources:
        prior = _prior(s)
        j = by_url.get(s["url"])
        if j is None:
            out[s["url"]] = {"posterior": prior, "prior": prior,
                             "llm_probability": None, "confidence": None,
                             "reason": "no judgment returned; heuristic prior kept"}
            continue
        posterior = combine_probabilities(prior, j["probability"], j["confidence"])
        out[s["url"]] = {
            "posterior": posterior,
            "prior": prior,
            "llm_probability": j["probability"],
            "confidence": j["confidence"],
            "reason": j["reason"],
        }
    return out
