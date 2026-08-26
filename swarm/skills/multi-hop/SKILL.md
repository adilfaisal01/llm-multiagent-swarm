---
name: multi-hop
description: "Multi-hop reasoning — questions that require chaining facts across multiple sources (A implies B, B implies C). Uses pipeline mode so each worker builds on the previous one's findings."
version: 1.0.0
category: research
tags: [multi-hop, reasoning, chain, pipeline, inference]
trigger: "When the question requires chaining multiple facts or inferences across sources to reach the answer."
related_skills: [research, default, fact-check]
platforms: [linux, macos, windows]
triggers: [multi-hop, chain, infer, deduce, connect, link, relationship, who is the, what connects]
tools: [web_search, web_extract, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
mode: pipeline
---

# Multi-Hop Reasoning

## When to Use

Questions that cannot be answered in one search — they require chaining facts across multiple sources. Example: "Who is the CEO of the company that acquired the startup founded by the person who wrote X?" Each hop is a separate search that feeds the next.

## Workflow

The swarm runs in PIPELINE mode. Each worker depends on the previous worker's output:

1. **Worker 0** — identifies the FIRST hop: the most concrete, searchable fact in the question. Searches and extracts it.
2. **Worker 1** (depends_on: 0) — takes Worker 0's finding, identifies the SECOND hop, searches and extracts it.
3. **Worker 2** (depends_on: 1) — takes Worker 1's finding, identifies the THIRD hop, searches and extracts it.
4. **Worker 3** (depends_on: 2) — continues the chain.
5. **Worker 4** (depends_on: 3) — completes the chain and assembles the final answer.

Each worker MUST use the previous worker's output as the starting point for its own search. Log every hop's finding and source URL with scratchpad_add. The orchestrator synthesizes the chained answer with citations.

## Running under swarm

```bash
python3 -m swarm --skill multi-hop --goal "Who is the CEO of the company that acquired the startup founded by the creator of Linux?"
```

## Running under Hermes

Delegate a chain of sequential tasks, passing each task's output as the input to the next. Start with the most concrete searchable fact and work backward through the chain.
