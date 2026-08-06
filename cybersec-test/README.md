# Swarm Reverse Engineering Demo — Implementation Plan

> **For OpenCode:** Execute this plan task-by-task using the exact file paths and commands below.

**Goal:** Build a polished, demo-ready reverse engineering toolkit using the llm-multiagent-swarm — drop an obfuscated file in, 5 parallel agents deobfuscate it, trace C2 endpoints, check threat intel, and produce a full report in under 2 minutes.

**Architecture:** Docker container with host networking → Ollama cloud models → 5 parallel workers (Vera/Cyrus/Ash/Zara/Romy) with custom tool bundles → Textual TUI for live progress → markdown report output.

**Tech Stack:** Python 3.12, Textual (TUI), Ollama Cloud API, Docker, DuckDuckGo search

**Prerequisites:**
- Ollama running locally with cloud models pulled (`gpt-oss:120b-cloud`, `deepseek-v4-flash:cloud`, `nemotron-3-nano:30b-cloud`, `gemma4:31b-cloud`)
- Docker + Docker Compose installed
- `llm-multiagent-swarm` repo cloned at `/mnt/E/github-projects/llm-multiagent-swarm`

---

### Task 1: Create the Reverse Engineering Config

**Objective:** Write a swarm config that assigns each worker a specific reverse engineering role with tailored prompts and tool bundles.

**Files:**
- Create: `configs/reverse-engineering.json`

**Config structure:**
```json
{
  "team": [
    {
      "name": "Vera",
      "model": "gpt-oss:120b-cloud",
      "angle": "Structural analysis — identify encoding, obfuscation layers, control flow, and overall architecture",
      "prompt": "You are Vera, a reverse engineering specialist focused on structure and encoding. Analyze the obfuscated blob: What encoding or encryption is used? What is the control flow? How many layers of obfuscation exist? Use python_exec to decode and deobfuscate. MAIN QUESTION: {goal} YOUR ANGLE: {angle}"
    },
    {
      "name": "Cyrus",
      "model": "nemotron-3-nano:30b-cloud",
      "angle": "Data flow and network tracing — find external endpoints, C2 servers, API calls, exfiltration patterns",
      "prompt": "You are Cyrus, a network forensics specialist. Trace the data flow: What external endpoints are contacted? What data is sent/received? Are there C2 patterns? Use python_exec to extract URLs and endpoints. MAIN QUESTION: {goal} YOUR ANGLE: {angle}"
    },
    {
      "name": "Ash",
      "model": "deepseek-v4-flash:cloud",
      "angle": "Threat attribution — find signature patterns, known malware families, author fingerprints, broader context",
      "prompt": "You are Ash, a threat intelligence analyst. Identify: What known obfuscation frameworks or malware families does this resemble? Any author fingerprints? Use web_search to look up patterns. MAIN QUESTION: {goal} YOUR ANGLE: {angle}"
    },
    {
      "name": "Zara",
      "model": "gpt-oss:120b-cloud",
      "angle": "Technical deobfuscation — produce clean readable version of decoded payload with inline commentary",
      "prompt": "You are Zara, a code analysis specialist. Deobfuscate the blob and produce: A clean readable version of the decoded code. Inline comments explaining each section. Hidden functionality. Use python_exec to run deobfuscation. MAIN QUESTION: {goal} YOUR ANGLE: {angle}"
    },
    {
      "name": "Romy",
      "model": "gemma4:31b-cloud",
      "angle": "Impact analysis — explain what happens when this payload executes, who is affected, the full attack chain",
      "prompt": "You are Romy, an impact assessment specialist. Analyze: What happens when this payload executes? What's the kill chain? Who would be affected? How would you detect this? MAIN QUESTION: {goal} YOUR ANGLE: {angle}"
    }
  ],
  "default_model": "deepseek-v4-flash:cloud",
  "angles": [
    "Structural analysis — encoding, obfuscation layers, control flow",
    "Network tracing — endpoints, C2, API calls, exfiltration",
    "Threat attribution — known families, author fingerprints, context",
    "Technical deobfuscation — clean readable code with commentary",
    "Impact analysis — kill chain, affected systems, detection"
  ],
  "fallback_models": ["gpt-oss:120b-cloud", "deepseek-v4-flash:cloud"]
}
```

**Verify:** `python3 -c "import json; json.load(open('configs/reverse-engineering.json')); print('valid')"`

---

### Task 2: Create a Synthetic Demo Payload

**Objective:** Write a realistic obfuscated JavaScript payload that mimics real malware techniques (base64, XOR, string reversal, hidden C2 endpoints, sendBeacon exfil) for demo purposes.

**Files:**
- Create: `samples/obfuscated_payload.js`

**Payload requirements:**
- Layer 1: Array of base64-encoded strings
- Layer 2: XOR-decoded fallback URL from hex key
- Layer 3: `_reveal` function = atob decode + string reverse
- 4 C2 endpoints reconstructed from decoded strings
- Data collection function harvesting navigator, document, localStorage
- Dual exfil method: sendBeacon primary, Image fallback
- Heartbeat + delayed profile exfil pattern
- Wrapped in try/catch for stealth

**Verify:** `node -e "eval(require('fs').readFileSync('samples/obfuscated_payload.js','utf8')); console.log('syntax ok')"`

---

### Task 3: Create Dockerfile

**Objective:** Containerize the swarm for one-command demo deployment.

**Files:**
- Create: `Dockerfile`

```dockerfile
FROM python:3.12-slim

WORKDIR /app

# Install runtime deps
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir "textual>=0.70.0"

# Copy the swarm module
COPY swarm/ ./swarm/
COPY configs/ ./configs/
COPY samples/ ./samples/

# Install the package itself
RUN pip install --no-cache-dir -e .

# Default: show help
CMD ["python3", "-m", "swarm", "--help"]
```

**Verify:** `docker build -t swarm-re-demo . 2>&1 | tail -5`

---

### Task 4: Create Docker Compose

**Objective:** One-command TUI launch with host networking for Ollama access.

**Files:**
- Create: `docker-compose.yml`

```yaml
services:
  swarm-reverse-engineering:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: swarm-re-demo
    network_mode: host
    environment:
      OLLAMA_HOST: ${OLLAMA_HOST:-http://localhost:11434}
      SEARCH_BACKEND: ddgs
    volumes:
      - ./samples:/app/samples
      - ./configs:/app/configs
    stdin_open: true
    tty: true
    entrypoint: ["python3", "-m", "swarm", "--tui"]
```

**Verify:** `docker compose config` — should print resolved config without errors.

---

### Task 5: Create the One-Shot Demo Script

**Objective:** A bash script that builds and runs the swarm against a specific file in one command.

**Files:**
- Create: `run-re-demo.sh`

```bash
#!/bin/bash
set -e

SAMPLE="${1:-samples/obfuscated_payload.js}"
SAMPLE_ABS="$(cd "$(dirname "$SAMPLE")" && pwd)/$(basename "$SAMPLE")"
SAMPLE_DIR="$(dirname "$SAMPLE_ABS")"
SAMPLE_FILE="$(basename "$SAMPLE_ABS")"

echo "🔍 Swarm Reverse Engineering Demo"
echo "================================="
echo "Target: $SAMPLE_FILE"
echo ""

docker build -t swarm-re-demo -f Dockerfile . > /dev/null 2>&1
echo "✅ Build complete"

docker run --rm -it \
  -e OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}" \
  -v "$SAMPLE_DIR:/app/samples" \
  swarm-re-demo \
  python3 -m swarm \
    --config /app/configs/reverse-engineering.json \
    --mix \
    --no-synthesize \
    --goal "Reverse engineer this obfuscated payload at /app/samples/$SAMPLE_FILE. Use your available tools (python_exec, file_reader, web_search) to analyze, decode, and attribute it. Do NOT guess. Use your tools."
```

**Verify:** `chmod +x run-re-demo.sh && shellcheck run-re-demo.sh`

---

### Task 6: Create the README Section

**Objective:** Add a "Reverse Engineering Demo" section to the existing README.md that explains the demo, how to run it, and what to expect.

**Files:**
- Modify: `README.md` (append before the "Files" section)

**Content to add:**
```markdown
## 🕵️ Reverse Engineering Demo

Drop an obfuscated payload into `samples/` and watch 5 parallel AI agents deobfuscate it, trace C2 endpoints, check threat intel, and produce a full report.

### Quick Start

```bash
# Fire up the TUI
docker compose up

# Or one-shot against a file
./run-re-demo.sh samples/obfuscated_payload.js
```

### The Team

| Agent | Model | Role | Tools |
|-------|-------|------|-------|
| 🐝 Vera | gpt-oss:120b | Structure & encoding | python_exec |
| 🐝 Cyrus | nemotron-3-nano | Network & exfil | python_exec |
| 🐝 Ash | deepseek-v4-flash | Threat attribution | web_search |
| 🐝 Zara | gpt-oss:120b | Deobfuscation | python_exec + file_reader |
| 🐝 Romy | gemma4:31b | Impact analysis | scratchpad |

### What It Does

1. **Vera** breaks the encoding layers (base64, XOR, string reversal)
2. **Cyrus** traces the data flow, extracts C2 endpoints
3. **Ash** searches threat intel databases to confirm/debunk attribution
4. **Zara** produces clean deobfuscated code with commentary
5. **Romy** explains the kill chain and impact

All 5 run in parallel. Full report in under 2 minutes.
```

**Verify:** `grep -q "Reverse Engineering Demo" README.md && echo "section added"`

---

### Task 7: End-to-End Smoke Test

**Objective:** Verify the entire pipeline works — build, run against the synthetic payload, confirm output.

**Run:**
```bash
# Build
docker build -t swarm-re-demo .

# Run against synthetic payload
docker run --rm --network host \
  -v $(pwd)/samples:/app/samples \
  -v $(pwd)/configs:/app/configs \
  swarm-re-demo \
  python3 -m swarm \
    --config /app/configs/reverse-engineering.json \
    --mix \
    --no-synthesize \
    --goal "Reverse engineer this obfuscated payload at /app/samples/obfuscated_payload.js. Use your tools." 2>&1 | tail -20
```

**Expected output:** All 5 workers complete with findings. Vera identifies 3 encoding layers. Cyrus extracts 4 C2 endpoints. Ash confirms "synthetic/demo — not known malicious infrastructure." Zara produces deobfuscated code. Romy explains the kill chain.

**Verify:** Check that `swarm_outputs/` contains a new markdown file with the date.

---

### Task 8: Add .gitignore Entries

**Objective:** Prevent generated files from being committed.

**Files:**
- Modify: `.gitignore`

**Add:**
```
# Generated outputs
swarm_outputs/
test-results/

# Docker
.docker/
```

**Verify:** `grep -q "swarm_outputs" .gitignore && echo "added"`
