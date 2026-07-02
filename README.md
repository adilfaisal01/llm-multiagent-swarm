# 🐝 Swarm v2

Multi-agent research orchestration using Ollama cloud models. Spawn parallel workers with focused research angles, each with web search access, and collect their outputs via a shared scratchpad.

Zero dependencies — pure Python stdlib. Just needs Ollama running locally. Web search works out of the box via DuckDuckGo (no API key, no self-hosting).

```bash
# Quick start
python3 -m swarm --goal "What's happening with AI regulation in the EU?" --mix
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
                         │  • Spawns workers in parallel      │
                         │  • Reads scratchpad after workers   │
                         │  • Destroys scratchpad, saves .md   │
                         └──────┬──────┬──────┬──────┬───────┘
                                │      │      │      │
          ┌─────────────────────┼──────┼──────┼──────┼─────────────────────┐
          │                     │      │      │      │                     │
          ▼                     ▼      ▼      ▼      ▼                     ▼
   ┌───────────┐        ┌───────────┐ ┌───────────┐ ┌───────────┐  ┌───────────┐
   │   VERA    │        │   CYRUS   │ │   ROMY    │ │   ASH     │  │   ZARA    │
   │ gpt-oss   │        │ nemotron  │ │ qwen3.5   │ │ deepseek  │  │ gpt-oss   │
   │ 120B      │        │ 30B       │ │ 397B      │ │ flash     │  │ 120B      │
   │           │        │           │ │           │ │           │  │           │
   │ ORIGINS   │        │  MONEY    │ │ FUTURE    │ │ CONTRO-   │  │ TECHNICAL │
   │ & HISTORY │        │ & PLAYERS │ │ & IMPLI-  │ │ VERSIES   │  │ DETAILS   │
   │           │        │           │ │ CATIONS   │ │           │  │           │
   └─────┬─────┘        └─────┬─────┘ └─────┬─────┘ └─────┬─────┘  └─────┬─────┘
         │                    │             │             │              │
         └──────────┬─────────┘             │             │              │
                     │                       │             │              │
          ┌──────────▼───────────────────────▼─────────────▼──────────────▼──────┐
          │                     TOOL RUNTIME                                     │
          │                                                                      │
          │  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────┐  │
          │  │   web_search()   │  │  web_extract()  │  │  Ollama /api/chat   │  │
          │  │  ┌───────────┐  │  │  ┌───────────┐  │  │  ┌────────────────┐ │  │
          │  │  │ SearXNG   │  │  │  │ Web pages │  │  │  │ Model response │ │  │
          │  │  │ DuckDuckGo│  │  │  │ Articles  │  │  │  │ + tool_calls   │ │  │
          │  │  │ Google    │  │  │  │ PDFs      │  │  │  │ + content      │ │  │
          │  │  └───────────┘  │  │  └───────────┘  │  │  └────────────────┘ │  │
          │  └─────────────────┘  └─────────────────┘  └──────────────────────┘  │
          │                                                                      │
          │  ┌────────────────────────────────────────────────────────────────┐  │
          │  │   SCRATCHPAD (write-only RAM SQLite)                          │  │
          │  │   • Agents auto-log every web_search + web_extract result     │  │
          │  │   • Agents can also call scratchpad_add() manually             │  │
          │  │   • Write-only from agent perspective — no context pollution  │  │
          │  │   • Orchestrator reads after all workers finish               │  │
          │  │   • DB destroyed after .md file is saved                      │  │
          │  └────────────────────────────────────────────────────────────────┘  │
          └──────────────────────────────────────────────────────────────────────┘
                                        │
                         ┌──────────────▼──────────────────────┐
                         │         OUTPUT                      │
                         │  • Auto-saved to .md file          │
                         │  • Per-worker sections + stats     │
                         │  • Scratchpad findings table       │
                         │  • Source URL list                  │
                         │  • JSON (--json flag)             │
                         └─────────────────────────────────────┘
```

Each worker is an independent Ollama model with tool-calling access to `web_search` and `web_extract`. They search the web, read pages, and write their report — all in parallel via `ThreadPoolExecutor`. Every search and extract result is automatically logged to the scratchpad. The orchestrator collects everything, reads the scratchpad for cross-referencing, and saves the full output to a timestamped `.md` file.

## Quick start

```bash
# Make sure Ollama is running
ollama serve

# Pull cloud models
ollama pull gpt-oss:120b-cloud
ollama pull deepseek-v4-flash:cloud
ollama pull qwen3.5:397b-cloud
ollama pull nemotron-3-nano:30b-cloud

# Fire the swarm (new package)
python3 -m swarm --goal "Your research question" --mix

# Auto-estimate worker count based on query complexity
python3 -m swarm --goal "Your question" --auto --mix

# Uniform mode (all workers use the same model)
python3 -m swarm --goal "Your question" --model qwen --workers 3

# JSON output for programmatic use
python3 -m swarm --goal "Your question" --mix --json

# Legacy script (still works)
python3 swarm2.py --goal "Your question" --mix
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
| `qwen` | qwen3.5:397b-cloud | 397B | ~8-50s | Best reasoning, often answers from weights |
| `gemma` | gemma4:31b-cloud | 31B | ~13-30s | Slower, pre-2026 cutoff |
| `deepseek` | deepseek-v4-flash:cloud | ~158B | ~4-20s | Fast, used for complexity estimation |
| `ministral` | ministral-3:14b-cloud | 14B | ~4.5-20s | ⚠️ Being retired by Ollama Cloud |
| `nemotron-super` | nemotron-3-super:cloud | 120B | ~1-20s | ⚠️ Buggy — may time out or return empty |

All models route through your local Ollama as a cloud proxy. Pull them with `ollama pull <model>:cloud`.

## The team (--mix mode)

In `--mix` mode, each worker gets a different model and named identity:

| Name | Model | Angle |
|------|-------|-------|
| **Vera** | gpt-oss | Origins & history |
| **Cyrus** | nemotron | Money & players |
| **Romy** | qwen | Implications & future |
| **Ash** | deepseek | Controversies |
| **Zara** | gpt-oss | Technical details |

```bash
python3 -m swarm --goal "Your question" --mix --config my_team.json
```

## How tool calling works

Ollama's `/api/chat` endpoint supports native function calling. The swarm:

1. Sends prompt + tool definitions to the model
2. Model responds with `tool_calls` (search query) or content (final answer)
3. Script executes the tool against the configured search backend
4. Feeds results back as a `role: "tool"` message
5. Loop repeats up to 3 rounds until the model has enough info to answer

If a model exhausts all 3 search rounds without producing a final answer, the script:
1. Sends a gentle "synthesize your findings" prompt
2. If that fails, sends an aggressive "STOP SEARCHING. WRITE NOW." prompt
3. If both fail, falls back to re-firing the question at a different model

## Performance

Parallel swarm is **3.3-3.4× faster** than sequential execution. See `BENCHMARK.md` for full results.

| Mode | Easy query | Hard query |
|------|-----------|------------|
| Sequential | 150.4s | 264.0s |
| Parallel | 45.6s (3.3×) | 77.3s (3.4×) |

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

- Python 3.8+ (stdlib only — no pip install needed)
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
│   ├── worker.py          # Worker agent loop
│   ├── scratchpad.py      # Write-only RAM SQLite scratchpad
│   ├── search.py          # Search backends (SearXNG, DDG, Google)
│   ├── tools.py           # Tool definitions + execute_tool()
│   ├── config.py          # Config loader + defaults
│   ├── complexity.py      # Model-based complexity estimation
│   └── output.py          # Output formatting + markdown saving
├── swarm2.py              # Legacy monolith (preserved)
├── swarm_config.json       # Configurable team, models, prompts
├── swarm.py               # Minimal version (no web search)
├── SCRATCHPAD.md           # Scratchpad architecture docs
├── BENCHMARK.md            # Benchmark results
├── benchmark.py            # Benchmark script
├── CHAOS_MONKEY_RESULTS.md # Chaos monkey test results
├── AGENTS.md               # AI agent context file
├── chaos_monkey.sh         # 15 chaos monkey tests
├── setup-hooks.sh          # Git hook installer
├── .githooks/              # Git hooks directory
│   └── post-commit        # Auto-runs tests on every commit
└── README.md               # This file
```
