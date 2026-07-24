"""In-memory session model + follow-up context builder for the TUI."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    """A single TUI research session."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    title: str = "New session"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    messages: list[dict[str, Any]] = field(default_factory=list)
    results: list[dict[str, Any]] = field(default_factory=list)

    def add_user_message(self, text: str) -> None:
        self.messages.append({
            "role": "user",
            "content": text,
            "timestamp": time.time(),
        })
        if len(self.messages) == 1:
            self.title = text.strip()[:60] or "New session"
        self.updated_at = time.time()

    def last_user_query(self) -> str:
        """Return the most recent user message text for clean filenames/context."""
        for msg in reversed(self.messages):
            if msg.get("role") == "user":
                return msg.get("content", "")
        return ""

    def add_orchestrator_message(self, text: str, result: dict[str, Any] | None = None) -> None:
        self.messages.append({
            "role": "orchestrator",
            "content": text,
            "timestamp": time.time(),
        })
        if result:
            self.results.append(result)
        self.updated_at = time.time()

    def add_worker_messages(self, workers: list[dict[str, Any]]) -> None:
        for w in workers:
            self.messages.append({
                "role": "worker",
                "name": w.get("name", "Worker"),
                "bundle": w.get("tool_bundle", "default"),
                "model": w.get("model", ""),
                "status": w.get("status", "ok"),
                "duration_s": w.get("duration_s", 0),
                "search_rounds": w.get("search_rounds", 0),
                "content": w.get("response", "")[:2000],
                "timestamp": time.time(),
            })
        self.updated_at = time.time()

    def last_result(self) -> dict[str, Any] | None:
        return self.results[-1] if self.results else None

    def context_for_followup(self) -> str:
        """Build a concise context string from the previous run for the next swarm."""
        result = self.last_result()
        if not result:
            return ""
        parts: list[str] = []
        synthesis = result.get("synthesis", "")
        if synthesis:
            parts.append(f"Previous synthesis:\n{synthesis[:2000].strip()}")
        sp = result.get("scratchpad", {})
        findings = sp.get("findings", [])
        if findings:
            parts.append("Top previous findings:")
            for row in findings[:10]:
                worker, source_url, finding, category, confidence = row
                parts.append(f"- [{category}/{confidence}] {finding[:200]}")
        return "\n\n".join(parts)
