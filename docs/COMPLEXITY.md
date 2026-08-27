# Complexity Estimation (`--auto`)

When `--auto` is set, the orchestrator model (DeepSeek V4 Flash) reads the
query and rates its complexity 1-5 before spawning workers:

| Rating | Meaning | Example | Workers |
|--------|---------|---------|---------|
| 1 | Simple fact lookup | "What is the capital of France?" | 1 |
| 2 | Straightforward explanation | "Explain REST vs GraphQL" | 2 |
| 3 | Multi-faceted topic | "Impact of quantum computing on cryptography" | 3 |
| 4 | Complex with controversy | "Is the industrial revolution a disaster for humanity?" | 4 |
| 5 | Deep philosophical/scientific | "Philosophical implications of AI consciousness" | 5 |

Falls back to returning 3 (safe default) if the LLM call fails.
