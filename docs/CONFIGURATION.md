# Configuration

All config is via environment variables or a JSON config file
(`swarm_config.json` by default, or set via `SWARM_CONFIG` env var or
`--config` flag).

## Env vars

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint (default ollama provider base) |
| `SWARM_VISION_MODEL` | `ollama/qwen3.5:397b-cloud` | Vision model for the `read_image` tool |
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

## Search backends

| Backend | Auth needed | Notes |
|---------|-------------|-------|
| `ddgs` | No | **Default.** DuckDuckGo via the `ddgs` package (installed by default). No API key, no setup. Rate limits may apply. |
| `searxng` | No (self-hosted) | Point `SEARXNG_URL` at your instance. |
| `google` | `SEARCH_API_KEY` + `GOOGLE_CX` | Google Custom Search JSON API. 100 free queries/day. |

## JSON config file

The `swarm_config.json` file lets you customize models, team members, prompts,
angles, and fallback models. Pass a custom config with
`--config my_config.json` or `SWARM_CONFIG=my_config.json`.

### Providers (OpenAI-compatible APIs)

Model tags carry a `provider/name` shape (e.g. `openai/gpt-4o`,
`ollama/deepseek-v4-flash:cloud`). The `providers` block maps each provider to
its base URL and API key env var:

```json
{
  "providers": {
    "ollama":     {"base_url": "http://localhost:11434/v1"},
    "openai":     {"base_url": "https://api.openai.com/v1",    "api_key_env": "OPENAI_API_KEY"},
    "anthropic":  {"base_url": "https://api.anthropic.com/v1", "api_key_env": "ANTHROPIC_API_KEY"},
    "deepseek":   {"base_url": "https://api.deepseek.com",     "api_key_env": "DEEPSEEK_API_KEY"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "api_key_env": "OPENROUTER_API_KEY"}
  },
  "models": {
    "gpt-4o":  "openai/gpt-4o",
    "claude":  "anthropic/claude-3-5-sonnet",
    "deepseek": "deepseek/deepseek-chat"
  }
}
```

- **Bare tags** (no `/`, e.g. `gpt-oss:120b-cloud`) fall back to the `ollama`
  provider — existing configs keep working unchanged.
- **`OLLAMA_HOST`** env var is honored as the default ollama base URL when no
  `providers.ollama.base_url` is set.
- **`vision_model`** config key (or `SWARM_VISION_MODEL` env var) overrides the
  vision tool's default model (`ollama/qwen3.5:397b-cloud`).
- **`use_litellm`** config key forces the transport: `true`/`false` override
  auto-detection. By default, if the optional `litellm` package is installed
  (`pip install -e ".[providers]"`, pinned `>=1.50,<2.0`), calls route through
  it for native provider support (Anthropic, Gemini, Bedrock, etc.) and
  normalized tool calls; otherwise the stdlib OpenAI-compat path is used.

A config may also declare a `"skill"` field — the skill's prompt body and tools
are used with the JSON's team:

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

See `swarm_config.json` for a full example. `--skill` and `--config` are
mutually exclusive.

## Streaming, retry, cache, and cost

- **Streaming**: `run_swarm()` accepts a `stream_callback(chunk, phase)` hook
  (`phase` is `"preflight"` or `"synthesis"`). When provided, preflight and
  synthesis tokens stream through it. Worker turns stay non-streaming.
- **Retry/backoff**: all LLM calls go through `swarm/llm.py` with up to 3
  attempts, exponential backoff + jitter, no retry on 4xx (except 429, which
  honors `Retry-After`). LiteLLM rate-limit/connection/timeout exceptions are
  treated as transient too.
- **Result cache**: `web_search` and `web_extract` results are cached in SQLite
  (`swarm/cache.py`, keyed on `backend|query`, 24h TTL, `SWARM_CACHE=0`
  disables). Cache hits still log to the scratchpad — transparent to workers.
  All cache access is guarded by a `threading.Lock` — do not remove it.
- **Cost accounting**: the result dict gains a `cost` key (`prompt_tokens`,
  `completion_tokens`, `total_tokens`, `seconds`, `calls`,
  `estimated_cost_usd`). Cost rates are opt-in via the `model_costs` config
  field — until populated, `estimated_cost_usd` stays 0.
