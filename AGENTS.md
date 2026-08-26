# AGENTS.md — Swarm v2

This file tells AI agents (Claude Code, Codex, Cursor, Hermes, etc.) how to work with this project.

## Project Overview

Multi-agent research orchestration using Ollama cloud models. Spawns parallel workers with focused research angles, each with tool access, and collects their outputs via a shared write-only scratchpad.

**Library core is still pure stdlib**, but the optional persistent TUI uses `textual` as its one external dependency.

## Architecture

```
swarm/
├── __init__.py       # Public API: from swarm import run_swarm
├── __main__.py       # CLI entry point (thin wrapper, ~60 lines)
├── runner.py         # Library entry point: run_swarm()
├── orchestrator.py   # Spawns workers, manages scratchpad, pipeline mode
├── preflight.py      # LLM-based question analysis + skill assignment
├── worker.py         # Worker agent loop (Ollama chat + tool calls)
├── scratchpad.py     # Write-only RAM SQLite for raw findings
├── search.py         # Search backends: SearXNG, DuckDuckGo, Google
├── synthesis.py      # Orchestrator synthesis (boss reads the room)
├── llm.py            # Shared Ollama helper: retry/backoff, streaming, cost
├── credibility.py    # AI-based probabilistic source credibility (Bayesian)
├── cache.py          # SQLite search/extract result cache
├── config.py         # Config loader from JSON file
├── complexity.py     # Model-based complexity estimation (1-5)
├── output.py         # Output formatting + markdown file saving
├── skills/           # Skill system (capability packs)
│   ├── __init__.py   # SkillRegistry, get_skill_registry()
│   ├── _base.py      # Skill dataclass + registry + hand-rolled YAML parser
│   ├── default/SKILL.md
│   ├── research/     # Full pack: SKILL.md + team.json
│   ├── search/SKILL.md
│   ├── vision/SKILL.md
│   ├── code/SKILL.md
│   ├── code-debug/SKILL.md
│   ├── files/SKILL.md
│   ├── fact-check/   # Full pack: SKILL.md + team.json
│   ├── multi-hop/SKILL.md
│   ├── comparison/SKILL.md
│   ├── academic/     # Full pack: SKILL.md + team.json
│   ├── legal/        # Full pack: SKILL.md + team.json
│   ├── medical/      # Full pack: SKILL.md + team.json
│   ├── finance/      # Full pack: SKILL.md + team.json
│   └── reverse-engineering/  # Full pack: SKILL.md + team.json
├── integrations/     # External harness adapters
│   └── mcp/          # MCP server: swarm_research tool (optional mcp extra)
├── prompts/          # External markdown prompt templates
│   ├── __init__.py   # load_prompt() and render_prompt()
│   ├── preflight.md  # Preflight JSON-generation prompt
│   ├── worker.md     # Worker system prompt template
│   ├── synthesis.md  # Synthesis prompt template
│   ├── mode_*.md     # Objective / subjective mode instructions
│   └── fallback_*.md # Fallback model prompts
├── tui/              # Optional persistent Textual TUI
│   ├── __init__.py   # Exports run_tui, Session, SessionStore
│   ├── app.py        # Main Textual app + event loop
│   ├── session.py    # In-memory session model + follow-up context
│   ├── store.py      # SQLite persistence for sessions/results
│   └── widgets.py    # ChatLog, WorkerGrid, SessionList, InputBar
└── tools/            # Modular tool registry
    ├── __init__.py   # Registry: get_registry(), reset_registry()
    ├── base.py       # BaseTool abstract class
    ├── registry.py   # ToolRegistry: discover, register, skill delegation
    ├── web_search.py # Search the web
    ├── web_extract.py# Read content from URLs
    ├── scratchpad.py # Log findings tool
    ├── vision.py     # Read images via Gemma4
    ├── python_exec.py# Execute Python code
    ├── file_reader.py# Read .txt/.csv/.json/.xlsx
    ├── wikipedia_search.py # Search Wikipedia for encyclopedic facts
    ├── arxiv_search.py # Search arXiv for academic papers
    ├── github_search.py # Search GitHub repos/issues/code
    ├── wayback_machine.py # Find archived snapshots of URLs
    ├── http_request.py # Generic REST API client
    ├── pdf_extract.py # Read PDFs (optional pdf extra)
    ├── sql_query.py # Run read-only SQL against a local DB
    ├── regex_extract.py # Extract structured data from text
    ├── text_diff.py # Unified diff between two texts
    └── date_calculator.py # Date arithmetic (days between, weekday, age)
```

## Key Design Decisions

### Library-first
The main entry point is `swarm/runner.py` → `run_swarm()`. The CLI (`__main__.py`) is a thin wrapper. Use as a library:

```python
from swarm import run_swarm
from swarm.output import save_markdown

result = run_swarm("Your question", mix=True)
save_markdown(result, result["goal"])
```

### Preflight (LLM-based question analysis)
Before spawning workers, the orchestrator calls DeepSeek V4 Flash to analyze the question:

1. **Classifies answer type**: number, name, phrase, date, or other
2. **Assigns skills**: The LLM reasons about what tools each worker needs (vision for images, code for calculations, files for spreadsheets, etc.) and picks from the discovered skill list
3. **Decides execution mode**: `parallel` or `pipeline` based on dependencies
4. **Generates strategies**: Each worker gets a specific search/action plan

The LLM decides, not hardcoded rules. No preload hack — workers use their tools.

### Skills (capability packs, modular)
A **skill** is a folder under `swarm/skills/<name>/` with a `SKILL.md` file. The YAML `---` frontmatter declares metadata (`name`, `description`, `triggers`, `tools`, `recommended_model`, optional `team`/`mode`) plus Hermes-style fields (`version`, `tags`, `trigger`, `related_skills`, `platforms`). The markdown body is the worker's behavior rules.

Skills reference tools **by name** — all tool implementations live in `swarm/tools/` and are resolved against the `ToolRegistry`. Built-in skills:

- `default` — web_search, web_extract, scratchpad_add (fallback)
- `research` — web_search, web_extract, scratchpad_add (ships a 5-worker team.json)
- `search` — web_search only (no scratchpad)
- `vision` — +read_image (for image files)
- `code` — +python_exec (for calculations)
- `code-debug` — +python_exec, read_file (for debugging/fixing code)
- `files` — +read_file, read_image (for data files)
- `fact-check` — web_search, web_extract, scratchpad_add (ships a 5-worker team.json)
- `multi-hop` — web_search, web_extract, scratchpad_add (pipeline mode for chained facts)
- `comparison` — web_search, web_extract, scratchpad_add (side-by-side option comparison)
- `academic` — wikipedia_search, arxiv_search, web_search, web_extract, pdf_extract, scratchpad_add (ships a 5-worker team.json)
- `legal` — web_search, web_extract, wayback_machine, scratchpad_add (ships a 5-worker team.json)
- `medical` — wikipedia_search, arxiv_search, web_search, web_extract, scratchpad_add (ships a 5-worker team.json)
- `finance` — web_search, web_extract, http_request, sql_query, scratchpad_add (ships a 5-worker team.json)
- `reverse-engineering` — python_exec, web_search, web_extract, read_file, read_image, scratchpad_add (ships a 5-worker team.json)

**Full-pack skills** (`research`, `reverse-engineering`, `fact-check`, `academic`, `legal`, `medical`, `finance`) ship a `team.json` with named workers/models/angles. Use with `--skill <name>`. A `--config` JSON may also declare a `"skill"` field to use a skill's prompt body + tools with a custom team. `--skill` and `--config` are mutually exclusive.

**Adding a skill:** create `swarm/skills/<name>/SKILL.md` with frontmatter + body. Auto-discovered, no code changes. Copy a full-pack skill to `swarm/skills/research-<topic>/` and edit `name` + `team.json` for a domain-specific pack.

**Hermes compatibility:** every `SKILL.md` uses Hermes-native YAML `---` frontmatter and a `## Running under Hermes` section, so Hermes users can read skills natively, copy them into `~/.hermes/skills/`, or adapt the workflow to `delegate_task`. Do NOT add tools to skill folders — all tools live in `swarm/tools/`.

### Pipeline mode
For questions with sequential dependencies, preflight sets `mode: pipeline`:

```
Worker 0: vision (depends_on: null) — reads image
Worker 1: code (depends_on: 0) — computes from extracted numbers
```

Non-dependent workers still run in parallel. Previous worker output is injected into downstream prompts.

### Aggressive tool forcing
Workers are aggressively prompted to use their tools:
- "CRITICAL INSTRUCTIONS: CALL read_image NOW"
- "NEVER guess the file contents"
- "CALL python_exec to compute. Do NOT compute in your head."

This solved the "essay-writing" problem — workers actually use their tools now.

### Scratchpad (write-only RAM SQLite)
- Workers **write only** — they never read from it (no context pollution)
- Every `web_search` and `web_extract` result is auto-logged
- Workers can also call `scratchpad_add()` manually
- Orchestrator reads after all workers finish
- DB is `:memory:` with `check_same_thread=False` and `isolation_level=None`
- Sources are **deduplicated** (URLs normalized: fragment stripped, tracking params removed, host lowercased) and **credibility-scored** (domain authority + recency + corroboration). `score_sources()` runs before the orchestrator reads; `top_sources()` feeds synthesis.
- **AI-based probabilistic scoring** (`swarm/credibility.py`): an LLM judge refines the heuristic prior into a Bayesian posterior via confidence-weighted log-odds pooling. Falls back to the prior on judge failure. `run_swarm(..., ai_credibility=False)` disables it.

### Inline citations
- Synthesis is given a numbered, credibility-ranked source list and asked to cite claims with `[N]` markers
- A post-processor validates markers, drops hallucinated numbers, and appends a `## Sources` section
- Graceful fallback: if the model emits no markers, prose is kept as-is and sources are still listed
- Result dict gains `citations`, `sources_used`, `sources_total` keys

### Streaming, retry, cache, cost
- `run_swarm()` accepts `stream_callback(chunk, phase)` — preflight + synthesis stream tokens (`phase` in `{"preflight", "synthesis"}`); workers stay non-streaming
- All Ollama calls go through `swarm/llm.py` (`call_llm`): up to 3 attempts, exp backoff + jitter, no retry on 4xx (except 429 honoring `Retry-After`), `RunCost` token/cost accounting
- `web_search`/`web_extract` results cached in SQLite (`swarm/cache.py`, keyed on `backend|query`, 24h TTL, `SWARM_CACHE=0` disables). Cache hits still log to the scratchpad — transparent to workers
- Result dict gains a `cost` key; `estimated_cost_usd` is 0 until `model_costs` is populated in config

### Complexity estimation
- Uses DeepSeek V4 Flash to read the query and rate it 1-5
- Returns 3 (safe default) if the LLM call fails
- `--auto` flag enables this

### Worker loop
- Up to **5** tool rounds per worker (increased from 3)
- Auto-nudge after tool results
- Force-synthesis: if exhausted, sends "synthesize your findings" → "STOP SEARCHING" → fallback model

### Search backends
- `ddgs` (default — DuckDuckGo via the `ddgs` package, declared as a hard dependency in `pyproject.toml`/`requirements.txt`)
- `searxng` (self-hosted at localhost:8080, higher rate limits)
- `google` (requires API key + CX)

## CLI Usage

```bash
python3 -m swarm --goal "Your question" --mix
python3 -m swarm --goal "Your question" --auto --mix
python3 -m swarm --goal "Your question" --model qwen --workers 3
python3 -m swarm --goal "Your question" --mix --json
python3 -m swarm --goal "Your question" --no-synthesize
```

## Config

`swarm_config.json` controls models, team members, prompts, angles, and fallbacks. Pass custom config with `--config path.json` or `SWARM_CONFIG=path.json`.

## Demo / Research Version

The original pre-modular swarm is in `demo-swarm/` for reference:

```bash
python3 -m demo-swarm --goal "Your question" --mix
```

The pre-modular root monoliths (`swarm2.py`, `swarm.py`) are preserved in `legacy/` for historical reference. They are not imported by the package and are not maintained.

## Testing

The Makefile is the canonical entry point. All `test-*` targets accept a verbosity flag: default is quiet (compact one-liner per module), `V=1` prints the grouped colored summary, `V=2` prints the raw per-test trace. Full guide: `docs/TESTING.md`.

```bash
make test                 # tool smoke + full grouped summary (default)
make test-summary         # all hermetic suites, grouped summary
make test-summary V=1     # per-test ✓/✗/⏭ breakdown
make test-summary V=2     # raw unittest -v trace

# Per-tool
make test-tool-unit       # hermetic per-tool tests (mocked network/Ollama), quiet
make test-tool-unit V=1   # grouped summary per tool
make test-tool-unit V=2   # raw trace
make test-tools           # live smoke (real ddgs + Ollama)

# Per-suite
make test-skills          # skill system unit tests
make test-skills V=1      # grouped summary

# Full hermetic suites
make test-unit            # unittest discover (quiet dots)
make test-unit V=1        # per-test names
make test-pytest          # pytest
make test-pytest V=2      # pytest -vv

# CI mirror + end-to-end
make test-ci              # mirror GitHub Actions CI exactly
make test-e2e             # Ollama-dependent end-to-end (needs Ollama running)

# Live smoke slice flags (test_tools.py)
python3 test_tools.py --skill vision      # only the tools a skill grants
python3 test_tools.py --tool web_search  # only one tool

# Chaos monkey
bash chaos_monkey.sh      # 15 adversarial CLI tests
```

The hermetic per-tool suite (`tests/test_tools.py`) mocks all network and Ollama calls and is the fastest feedback loop during tool or skill development — run `make test-tool-unit`.

## CI

A GitHub Actions workflow (`.github/workflows/ci.yml`) runs on every push to `main`/`feature/*` and on pull requests:

- Matrix: Python 3.11, 3.12
- Compiles all `swarm/**/*.py`
- Checks core + TUI imports
- Runs `test_tools.py --skip-swarm`
- Runs `python3 -m unittest discover tests/`
- Runs `pytest tests/`

The test suite under `tests/` covers:
- Prompt template loading and rendering
- TUI session model + SQLite persistence
- CLI argument validation
- Hermetic per-tool tests (`tests.test_tools` — every tool in isolation, mocked network/Ollama)
- Adversarial cases derived from `chaos_monkey.sh` (empty goal, unicode, missing config, etc.)

## Releases

Releases are cut with git tags (`v*`). `make release KIND=patch|minor|major`
bumps `pyproject.toml`, commits, tags, and pushes. CI (`.github/workflows/release.yml`)
then generates `CHANGELOG.md` from the git log and publishes a GitHub Release.

- `CHANGELOG.md` is **auto-generated** — do not hand-edit it
- The tag version must match `pyproject.toml` (enforced by the workflow)
- Full guide: `docs/RELEASE.md`

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

## Maintenance Rules for AI Agents

### After every commit
1. **UPDATE README.md** — Cross-check against actual code state:
   - Architecture diagram matches current file structure
   - Preflight section reflects LLM reasoning (not old hardcoded rules)
   - Tool system docs match the actual registry
   - Pipeline mode is documented if implemented
   - Files tree matches `find swarm/ demo-swarm/ -name '*.py' | sort`
   - Any new features are documented
2. **UPDATE AGENTS.md** — Keep this file in sync with architecture changes
3. Commit README + AGENTS updates alongside code changes

### Don't
- Don't reference the old monolithic `tools.py` (it's dead, long live the modular registry)
- Don't describe the preload hack (it's removed — workers use tools now)
- Don't suggest hardcoded bundle/skill assignments (the LLM decides)
- Don't reference `bundle_*.md` (removed — skills own their prompts now)
- Don't add tools to skill folders — all tools live in `swarm/tools/`

### Persistent TUI (`--tui`)
A Textual-based terminal UI is available as an optional mode:

- Run with `python3 -m swarm --tui`
- Persistent session sidebar: previous research sessions are loaded from `swarm_sessions.db`
- Follow-up questions inject the previous run's synthesis + top scratchpad findings as context
- Live worker grid shows each worker's status, model, skill, elapsed time, and a hybrid progress bar
- Live sources panel shows worker name + tool + query/URL as research happens
- Preflight auto-detects `objective` vs `subjective` research mode; synthesis style adapts accordingly
- `Ctrl+N` creates a new session, `Ctrl+S` exports the current run to markdown, `Ctrl+Q` quits
- Markdown is auto-saved to `swarm_outputs/` on every completed run
- Sessions are saved to SQLite automatically; markdown exports use the existing `save_markdown()`

### Research modes (auto-detected)
Preflight classifies every question as either:

- **objective** — asks for facts, numbers, dates, definitions, current events
- **subjective** — asks for opinions, views, interpretations, debates, or perspectives

The mode changes:
- Worker prompt tone and angle strategy
- Scratchpad guidance (e.g., log `direct_quote`, `paraphrase`, `claim`, `contradiction`)
- Orchestrator synthesis style (factual answer vs perspective map with attribution)

### Future Ideas
- **MMLU benchmark (no tools)**: Strip the swarm of all tools (no search, no code exec, no vision) and run on MMLU. Tests whether multi-agent debate + synthesis beats single-model baselines on pure reasoning alone. Key question: does the orchestrate → synthesize pipeline add value beyond asking one good model?
- **BrowserComp benchmark**: Run the swarm on BrowserComp (web interaction tasks) using browser_navigate/click/type tools. Tests the swarm's ability to coordinate multi-step browser workflows across workers. Pipeline mode especially relevant here — one worker researches, another fills forms, a third verifies.
- **Hermes plugin (Phase 2)**: Expose the swarm as a `swarm_research` tool in Hermes's tool registry via a subprocess wrapper in `swarm/integrations/hermes/`. Hermes agents call it like any other tool. (The MCP server in `swarm/integrations/mcp/` is the reference implementation of the same idea.)

## Common Pitfalls

- **Scratchpad race conditions**: `isolation_level=None` on the SQLite connection prevents "cannot commit - no transaction is active" errors with concurrent workers
- **Result cache concurrency**: the `Cache` in `swarm/cache.py` guards all SQLite access with a `threading.Lock` — do not remove it, concurrent workers will corrupt the connection
- **Persistent TUI dependency**: `textual>=0.70.0` is declared in `pyproject.toml`; install with `pip install -e .` or just `pip install textual`
- **MCP dependency**: the `mcp` SDK is an optional extra (`pip install -e ".[mcp]"`). `swarm/integrations/mcp/` raises a clear `ImportError` if it's missing — the library core stays stdlib-only
- **TUI output**: Markdown auto-saved to `swarm_outputs/` on every run; live sources shown in side panel
- **JSON output**: Goes to stdout (not stderr) so piping works: `python3 -m swarm --goal "..." --json | python3 -c "import json,sys; ..."`
- **Model names**: Use aliases from config (e.g. `deepseek`, `qwen`, `nemotron`) or full tags (e.g. `deepseek-v4-flash:cloud`)
- **Worker count**: Explicit `--workers N` is clamped to 1-5. When a skill ships a `team.json`, the runner defaults to the full team size (no clamp) — concurrency is capped at 5 in the orchestrator and extra workers queue until a slot frees up
- **Ollama URL**: Defaults to `http://localhost:11434`. Set `OLLAMA_HOST` env var to override
- **Vision**: Only Gemma4:31b-cloud works for images. Kimi K2.5 returns empty.
- **xlsx merged cells**: The simple XML parser in `file_reader.py` can't handle merged cells