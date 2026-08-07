---
name: vision
description: "Has read_image tool — use for questions with image attachments (.png/.jpg). Best model: gemma4:31b-cloud (multimodal)."
version: 1.0.0
category: research
tags: [vision, image, multimodal]
trigger: "When the question involves an image attachment that must be read."
related_skills: [files, code]
platforms: [linux, macos, windows]
triggers: [image, png, jpg, screenshot, diagram, chart, photo]
tools: [read_image, web_search, web_extract, scratchpad_add]
recommended_model: gemma4:31b-cloud
---

# Vision

## When to Use

Questions with image attachments (.png/.jpg) that must be read and analyzed.

## Workflow

1. CALL read_image NOW with the ATTACHED FILE path.
2. After reading the image, use scratchpad_add to log the raw data.
3. If you need to look something up, use web_search and web_extract.
4. Then state the answer CLEARLY at the TOP of your response.
5. Then explain your reasoning.
6. NEVER guess the file contents. You MUST call read_image.
7. Be precise. Exact names, exact numbers, exact dates.

## Running under swarm

```bash
python3 -m swarm --goal "Read this image [ATTACHED IMAGE: /path/to/image.png] and describe it"
```

## Running under Hermes

Delegate a task with the vision toolset, passing the image path and asking for a precise read of its contents.
