---
name: code-debug
description: "Has python_exec + read_file tools — use for debugging code, tracing errors, and fixing bugs. Best model: deepseek-v4-flash."
version: 1.0.0
category: code
tags: [debug, code, bug, error, traceback, fix]
trigger: "When the question involves debugging code, understanding an error/traceback, or fixing a bug."
related_skills: [code, files, reverse-engineering]
platforms: [linux, macos, windows]
triggers: [debug, bug, error, traceback, exception, crash, fix, broken, stack-trace]
tools: [python_exec, read_file, web_search, web_extract, scratchpad_add]
recommended_model: deepseek-v4-flash:cloud
---

# Code Debug

## When to Use

Questions involving debugging code, understanding an error or traceback, or fixing a bug. The worker reads the code, reproduces the error, isolates the cause, and proposes a fix.

## Workflow

1. If there is an attached file, CALL read_file NOW to get the code.
2. CALL python_exec to REPRODUCE the error. Do NOT guess the cause.
3. Isolate the failing line/expression. Log the error and your hypothesis with scratchpad_add.
4. Use web_search and web_extract to look up the error message, library docs, or known issues.
5. Then state the ROOT CAUSE CLEARLY at the TOP of your response.
6. Then give the FIX with corrected code, and explain why it works.
7. NEVER guess the cause. You MUST call python_exec to reproduce the error.
8. Be precise. Quote the exact error message and the exact fix.

## Running under swarm

```bash
python3 -m swarm --goal "Debug this code [ATTACHED FILE: /path/to/buggy.py]. It crashes with IndexError."
```

## Running under Hermes

Delegate a debugging task with the code-execution + file-reading toolset, instructing the worker to reproduce the error before proposing a fix.
