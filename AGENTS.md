# AGENTS.md — Swarm v2

This file tells AI agents (Claude Code, Codex, Cursor, Hermes, etc.) how to work with this project.

## Project Overview

Multi-agent research orchestration using Ollama cloud models. Spawns parallel workers with focused research angles, each with tool access, and collects their outputs via a shared write-only scratchpad.

**Zero dependencies** — pure Python stdlib. No pip install needed.

## Architecture

```
swarm/
├── __init__.py       # Public API: from swarm import run_swarm
├── __main__.py       # CLI entry point (thin wrapper, ~60 lines)
├── runner.py         # Library entry point: run_swarm()
├── orchestrator.py   # Spawns workers, manages scratchpad, pipeline mode
├── preflight.py      # LLM-based question analysis + bundle assignment
├── worker.py         # Worker agent loop (Ollama chat + tool calls)
├── scratchpad.py     # Write-only RAM SQLite for raw findings
├── search.py         # Search backends: SearXNG, DuckDuckGo, Google
├── synthesis.py      # Orchestrator synthesis (boss reads the room)
├── config.py         # Config loader from JSON file
├── complexity.py     # Model-based complexity estimation (1-5)
├── output.py         # Output formatting + markdown file saving
└── tools/            # Modular tool registry
    ├── __init__.py   # Registry: get_registry(), reset_registry()
    ├── base.py       # BaseTool abstract class
    ├── registry.py   # ToolRegistry: discover, register, bundle
    ├── web_search.py # Search the web
    ├── web_extract.py# Read content from URLs
    ├── scratchpad.py # Log findings tool
    ├── vision.py     # Read images via Gemma4
    ├── python_exec.py# Execute Python code
    └── file_reader.py# Read .txt/.csv/.json/.xlsx
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
2. **Assigns tool bundles**: The LLM reasons about what tools each worker needs (vision for images, code for calculations, files for spreadsheets, etc.)
3. **Decides execution mode**: `parallel` or `pipeline` based on dependencies
4. **Generates strategies**: Each worker gets a specific search/action plan

The LLM decides, not hardcoded rules. No preload hack — workers use their tools.

### Tool bundles (modular)
Each tool is a self-contained module extending `BaseTool`. Bundles are **additive** — specialty bundles include search + scratchpad + unique tools:

- `default` — web_search, web_extract, scratchpad_add
- `vision` — +read_image (for image files)
- `code` — +python_exec (for calculations)
- `files` — +read_file, read_image (for data files)
- `search` — web_search only (no scratchpad)

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

### Complexity estimation
- Uses DeepSeek V4 Flash to read the query and rate it 1-5
- Returns 3 (safe default) if the LLM call fails
- `--auto` flag enables this

### Worker loop
- Up to **5** tool rounds per worker (increased from 3)
- Auto-nudge after tool results
- Force-synthesis: if exhausted, sends "synthesize your findings" → "STOP SEARCHING" → fallback model

### Search backends
- `ddgs` (default — DuckDuckGo, no setup, works out of the box)
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

## Testing

```bash
python3 test_tools.py              # Tool smoke test (11/12 pass)
bash chaos_monkey.sh               # 15 chaos monkey tests
```

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
- Don't suggest hardcoded bundle assignments (the LLM decides)

### Future Ideas
- **TUI dashboard**: `textual` or `rich`-based live pipeline view showing worker status, findings counter, elapsed time, per-worker logs. Like a devops dashboard but make it fashion.

## Common Pitfalls

- **Scratchpad race conditions**: `isolation_level=None` on the SQLite connection prevents "cannot commit - no transaction is active" errors with concurrent workers
- **JSON output**: Goes to stdout (not stderr) so piping works: `python3 -m swarm --goal "..." --json | python3 -c "import json,sys; ..."`
- **Model names**: Use aliases from config (e.g. `deepseek`, `qwen`, `nemotron`) or full tags (e.g. `deepseek-v4-flash:cloud`)
- **Worker count**: Clamped to 1-5. `--workers 20` caps at 5 with wrap-around
- **Ollama URL**: Defaults to `http://localhost:11434`. Set `OLLAMA_HOST` env var to override
- **Vision**: Only Gemma4:31b-cloud works for images. Kimi K2.5 returns empty.
- **xlsx merged cells**: The simple XML parser in `file_reader.py` can't handle merged cells