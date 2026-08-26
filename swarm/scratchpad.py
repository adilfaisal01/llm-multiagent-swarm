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
import time
import urllib.parse

# Query params that are pure tracking noise — stripped during URL normalization.
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "gclsrc", "dclid", "msclkid", "mc_cid", "mc_eid",
    "igshid", "ref_src", "ref_url", "spm", "sca_esv", "srsltid", "yclid",
}

# Default credibility weights (overridable via config `credible_domains`).
_DEFAULT_CREDIBLE_DOMAINS = (".gov", ".edu", ".mil")

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
                url_normalized TEXT NOT NULL UNIQUE,
                domain TEXT DEFAULT '',
                title TEXT DEFAULT '',
                snippet TEXT DEFAULT '',
                credibility REAL DEFAULT 0.5,
                corroboration INTEGER DEFAULT 1,
                first_seen TEXT DEFAULT (datetime('now')),
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
        """Log a source URL the agent scraped.

        URLs are normalized (fragment stripped, tracking params removed,
        host lowercased) and deduplicated: logging the same URL again bumps
        its corroboration count instead of inserting a duplicate row.
        """
        norm = normalize_url(url)
        domain = extract_domain(url)
        self._conn.execute(
            """
            INSERT INTO sources (worker, url, url_normalized, domain, title, snippet)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(url_normalized) DO UPDATE SET
                corroboration = corroboration + 1,
                timestamp = datetime('now')
            """,
            (worker, url, norm, domain, title, snippet[:500]),
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

    def findings_for_source(self, url: str) -> list:
        """Return findings associated with a source URL (normalized match)."""
        norm = normalize_url(url)
        return self._conn.execute(
            "SELECT worker, finding, category, confidence FROM findings WHERE source_url = ? ORDER BY id",
            (url,),
        ).fetchall()

    def top_sources(self, limit: int = 20, min_credibility: float = 0.0,
                    credible_domains: tuple = _DEFAULT_CREDIBLE_DOMAINS) -> list:
        """Return deduplicated sources ranked by credibility.

        Only the orchestrator calls this. Each row is a dict:
            {url, domain, title, snippet, credibility, corroboration, first_seen}
        """
        rows = self._conn.execute(
            """
            SELECT url, domain, title, snippet, credibility, corroboration, first_seen
            FROM sources
            ORDER BY credibility DESC, corroboration DESC, id
            """
        ).fetchall()
        out = []
        for url, domain, title, snippet, cred, corrob, first_seen in rows:
            if cred < min_credibility:
                continue
            out.append({
                "url": url,
                "domain": domain,
                "title": title,
                "snippet": snippet,
                "credibility": round(cred, 3),
                "corroboration": corrob,
                "first_seen": first_seen,
            })
            if len(out) >= limit:
                break
        return out

    def score_sources(self, credible_domains: tuple = _DEFAULT_CREDIBLE_DOMAINS):
        """Recompute credibility for every source row in place.

        Called by the orchestrator after all workers finish, so scores
        reflect final corroboration counts and recency.
        """
        rows = self._conn.execute(
            "SELECT id, url, domain, corroboration, first_seen FROM sources"
        ).fetchall()
        for sid, url, domain, corrob, first_seen in rows:
            cred = score_source(url, domain=domain, corroboration=corrob,
                                first_seen=first_seen, credible_domains=credible_domains)
            self._conn.execute(
                "UPDATE sources SET credibility = ? WHERE id = ?", (cred, sid)
            )
        self._conn.commit()

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
        """Close the underlying SQLite connection."""
        self._conn.close()


def normalize_url(url: str) -> str:
    """Normalize a URL for dedup: lowercase host, strip fragment + tracking params.

    Keeps the scheme and path so distinct pages on the same host stay distinct.
    """
    try:
        parsed = urllib.parse.urlparse(url.strip())
        if not parsed.scheme or not parsed.netloc:
            return url.strip()
        host = parsed.netloc.lower()
        query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        kept = [(k, v) for k, v in query if k.lower() not in _TRACKING_PARAMS]
        clean_query = urllib.parse.urlencode(kept)
        return urllib.parse.urlunparse((
            parsed.scheme, host, parsed.path, parsed.params, clean_query, ""
        ))
    except Exception:
        return url.strip()


def extract_domain(url: str) -> str:
    """Return the registrable-ish host of a URL (e.g. 'en.wikipedia.org')."""
    try:
        parsed = urllib.parse.urlparse(url.strip())
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host
    except Exception:
        return ""


def _domain_credibility(domain: str, credible_domains: tuple) -> float:
    """Domain authority boost: 1.0 for allowlisted suffixes, 0.5 otherwise."""
    if not domain:
        return 0.5
    for suffix in credible_domains:
        if domain == suffix or domain.endswith(suffix):
            return 1.0
    return 0.5


def _recency_credibility(first_seen: str) -> float:
    """Recency decay based on when the source was first logged."""
    if not first_seen:
        return 0.5
    try:
        # first_seen is stored as 'YYYY-MM-DD HH:MM:SS' (UTC from SQLite).
        seen = time.mktime(time.strptime(first_seen, "%Y-%m-%d %H:%M:%S"))
    except (ValueError, TypeError):
        return 0.5
    age_days = (time.time() - seen) / 86400.0
    if age_days <= 90:
        return 1.0
    if age_days <= 365:
        return 0.8
    return 0.6


def score_source(url: str, *, domain: str = "", corroboration: int = 1,
                 first_seen: str = "", credible_domains: tuple = _DEFAULT_CREDIBLE_DOMAINS) -> float:
    """Heuristic credibility score in [0, 1].

    Combines domain authority, recency, and corroboration (how many workers
    independently hit the same URL). Pure stdlib — no external scoring API.
    """
    dom = domain or extract_domain(url)
    domain_cred = _domain_credibility(dom, credible_domains)
    recency_cred = _recency_credibility(first_seen)
    corrob_cred = min(1.0, 0.5 + 0.1 * max(0, corroboration - 1))
    return round(0.5 * domain_cred + 0.3 * recency_cred + 0.2 * corrob_cred, 3)
