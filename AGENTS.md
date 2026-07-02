# AGENTS.md — Swarm v2

This file tells AI agents (Claude Code, Codex, Cursor, etc.) how to work with this project.

## Project Overview

Multi-agent research orchestration using Ollama cloud models. Spawns parallel workers with focused research angles, each with web search access, and collects their outputs via a shared write-only scratchpad.

**Zero dependencies** — pure Python stdlib. No pip install needed.

## Architecture

```
swarm/
├── __init__.py       # Public API: from swarm import run_swarm
├── __main__.py       # CLI entry point (thin wrapper, ~60 lines)
├── runner.py         # Library entry point: run_swarm()
├── orchestrator.py   # Spawns workers, manages scratchpad lifecycle
├── worker.py         # Worker agent loop (Ollama chat + tool calls)
├── scratchpad.py     # Write-only RAM SQLite for raw findings
├── search.py         # Search backends: SearXNG, DuckDuckGo, Google
├── tools.py          # Tool definitions + execute_tool()
├── config.py         # Config loader from JSON file
├── complexity.py     # Model-based complexity estimation (1-5)
└── output.py         # Output formatting + markdown file saving
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

### Scratchpad (write-only RAM SQLite)
- Workers **write only** — they never read from it (no context pollution)
- Every `web_search` and `web_extract` result is auto-logged
- Workers can also call `scratchpad_add()` manually
- Orchestrator reads after all workers finish
- DB is `:memory:` with `check_same_thread=False` and `isolation_level=None`
- Destroyed after `.md` file is saved

### Complexity estimation
- Uses DeepSeek V4 Flash to read the query and rate it 1-5
- Falls back to regex heuristic if the LLM call fails
- `--auto` flag enables this

### Worker loop
- Up to 3 search rounds per worker
- Force-synthesis: if exhausted, sends "synthesize your findings" → "STOP SEARCHING" → fallback model
- Each worker has its own `messages` list (thread-local)

### Search backends
- `searxng` (default, self-hosted at localhost:8080)
- `ddgs` (DuckDuckGo, no setup)
- `google` (requires API key + CX)

## CLI Usage

```bash
python3 -m swarm --goal "Your question" --mix
python3 -m swarm --goal "Your question" --auto --mix
python3 -m swarm --goal "Your question" --model qwen --workers 3
python3 -m swarm --goal "Your question" --mix --json
```

## Config

`swarm_config.json` controls models, team members, prompts, angles, and fallbacks. Pass custom config with `--config path.json` or `SWARM_CONFIG=path.json`.

## Testing

```bash
bash chaos_monkey.sh   # 15 chaos monkey tests
```

## Common Pitfalls

- **Scratchpad race conditions**: `isolation_level=None` on the SQLite connection prevents "cannot commit - no transaction is active" errors with concurrent workers
- **JSON output**: Goes to stdout (not stderr) so piping works: `python3 -m swarm --goal "..." --json | python3 -c "import json,sys; ..."`
- **Model names**: Use aliases from config (e.g. `deepseek`, `qwen`, `nemotron`) or full tags (e.g. `deepseek-v4-flash:cloud`)
- **Worker count**: Clamped to 1-5. `--workers 20` caps at 5 with wrap-around
- **Ollama URL**: Defaults to `http://localhost:11434`. Set `OLLAMA_HOST` env var to override
