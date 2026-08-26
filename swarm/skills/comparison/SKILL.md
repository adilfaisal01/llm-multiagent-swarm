---
name: comparison
description: "Side-by-side comparison — products, tools, frameworks, plans, or options. Each worker researches one option in depth; the orchestrator builds a comparison table with criteria, pros/cons, and a recommendation."
version: 1.0.0
category: research
tags: [comparison, compare, vs, alternatives, options, pros-cons]
trigger: "When the question asks to compare two or more options (products, tools, frameworks, plans, services)."
related_skills: [research, default, fact-check]
platforms: [linux, macos, windows]
triggers: [compare, comparison, vs, versus, alternatives, which is better, pros and cons, difference between]
tools: [web_search, web_extract, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
---

# Comparison

## When to Use

Questions that ask to compare two or more options — products, tools, frameworks, plans, or services. Each worker researches one option in depth; the orchestrator builds a side-by-side comparison.

## Workflow

1. **Worker 0** — researches option A in depth: features, pricing, strengths, weaknesses, reviews.
2. **Worker 1** — researches option B in depth: features, pricing, strengths, weaknesses, reviews.
3. **Worker 2** — researches option C (if a third option is named) or the general category landscape.
4. **Worker 3** — finds real-world usage, benchmarks, and user reviews for all options.
5. **Worker 4** — finds pricing, licensing, and total-cost-of-ownership details for all options.

All 5 run in parallel. Each worker logs findings with source URLs via scratchpad_add. The orchestrator builds a comparison table (criteria × options), lists pros/cons per option, and gives a recommendation with reasoning and citations.

## Running under swarm

```bash
python3 -m swarm --skill comparison --goal "Compare Python vs Go for building a CLI tool."
```

## Running under Hermes

Delegate one research task per option (features, pricing, reviews), then synthesize a comparison table yourself, or use the swarm directly via `--skill comparison` for the full pipeline.
