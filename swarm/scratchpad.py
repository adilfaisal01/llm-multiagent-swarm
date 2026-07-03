"""Scratchpad — write-only RAM SQLite database for raw findings.

Agents WRITE only — they never read from it. The orchestrator reads
after all agents finish to synthesize across all sources.

Usage:
    from swarm.scratchpad import get_scratchpad, set_scratchpad
    sp = get_scratchpad()
    if sp:
        sp.add_finding(...)
"""

import sqlite3

# Global scratchpad instance, set by the orchestrator before spawning workers
_GLOBAL_SCRATCHPAD = None


def set_scratchpad(sp):
    """Set the global scratchpad instance. Called by orchestrator before spawning workers."""
    global _GLOBAL_SCRATCHPAD
    _GLOBAL_SCRATCHPAD = sp


def get_scratchpad():
    """Get the current global scratchpad. Safe — returns None if not set."""
    return _GLOBAL_SCRATCHPAD


class Scratchpad:
    """Temporary SQLite database in RAM for agents to dump raw findings."""

    def __init__(self):
        self._conn = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
        self._conn.execute("""
            CREATE TABLE findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker TEXT NOT NULL,
                source_url TEXT,
                finding TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                confidence TEXT DEFAULT 'medium',
                timestamp TEXT DEFAULT (datetime('now'))
            )
        """)
        self._conn.execute("""
            CREATE TABLE sources (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker TEXT NOT NULL,
                url TEXT NOT NULL,
                title TEXT DEFAULT '',
                snippet TEXT DEFAULT '',
                timestamp TEXT DEFAULT (datetime('now'))
            )
        """)

    def add_finding(self, worker: str, finding: str, source_url: str = "",
                    category: str = "general", confidence: str = "medium"):
        """Write a finding to the scratchpad. Agents call this, never read."""
        self._conn.execute(
            "INSERT INTO findings (worker, source_url, finding, category, confidence) VALUES (?, ?, ?, ?, ?)",
            (worker, source_url, finding, category, confidence)
        )
        self._conn.commit()

    def add_source(self, worker: str, url: str, title: str = "", snippet: str = ""):
        """Log a source URL the agent scraped."""
        self._conn.execute(
            "INSERT INTO sources (worker, url, title, snippet) VALUES (?, ?, ?, ?)",
            (worker, url, title, snippet[:500])
        )
        self._conn.commit()

    def get_all_findings(self) -> list:
        """Read all findings. Only the orchestrator calls this."""
        return self._conn.execute(
            "SELECT worker, source_url, finding, category, confidence FROM findings ORDER BY id"
        ).fetchall()

    def get_all_sources(self) -> list:
        """Read all sources collected. Only the orchestrator calls this."""
        return self._conn.execute(
            "SELECT worker, url, title FROM sources ORDER BY id"
        ).fetchall()

    def get_summary(self) -> dict:
        """Get a quick summary of what was collected."""
        findings = self._conn.execute("SELECT COUNT(*), COUNT(DISTINCT worker) FROM findings").fetchone()
        sources = self._conn.execute("SELECT COUNT(*), COUNT(DISTINCT url) FROM sources").fetchone()
        return {
            "total_findings": findings[0],
            "workers_with_findings": findings[1],
            "total_sources": sources[0],
            "unique_urls": sources[1],
        }

    def close(self):
        self._conn.close()
