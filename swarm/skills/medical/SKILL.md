---
name: medical
description: "Medical/health research — 5 parallel workers covering mechanism, evidence, dosing, contraindications, and guidelines, sourcing from scholarly + clinical sources with verification."
version: 1.0.0
category: research
tags: [medical, health, clinical, evidence-based]
trigger: "When the question concerns health, medicine, drugs, treatments, conditions, or clinical evidence."
related_skills: [academic, research, fact-check]
platforms: [linux, macos, windows]
triggers: [medical, health, drug, medication, treatment, symptom, condition, clinical, disease, dose]
tools: [wikipedia_search, arxiv_search, web_search, web_extract, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
team: team.json
mode: parallel
---

# Medical Research Swarm

## When to Use

Questions about health, treatments, drugs, medical conditions, or clinical evidence. Workers prioritize peer-reviewed evidence and official clinical guidance, with Wikipedia for encyclopedic grounding.

## Workflow

1. **Vera** — mechanism: how the condition or treatment works biologically.
2. **Cyrus** — evidence: what clinical trials and studies show.
3. **Romy** — dosing: recommended dosages, schedules, and administration.
4. **Ash** — contraindications: risks, interactions, who should avoid it.
5. **Zara** — guidelines: what official bodies (WHO, FDA, CDC, NICE) recommend.

All 5 run in parallel. Each worker verifies across multiple sources, prefers official/scholarly sources, and logs every finding + source URL with scratchpad_add. The orchestrator synthesizes the final answer with citations. The swarm is for research and does not give personalized medical advice.

## Team

| Agent | Model | Angle |
|-------|-------|-------|
| Vera | gpt-oss:120b-cloud | Mechanism — how it works |
| Cyrus | nemotron-3-nano:30b-cloud | Evidence — trials, studies, outcomes |
| Romy | gemma4:31b-cloud | Dosing — doses, schedules, administration |
| Ash | deepseek-v4-flash:cloud | Contraindications — risks, warnings |
| Zara | gpt-oss:120b-cloud | Guidelines — WHO, FDA, CDC, NICE |

## Running under swarm

```bash
python3 -m swarm --skill medical --goal "What is the evidence for [treatment]?"
```

## Running under Hermes

Delegate 5 parallel research tasks (one per angle above) with arxiv_search, wikipedia_search, web_search, and web_extract tools. Prefer official clinical guidance and peer-reviewed sources. Collect and synthesize with citations. Flag any personalized-medical-advice limits.
