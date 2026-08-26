---
name: academic
description: "Scholarly research — 5 parallel workers covering methodology, related work, results, limitations, and replication, sourcing from arXiv, Wikipedia, and web sources with PDF extraction."
version: 1.0.0
category: research
tags: [academic, scholarly, arxiv, papers, research-methods]
trigger: "When the question concerns academic literature, research findings, methodology, or scholarly sources."
related_skills: [research, fact-check, default]
platforms: [linux, macos, windows]
triggers: [paper, study, academic, research, journal, methodology, citation, published]
tools: [wikipedia_search, arxiv_search, web_search, web_extract, pdf_extract, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
team: team.json
mode: parallel
---

# Academic Research Swarm

## When to Use

Questions about published research, papers, methodologies, or scholarly findings. Workers lean on arXiv (preprints/papers), Wikipedia (encyclopedic grounding), and open web sources, extracting PDFs where available.

## Workflow

1. **Vera** — methodology: how was the research conducted, design, sample, controls.
2. **Cyrus** — findings: what did the studies conclude, effect sizes, headline results.
3. **Romy** — related work: what else exists, seminal papers, competing approaches.
4. **Ash** — limitations: caveats, weaknesses, replication status, contradictions.
5. **Zara** — context: how the findings fit the wider field, open questions.

All 5 run in parallel. Each worker searches arXiv and the open web, extracts PDFs when relevant, verifies across multiple sources, and logs every finding + source URL with scratchpad_add. The orchestrator synthesizes the final answer with citations.

## Team

| Agent | Model | Angle |
|-------|-------|-------|
| Vera | gpt-oss:120b-cloud | Methodology — study design, sample, statistics |
| Cyrus | nemotron-3-nano:30b-cloud | Findings — conclusions, effect sizes |
| Romy | gemma4:31b-cloud | Related work — other papers, competing approaches |
| Ash | deepseek-v4-flash:cloud | Limitations — caveats, weaknesses, contradictions |
| Zara | gpt-oss:120b-cloud | Context — field landscape, open questions |

## Running under swarm

```bash
python3 -m swarm --skill academic --goal "What does the recent literature say about [topic]?"
```

## Running under Hermes

Delegate 5 parallel research tasks (one per angle above) each with arxiv_search, wikipedia_search, web_search, web_extract, and pdf_extract tools. Collect the reports and synthesize with citations.
