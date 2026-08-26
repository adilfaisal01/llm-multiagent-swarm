"""Synthesis — the orchestrator reads all worker reports + scratchpad and produces a unified answer.

This is the final pass that actually connects the dots across all 5 angles.
Without this, the swarm is just "here's 5 separate reports." With it,
you get a coherent research answer.

Synthesis now produces inline ``[N]`` citations: the model is given a
numbered source list and asked to cite claims with ``[N]`` markers. A
post-processor validates the markers, drops any that don't resolve to a
real source, and appends a numbered ``## Sources`` section.
"""

import json
import re

from .llm import call_llm
from .prompts import render_prompt

_CITE_RE = re.compile(r"\[(\d{1,3})\]")


def _build_source_section(sp: dict, credible_domains: tuple) -> str:
    """Render the numbered source list the model cites against.

    Each entry: ``[N] <domain> (credibility ★★) — <title>`` plus up to two
    associated findings so the model can attribute claims accurately.
    """
    sources = sp.get("top_sources", [])
    if not sources:
        return ""
    lines = []
    for i, src in enumerate(sources, start=1):
        stars = _stars(src.get("credibility", 0.0))
        title = (src.get("title") or src.get("url") or "")[:120]
        lines.append(f"[{i}] {src.get('domain', '')} ({stars}) — {title}")
        for finding in src.get("findings", [])[:2]:
            lines.append(f"    - {finding[:160]}")
    return "\n".join(lines)


def _stars(credibility: float) -> str:
    """Map a 0..1 credibility score to 1-3 stars."""
    if credibility >= 0.75:
        return "★★★"
    if credibility >= 0.5:
        return "★★"
    return "★"


def _extract_citations(text: str, sources: list) -> tuple[list, str]:
    """Validate [N] markers against the source list.

    Returns (citations, cleaned_text) where citations is a list of
    {n, url, domain, credibility} dicts and cleaned_text has hallucinated
    markers removed.
    """
    citations = []
    used = set()
    for m in _CITE_RE.finditer(text):
        n = int(m.group(1))
        if 1 <= n <= len(sources) and n not in used:
            src = sources[n - 1]
            citations.append({
                "n": n,
                "url": src["url"],
                "domain": src.get("domain", ""),
                "credibility": src.get("credibility", 0.0),
            })
            used.add(n)
    if not citations:
        return [], text
    cleaned = _CITE_RE.sub(
        lambda m: f"[{m.group(1)}]" if int(m.group(1)) in used else "",
        text,
    )
    return citations, cleaned


def _append_sources_section(text: str, citations: list) -> str:
    """Append a numbered Sources section mapping [N] to URLs."""
    if not citations:
        return text
    lines = ["", "## Sources", ""]
    for c in citations:
        stars = _stars(c["credibility"])
        lines.append(f"{c['n']}. {c['url']} — {c['domain']} ({stars})")
    return text + "\n".join(lines)


def synthesize(goal: str, result: dict, model: str,
               ollama_base: str = "http://localhost:11434",
               credible_domains: tuple = (".gov", ".edu", ".mil"),
               stream_cb=None, report: bool = False) -> dict:
    """Have the orchestrator model synthesize all worker findings into one answer.

    Args:
        goal: The original research question.
        result: The full swarm result dict (workers, scratchpad, etc.).
        model: Model to use for synthesis (e.g. deepseek-v4-flash:cloud).
        ollama_base: Ollama API base URL.
        credible_domains: Domain suffixes that boost source credibility.
        stream_cb: Optional callable(chunk, phase) for streaming synthesis.
        report: If True, use the structured report synthesis prompt instead of
            the analytical take.

    Returns:
        A dict with keys:
            synthesis: the unified markdown text (with [N] citations + Sources)
            citations: list of {n, url, domain, credibility}
            sources_used: number of distinct sources cited
            sources_total: number of sources offered to the model
    """
    # Build context from worker reports (truncated to keep prompt manageable)
    worker_section = ""
    for w in result["workers"]:
        # Truncate long responses to ~1000 chars each
        body = w["response"][:1000]
        if len(w["response"]) > 1000:
            body += f"\n... ({len(w['response'])} chars total, truncated for synthesis)"
        worker_section += f"### {w['name']} ({w['model']})\n"
        worker_section += f"*Angle: {w.get('angle', 'General')}*\n"
        worker_section += f"*Duration: {w['duration_s']}s | Searches: {w['search_rounds']}*\n\n"
        worker_section += f"{body}\n\n"

    # Build scratchpad findings section
    sp = result.get("scratchpad", {})
    findings_section = ""
    if sp.get("findings"):
        findings_section += "### Key Findings (from scratchpad)\n\n"
        for row in sp["findings"][:20]:  # cap at 20 to keep context manageable
            worker, src_url, finding, cat, conf = row
            findings_section += f"- [{cat}] {finding[:200]} (source: {src_url[:50]}) — {worker}\n"
        findings_section += "\n"

    # Numbered, credibility-ranked source list the model cites against
    sources = sp.get("top_sources", [])
    source_section = _build_source_section(sp, credible_domains)

    research_mode = result.get("research_mode", "objective")
    if report:
        synthesis_instructions = render_prompt("synthesis_report")
    else:
        synthesis_instructions = render_prompt(f"synthesis_{research_mode}")

    prompt = render_prompt(
        "synthesis",
        goal=goal,
        research_mode=research_mode.upper(),
        num_workers=result['num_workers'],
        worker_section=worker_section,
        findings_section=findings_section,
        source_section=source_section,
        synthesis_instructions=synthesis_instructions,
    )

    messages = [
        {"role": "system", "content": "You are a research synthesis expert. You read multiple reports on the same topic and produce a unified, insightful analysis."},
        {"role": "user", "content": prompt},
    ]

    text = call_llm(
        model,
        messages,
        ollama_base=ollama_base,
        stream=stream_cb is not None,
        temperature=0.3,
        max_tokens=4096,
        purpose="synthesis",
        stream_cb=stream_cb,
    )

    if text.startswith("[LLM error") or text.startswith("[Synthesis error"):
        return {
            "synthesis": f"[Synthesis error: {text}]",
            "citations": [],
            "sources_used": 0,
            "sources_total": len(sources),
        }

    citations, cleaned = _extract_citations(text, sources)
    final = _append_sources_section(cleaned, citations)
    return {
        "synthesis": final,
        "citations": citations,
        "sources_used": len(citations),
        "sources_total": len(sources),
    }
