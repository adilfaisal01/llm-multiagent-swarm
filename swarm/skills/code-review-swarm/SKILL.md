---
name: code-review-swarm
description: "Code review — 5 parallel workers reviewing code from different lenses (correctness, style, security, performance, testability), reading the file and cross-checking best practices online."
version: 1.0.0
category: code
tags: [code-review, code, security, quality]
trigger: "When the question asks to review, critique, or improve a piece of code."
related_skills: [code, code-debug, files]
platforms: [linux, macos, windows]
triggers: [review code, code review, critique, is this code, improve this code, check my code, audit]
tools: [read_file, python_exec, web_search, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
team: team.json
mode: parallel
---

# Code Review Swarm

## When to Use

Questions that ask to review, critique, or debug a piece of code. Workers each read the code file and review it from a different lens, so the combined review covers correctness, style, security, performance, and testability.

## Workflow

1. **Vera** — correctness: does it do what it's supposed to, edge cases, bugs.
2. **Cyrus** — style: readability, naming, structure, idioms.
3. **Romy** — security: injection, unsafe calls, secrets, input validation.
4. **Ash** — performance: algorithmic complexity, wasted work, hot spots.
5. **Zara** — testability: how to test it, missing tests, refactor suggestions.

All 5 run in parallel. Each worker reads the file with read_file, may run/verify with python_exec, consults best practices via web_search when useful, and logs findings with scratchpad_add. The orchestrator synthesizes an ordered, prioritized review.

## Running under swarm

```bash
python3 -m swarm --skill code-review-swarm --goal "Review /path/to/code.py for bugs, security, and style"
```

## Running under Hermes

Delegate 5 parallel review tasks (one per lens above), each reading the code file. Collect the five reports and merge into a prioritized review, or use the swarm directly via `--skill code-review-swarm`.
