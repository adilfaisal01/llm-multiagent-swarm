"""Complexity estimation — uses the orchestrator model to judge query depth.

The orchestrator model (default: gpt-oss:120b-cloud) reads the query and
rates its complexity 1-5 based on semantic understanding. Falls back to
regex heuristic if the LLM call fails.

This is one quick call before spawning workers — negligible overhead
compared to the full swarm run.
"""

import json
import re
import urllib.request


def _regex_fallback(goal: str) -> int:
    """Heuristic fallback if the LLM call fails."""
    score = 1

    if len(goal.split()) > 4:
        score += 1

    # Reasoning depth
    if re.search(r'\b(why|how|explain|analyze|describe|implications?|impact|analysis|effects?|'
                 r'significance|meaning|purpose|validity|evaluate|assessment?|critique|criteria|'
                 r'evidence|justif(y|ication)|merits|drawbacks|pros|cons|strengths|weaknesses|'
                 r'valid|claim|assertion|argument|thesis|hypothesis)\b', goal, re.IGNORECASE):
        score += 1

    # Comparison
    if re.search(r'\b(difference|differences|compare|contrast|vs|versus|compared)\b', goal, re.IGNORECASE):
        score += 1

    # Technical jargon
    if re.search(r'\b(quantum|cryptography|neural|transformer|MoE|LQR|PID|'
                 r'Riccati|REST|GraphQL|API|protocol|algorithm|architecture|'
                 r'distributed|concurrent|parallel|AI|ML|deep learning)\b', goal, re.IGNORECASE):
        score += 1

    # Abstract / philosophical
    if re.search(r'\b(philosophical|consciousness|ethics?|moral|existence|'
                 r'reality|perception|awareness|sentience|qualia)\b', goal, re.IGNORECASE):
        score += 1

    # Controversy / debate
    if re.search(r'\b(controvers(y|ial)|debate|critic(al|ism)?|skeptic(al)?|'
                 r'pros|cons|argument|disagreement)\b', goal, re.IGNORECASE):
        score += 1

    # Multi-dimensional
    dim_pattern = r'\b(history|origins|timeline|future|trends?|technical|'
    dim_pattern += r'economic|financial|political|social|cultural|practical|theoretical|'
    dim_pattern += r'industrial|revolution|consequences|disaster|environmental|humanity)\b'
    dim_matches = re.findall(dim_pattern, goal, re.IGNORECASE)
    if len(set(m.lower() for m in dim_matches)) >= 2:
        score += 1

    # Temporal
    if re.search(r'\b(202[4-9]|2030|current|recent|upcoming|modern|contemporary|forecast)\b', goal, re.IGNORECASE):
        score += 1

    return max(1, min(5, score))


def estimate_complexity(goal: str, model: str | None = None,
                        ollama_base: str = "http://localhost:11434") -> int:
    """Estimate query complexity 1-5 using the orchestrator model.

    Makes one quick LLM call to actually read and understand the query.
    Falls back to regex heuristic if the call fails.
    """
    if not model:
        return _regex_fallback(goal)

    prompt = (
        "Rate the research complexity of this query on a scale of 1 to 5.\n\n"
        "1 = Simple fact lookup (e.g. 'What is the capital of France?')\n"
        "2 = Straightforward explanation (e.g. 'Explain REST vs GraphQL')\n"
        "3 = Multi-faceted topic needing 2-3 angles (e.g. 'Impact of quantum computing on cryptography')\n"
        "4 = Complex topic needing 4+ angles with controversy or depth (e.g. 'Is the industrial revolution a disaster for humanity?')\n"
        "5 = Deep philosophical/scientific question needing 5 angles (e.g. 'Philosophical implications of AI consciousness')\n\n"
        "Respond with ONLY a single digit 1-5. No explanation, no formatting.\n\n"
        f"Query: {goal}"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a query complexity classifier. Respond with a single digit 1-5."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"num_predict": 4, "temperature": 0.0},
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{ollama_base}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
            content = result.get("message", {}).get("content", "").strip()

        # Parse the digit
        match = re.search(r'[1-5]', content)
        if match:
            return int(match.group(0))
    except Exception:
        pass

    # Fallback to regex heuristic
    return _regex_fallback(goal)
