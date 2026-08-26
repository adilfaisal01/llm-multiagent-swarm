---
name: translate
description: "Translation swarm — 5 parallel workers each translate independently from different angles (literal, idiomatic, cultural notes, back-translation check, glossary) and the orchestrator picks the most faithful version."
version: 1.0.0
category: research
tags: [translate, translation, language, localization]
trigger: "When the question asks to translate text, or to check/compare translations."
related_skills: [research, comparison]
platforms: [linux, macos, windows]
triggers: [translate, translation, how do you say, in french, in spanish, in chinese, localization]
tools: [web_search, web_extract, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
team: team.json
mode: parallel
---

# Translation Swarm

## When to Use

Questions that ask to translate a passage, or to verify/compare translations. The goal of a multi-agent translation is fidelity: the orchestrator blends independent drafts and a back-translation check into one faithful, natural result.

## Workflow

1. **Vera** — literal translation: faithful, word-accurate draft.
2. **Cyrus** — idiomatic translation: natural, fluent re-expression.
3. **Romy** — cultural notes: idioms, register, and context that don't transfer directly.
4. **Ash** — back-translation check: translates the drafts back and flags meaning drift.
5. **Zara** — glossary: fixed translations for key terms, names, and repeated phrases.

All 5 run in parallel. Workers consult web sources (bilingual references, dictionaries) when unsure, and log their drafts and notes with scratchpad_add. The orchestrator synthesizes the final translation, picking the most faithful + natural wording and flagging any ambiguous spots.

## Running under swarm

```bash
python3 -m swarm --skill translate --goal "Translate this to French and explain the nuances: [text]"
```

## Running under Hermes

Delegate 5 parallel translation tasks (one per angle above). Combine the drafts yourself, using the back-translation check to pick the most faithful version. Note that translation quality benefits from the context in the goal.
