---
name: data-analysis
description: "Data analysis — pipeline mode: load a data file, profile it, compute statistics, find patterns, and summarize. Runs sequentially so each stage builds on the previous one's output."
version: 1.0.0
category: data
tags: [data-analysis, statistics, csv, spreadsheet, analysis, pipeline]
trigger: "When the question involves analyzing a dataset — statistics, aggregations, patterns, or trends in a data file."
related_skills: [files, code, finance]
platforms: [linux, macos, windows]
triggers: [analyze data, data, statistics, average, trend, distribution, dataset, csv analysis, pivot]
tools: [read_file, sql_query, python_exec, regex_extract, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
team: team.json
mode: pipeline
---

# Data Analysis Swarm

## When to Use

Questions that require analyzing a dataset: computing statistics, aggregations, patterns, or trends from a data file (CSV, XLSX, JSON, SQLite DB). Use PIPELINE mode so each stage builds on the previous one's findings.

## Workflow

Run in PIPELINE mode — each worker depends on the previous worker's output:

1. **Worker 0** — load & profile: read the data file, describe its shape (columns, types, row count, missing values).
2. **Worker 1** (depends_on: 0) — clean & aggregate: compute summary statistics and aggregations.
3. **Worker 2** (depends_on: 1) — analyze: dig into the specific question (trends, distributions, comparisons).
4. **Worker 3** (depends_on: 2) — verify: cross-check the numbers with a second method (e.g. SQL + python).
5. **Worker 4** (depends_on: 3) — synthesize: assemble the answer, note caveats and what the data does NOT show.

Each worker MUST start from the previous worker's output, use read_file / sql_query / python_exec to compute (NEVER estimate), and log key numbers with scratchpad_add. The orchestrator synthesizes the final answer.

## Running under swarm

```bash
python3 -m swarm --skill data-analysis --goal "Analyze the attached sales.csv: average revenue per region and growth trend"
```

## Running under Hermes

Delegate a chain of sequential tasks, passing each stage's output to the next: profile the file, compute statistics, drill down, verify with an independent method, then synthesize.
