---
name: summarize
description: "Document summarization — 5 parallel workers reading a long document or URL from different angles (key points, entities, arguments, gaps, TL;DR) and assembling a comprehensive summary."
version: 1.0.0
category: research
tags: [summarize, document, digest, abstract]
trigger: "When the question asks to summarize a long document, article, paper, or text."
related_skills: [academic, research, files]
platforms: [linux, macos, windows]
triggers: [summarize, summary, digest, tl;dr, key points, main points, overview of this]
tools: [read_file, pdf_extract, web_extract, python_exec, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
team: team.json
mode: parallel
---

# Summarization Swarm

## When to Use

Questions that ask to summarize a long document, article, paper, or report — either an attached file (txt, md, PDF) or a URL. Workers each read the document from a different angle so the combined summary is complete.

## Workflow

1. **Vera** — key points: the core claims and structure.
2. **Cyrus** — entities: the people, organizations, products, and dates.
3. **Romy** — arguments: the reasoning, evidence, and conclusions.
4. **Ash** — gaps: what is missing, ambiguous, or unsupported.
5. **Zara** — TLDR: a condensed one-paragraph version.

All 5 run in parallel. Each worker reads the document with read_file / pdf_extract / web_extract, quotes the most important passages, and logs findings with scratchpad_add. The orchestrator synthesizes a comprehensive summary with citations.

## Running under swarm

```bash
python3 -m swarm --skill summarize --goal "Summarize the key points of /path/to/report.pdf"
python3 -m swarm --skill summarize --goal "Summarize this article: https://example.com/article"
```

## Running under Hermes

Delegate 5 parallel summarization tasks (one per angle above), each reading the full document. Collect the angle summaries and assemble a single coherent summary, or use the swarm directly via `--skill summarize`.
