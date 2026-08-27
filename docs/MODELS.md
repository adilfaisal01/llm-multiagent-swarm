# Models & The Team

## Available models

| Alias | Model | Size | Speed | Notes |
|-------|-------|------|-------|-------|
| `gpt-oss` | gpt-oss:120b-cloud | 120B | ~2-15s | Reliable, clean output |
| `nemotron` | nemotron-3-nano:30b-cloud | 30B | ~0.5-15s | Fast, production-proven |
| `gemma` | gemma4:31b-cloud | 31B | ~13-30s | Multimodal (reads images), Romy's model |
| `deepseek` | deepseek-v4-flash:cloud | ~158B | ~4-20s | Fast, orchestrator model |
| `ministral` | ministral-3:14b-cloud | 14B | ~4.5-20s | ⚠️ Being retired by Ollama Cloud |
| `nemotron-super` | nemotron-3-super:cloud | 120B | ~1-20s | ⚠️ Buggy — may time out or return empty |

All models route through your local Ollama as a cloud proxy. Pull them with
`ollama pull <model>:cloud`.

Use aliases from config (e.g. `deepseek`, `qwen`, `nemotron`) or full tags (e.g.
`deepseek-v4-flash:cloud`). Provider-prefixed tags (`openai/gpt-4o`) route to
that provider's endpoint.

## The team (`--mix` mode)

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

An explicit `--workers N` is clamped to 1-5. When a skill ships a `team.json`,
the runner defaults to the full team size (no clamp) — concurrency is capped at
5 in the orchestrator and extra workers queue until a slot frees up.
