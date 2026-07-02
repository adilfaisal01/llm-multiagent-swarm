"""Swarm v2 — parallel research agents with write-only scratchpad.

Usage as a library:
    from swarm import run_swarm

    result = run_swarm("What is the capital of France?", mix=True)
    print(result["workers"][0]["response"][:200])
"""

from .runner import run_swarm
from .scratchpad import Scratchpad
from .orchestrator import orchestrate
from .complexity import estimate_complexity
