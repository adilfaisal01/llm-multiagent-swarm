#!/bin/bash
# FILE: run-re-demo.sh (43 lines)
# Build + run the reverse engineering swarm against a file
# Usage: ./run-re-demo.sh <path-to-obfuscated-file>

set -e

SAMPLE="${1:-samples/obfuscated_payload.js}"
SAMPLE_ABS="$(cd "$(dirname "$SAMPLE")" && pwd)/$(basename "$SAMPLE")"
SAMPLE_DIR="$(dirname "$SAMPLE_ABS")"
SAMPLE_FILE="$(basename "$SAMPLE_ABS")"

echo "🔍 Swarm Reverse Engineering Demo"
echo "================================="
echo "Target: $SAMPLE_FILE"
echo ""

# Build if needed
docker build -t swarm-re-demo -f Dockerfile . > /dev/null 2>&1
echo "✅ Build complete"

# Run against the sample
docker run --rm -it \
  -e OLLAMA_HOST="${OLLAMA_HOST:-http://host.docker.internal:11434}" \
  -v "$SAMPLE_DIR:/app/samples" \
  swarm-re-demo \
  python3 -m swarm \
    --config /app/configs/reverse-engineering.json \
    --mix \
    --no-synthesize \
    --goal "Reverse engineer this obfuscated payload at /app/samples/$SAMPLE_FILE. Use your available tools (python_exec, file_reader, web_search) to analyze, decode, and attribute it. Do NOT guess. Use your tools."
