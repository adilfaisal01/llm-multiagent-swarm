---
name: debate
description: "Debate / pro-con analysis — 5 parallel workers build the strongest case for, strongest case against, surface assumptions, grade evidence, and weigh a conclusion for balanced subjective questions."
version: 1.0.0
category: research
tags: [debate, pro-con, subjective, arguments]
trigger: "When the question is subjective or contested — should we, is X better than Y, is X worth it, does X work — and deserves a balanced argument map."
related_skills: [research, comparison, fact-check]
platforms: [linux, macos, windows]
triggers: [debate, should we, is it worth, pros and cons, for and against, argue, contested, opinion, stance]
tools: [web_search, web_extract, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
team: team.json
mode: parallel
---

# Debate Swarm

## When to Use

Subjective or contested questions that deserve a balanced treatment rather than a single answer: "Should we adopt X?", "Is X worth the cost?", "Was X justified?", "Which side is stronger?" The swarm builds both sides of the argument with evidence, then weighs them.

## Workflow

1. **Vera** — the case FOR: the strongest arguments and evidence supporting the proposition.
2. **Cyrus** — the case AGAINST: the strongest arguments and evidence opposing it.
3. **Romy** — assumptions: the implicit premises each side relies on.
4. **Ash** — evidence quality: how solid is the evidence on each side, and where is it weak.
5. **Zara** — weighing: how the arguments balance, and a nuanced conclusion.

All 5 run in parallel. Each worker gathers real evidence with web_search/web_extract, attributes claims to sources, and logs findings with scratchpad_add. The orchestrator synthesizes a balanced, cited argument map rather than a one-sided verdict.

## Running under swarm

```bash
python3 -m swarm --skill debate --goal "Should remote work become the default for software companies?"
```

## Running under Hermes

Delegate 5 parallel research tasks (one per role above) with web_search and web_extract. Assemble both sides of the argument with evidence and weigh them into a nuanced synthesis rather than a binary verdict.
