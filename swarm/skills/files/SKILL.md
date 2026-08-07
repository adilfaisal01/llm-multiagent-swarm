---
name: files
description: "Has read_file and read_image tools — use for data files (.docx, .xlsx, .csv, .txt, .json, .xml). Best model: gpt-oss:120b-cloud."
version: 1.0.0
category: research
tags: [files, data, spreadsheet, document]
trigger: "When the question involves attached data files that must be read."
related_skills: [vision, code]
platforms: [linux, macos, windows]
triggers: [file, csv, xlsx, docx, json, txt, spreadsheet, data-file]
tools: [read_file, read_image, web_search, web_extract, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
---

# Files

## When to Use

Questions with attached data files (.docx, .xlsx, .csv, .txt, .json, .xml) that must be read and analyzed.

## Workflow

1. CALL read_file or read_image NOW with the ATTACHED FILE path.
2. After reading the file, use scratchpad_add to log the raw data.
3. Use web_search and web_extract if you need to look up additional context.
4. Then state the answer CLEARLY at the TOP of your response.
5. Then explain your reasoning.
6. NEVER guess the file contents. You MUST call read_file or read_image.
7. Be precise. Exact names, exact numbers, exact dates.

## Running under swarm

```bash
python3 -m swarm --goal "Summarize this spreadsheet [ATTACHED FILE: /path/to/data.xlsx]"
```

## Running under Hermes

Delegate a task with the file-reading toolset, passing the file path and asking for a precise read of its contents.
