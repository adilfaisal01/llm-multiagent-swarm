# Testing Workflow

This is the canonical guide for running the swarm test suite. The Makefile is the entry point; every `test-*` target accepts a verbosity flag.

## Verbosity flag

All `test-*` targets accept `V` to control output detail. Default is **quiet** (compact one-liner per module).

| Level | Output |
|-------|--------|
| *(none)* | One compact line per module: `PASS tests.test_tools  (37 ✓, 0 ✗, 0 skipped)` |
| `V=1` | Grouped colored summary — module header + per-suite + per-test `✓`/`✗`/`⏭` breakdown |
| `V=2` | Raw per-test trace (`unittest -v` / `pytest -vv`) for full debugging detail |

```bash
make test-tool-unit        # quiet
make test-tool-unit V=1    # grouped summary
make test-tool-unit V=2    # raw trace
```

## Make targets

| Target | What it runs | Notes |
|--------|-------------|-------|
| `make test` | `test-tools` + `test-summary` | Default entry point |
| `make test-summary` | All hermetic suites via `tests/summary_runner.py` | Grouped, colored, quiet by default |
| `make test-tool-unit` | `tests.test_tools` via summary runner | Hermetic per-tool tests (mocked network/Ollama) |
| `make test-skills` | `tests.test_skills` via summary runner | Skill system unit tests |
| `make test-tools` | `test_tools.py --skip-swarm` | Live smoke (real ddgs + Ollama) |
| `make test-unit` | `unittest discover tests/` | Full hermetic suite, dots output |
| `make test-pytest` | `pytest tests/` | Same suite via pytest |
| `make test-ci` | Mirror GitHub Actions CI exactly | Installs deps, compiles, imports, runs all |
| `make test-e2e` | `tests.test_e2e` | Ollama-dependent end-to-end (needs Ollama running) |

## Per-tool / per-skill slices (live smoke)

`test_tools.py` supports slicing to a single skill or tool:

```bash
python3 test_tools.py --skill vision        # only the tools a skill grants
python3 test_tools.py --skill code --skip-swarm
python3 test_tools.py --tool web_search     # only one tool
python3 test_tools.py --verbose             # show full tool outputs
python3 test_tools.py --samples=100        # bigger test files
```

## Hermetic per-tool suite

`tests/test_tools.py` exercises every tool in isolation with all network and
Ollama calls mocked — it runs offline and is the fastest feedback loop during
tool or skill development:

```bash
make test-tool-unit          # quiet summary
make test-tool-unit V=1      # grouped per-tool breakdown
python3 -m unittest tests.test_tools -v   # raw trace
```

It also includes a skill-coverage matrix that verifies every skill's declared
tools resolve to real `BaseTool` instances (catches stale `SKILL.md` references).

## Chaos monkey

Adversarial CLI tests (empty goal, unicode, SQL injection, missing config, etc.):

```bash
bash chaos_monkey.sh         # 15 chaos monkey tests
```

## CI

`.github/workflows/ci.yml` runs on every push to `main`/`feature/*` and on PRs:

- Matrix: Python 3.11, 3.12
- Compiles all `swarm/**/*.py`
- Checks core + TUI imports
- Runs `test_tools.py --skip-swarm`
- Runs `python3 -m unittest discover tests/`
- Runs `pytest tests/`

Mirror it locally with `make test-ci`.

## Auto-testing on commit

A post-commit git hook runs chaos monkey + benchmark after every commit:

- Results saved to `test-results/<commit-hash>/`
- Files: `chaos_monkey.txt`, `benchmark.txt`, `run.log`
- `test-results/` is gitignored

Install with `bash setup-hooks.sh` (run once after cloning).
