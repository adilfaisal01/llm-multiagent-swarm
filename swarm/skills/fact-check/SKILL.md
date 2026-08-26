---
name: fact-check
description: "Verify claims against multiple authoritative sources — 5 parallel workers each independently check a claim, cross-reference sources, flag contradictions, and produce a verdict with confidence + credibility-weighted citations."
version: 1.0.0
category: research
tags: [fact-check, verification, claims, credibility, multi-agent, parallel]
trigger: "When verifying whether a claim, statement, statistic, or news item is true, false, or misleading."
related_skills: [research, search, default]
platforms: [linux, macos, windows]
triggers: [fact-check, verify, is it true, debunk, claim, rumor, misinformation, accurate, correct]
tools: [web_search, web_extract, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
team: team.json
mode: parallel
---

# Fact-Check Swarm

## When to Use

Verify a claim, statement, statistic, or news item. The swarm deploys 5 parallel workers, each independently checking the claim from a different angle, then the orchestrator produces a verdict with confidence level and credibility-weighted citations.

## Workflow

1. **Vera** finds the ORIGINAL SOURCE — where the claim originated, who said it, in what context.
2. **Cyrus** checks PRIMARY SOURCES — official records, government data, peer-reviewed papers, the original study.
3. **Romy** checks REPUTABLE SECONDARY SOURCES — established news outlets, fact-checking organizations (Snopes, PolitiFact, Reuters Fact Check).
4. **Ash** hunts for CONTRADICTIONS — sources that dispute the claim, retractions, corrections, debunking.
5. **Zara** assesses the CLAIM'S PRECISION — is the claim a precise restatement of the source, or a distortion (cherry-picking, missing context, overgeneralization)?

All 5 run in parallel. Each worker logs findings with source URLs via scratchpad_add. The orchestrator weighs source credibility (domain authority + corroboration) and produces a verdict: TRUE / MOSTLY TRUE / MIXED / MOSTLY FALSE / FALSE / UNVERIFIABLE, with a confidence level and the key evidence.

## Team

| Agent | Model | Angle |
|-------|-------|-------|
| Vera | gpt-oss:120b-cloud | Original source — who said it, context |
| Cyrus | nemotron-3-nano:30b-cloud | Primary sources — official records, studies |
| Romy | gemma4:31b-cloud | Secondary sources — news, fact-checkers |
| Ash | deepseek-v4-flash:cloud | Contradictions — disputes, retractions, debunks |
| Zara | gpt-oss:120b-cloud | Precision — exact vs distorted restatement |

## Customizing the team

Edit `team.json` in this folder to change workers, models, angles, or prompts. Copy this folder to `swarm/skills/fact-check-<topic>/`, update the `name` field in `SKILL.md`, and run with `--skill fact-check-<topic>` for a domain-specific verification pack.

## Running under swarm

```bash
python3 -m swarm --skill fact-check --goal "Is it true that [claim]?"
```

## Running under Hermes

Delegate 5 parallel verification tasks using the team roster above (one per angle), each with web search + extract tools. Collect the 5 reports and synthesize a verdict yourself, or use the swarm directly via `--skill fact-check` for the full pipeline.
