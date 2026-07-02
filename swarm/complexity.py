"""Complexity estimation — asks the orchestrator model to rate query depth 1-5.

One quick LLM call before spawning workers. Negligible overhead
compared to the full swarm run (~30s timeout, 4 tokens output).
"""

import json
import re
import urllib.request


def estimate_complexity(goal: str, model: str,
                        ollama_base: str = "http://localhost:11434") -> int:
    """Ask the model to rate query complexity 1-5.

    Makes one quick call to the orchestrator model (DeepSeek V4 Flash).
    The model reads the query and classifies it. Returns 3 (default)
    if the call fails.
    """
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
        "options": {"temperature": 0.0, "num_predict": 200},
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

        match = re.search(r'[1-5]', content)
        if match:
            return int(match.group(0))
    except Exception:
        pass

    return 3  # safe default
