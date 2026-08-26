# 🐝 Swarm v2

Multi-agent research orchestration using Ollama cloud models. Spawn parallel workers with focused research angles, each with web search access, and collect their outputs via a shared scratchpad.

Core library is pure Python stdlib. The optional persistent TUI requires `textual`. Web search works out of the box via DuckDuckGo (the `ddgs` package, no API key, no self-hosting).

```bash
# Quick start
python3 -m swarm --goal "What's happening with AI regulation in the EU?" --mix

# Persistent TUI with follow-up support
python3 -m swarm --tui
```

## Architecture

```
                         ┌─────────────────────────────────────┐
                         │         YOU (the user)             │
                         │   python3 -m swarm --goal "..."   │
                         └──────────────┬──────────────────────┘
                                        │
                          ┌──────────────▼──────────────────────┐
                          │         ORCHESTRATOR               │
                          │  • Parses --goal, --mix, --config  │
                          │  • Loads swarm_config.json         │
                          │  • Estimates complexity (1-5)      │
                          │  • Preflight: LLM analyzes question│
                          │  • LLM assigns skills+mode         │
                          │  • Spawns workers (parallel|pipeline)│
                          │  • Reads scratchpad after workers  │
                          │  • Destroys scratchpad, saves .md  │
                          └──────┬──────┬──────┬──────┬───────┘
                                 │      │      │      │
          ┌─────────────────────┼──────┼──────┼──────┼─────────────────────┐
          │                     │      │      │      │                     │
          ▼                     ▼      ▼      ▼      ▼                     ▼
   ┌───────────┐        ┌───────────┐ ┌───────────┐ ┌───────────┐  ┌───────────┐
   │   VERA    │        │   CYRUS   │ │   ROMY    │ │   ASH     │  │   ZARA    │
   │ gpt-oss   │        │ nemotron  │ │ gemma4    │ │ deepseek  │  │ gpt-oss   │
   │ 120B      │        │ 30B       │ │ 31B       │ │ ~158B     │  │ 120B      │
   │           │        │           │ │           │ │           │  │           │
   │vision     │        │  code     │ │ default   │ │ search    │  │ files     │
   │ skill     │        │  skill    │ │ skill     │ │ skill     │  │ skill     │
   └─────┬─────┘        └─────┬─────┘ └─────┬─────┘ └─────┬─────┘  └─────┬─────┘
          │                    │             │             │              │
          └──────────┬─────────┘             │             │              │
                     │                       │             │              │
          ┌──────────▼───────────────────────▼─────────────▼──────────────▼──────┐
          │                  MODULAR TOOL REGISTRY                               │
          │                                                                      │
          │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐  │
          │  │  web_search  │ │ web_extract  │ │  read_image  │ │ python_exec│  │
          │  │  (search web)│ │ (read URL)   │ │ (vision OCR) │ │ (run code) │  │
          │  └──────────────┘ └──────────────┘ └──────────────┘ └────────────┘  │
          │                                                                      │
          │  ┌──────────────┐ ┌──────────────┐ ┌─────────────────────────────┐  │
          │  │  read_file   │ │scratchpad_add│ │      SCRATCHPAD (SQLite)    │  │
          │  │(txt/csv/xlsx)│ │ (log finding)│ │  Write-only, auto-logged    │  │
          │  └──────────────┘ └──────────────┘ └─────────────────────────────┘  │
          └──────────────────────────────────────────────────────────────────────┘
                                        │
                         ┌──────────────▼──────────────────────┐
                         │         OUTPUT                      │
                         │  • Auto-saved to .md file          │
                         │  • Per-worker sections + stats     │
                         │  • Scratchpad findings table       │
                         │  • Source URL list                  │
                         │  • JSON (--json flag)             │
                         │  • Orchestrator synthesis           │
                         └─────────────────────────────────────┘
```

Each worker is an independent Ollama model with a **skill** assigned by the preflight LLM. The orchestrator analyzes the question, determines what tools are needed, and gives each worker tailored capabilities. Workers can search the web, read files, analyze images, and run Python code — all in parallel via `ThreadPoolExecutor` or sequentially in pipeline mode when dependencies exist. Every tool call result is automatically logged to the scratchpad. The orchestrator collects everything, optionally synthesizes the findings, and saves the full output to a timestamped `.md` file.

## Quick start

```bash
# Install (required only for the TUI; core library is stdlib)
pip install -e .

# Make sure Ollama is running
ollama serve

# Pull cloud models
ollama pull gpt-oss:120b-cloud
ollama pull deepseek-v4-flash:cloud
ollama pull gemma4:31b-cloud
ollama pull nemotron-3-nano:30b-cloud

# Fire the swarm
python3 -m swarm --goal "Your research question" --mix

# Auto-estimate worker count based on query complexity
python3 -m swarm --goal "Your question" --auto --mix

# Uniform mode (all workers use the same model)
python3 -m swarm --goal "Your question" --model qwen --workers 3

# JSON output for programmatic use
python3 -m swarm --goal "Your question" --mix --json

# Use a named skill (loads its team.json if it ships one)
python3 -m swarm --skill research --goal "Your research question"
python3 -m swarm --skill reverse-engineering --goal "Reverse engineer this payload at /path/to/payload.js"

# Persistent TUI with session history and follow-ups
python3 -m swarm --tui

# Demo version (original pre-modular research script)
python3 -m demo-swarm --goal "Your question" --mix
```

## Releases

Releases are cut with git tags (`v*`). Bump the version, commit, tag, and push in one command:

```bash
make release KIND=patch   # 2.0.0 -> 2.0.1 (bug fixes)
make release KIND=minor   # 2.0.0 -> 2.1.0 (new features)
make release KIND=major   # 2.0.0 -> 3.0.0 (breaking changes)
```

Pushing a `v*` tag triggers a GitHub Actions workflow that generates `CHANGELOG.md`
from the git log, commits it back to `main`, and publishes a GitHub Release.
Full guide: `docs/RELEASE.md`.

## Complexity estimation (`--auto`)

When `--auto` is set, the orchestrator model (DeepSeek V4 Flash) reads the query and rates its complexity 1-5 before spawning workers:

| Rating | Meaning | Example | Workers |
|--------|---------|---------|---------|
| 1 | Simple fact lookup | "What is the capital of France?" | 1 |
| 2 | Straightforward explanation | "Explain REST vs GraphQL" | 2 |
| 3 | Multi-faceted topic | "Impact of quantum computing on cryptography" | 3 |
| 4 | Complex with controversy | "Is the industrial revolution a disaster for humanity?" | 4 |
| 5 | Deep philosophical/scientific | "Philosophical implications of AI consciousness" | 5 |

Falls back to returning 3 (safe default) if the LLM call fails.

## Scratchpad

The scratchpad is a write-only RAM SQLite database that workers use to log raw findings:

- **Auto-logged**: Every `web_search` and `web_extract` result is automatically saved
- **Manual logging**: Workers can call `scratchpad_add()` for custom facts, quotes, numbers
- **Write-only**: Workers never read the scratchpad — no context pollution between agents
- **Orchestrator reads**: After all workers finish, the orchestrator reads the scratchpad and includes a findings table + source list in the output
- **Auto-destroyed**: The `:memory:` database is closed after the `.md` file is saved

Schema:
- `findings(worker, source_url, finding, category, confidence, timestamp)`
- `sources(worker, url, url_normalized, domain, title, snippet, credibility, corroboration, first_seen, timestamp)`

### Source dedup + credibility scoring

Sources are **deduplicated** (URLs normalized: fragment stripped, tracking
params removed, host lowercased) and **scored** on a 0–1 credibility scale
combining domain authority (`.gov`/`.edu`/`.mil` boosted), recency, and
corroboration (how many workers independently hit the same URL). The
orchestrator ranks sources by credibility and feeds the top 20 to synthesis.

### AI-based probabilistic credibility

Credibility is refined by an **LLM judge** into a Bayesian posterior. The
heuristic score becomes a **prior**; the judge estimates each source's
credibility probability + its own confidence; confidence-weighted **log-odds
pooling** combines them into a **posterior**. If the judge call fails, the
prior is kept — output is never worse than the heuristic baseline. Each
`top_sources` entry gains `credibility_prior`, `llm_probability`,
`llm_confidence`, and `credibility_reason`; the result dict gains a
`credibility` map. Disable with `run_swarm(..., ai_credibility=False)`.

### Inline citations

Synthesis now produces **inline `[N]` citations**: the model is given a
numbered, credibility-ranked source list and asked to cite claims with `[N]`
markers. A post-processor validates the markers, drops any that don't resolve
to a real source, and appends a numbered `## Sources` section. If the model
emits no markers, the prose is kept as-is and sources are still listed — output
is never worse than before. The result dict gains `citations`,
`sources_used`, and `sources_total` keys.

## Modular Tool System

The swarm uses a plugin-style tool registry in `swarm/tools/`. Each tool is a self-contained module extending `BaseTool`. Adding a new tool is just: create a file, extend `BaseTool`, register it in `__init__.py`.

### Available tools

| Tool | Description | Used by skills |
|------|-------------|----------------|
| `web_search` | Search the web (DuckDuckGo/SearXNG/Google) | all |
| `web_extract` | Read content from a URL | all |
| `scratchpad_add` | Log raw findings to the shared scratchpad | all |
| `read_image` | Read text/numbers from images via Gemma4 vision | vision, files, all |
| `read_file` | Read .txt, .csv, .json, .xml, .xlsx files | files, all |
| `python_exec` | Execute Python code for calculations/processing | code, all |
| `wikipedia_search` | Search Wikipedia for encyclopedic facts | search, default, all |
| `arxiv_search` | Search arXiv for academic papers | research, all |
| `github_search` | Search GitHub repos/issues/code | code, research, all |
| `wayback_machine` | Find archived snapshots of URLs | search, research, all |
| `http_request` | Generic REST API client (weather, exchange rates, etc.) | research, code, all |
| `pdf_extract` | Extract text from PDF files (optional `pdf` extra) | files, all |
| `sql_query` | Run read-only SQL against a local SQLite DB | files, code, all |
| `regex_extract` | Extract structured data from text via regex | files, code, all |
| `text_diff` | Unified diff between two texts | files, code, all |
| `date_calculator` | Date arithmetic: days between, weekday, age | code, research, all |

The full catalog (including new tools added incrementally) lives in
[`docs/TOOLS.md`](docs/TOOLS.md). The full skill catalog lives in
[`docs/SKILLS.md`](docs/SKILLS.md).

### Skills (capability packs)

Skills live in `swarm/skills/<name>/SKILL.md` and are the single source of truth for what a worker can do. Each skill declares its tool list, behavior rules (the markdown body), and optional team config in YAML frontmatter. Skills reference tools **by name** — all tool implementations live in `swarm/tools/`.

```markdown
---
name: vision
description: "Has read_image tool — use for questions with image attachments (.png/.jpg)."
triggers: [image, png, jpg, screenshot]
tools: [read_image, web_search, web_extract, scratchpad_add]
recommended_model: gemma4:31b-cloud
---

CRITICAL INSTRUCTIONS — FOLLOW THESE EXACTLY:
1. CALL read_image NOW with the ATTACHED FILE path.
...
```

| Skill | Tools | When assigned |
|-------|-------|--------------|
| `default` | web_search, web_extract, scratchpad_add | Fallback when no more specific skill fits |
| `research` | web_search, web_extract, scratchpad_add | Open-ended multi-perspective research (ships a 5-worker team) |
| `search` | web_search, web_extract | Simple fact lookups (no scratchpad) |
| `vision` | read_image, web_search, web_extract, scratchpad_add | Questions with image attachments (.png/.jpg) |
| `code` | python_exec, web_search, web_extract, scratchpad_add | Questions needing computation ("calculate", "average") |
| `files` | read_file, read_image, web_search, web_extract, scratchpad_add | Questions with attached data files (.xlsx/.csv/.docx) |
| `reverse-engineering` | python_exec, web_search, web_extract, read_file, read_image, scratchpad_add | Obfuscated payload analysis (ships a 5-worker team) |
| `fact-check` | web_search, web_extract, scratchpad_add | Verifying claims / debunking (ships a 5-worker team) |
| `code-debug` | python_exec, read_file, web_search, web_extract, scratchpad_add | Debugging code, tracing errors, fixing bugs |
| `multi-hop` | web_search, web_extract, scratchpad_add | Chaining facts across sources (pipeline mode) |
| `comparison` | web_search, web_extract, scratchpad_add | Comparing products/tools/options side-by-side |
| `academic` | wikipedia_search, arxiv_search, web_search, web_extract, pdf_extract, scratchpad_add | Academic literature / papers / methodology (ships a 5-worker team) |
| `legal` | web_search, web_extract, wayback_machine, scratchpad_add | Laws, statutes, court cases (ships a 5-worker team) |
| `medical` | wikipedia_search, arxiv_search, web_search, web_extract, scratchpad_add | Health, treatments, drugs (ships a 5-worker team) |
| `finance` | web_search, web_extract, http_request, sql_query, scratchpad_add | Companies, markets, financials (ships a 5-worker team) |
| `data-analysis` | read_file, sql_query, python_exec, regex_extract, scratchpad_add | Analyzing data files / statistics (pipeline mode, ships a 5-worker team) |
| `summarize` | read_file, pdf_extract, web_extract, python_exec, scratchpad_add | Summarizing documents/PDFs/URLs (ships a 5-worker team) |

**Full-pack skills** (`research`, `reverse-engineering`, `fact-check`, `academic`, `legal`, `medical`, `finance`, `data-analysis`, `summarize`) ship a `team.json` with named workers, models, and angles. Run them with `--skill <name>`:

```bash
python3 -m swarm --skill research --goal "Your research question"
python3 -m swarm --skill reverse-engineering --goal "Reverse engineer this payload at /path/to/payload.js"
python3 -m swarm --skill fact-check --goal "Is it true that [claim]?"
python3 -m swarm --skill academic --goal "What does the literature say about [topic]?"
python3 -m swarm --skill legal --goal "What are the rules on [legal topic]?"
python3 -m swarm --skill medical --goal "What is the evidence for [treatment]?"
python3 -m swarm --skill finance --goal "Analyze the financial health of [company]"
python3 -m swarm --skill data-analysis --goal "Analyze sales.csv: average revenue per region"
python3 -m swarm --skill summarize --goal "Summarize the key points of /path/to/report.pdf"
```

**Customizing a skill:** edit its `team.json` (workers/models/angles/prompts) or copy the folder to `swarm/skills/research-<topic>/`, update the `name` field in `SKILL.md`, and run with `--skill research-<topic>`. No code changes needed.

**Hermes compatibility:** every `SKILL.md` uses YAML `---` frontmatter with Hermes-style fields (`name`, `description`, `version`, `tags`, `trigger`, `related_skills`, `platforms`) and a `## Running under Hermes` section. Hermes users can read any skill natively, copy a folder into `~/.hermes/skills/`, or adapt the documented workflow to `delegate_task`.

### Preflight question analysis

Before spawning workers, the orchestrator runs a **preflight** pass using the orchestrator model (DeepSeek V4 Flash):

1. **Classifies answer type**: number, name, phrase, date, or other
2. **Assigns skills via LLM**: The model reasons about what tools each worker needs and assigns the right skill (`vision` for images, `code` for calculations, `files` for spreadsheets, etc.)
3. **Decides execution mode**: Outputs `parallel` or `pipeline` based on whether workers have sequential dependencies
4. **Generates search strategies**: Each worker gets a specific, actionable plan tailored to the question
5. **Injects file paths**: For file-based questions, the file path is injected into the worker prompt — workers are aggressively prompted to use their tools to read it (never guess)

The key difference from the old system: **the LLM decides, not hardcoded rules**. No more preload hack where data was dumped into prompts — workers now use their tools properly.

### Pipeline mode

For questions where workers have sequential dependencies, the preflight LLM can set `mode: pipeline`:

```
Mode: pipeline 🔗
  Worker 0: vision (reads image, extracts numbers)
  Worker 1: code (depends_on: 0) — takes numbers and computes
  Worker 2: code (depends_on: 1) — verifies the computation
```

In pipeline mode:
- Workers execute in dependency order
- Each worker's output is injected into the next dependent worker's prompt
- Non-dependent workers still run in parallel

## Configuration

All config is via environment variables or a JSON config file (`swarm_config.json` by default, or set via `SWARM_CONFIG` env var or `--config` flag).

### Env vars

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `SEARCH_BACKEND` | `ddgs` | Search engine: `ddgs`, `searxng`, or `google` |
| `SEARXNG_URL` | `http://localhost:8080` | SearXNG endpoint (only for `searxng` backend) |
| `SEARCH_API_KEY` | `""` | API key (required for `google` backend) |
| `GOOGLE_CX` | `""` | Google Custom Search CX ID (only for `google` backend) |
| `SEARCH_TIMEOUT` | `15` | Timeout for search/extract calls in seconds |
| `SWARM_CONFIG` | `swarm_config.json` | Path to JSON config file |
| `SWARM_CACHE` | `1` | Set to `0` to disable the search/extract result cache |
| `SWARM_CACHE_DIR` | `~/.cache/swarm` | Directory for the SQLite result cache |
| `SWARM_CACHE_TTL` | `86400` | Cache TTL in seconds |
| `SWARM_CACHE_MAX_ROWS` | `10000` | Max cached rows before the oldest are swept |

### Streaming, retry, cache, and cost

- **Streaming**: `run_swarm()` accepts a `stream_callback(chunk, phase)` hook
  (`phase` is `"preflight"` or `"synthesis"`). When provided, preflight and
  synthesis tokens stream through it. Worker turns stay non-streaming.
- **Retry/backoff**: all Ollama calls go through `swarm/llm.py` with up to 3
  attempts, exponential backoff + jitter, no retry on 4xx (except 429, which
  honors `Retry-After`).
- **Result cache**: `web_search` and `web_extract` results are cached in
  SQLite keyed on `backend|query`, transparent to workers (a cache hit still
  logs to the scratchpad).
- **Cost accounting**: the result dict gains a `cost` key
  (`prompt_tokens`, `completion_tokens`, `total_tokens`, `seconds`, `calls`,
  `estimated_cost_usd`). Cost rates are opt-in via the `model_costs` config
  field — until populated, `estimated_cost_usd` stays 0.

### MCP server

The swarm ships an optional **Model Context Protocol** server
(`swarm/integrations/mcp/`) exposing `swarm_research` as a single tool, so
Claude Desktop, Cursor, opencode, or any MCP client can run a full research
swarm. Install with `pip install -e ".[mcp]"`, run with `swarm-mcp` (or
`python3 -m swarm.integrations.mcp`). Full guide: `docs/MCP.md`.

### Search backends

| Backend | Auth needed | Notes |
|---------|-------------|-------|
| `ddgs` | No | **Default.** DuckDuckGo via the `ddgs` package (installed by default). No API key, no setup. Rate limits may apply. |
| `searxng` | No (self-hosted) | Point `SEARXNG_URL` at your instance. |
| `google` | `SEARCH_API_KEY` + `GOOGLE_CX` | Google Custom Search JSON API. 100 free queries/day. |

### JSON config file

The `swarm_config.json` file lets you customize models, team members, prompts, angles, and fallback models. Pass a custom config with `--config my_config.json` or `SWARM_CONFIG=my_config.json`.

A config may also declare a `"skill"` field — the skill's prompt body and tools are used with the JSON's team:

```json
{
  "skill": "research",
  "team": [
    {
      "name": "Agent1",
      "model": "my-model",
      "angle": "Your angle description",
      "prompt": "You are Agent1... MAIN QUESTION: {goal}... YOUR ANGLE: {angle}..."
    }
  ],
  "angles": ["Angle 1", "Angle 2"],
  "fallback_models": ["my-model:latest"]
}
```

See `swarm_config.json` for a full example.

## Available models

| Alias | Model | Size | Speed | Notes |
|-------|-------|------|-------|-------|
| `gpt-oss` | gpt-oss:120b-cloud | 120B | ~2-15s | Reliable, clean output |
| `nemotron` | nemotron-3-nano:30b-cloud | 30B | ~0.5-15s | Fast, production-proven |
| `gemma` | gemma4:31b-cloud | 31B | ~13-30s | Multimodal (reads images), Romy's model |
| `deepseek` | deepseek-v4-flash:cloud | ~158B | ~4-20s | Fast, orchestrator model |
| `ministral` | ministral-3:14b-cloud | 14B | ~4.5-20s | ⚠️ Being retired by Ollama Cloud |
| `nemotron-super` | nemotron-3-super:cloud | 120B | ~1-20s | ⚠️ Buggy — may time out or return empty |

All models route through your local Ollama as a cloud proxy. Pull them with `ollama pull <model>:cloud`.

## The team (--mix mode)

In `--mix` mode, each worker gets a different model and named identity:

| Name | Model | Angle |
|------|-------|-------|
| **Vera** | gpt-oss | Origins & history |
| **Cyrus** | nemotron | Money & players |
| **Romy** | gemma | Implications & future (vision specialist) |
| **Ash** | deepseek | Controversies |
| **Zara** | gpt-oss | Technical details |

```bash
python3 -m swarm --goal "Your question" --mix --config my_team.json
```

## How tool calling works

Ollama's `/api/chat` endpoint supports native function calling. The swarm:

1. **Preflight** analyzes the question via the orchestrator LLM, which assigns tool bundles + execution mode
2. Injects file paths (not file contents) into worker prompts
3. Aggressively prompts workers to use their tools (never guess, never write from memory)
4. Sends prompt + tool definitions (filtered by bundle) to each model
5. Model responds with `tool_calls` (search query, image read, code exec) or content (final answer)
6. Script executes the tool against the configured backend
7. Feeds results back as a `role: "tool"` message
8. Loop repeats up to 5 rounds until the model has enough info to answer

If a model exhausts all tool rounds without producing a final answer, the script:
1. Sends a gentle "synthesize your findings" prompt
2. If that fails, sends an aggressive "STOP SEARCHING. WRITE NOW." prompt
3. If both fail, falls back to re-firing the question at a different model

For **pipeline mode**, workers execute in stages: a vision worker reads an image, then a code worker computes from the extracted data. Previous worker output is injected into downstream workers' prompts.

### Testing

The Makefile is the canonical entry point. All `test-*` targets accept a verbosity flag: default is quiet (compact one-liner per module), `V=1` prints the grouped colored summary, `V=2` prints the raw per-test trace. Full guide: `docs/TESTING.md`.

```bash
make test                 # tool smoke + full grouped summary (default)
make test-tool-unit       # hermetic per-tool tests (mocked network/Ollama), quiet
make test-tool-unit V=1   # grouped summary per tool
make test-tools           # live smoke (real ddgs + Ollama)
make test-summary         # all hermetic suites, grouped summary
make test-ci              # mirror GitHub Actions CI exactly
```

Live smoke slice flags (`test_tools.py`):

```bash
python3 test_tools.py                    # Quick tool smoke test
python3 test_tools.py --verbose          # Show full tool outputs
python3 test_tools.py --samples=100      # Bigger test files
python3 test_tools.py --skip-swarm       # Skip full swarm tests (faster)
python3 test_tools.py --skill vision     # Only the tools a skill grants
python3 test_tools.py --tool web_search  # Only one tool
```

The smoke script hits live `ddgs` and Ollama. For hermetic, offline per-tool tests (all network/Ollama calls mocked), run the unittest suite:

```bash
python3 -m unittest tests.test_tools -v   # Per-tool hermetic tests
python3 -m unittest discover tests/       # Full hermetic suite
```

## Performance

Parallel swarm is **3.3-3.4× faster** than sequential execution. See `docs/BENCHMARK.md` for full results.

| Mode | Easy query | Hard query |
|------|-----------|------------|
| Sequential | 150.4s | 264.0s |
| Parallel | 45.6s (3.3×) | 77.3s (3.4×) |

## Demo / Research Version

The original pre-modular swarm is preserved in `demo-swarm/` for reference, testing, and research:

```bash
python3 -m demo-swarm --goal "Your question" --mix
```

| Feature | Demo | Main |
|---------|------|------|
| Tool system | Monolithic `tools.py` | Modular registry |
| Worker angles | Hardcoded (Origins, Money, Future...) | LLM-generated per question |
| Tool bundles | None (all workers = search) | vision/code/files/search/default |
| Execution mode | Parallel only | Parallel or pipeline |
| File attachments | Not supported | Tool-based (workers read files) |
| Preflight | None | LLM analyzes question + assigns bundles |

## CI

A GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push to `main`/`feature/*` and on pull requests:

- Matrix: Python 3.11, 3.12
- Compiles all `swarm/**/*.py`
- Checks core + TUI imports
- Runs `test_tools.py --skip-swarm`
- Runs `python3 -m unittest discover tests/`
- Runs `pytest tests/`

## Auto-Testing on Commit

A **post-commit git hook** runs chaos monkey + benchmark automatically after every commit:

- Results saved to `test-results/<commit-hash>/`
- Files: `chaos_monkey.txt`, `benchmark.txt`, `run.log`
- `test-results/` is gitignored (not committed)
- Stray `swarm_*.md` output files are cleaned up after each run

### Install hooks

```bash
bash setup-hooks.sh
```

This symlinks `.githooks/post-commit` into `.git/hooks/`. Run once after cloning.

### Manual run

```bash
bash .githooks/post-commit   # re-run tests for the latest commit
```

## Requirements

- Python 3.11+ (stdlib for the core library)
- `textual>=0.70.0` for the optional TUI (`pip install -e .`)
- Ollama running at `OLLAMA_HOST` (default: localhost:11434)
- Cloud models pulled via `ollama pull <model>:cloud`
- No SearXNG needed — DuckDuckGo is the default backend and works out of the box
- Optional: SearXNG instance at `SEARXNG_URL` for higher rate limits

## Persistent TUI

Run with `python3 -m swarm --tui`:

- Three-pane layout: sessions sidebar, chat + worker dashboard, live sources panel
- Each worker shows a hybrid progress bar (fills per tool round, capped at 5)
- Sources panel shows worker name + tool + query/URL as research happens
- Markdown is auto-saved to `swarm_outputs/` after every completed run
- Follow-up questions inject the previous run's synthesis + top scratchpad findings
- Preflight auto-detects research mode (`objective` vs `subjective`) and adapts synthesis style:
  - **Objective** mode aims for a clear factual answer
  - **Subjective** mode maps perspectives, attributes claims, and flags contradictions
- `Ctrl+N` new session, `Ctrl+S` re-save, `Ctrl+Q` quit

## Files

```
├── swarm/                 # Modular package
│   ├── __init__.py        # Public API: from swarm import run_swarm
│   ├── __main__.py        # CLI entry point (thin wrapper)
│   ├── runner.py          # Library entry point: run_swarm()
│   ├── orchestrator.py    # Spawns workers, manages scratchpad
│   ├── preflight.py       # LLM-based question analysis + skill assignment
│   ├── worker.py          # Worker agent loop with tool access
│   ├── scratchpad.py      # Write-only RAM SQLite scratchpad
│   ├── search.py          # Search backends (SearXNG, DDG, Google)
│   ├── synthesis.py       # Orchestrator synthesis (boss reads the room)
│   ├── llm.py             # Shared Ollama helper: retry/backoff, streaming, cost
│   ├── credibility.py     # AI-based probabilistic source credibility (Bayesian)
│   ├── cache.py           # SQLite search/extract result cache
│   ├── config.py          # Config loader + defaults
│   ├── complexity.py      # Model-based complexity estimation
│   ├── output.py          # Output formatting + markdown saving
│   ├── skills/            # Skill system (capability packs)
│   │   ├── __init__.py    # SkillRegistry, get_skill_registry()
│   │   ├── _base.py       # Skill dataclass + registry + YAML parser
│   │   ├── default/SKILL.md
│   │   ├── research/      # Full pack: SKILL.md + team.json
│   │   ├── search/SKILL.md
│   │   ├── vision/SKILL.md
│   │   ├── code/SKILL.md
│   │   ├── code-debug/SKILL.md
│   │   ├── files/SKILL.md
│   │   ├── fact-check/    # Full pack: SKILL.md + team.json
│   │   ├── multi-hop/SKILL.md
│   │   ├── comparison/SKILL.md
│   │   ├── academic/      # Full pack: SKILL.md + team.json
│   │   ├── legal/         # Full pack: SKILL.md + team.json
│   │   ├── medical/       # Full pack: SKILL.md + team.json
│   │   ├── finance/       # Full pack: SKILL.md + team.json
│   │   ├── data-analysis/ # Full pack: SKILL.md + team.json (pipeline)
│   │   ├── summarize/     # Full pack: SKILL.md + team.json
│   │   └── reverse-engineering/  # Full pack: SKILL.md + team.json
│   ├── integrations/      # External harness adapters
│   │   └── mcp/           # MCP server: swarm_research tool (optional extra)
│   ├── tools/             # Modular tool registry
│   │   ├── __init__.py    # Registry: get_registry(), reset_registry()
│   │   ├── base.py        # BaseTool abstract class
│   │   ├── registry.py    # ToolRegistry: discover, register, skill delegation
│   │   ├── web_search.py  # Search the web
│   │   ├── web_extract.py # Read content from URLs
│   │   ├── scratchpad.py  # Log findings tool
│   │   ├── vision.py      # Read images via Gemma4
│   │   ├── python_exec.py # Execute Python code
│   │   ├── file_reader.py # Read .txt/.csv/.json/.xlsx
│   │   ├── wikipedia_search.py # Search Wikipedia for encyclopedic facts
│   │   ├── arxiv_search.py # Search arXiv for academic papers
│   │   ├── github_search.py # Search GitHub repos/issues/code
│   │   ├── wayback_machine.py # Find archived snapshots of URLs
│   │   ├── http_request.py # Generic REST API client
│   │   ├── pdf_extract.py # Read PDFs (optional pdf extra)
│   │   ├── sql_query.py # Run read-only SQL against a local DB
│   │   ├── regex_extract.py # Extract structured data from text
│   │   ├── text_diff.py # Unified diff between two texts
│   │   └── date_calculator.py # Date arithmetic (days between, weekday, age)
│   ├── prompts/           # External markdown prompt templates
│   │   ├── __init__.py    # load_prompt() and render_prompt()
│   │   ├── preflight.md   # Preflight JSON-generation prompt
│   │   ├── worker.md      # Worker system prompt template
│   │   ├── synthesis.md   # Synthesis prompt template
│   │   ├── mode_*.md      # Objective / subjective mode instructions
│   │   └── fallback_*.md  # Fallback model prompts
│   └── tui/               # Optional persistent Textual TUI
│       ├── __init__.py    # Exports run_tui, Session, SessionStore
│       ├── app.py         # Main Textual app + event loop
│       ├── session.py     # In-memory session model + follow-up context
│       ├── store.py       # SQLite persistence for sessions/results
│       └── widgets.py     # ChatLog, WorkerGrid, SessionList, InputBar
├── cybersec-test/         # Reverse-engineering demo wrapper
│   ├── README.md          # Demo documentation
│   ├── run-re-demo.sh     # One-shot demo script (--skill reverse-engineering)
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── samples/           # Obfuscated payload samples
├── demo-swarm/            # Original research version (demo)
│   ├── __init__.py
│   ├── __main__.py
│   ├── runner.py
│   ├── orchestrator.py
│   ├── worker.py
│   ├── scratchpad.py
│   ├── search.py
│   ├── synthesis.py
│   ├── config.py
│   ├── complexity.py
│   ├── output.py
│   └── tools.py           # Monolithic tool file (pre-modular)
├── test_tools.py            # Tool smoke test (random files, all tool paths)
├── legacy/                  # Pre-modular monoliths (preserved for reference)
│   ├── swarm2.py            # Legacy monolith (pre-demo, single-file swarm)
│   └── swarm.py             # Minimal version (no web search)
├── docs/                    # Documentation
│   ├── TESTING.md           # Testing workflow (make targets + verbosity flag)
│   ├── BENCHMARK.md         # Benchmark results
│   ├── TOOLS.md             # Tool catalog
│   ├── SKILLS.md            # Skill catalog
│   └── RELEASE.md           # Release process (tags, versions, CHANGELOG)
├── scripts/                 # Helper scripts
│   └── gen_changelog.py     # Auto-generates CHANGELOG.md from git log
├── CHANGELOG.md             # Auto-generated release changelog (do not hand-edit)
├── swarm_config.json        # Configurable team, models, prompts
├── gaia_eval.py             # GAIA benchmark eval harness
├── SCRATCHPAD.md            # Scratchpad architecture docs
├── benchmark.py             # Benchmark script (library-based)
├── benchmark_hard.py        # Hard query benchmark (library-based)
├── CHAOS_MONKEY_RESULTS.md  # Chaos monkey test results
├── AGENTS.md                # AI agent context file
├── chaos_monkey.sh          # 15 chaos monkey tests
├── test_queries.sh          # Test query runner
├── setup-hooks.sh           # Git hook installer
├── .githooks/               # Git hooks directory
│   └── post-commit         # Auto-runs tests on every commit
└── README.md                # This file
```