---
name: search
description: "Fast web search only — no scratchpad. Use for simple fact lookups where a quick authoritative answer suffices."
version: 1.0.0
category: research
tags: [search, fact-lookup, fast]
trigger: "When the question is a simple fact lookup that needs a quick authoritative answer."
related_skills: [default, research]
platforms: [linux, macos, windows]
triggers: [fact, lookup, quick, definition, who, what, when]
tools: [web_search, web_extract]
recommended_model: nemotron-3-nano:30b-cloud
---

# Search

## When to Use

Simple fact lookups where a fast, authoritative answer is enough — no scratchpad logging needed.

## Workflow

1. Search the web to find relevant information. Use web_search and web_extract.
2. This skill does NOT have scratchpad_add — only search and read URLs.
3. Focus on finding authoritative sources quickly. State the answer clearly at the top.
4. Cite the best sources you found. Avoid unverified claims.

## Running under swarm

```bash
python3 -m swarm --goal "What year was the Eiffel Tower built?"
```

## Running under Hermes

Delegate a single fact-lookup task with web search + extract tools, asking for the answer at the top with cited sources.
