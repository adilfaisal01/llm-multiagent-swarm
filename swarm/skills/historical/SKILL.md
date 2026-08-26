---
name: historical
description: "Historical research — 5 parallel workers covering timeline, origins, key figures, causation, and historiography, using archived sources to verify how events were reported at the time."
version: 1.0.0
category: research
tags: [history, historical, timeline, origins]
trigger: "When the question concerns history, the past, how something changed over time, or what sources said at a particular time."
related_skills: [research, academic, fact-check]
platforms: [linux, macos, windows]
triggers: [history, historical, when did, timeline, origin, evolution, over time, century, era, decade]
tools: [wayback_machine, web_search, web_extract, wikipedia_search, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
team: team.json
mode: parallel
---

# Historical Research Swarm

## When to Use

Questions about the past: timelines, origins, how something changed over time, or how events were reported when they happened. Workers use archived snapshots (wayback_machine) to verify historical source text and distinguish primary accounts from later retellings.

## Workflow

1. **Vera** — timeline: the key dates and sequence of events.
2. **Cyrus** — origins: where the thing started and how it developed.
3. **Romy** — key figures: the people who shaped it.
4. **Ash** — causation: why it happened, what drove the changes.
5. **Zara** — historiography: how accounts of it have changed over time.

All 5 run in parallel. Each worker uses wayback_machine and web sources to verify contemporaneous reports, distinguishes primary from secondary accounts, and logs every finding + source URL with scratchpad_add. The orchestrator synthesizes the final answer with citations.

## Running under swarm

```bash
python3 -m swarm --skill historical --goal "How has the public debate about [topic] changed over the last 30 years?"
```

## Running under Hermes

Delegate 5 parallel research tasks (one per angle above) with wayback_machine, web_search, web_extract, and wikipedia_search tools. Emphasize contemporaneous sources and archived pages. Collect and synthesize with citations.
