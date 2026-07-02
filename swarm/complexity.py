"""Complexity estimation — feedforward worker count based on query analysis.

The orchestrator (me) judges query complexity before spawning workers.
This sets the initial worker count. The scratchpad provides feedback
for adjustment if needed.

Note: This is a heuristic, not a measurement. It's good enough for a starting
point. The feedback loop (marginal gain from scratchpad) corrects for
mis-estimates.
"""

import re


def estimate_complexity(goal: str) -> int:
    """Estimate query complexity on a scale of 1-5.

    Counts distinct signals that indicate depth/breadth.
    """
    score = 1  # base: at least 1 worker for any query

    # Longer questions tend to be more complex
    if len(goal.split()) > 4:
        score += 1

    # Reasoning depth
    if re.search(r'\b(why|how|explain|analyze|describe|implications?|impact|analysis|effects?|significance|meaning|purpose)\b', goal, re.IGNORECASE):
        score += 1

    # Comparison / sub-topics
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

    # Multi-dimensional (mentions 2+ of history/future/technical/economic/etc)
    dim_pattern = r'\b(history|origins|timeline|future|trends?|technical|'
    dim_pattern += r'economic|financial|political|social|cultural|practical|theoretical)\b'
    dim_matches = re.findall(dim_pattern, goal, re.IGNORECASE)
    if len(set(m.lower() for m in dim_matches)) >= 2:
        score += 1

    # Temporal (current events, recent, year)
    if re.search(r'\b(202[4-9]|2030|current|recent|upcoming|modern|contemporary|forecast)\b', goal, re.IGNORECASE):
        score += 1

    return max(1, min(5, score))
