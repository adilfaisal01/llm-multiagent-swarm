# 🐝 Demo Swarm — Original Research Version

This is the original version of the swarm before the modular tool system,
preflight analysis, and pipeline execution were added. It's a simple
parallel research agent that uses hardcoded research angles.

## Usage

```bash
python3 -m swarm --goal "Your research question" --mix
```

## What's different from the main version

| Feature | Demo | Main |
|---------|------|------|
| Tool system | Monolithic `tools.py` | Modular registry |
| Worker angles | Hardcoded (Origins, Money, Future...) | LLM-generated per question |
| Tool bundles | None (all workers = search) | vision/code/files/search/default |
| Execution mode | Parallel only | Parallel or pipeline |
| File attachments | Not supported | Preloaded + tool-based |
| Preflight | None | LLM analyzes question |
</details>
