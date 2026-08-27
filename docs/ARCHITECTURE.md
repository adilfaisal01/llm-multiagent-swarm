# Architecture

Multi-agent research orchestration using Ollama cloud models. The orchestrator
spawns parallel workers with focused research angles, each with tool access,
and collects their outputs via a shared write-only scratchpad. The core library
is pure Python stdlib; the optional persistent TUI uses `textual` as its one
external dependency.

## System diagram

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

Each worker is an independent Ollama model with a **skill** assigned by the
preflight LLM. The orchestrator analyzes the question, determines what tools are
needed, and gives each worker tailored capabilities. Workers can search the web,
read files, analyze images, and run Python code — all in parallel via
`ThreadPoolExecutor` or sequentially in pipeline mode when dependencies exist.
Every tool-call result is auto-logged to the scratchpad. The orchestrator
collects everything, optionally synthesizes the findings, and saves the full
output to a timestamped `.md` file.

## Preflight question analysis

Before spawning workers, the orchestrator runs a **preflight** pass using the
orchestrator model (DeepSeek V4 Flash):

1. **Classifies answer type**: number, name, phrase, date, or other
2. **Assigns skills via LLM**: The model reasons about what tools each worker
   needs and assigns the right skill (`vision` for images, `code` for
   calculations, `files` for spreadsheets, etc.)
3. **Decides execution mode**: Outputs `parallel` or `pipeline` based on whether
   workers have sequential dependencies
4. **Generates search strategies**: Each worker gets a specific, actionable plan
   tailored to the question
5. **Injects file paths**: For file-based questions, the file path is injected
   into the worker prompt — workers are aggressively prompted to use their tools
   to read it (never guess)

The key difference from the old system: **the LLM decides, not hardcoded rules**.
There is no preload hack — workers use their tools properly.

### Research modes

Preflight also classifies every question as **objective** (facts, numbers,
dates, definitions, current events) or **subjective** (opinions, views,
interpretations, debates). The mode changes the worker prompt tone and angle
strategy, scratchpad guidance (e.g. log `direct_quote`, `paraphrase`, `claim`,
`contradiction`), and the orchestrator synthesis style (factual answer vs
perspective map with attribution).

## Pipeline mode

For questions where workers have sequential dependencies, the preflight LLM can
set `mode: pipeline`:

```
Mode: pipeline
  Worker 0: vision (reads image, extracts numbers)
  Worker 1: code (depends_on: 0) — takes numbers and computes
  Worker 2: code (depends_on: 1) — verifies the computation
```

In pipeline mode:

- Workers execute in dependency order
- Each worker's output is injected into the next dependent worker's prompt
- Non-dependent workers still run in parallel

## Tool calling flow

The swarm speaks the OpenAI-compatible `/v1/chat/completions` protocol, which
covers OpenAI, Anthropic (compat layer), Ollama (`/v1`), Groq, Together,
DeepSeek, OpenRouter, vLLM, and more:

1. **Preflight** analyzes the question via the orchestrator LLM, which assigns
   tool bundles + execution mode
2. Injects file paths (not file contents) into worker prompts
3. Aggressively prompts workers to use their tools (never guess, never write
   from memory)
4. Sends prompt + tool definitions (filtered by bundle) to each model
5. Model responds with `tool_calls` (search query, image read, code exec) or
   content (final answer)
6. The swarm executes the tool against the configured backend
7. Feeds results back as a `role: "tool"` message with the matching
   `tool_call_id`
8. Loop repeats up to 5 rounds until the model has enough info to answer

If a model exhausts all tool rounds without producing a final answer, the script:

1. Sends a gentle "synthesize your findings" prompt
2. If that fails, sends an aggressive "STOP SEARCHING. WRITE NOW." prompt
3. If both fail, falls back to re-firing the question at a different model

## Modules

```
swarm/
├── __init__.py       # Public API: from swarm import run_swarm
├── __main__.py        # CLI entry point (thin wrapper)
├── runner.py          # Library entry point: run_swarm()
├── orchestrator.py    # Spawns workers, manages scratchpad, pipeline mode
├── preflight.py       # LLM-based question analysis + skill assignment
├── worker.py          # Worker agent loop (Ollama chat + tool calls)
├── scratchpad.py      # Write-only RAM SQLite for raw findings
├── search.py          # Search backends: SearXNG, DuckDuckGo, Google
├── synthesis.py       # Orchestrator synthesis (boss reads the room)
├── llm.py             # Shared LLM helper: OpenAI-compat + optional LiteLLM, retry/backoff, streaming, cost
├── providers.py       # Provider resolution: model tags → endpoint, API key, headers
├── credibility.py     # AI-based probabilistic source credibility (Bayesian)
├── cache.py           # SQLite search/extract result cache
├── config.py          # Config loader + defaults
├── complexity.py      # Model-based complexity estimation (1-5)
├── output.py          # Output formatting + markdown saving
├── skills/            # Skill system (capability packs) — see docs/SKILLS.md
├── integrations/      # External harness adapters
│   └── mcp/           # MCP server: swarm_research tool (optional extra)
├── prompts/           # External markdown prompt templates
└── tools/             # Modular tool registry — see docs/TOOLS.md
```

## Scratchpad

The scratchpad is a write-only RAM SQLite database — workers write raw findings
and never read each other's data, preventing context pollution. The orchestrator
reads it once all workers finish, then destroys it. Full design:
[docs/SCRATCHPAD.md](SCRATCHPAD.md).

## Complexity estimation (`--auto`)

With `--auto`, the orchestrator model rates the query 1-5 before spawning
workers and scales the worker count accordingly. Falls back to 3 (safe default)
on LLM failure. Full table: **docs/COMPLEXITY.md**.
