---
name: reverse-engineering
description: "Drop an obfuscated payload and 5 parallel AI agents deobfuscate it, trace C2 endpoints, check threat intel, and produce a full report."
version: 1.0.0
category: security
tags: [reverse-engineering, malware, security, multi-agent, parallel]
trigger: "When analyzing an obfuscated or suspicious file (JS, binary, script) and needing deobfuscation, C2 tracing, and threat attribution."
related_skills: [lightweight-swarm, research]
platforms: [linux, macos, windows]
triggers: [obfuscated, malware, payload, c2, deobfuscation, base64, xor, threat]
tools: [python_exec, web_search, web_extract, read_file, read_image, scratchpad_add]
recommended_model: gpt-oss:120b-cloud
team: team.json
mode: parallel
---

# Reverse Engineering Swarm

## When to Use

Drop an obfuscated payload into `samples/` and the swarm deploys 5 parallel workers to deobfuscate it, trace C2 endpoints, check threat intel, and produce a full report in under 2 minutes.

## Workflow

1. **Vera** breaks the encoding layers (base64, XOR, string reversal) using python_exec.
2. **Cyrus** traces the data flow and extracts C2 endpoints using python_exec.
3. **Ash** searches threat intel databases to confirm/debunk attribution using web_search.
4. **Zara** produces clean deobfuscated code with commentary using python_exec + read_file.
5. **Romy** explains the kill chain and impact using scratchpad_add.

All 5 run in parallel. The orchestrator synthesizes the final report.

## Team

| Agent | Model | Role | Tools |
|-------|-------|------|-------|
| Vera | gpt-oss:120b-cloud | Structure & encoding | python_exec |
| Cyrus | nemotron-3-nano:30b-cloud | Network & exfil | python_exec |
| Ash | deepseek-v4-flash:cloud | Threat attribution | web_search |
| Zara | gpt-oss:120b-cloud | Deobfuscation | python_exec + read_file |
| Romy | gemma4:31b-cloud | Impact analysis | scratchpad_add |

## Running under swarm

```bash
python3 -m swarm --skill reverse-engineering \
  --goal "Reverse engineer this obfuscated payload at /path/to/payload.js. Use your tools. Do NOT guess."
```

## Running under Hermes

Delegate 5 parallel tasks using the team roster above (one per role), each with the appropriate tools (python_exec for Vera/Cyrus/Zara, web_search for Ash, scratchpad for Romy). Collect the 5 reports and synthesize them yourself, or use the swarm directly via `--skill reverse-engineering` for the full pipeline.
