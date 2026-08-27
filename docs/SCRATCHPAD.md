# Scratchpad — Write-Only RAM Data Collection

## Concept

The scratchpad is a **write-only SQLite database in RAM** (`:memory:`) that
agents use to dump raw findings during research. Agents **never read** from it —
only the orchestrator reads after all agents finish. This prevents context
pollution while giving the orchestrator a complete picture of all raw data
collected.

## Why write-only?

| Approach | Problem |
|----------|---------|
| Agents read each other's work | Context pollution — agent A's conclusions bias agent B's research |
| Agents write to a shared file | Race conditions, partial reads, file locking |
| No shared state at all | Orchestrator has no visibility into what agents found |
| **Write-only scratchpad** ✅ | **Agents stay independent, orchestrator gets full picture** |

## Schema

```sql
-- Raw findings dumped by agents
CREATE TABLE findings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    worker      TEXT NOT NULL,        -- Vera, Cyrus, Romy, Ash, Zara
    source_url  TEXT,                 -- where the fact came from
    finding     TEXT NOT NULL,        -- the raw fact, quote, or number
    category    TEXT DEFAULT 'general', -- search | extract | timeline | money
                                      -- | players | impact | technical
                                      -- | controversy | general
    confidence  TEXT DEFAULT 'medium', -- high | medium | low
    timestamp   TEXT DEFAULT (datetime('now'))
);

-- Sources collected (URLs + snippets)
CREATE TABLE sources (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    worker      TEXT NOT NULL,
    url         TEXT NOT NULL,
    title       TEXT DEFAULT '',
    snippet     TEXT DEFAULT '',
    timestamp   TEXT DEFAULT (datetime('now'))
);
```

## How data gets in

### 1. Auto-log on `web_search` (automatic)

Every `web_search` call automatically logs the query plus each result URL +
snippet as a source. The agent only sees the search results — it has no idea the
scratchpad was updated.

### 2. Auto-log on `web_extract` (automatic)

Every `web_extract` call automatically logs the URL, a snippet of the content,
and an "extracted" finding.

### 3. Manual `scratchpad_add` (agent-initiated)

Agents can also call `scratchpad_add` to log specific facts:

```json
{
    "finding": "RSA-2048 can be broken with 4096 logical qubits",
    "source_url": "https://example.com/quantum-crypto",
    "category": "technical",
    "confidence": "high"
}
```

Returns: `"[Scratchpad: saved finding (technical, high)]"`.

## How data gets out

After **all agents finish**, the orchestrator reads the scratchpad:

- `get_summary()` — counts
- `get_all_findings()` — all rows
- `get_all_sources()` — all sources
- `close()` — destroys the `:memory:` database

The data is now in Python dicts; the database is gone (no temp files).

## Thread safety

- `check_same_thread=False` allows the connection to be shared across
  `ThreadPoolExecutor` workers
- `isolation_level=None` prevents "cannot commit - no transaction is active"
  errors with concurrent workers
- SQLite's internal locking serializes concurrent writes
- No read/write contention: agents only write, orchestrator reads after all
  writes complete

## Source dedup + credibility scoring

Sources are **deduplicated** (URLs normalized: fragment stripped, tracking
params removed, host lowercased) and **scored** on a 0–1 credibility scale
combining domain authority (`.gov`/`.edu`/`.mil` boosted), recency, and
corroboration (how many workers independently hit the same URL). The
orchestrator ranks sources by credibility and feeds the top 20 to synthesis.

## AI-based probabilistic credibility

Credibility is refined by an **LLM judge** into a Bayesian posterior
(`swarm/credibility.py`). The heuristic score becomes a **prior**; the judge
estimates each source's credibility probability plus its own confidence;
confidence-weighted **log-odds pooling** combines them into a **posterior**.
If the judge call fails, the prior is kept — output is never worse than the
heuristic baseline. Each `top_sources` entry gains `credibility_prior`,
`llm_probability`, `llm_confidence`, and `credibility_reason`; the result dict
gains a `credibility` map. Disable with `run_swarm(..., ai_credibility=False)`.

## Inline citations

Synthesis produces **inline `[N]` citations**: the model is given a numbered,
credibility-ranked source list and asked to cite claims with `[N]` markers. A
post-processor validates the markers, drops any that don't resolve to a real
source, and appends a numbered `## Sources` section. If the model emits no
markers, the prose is kept as-is and sources are still listed — output is never
worse than before. The result dict gains `citations`, `sources_used`, and
`sources_total` keys.

## Output in markdown

The saved `.md` file includes two scratchpad sections at the bottom:

```
### Scratchpad Findings
| Worker | Category | Finding | Source |
|--------|----------|---------|--------|
| Vera   | search   | Search: history of Paris origins | -     |
| Cyrus  | money    | Paris contributes €700bn to GDP | -     |

### Sources Collected
- [Wikipedia: Paris](https://en.wikipedia.org/wiki/Paris) — Vera
- [INSEE Economic Report](https://example.com) — Cyrus
```

## Key properties

- **No temp files** — `:memory:` database, destroyed on `close()`
- **No context pollution** — agents never see other agents' data
- **No race conditions** — orchestrator reads after all agents finish
- **Zero dependencies** — Python stdlib `sqlite3` only
- **Auto-logging** — every search and extract is captured automatically
- **Manual logging** — agents can also call `scratchpad_add` for specific facts
