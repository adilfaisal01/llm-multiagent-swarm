# Swarm v2

Multi-agent research orchestration using Ollama cloud models. Spawn parallel workers with focused research angles, each with web search access, and collect their outputs via a shared scratchpad.

Core library is pure Python stdlib. The optional persistent TUI requires `textual`. Web search works out of the box via DuckDuckGo (the `ddgs` package, no API key, no self-hosting).

```bash
# Quick start
python3 -m swarm --goal "What's happening with AI regulation in the EU?" --mix

# Persistent TUI with follow-up support
python3 -m swarm --tui
```

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

# Demo version (original pre-modular research script)
python3 -m demo-swarm --goal "Your question" --mix
```

## Overview

The orchestrator LLM (DeepSeek V4 Flash) analyzes your question, assigns each
worker a **skill** (tool bundle) and research angle, and decides whether workers
run in **parallel** or **pipeline** mode. Workers research independently using
their tools (web search, image reading, code execution, file reading), logging
every finding to a write-only scratchpad. When they finish, the orchestrator
reads the scratchpad, credibility-scores and dedupes the sources, optionally
synthesizes a cited answer, and saves the output to a timestamped `.md` file.

## Documentation

| Doc | What's in it |
|-----|--------------|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System diagram, preflight analysis, pipeline mode, tool-calling flow, module tree |
| [docs/TOOLS.md](docs/TOOLS.md) | Full tool catalog (registry, cache behavior) |
| [docs/SKILLS.md](docs/SKILLS.md) | Full skill catalog (tools, modes, teams) |
| [docs/SCRATCHPAD.md](docs/SCRATCHPAD.md) | Write-only scratchpad, source dedup + credibility, inline citations |
| [docs/CONFIGURATION.md](docs/CONFIGURATION.md) | Env vars, JSON config, providers, search backends, streaming/retry/cache/cost |
| [docs/MODELS.md](docs/MODELS.md) | Available models + the `--mix` team |
| [docs/TUI.md](docs/TUI.md) | Persistent TUI (`--tui`) |
| [docs/COMPLEXITY.md](docs/COMPLEXITY.md) | `--auto` complexity estimation (1-5) |
| [docs/MCP.md](docs/MCP.md) | MCP server (`swarm_research` tool for Claude Desktop / Cursor / opencode) |
| [docs/DEMO.md](docs/DEMO.md) | Demo version (`demo-swarm/`) vs main |
| [docs/TESTING.md](docs/TESTING.md) | Testing workflow (make targets, verbosity, hermetic suites, CI) |
| [docs/BENCHMARK.md](docs/BENCHMARK.md) | Parallel vs sequential benchmark results |
| [docs/RELEASE.md](docs/RELEASE.md) | Release process (tags, versions, CHANGELOG) |

## Configuration

All config is via environment variables or a JSON config file
(`swarm_config.json` by default). Models, team members, prompts, angles,
fallbacks, providers, search backends, and cost rates are all configurable.
See [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Releases

Releases are cut with git tags (`v*`):

```bash
make release KIND=patch   # 2.0.0 -> 2.0.1 (bug fixes)
make release KIND=minor   # 2.0.0 -> 2.1.0 (new features)
make release KIND=major   # 2.0.0 -> 3.0.0 (breaking changes)
```

Pushing a `v*` tag triggers a GitHub Actions workflow that generates
`CHANGELOG.md` from the git log, commits it back to `main`, and publishes a
GitHub Release. Full guide: [docs/RELEASE.md](docs/RELEASE.md).

## Performance

Parallel swarm is **3.3-3.4× faster** than sequential execution.
See [docs/BENCHMARK.md](docs/BENCHMARK.md).

| Mode | Easy query | Hard query |
|------|-----------|------------|
| Sequential | 150.4s | 264.0s |
| Parallel | 45.6s (3.3×) | 77.3s (3.4×) |

## Requirements

- Python 3.11+ (stdlib for the core library)
- `textual>=0.70.0` for the optional TUI (`pip install -e .`)
- Ollama running at `OLLAMA_HOST` (default: localhost:11434)
- Cloud models pulled via `ollama pull <model>:cloud`
- No SearXNG needed — DuckDuckGo is the default backend and works out of the box
- Optional: SearXNG instance at `SEARXNG_URL` for higher rate limits

## Auto-testing on commit

A **post-commit git hook** runs chaos monkey + benchmark after every commit.
Install once:

```bash
bash setup-hooks.sh
```

## Files

```
├── swarm/                 # Modular package
│   ├── __init__.py        # Public API: from swarm import run_swarm
│   ├── __main__.py        # CLI entry point (thin wrapper)
│   ├── runner.py          # Library entry point: run_swarm()
│   ├── orchestrator.py    # Spawns workers, manages scratchpad, pipeline mode
│   ├── preflight.py       # LLM-based question analysis + skill assignment
│   ├── worker.py          # Worker agent loop (Ollama chat + tool calls)
│   ├── scratchpad.py      # Write-only RAM SQLite for raw findings
│   ├── search.py          # Search backends (SearXNG, DDG, Google)
│   ├── synthesis.py       # Orchestrator synthesis (boss reads the room)
│   ├── llm.py             # Shared LLM helper: OpenAI-compat + optional LiteLLM, retry/backoff, streaming, cost
│   ├── providers.py       # Provider resolution: model tags → endpoint, API key, headers
│   ├── credibility.py     # AI-based probabilistic source credibility (Bayesian)
│   ├── cache.py           # SQLite search/extract result cache
│   ├── config.py          # Config loader + defaults
│   ├── complexity.py      # Model-based complexity estimation
│   ├── output.py          # Output formatting + markdown saving
│   ├── skills/            # Skill system (capability packs)
│   ├── integrations/      # External harness adapters
│   │   └── mcp/           # MCP server: swarm_research tool (optional extra)
│   ├── prompts/           # External markdown prompt templates
│   ├── tools/             # Modular tool registry
│   └── tui/               # Optional persistent Textual TUI
├── docs/                  # Documentation (see table above)
├── scripts/               # Helper scripts
│   └── gen_changelog.py   # Auto-generates CHANGELOG.md from git log
├── test_tools.py          # Tool smoke test (random files, all tool paths)
├── demo-swarm/            # Original research version (demo)
├── legacy/                # Pre-modular monoliths (preserved for reference)
├── cybersec-test/         # Reverse-engineering demo wrapper
├── CHANGELOG.md           # Auto-generated release changelog (do not hand-edit)
├── swarm_config.json      # Configurable team, models, prompts
├── AGENTS.md              # AI agent context file
├── chaos_monkey.sh        # 15 chaos monkey tests
├── setup-hooks.sh         # Git hook installer
├── .githooks/             # Git hooks directory
└── benchmark.py           # Benchmark script (library-based)
```
