---
name: research
description: "Thorough general research — 5 parallel workers with distinct angles (origins, money, implications, controversies, technical), multi-source verification, citation discipline, and contradiction logging."
version: 1.0.0
category: research
tags: [research, multi-agent, parallel, general]
trigger: "When researching an open-ended question across multiple sources and perspectives."
related_skills: [lightweight-swarm, reverse-engineering, default]
platforms: [linux, macos, windows]
triggers: [research, investigate, compare, overview, analysis, deep-dive]
tools: [web_search, web_extract, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
team: team.json
mode: parallel
---

# Research Swarm

## When to Use

Open-ended research questions that benefit from multiple perspectives and thorough multi-source verification. The shipped team covers origins, money, implications, controversies, and technical detail in parallel.

## Workflow

1. **Vera** traces origins — timelines, history, what happened.
2. **Cyrus** follows the money — players, financial engineering, who benefits.
3. **Romy** analyzes implications — consequences, who wins/loses, where this is heading.
4. **Ash** surfaces controversies — alternate angles, counter-narratives, criticisms.
5. **Zara** covers technical details — architecture, implementation, how it works.

All 5 run in parallel. Each worker verifies across multiple sources, cites what it finds, and logs contradictions to the scratchpad. The orchestrator synthesizes the final answer.

## Team

| Agent | Model | Angle |
|-------|-------|-------|
| Vera | gpt-oss:120b-cloud | Origins — timelines, history |
| Cyrus | nemotron-3-nano:30b-cloud | Money — players, financial engineering |
| Romy | gemma4:31b-cloud | Implications — consequences, who wins/loses |
| Ash | deepseek-v4-flash:cloud | Controversies — alternate angles, counter-narratives |
| Zara | gpt-oss:120b-cloud | Technical — architecture, implementation |

## Customizing the team

Edit `team.json` in this folder to change workers, models, angles, or prompts. Copy this folder to `swarm/skills/research-<topic>/`, update the `name` field in `SKILL.md`, and run with `--skill research-<topic>` for a domain-specific research pack.

## Running under swarm

```bash
python3 -m swarm --skill research --goal "Your research question"
```

## Running under Hermes

Delegate 5 parallel tasks using the team roster above (one per angle), each with web search + extract tools. Collect the 5 reports and synthesize them yourself, or use the swarm directly via `--skill research` for the full pipeline.
