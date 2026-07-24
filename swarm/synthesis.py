"""Synthesis — the orchestrator reads all worker reports + scratchpad and produces a unified answer.

This is the final pass that actually connects the dots across all 5 angles.
Without this, the swarm is just "here's 5 separate reports." With it,
you get a coherent research answer.
"""

import json
import urllib.request

from .prompts import render_prompt


def synthesize(goal: str, result: dict, model: str,
               ollama_base: str = "http://localhost:11434") -> str:
    """Have the orchestrator model synthesize all worker findings into one answer.

    Args:
        goal: The original research question.
        result: The full swarm result dict (workers, scratchpad, etc.).
        model: Model to use for synthesis (e.g. deepseek-v4-flash:cloud).
        ollama_base: Ollama API base URL.

    Returns:
        A unified synthesis text, or empty string if synthesis fails.
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

    research_mode = result.get("research_mode", "objective")
    synthesis_instructions = render_prompt(f"synthesis_{research_mode}")

    prompt = render_prompt(
        "synthesis",
        goal=goal,
        research_mode=research_mode.upper(),
        num_workers=result['num_workers'],
        worker_section=worker_section,
        findings_section=findings_section,
        synthesis_instructions=synthesis_instructions,
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a research synthesis expert. You read multiple reports on the same topic and produce a unified, insightful analysis."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 4096},
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{ollama_base}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            content = result.get("message", {}).get("content", "").strip()
            return content
    except Exception as e:
        return f"[Synthesis error: {e}]"