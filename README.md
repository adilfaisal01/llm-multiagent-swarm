# 🐝 Lightweight Swarm

Grok-style multi-agent orchestration using Ollama cloud models. Spawn parallel workers with focused research angles, each with web search access, and synthesize their outputs.

Zero dependencies — pure Python stdlib. Just needs Ollama running locally and optionally a SearXNG instance.

```bash
python3 swarm2.py --goal "What's happening with AI regulation in the EU?" --mix
```

## How it works

```
You (orchestrator)
    ├── Worker 1: origins & history
    ├── Worker 2: money & players
    ├── Worker 3: implications & future
    ├── Worker 4: controversies
    └── Worker 5: technical details
              ↓
    You synthesize everything into a unified take
```

Each worker is an Ollama model with tool-calling access to `web_search` and `web_extract`. They search independently, read pages, and write their report. The orchestrator runs them in parallel via `ThreadPoolExecutor`.

## Quick start

```bash
# Make sure Ollama is running
ollama serve

# Pull a cloud model (or use any model you have locally)
ollama pull gpt-oss:120b-cloud

# Fire the swarm
python3 swarm2.py --goal "Your research question" --mix

# Get JSON output for programmatic use
python3 swarm2.py --goal "Your question" --mix --json

# Uniform mode (all workers use the same model)
python3 swarm2.py --goal "Your question" --model qwen --workers 3
```

## Configuration

All config is via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `SEARCH_BACKEND` | `searxng` | Search engine: `searxng`, `ddgs`, or `google` |
| `SEARXNG_URL` | `http://localhost:8080` | SearXNG endpoint (only for `searxng` backend) |
| `SEARCH_API_KEY` | `""` | API key (required for `google` backend) |
| `GOOGLE_CX` | `""` | Google Custom Search CX ID (only for `google` backend) |
| `SEARCH_TIMEOUT` | `15` | Timeout for search/extract calls in seconds |

### Search backends

| Backend | Auth needed | Notes |
|---------|-------------|-------|
| `searxng` | No (self-hosted) | Default. Point `SEARXNG_URL` at your instance. |
| `ddgs` | No | DuckDuckGo HTML scraping. No API key, no setup. Rate limits may apply. |
| `google` | `SEARCH_API_KEY` + `GOOGLE_CX` | Google Custom Search JSON API. 100 free queries/day. |

## Available models

| Alias | Model | Size | Speed | Notes |
|-------|-------|------|-------|-------|
| `gpt-oss` | gpt-oss:120b-cloud | 120B | ~2-15s | Reliable, clean output |
| `nemotron` | nemotron-3-nano:30b-cloud | 30B | ~0.5-15s | Fast, production-proven |
| `qwen` | qwen3.5:397b-cloud | 397B | ~8-50s | Best reasoning, often answers from weights |
| `gemma` | gemma4:31b-cloud | 31B | ~13-30s | Slower, pre-2026 cutoff |
| `deepseek` | deepseek-v4-flash:cloud | ~158B | ~4-20s | Fast, thinking mode spills monologue |
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
python3 swarm2.py --goal "Your question" --mix
```

## How tool calling works

Ollama's `/api/chat` endpoint supports native function calling. The swarm script:

1. Sends prompt + tool definitions to the model
2. Model responds with `tool_calls` (search query) or content (final answer)
3. Script executes the tool against SearXNG
4. Feeds results back as a `role: "tool"` message
5. Loop repeats up to 3 rounds until the model has enough info to answer

If a model exhausts all 3 search rounds without producing a final answer, the script:
1. Sends a gentle "synthesize your findings" prompt
2. If that fails, sends an aggressive "STOP SEARCHING. WRITE NOW." prompt
3. If both fail, falls back to re-firing the question at a different model

## Requirements

- Python 3.8+ (stdlib only — no pip install needed)
- Ollama running at `OLLAMA_HOST` (default: localhost:11434)
- Cloud models pulled via `ollama pull <model>:cloud`
- SearXNG instance at `SEARXNG_URL` (default: localhost:8080) — optional, workers work without it but can't search the web

## Files

```
├── swarm2.py     # Main script with web search support
├── swarm.py      # Minimal version (no web search, training data only)
└── README.md     # This file
```
