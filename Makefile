.PHONY: help test test-unit test-pytest test-tools test-tool-unit test-skills test-summary test-e2e test-ci act clean

PYTHON ?= python3
PYTEST ?= $(PYTHON) -m pytest

# Verbosity flag: default is quiet (compact one-liner per module).
#   V=1  grouped colored summary (per-suite / per-test breakdown)
#   V=2  raw per-test trace (unittest -v / pytest -vv)
V ?=
VFLAGS = $(if $(filter 1,$(V)),-v,$(if $(filter 2,$(V)),-vv,))
UTFLAGS = $(if $(filter 1,$(V)),-v,$(if $(filter 2,$(V)),-v,))
PTFLAGS = $(if $(filter 1,$(V)),-v,$(if $(filter 2,$(V)),-vv,))

help:
	@echo "Swarm test targets:"
	@echo "  make test        - organized summary + tool smoke tests (default)"
	@echo "  make test-unit   - python3 -m unittest discover tests/"
	@echo "  make test-pytest - pytest tests/"
	@echo "  make test-tools  - tool smoke tests (test_tools.py --skip-swarm)"
	@echo "  make test-tool-unit - hermetic per-tool tests (tests/test_tools.py, mocked network)"
	@echo "  make test-skills - skill system unit tests only"
	@echo "  make test-summary- organized grouped summary with pass/fail colors"
	@echo "  make test-ci     - mirror GitHub Actions CI exactly"
	@echo "  make test-e2e    - Ollama-dependent end-to-end tests (needs Ollama)"
	@echo "  make act         - run GitHub Actions locally via act (3.11 + 3.12)"
	@echo "  make clean       - pycache, stray swarm_*.md, test-results/"
	@echo ""
	@echo "  Verbosity: append V=1 (grouped summary) or V=2 (raw trace). Default is quiet."

test: test-tools test-summary

test-unit:
	$(PYTHON) -m unittest discover $(UTFLAGS) tests/

test-pytest:
	$(PYTEST) tests/ $(PTFLAGS)

test-tools:
	$(PYTHON) test_tools.py --skip-swarm

test-tool-unit:
	$(PYTHON) tests/summary_runner.py $(VFLAGS) tests.test_tools

test-skills:
	$(PYTHON) tests/summary_runner.py $(VFLAGS) tests.test_skills

test-summary:
	$(PYTHON) tests/summary_runner.py $(VFLAGS)

test-ci:
	pip install -e ".[dev]"
	$(PYTHON) -m py_compile $$(find swarm -name '*.py')
	$(PYTHON) -c "from swarm import run_swarm; print('core import ok')"
	$(PYTHON) -c "from swarm.tui import run_tui; print('tui import ok')"
	$(PYTHON) test_tools.py --skip-swarm
	$(PYTHON) -m unittest discover tests/
	$(PYTEST) tests/

test-e2e:
	SWARM_E2E=1 $(PYTHON) -m unittest tests.test_e2e $(UTFLAGS)

act:
	act -j test --matrix python-version:"3.11"
	act -j test --matrix python-version:"3.12"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -f swarm_*.md
	rm -rf test-results/
