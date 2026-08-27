# Demo Version

The original pre-modular swarm is preserved in `demo-swarm/` for reference,
testing, and research:

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

The pre-modular root monoliths (`swarm2.py`, `swarm.py`) are preserved in
`legacy/` for historical reference. They are not imported by the package and
are not maintained.
