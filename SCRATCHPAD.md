# Scratchpad — Write-Only RAM Data Collection for the Swarm

## Concept

The scratchpad is a **write-only SQLite database in RAM** (`:memory:`) that agents use to dump raw findings during research. Agents **never read** from it — only the orchestrator reads after all agents finish. This prevents context pollution while giving the orchestrator a complete picture of all raw data collected.

## Why Write-Only?

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

## How Data Gets In

### 1. Auto-log on `web_search` (automatic)

Every time an agent calls `web_search`, the scratchpad automatically logs:

```python
# In execute_tool():
_SCRATCHPAD.add_finding(worker_name, f"Search: {query}", "", "search", "high")
# Plus each result URL + snippet is logged as a source
_SCRATCHPAD.add_source(worker_name, url, snippet, snippet)
```

The agent only sees the search results — it has no idea the scratchpad was updated.

### 2. Auto-log on `web_extract` (automatic)

Every time an agent extracts a URL, the scratchpad logs:

```python
_SCRATCHPAD.add_source(worker_name, url, url, result[:200])
_SCRATCHPAD.add_finding(worker_name, f"Extracted: {url}", url, "extract", "medium")
```

### 3. Manual `scratchpad_add` (agent-initiated)

Agents can also call `scratchpad_add` directly to log specific facts:

```json
{
    "finding": "RSA-2048 can be broken with 4096 logical qubits",
    "source_url": "https://example.com/quantum-crypto",
    "category": "technical",
    "confidence": "high"
}
```

Returns: `"[Scratchpad: saved finding (technical, high)]"`

## How Data Gets Out

After **all agents finish**, the orchestrator reads the scratchpad:

```python
# In orchestrate(), after ThreadPoolExecutor.as_completed():
scratch_summary = _SCRATCHPAD.get_summary()      # counts
scratch_findings = _SCRATCHPAD.get_all_findings()  # all rows
scratch_sources = _SCRATCHPAD.get_all_sources()     # all sources
_SCRATCHPAD.close()  # 💥 DB destroyed
```

The data is now in Python dicts — the `:memory:` database is gone.

## Lifecycle

```
orchestrate() starts
    │
    ├── Scratchpad() created  ──►  :memory: SQLite
    │
    ├── ThreadPoolExecutor spawns workers
    │       │
    │       ├── Vera  ──► web_search() ──► auto-log to scratchpad
    │       ├── Cyrus ──► web_search() ──► auto-log to scratchpad
    │       ├── Romy  ──► scratchpad_add() ──► manual log
    │       ├── Ash   ──► web_extract() ──► auto-log to scratchpad
    │       └── Zara  ──► web_search() ──► auto-log to scratchpad
    │
    ├── All workers join
    │
    ├── Orchestrator reads scratchpad
    │       ├── get_all_findings()  ──► list of tuples
    │       ├── get_all_sources()   ──► list of tuples
    │       └── get_summary()       ──► dict of counts
    │
    ├── close()  ──► 💥 DB destroyed (no temp files)
    │
    └── main() writes .md file using extracted data
```

## Thread Safety

- `check_same_thread=False` allows the connection to be shared across `ThreadPoolExecutor` workers
- SQLite's internal locking serializes concurrent writes — fine for this use case
- No read/write contention: agents only write, orchestrator only reads after all writes complete

## Output in Markdown

The saved `.md` file includes two scratchpad sections at the bottom:

### 📋 Scratchpad Findings

| Worker | Category | Finding | Source |
|--------|----------|---------|--------|
| Vera | search | Search: history of Paris origins | - |
| Cyrus | money | Paris contributes €700bn to GDP | - |
| Romy | timeline | Paris has been capital since 987 AD | - |
| Ash | controversy | Centralization debate "Paris et le désert" | - |
| Zara | extract | Extracted: en.wikipedia.org/wiki/Paris | URL |

### 🔗 Sources Collected

- [Wikipedia: Paris](https://en.wikipedia.org/wiki/Paris) — Vera
- [INSEE Economic Report](https://example.com) — Cyrus

## Key Properties

- **No temp files** — `:memory:` database, destroyed on `close()`
- **No context pollution** — agents never see other agents' data
- **No race conditions** — orchestrator reads after all agents finish
- **Zero dependencies** — Python stdlib `sqlite3` only
- **Auto-logging** — every search and extract is captured automatically
- **Manual logging** — agents can also call `scratchpad_add` for specific facts
