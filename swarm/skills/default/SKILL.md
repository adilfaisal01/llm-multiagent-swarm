---
name: default
description: "General research fallback — web search + extract + scratchpad. Used when no more specific skill fits."
version: 1.0.0
category: research
tags: [research, fallback, general]
trigger: "When no more specific skill applies to the question."
related_skills: [research, search]
platforms: [linux, macos, windows]
triggers: [general, fallback, default]
tools: [web_search, web_extract, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
---

# Default Research

## When to Use

Fallback skill when preflight cannot confidently classify the question into a more specific skill.

## Workflow

1. Search the web to find relevant information. Use web_search and web_extract.
2. For EVERY search result, use scratchpad_add to log raw facts, quotes, numbers, and source URLs you find.
3. After collecting data, state the answer CLEARLY at the TOP of your response.
4. Then explain your reasoning and cite your sources.
5. If you find conflicting information, note it and explain why you chose one answer.
6. Be precise. Exact names, exact numbers, exact dates.
7. Keep searching until you're confident in the answer.

## Running under swarm

```bash
python3 -m swarm --goal "Your question"
```

## Running under Hermes

Delegate a single research task with web search + extract tools, instructing the worker to log findings and state the answer at the top of its response.
