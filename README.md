# 🐝 Swarm v2

Multi-agent research orchestration using Ollama cloud models. Spawn parallel workers with focused research angles, each with web search access, and collect their outputs via a shared scratchpad.

Core library is pure Python stdlib. The optional persistent TUI requires `textual`. Web search works out of the box via DuckDuckGo (no API key, no self-hosting).

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
                         │  • LLM assigns tool bundles+mode   │
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
   │ bundle    │        │  bundle   │ │ bundle    │ │ bundle    │  │ bundle    │
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

Each worker is an independent Ollama model with a **tool bundle** assigned by the preflight LLM. The orchestrator analyzes the question, determines what tools are needed, and gives each worker tailored capabilities. Workers can search the web, read files, analyze images, and run Python code — all in parallel via `ThreadPoolExecutor` or sequentially in pipeline mode when dependencies exist. Every tool call result is automatically logged to the scratchpad. The orchestrator collects everything, optionally synthesizes the findings, and saves the full output to a timestamped `.md` file.

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

# Persistent TUI with session history and follow-ups
python3 -m swarm --tui

# Demo version (original pre-modular research script)
python3 -m demo-swarm --goal "Your question" --mix
```

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
- `sources(worker, url, title, snippet, timestamp)`

## Modular Tool System

The swarm uses a plugin-style tool registry in `swarm/tools/`. Each tool is a self-contained module extending `BaseTool`. Adding a new tool is just: create a file, extend `BaseTool`, register it in `__init__.py`.

### Available tools

| Tool | Description | Used by bundles |
|------|-------------|-----------------|
| `web_search` | Search the web (DuckDuckGo/SearXNG/Google) | all |
| `web_extract` | Read content from a URL | all |
| `scratchpad_add` | Log raw findings to the shared scratchpad | all |
| `read_image` | Read text/numbers from images via Gemma4 vision | vision, files, all |
| `read_file` | Read .txt, .csv, .json, .xml, .xlsx files | files, all |
| `python_exec` | Execute Python code for calculations/processing | code, all |

### Tool bundles

Preflight assigns a tool bundle to each worker based on the question. Bundles are **additive** — specialty bundles include search + scratchpad + their unique tools.

| Bundle | Tools | When assigned |
|--------|-------|--------------|
| `default` | web_search, web_extract, scratchpad_add | General research questions |
| `vision` | read_image, web_search, web_extract, scratchpad_add | Questions with image attachments (.png/.jpg) |
| `code` | python_exec, web_search, web_extract, scratchpad_add | Questions needing computation ("calculate", "average") |
| `files` | read_file, read_image, web_search, web_extract, scratchpad_add | Questions with attached data files (.xlsx/.csv/.docx) |
| `search` | web_search, web_extract | Lightweight search-only (no scratchpad) |
| `scratchpad` | scratchpad_add | Logging-only (no search) |
| `all` | Every registered tool | Everything (debugging) |

### Preflight question analysis

Before spawning workers, the orchestrator runs a **preflight** pass using the orchestrator model (DeepSeek V4 Flash):

1. **Classifies answer type**: number, name, phrase, date, or other
2. **Assigns tool bundles via LLM**: The model reasons about what tools each worker needs and assigns the right bundle (`vision` for images, `code` for calculations, `files` for spreadsheets, etc.)
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

### Search backends

| Backend | Auth needed | Notes |
|---------|-------------|-------|
| `ddgs` | No | **Default.** DuckDuckGo HTML scraping. No API key, no setup. Rate limits may apply. |
| `searxng` | No (self-hosted) | Point `SEARXNG_URL` at your instance. |
| `google` | `SEARCH_API_KEY` + `GOOGLE_CX` | Google Custom Search JSON API. 100 free queries/day. |

### JSON config file

The `swarm_config.json` file lets you customize models, team members, prompts, angles, and fallback models. Pass a custom config with `--config my_config.json` or `SWARM_CONFIG=my_config.json`.

```json
{
  "models": {
    "my-model": "my-model:latest"
  },
  "default_model": "my-model",
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

### Smoke test

```bash
python3 test_tools.py                    # Quick tool smoke test
python3 test_tools.py --verbose          # Show full tool outputs
python3 test_tools.py --samples=100      # Bigger test files
python3 test_tools.py --skip-swarm       # Skip full swarm tests (faster)
```

## Performance

Parallel swarm is **3.3-3.4× faster** than sequential execution. See `BENCHMARK.md` for full results.

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

## Files

```
├── swarm/                 # Modular package
│   ├── __init__.py        # Public API: from swarm import run_swarm
│   ├── __main__.py        # CLI entry point (thin wrapper)
│   ├── runner.py          # Library entry point: run_swarm()
│   ├── orchestrator.py    # Spawns workers, manages scratchpad
│   ├── preflight.py       # LLM-based question analysis + bundle assignment
│   ├── worker.py          # Worker agent loop with tool access
│   ├── scratchpad.py      # Write-only RAM SQLite scratchpad
│   ├── search.py          # Search backends (SearXNG, DDG, Google)
│   ├── synthesis.py       # Orchestrator synthesis (boss reads the room)
│   ├── config.py          # Config loader + defaults
│   ├── complexity.py      # Model-based complexity estimation
│   ├── output.py          # Output formatting + markdown saving
│   └── tools/             # Modular tool registry
│   │   ├── __init__.py    # Registry: get_registry(), reset_registry()
│   │   ├── base.py        # BaseTool abstract class
│   │   ├── registry.py    # ToolRegistry: discover, register, bundle
│   │   ├── web_search.py  # Search the web
│   │   ├── web_extract.py # Read content from URLs
│   │   ├── scratchpad.py  # Log findings tool
│   │   ├── vision.py      # Read images via Gemma4
│   │   ├── python_exec.py # Execute Python code
│   │   └── file_reader.py # Read .txt/.csv/.json/.xlsx
│   └── tui/               # Optional persistent Textual TUI
│       ├── __init__.py    # Exports run_tui, Session, SessionStore
│       ├── app.py         # Main Textual app + event loop
│       ├── session.py     # In-memory session model + follow-up context
│       ├── store.py       # SQLite persistence for sessions/results
│       └── widgets.py     # ChatLog, WorkerGrid, SessionList, InputBar
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
├── swarm2.py                # Legacy monolith (preserved, pre-demo)
├── swarm_config.json        # Configurable team, models, prompts
├── swarm.py                 # Minimal version (no web search)
├── gaia_eval.py             # GAIA benchmark eval harness
├── SCRATCHPAD.md            # Scratchpad architecture docs
├── BENCHMARK.md             # Benchmark results
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