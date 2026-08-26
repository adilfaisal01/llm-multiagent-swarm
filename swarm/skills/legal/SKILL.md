---
name: legal
description: "Legal research — 5 parallel workers covering statutes, case law, precedent, jurisdiction, and recent rulings, sourcing from web + archived sources with verification."
version: 1.0.0
category: research
tags: [legal, law, statutes, case-law, regulatory]
trigger: "When the question concerns laws, statutes, regulations, court cases, legal precedent, or compliance."
related_skills: [research, fact-check, academic]
platforms: [linux, macos, windows]
triggers: [law, legal, statute, regulation, court, case, precedent, lawsuit, compliance, rights]
tools: [web_search, web_extract, wayback_machine, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
team: team.json
mode: parallel
---

# Legal Research Swarm

## When to Use

Questions about laws, regulations, court decisions, legal precedent, or regulatory compliance. Workers prefer primary legal sources (statutes, court opinions, official records) and use archived snapshots to verify historical law text.

## Workflow

1. **Vera** — statutes: the relevant laws, acts, and regulations verbatim.
2. **Cyrus** — case law: landmark court decisions and holdings.
3. **Romy** — precedent: how courts have interpreted the law over time.
4. **Ash** — jurisdiction: which jurisdiction applies, venue, and conflicts.
5. **Zara** — recent: latest rulings, amendments, and pending changes.

All 5 run in parallel. Each worker verifies against primary sources (official statute and court sites), uses wayback_machine to check archived or amended text, and logs every finding + source URL with scratchpad_add. The orchestrator synthesizes the final answer with citations.

## Team

| Agent | Model | Angle |
|-------|-------|-------|
| Vera | gpt-oss:120b-cloud | Statutes — the text of the law itself |
| Cyrus | nemotron-3-nano:30b-cloud | Case law — leading decisions and holdings |
| Romy | gemma4:31b-cloud | Precedent — how the rule has been interpreted |
| Ash | deepseek-v4-flash:cloud | Jurisdiction — what applies, conflicts |
| Zara | gpt-oss:120b-cloud | Recent — latest rulings and amendments |

## Running under swarm

```bash
python3 -m swarm --skill legal --goal "What are the current US federal rules on [topic]?"
```

## Running under Hermes

Delegate 5 parallel research tasks (one per angle above), each with web_search, web_extract, and wayback_machine tools. Emphasize primary sources: statute texts, court opinions, and official records. Collect and synthesize with citations.
