#!/bin/bash
# Chaos Monkey test suite for Swarm v2 (modular package)
cd /mnt/E/github-projects/llm-multiagent-swarm

echo "═══════════════════════════════════════════════════"
echo "  🐒 CHAOS MONKEY TEST SUITE"
echo "  Date: $(date)"
echo "═══════════════════════════════════════════════════"

# ─── Test 1: Empty goal ──────────────────────────────────
echo ""
echo "═══ TEST 1: Empty goal (--goal '') ═══"
python3 -m swarm --goal "" --mix 2>&1 | tail -5
echo ""

# ─── Test 2: Missing required arg (no --goal) ────────────
echo "═══ TEST 2: Missing --goal ═══"
python3 -m swarm --mix 2>&1 | tail -5
echo ""

# ─── Test 3: 0 workers ──────────────────────────────────
echo "═══ TEST 3: --workers 0 ═══"
python3 -m swarm --goal "test" --workers 0 --mix 2>&1 | tail -5
echo ""

# ─── Test 4: 1 worker ────────────────────────────────────
echo "═══ TEST 4: --workers 1 --mix ═══"
python3 -m swarm --goal "What is 2+2?" --workers 1 --mix 2>&1 | tail -8
echo ""

# ─── Test 5: 20 workers (more than team size) ────────────
echo "═══ TEST 5: --workers 20 --mix (wrap-around) ═══"
python3 -m swarm --goal "What is the speed of light?" --workers 20 --mix 2>&1 | tail -10
echo ""

# ─── Test 6: Non-existent config file ───────────────────
echo "═══ TEST 6: --config /tmp/nope.json ═══"
python3 -m swarm --goal "test" --config /tmp/nope.json --mix 2>&1 | tail -5
echo ""

# ─── Test 7: Broken config (malformed JSON) ─────────────
echo "═══ TEST 7: Malformed config JSON ═══"
echo "{broken json" > /tmp/broken.json
python3 -m swarm --goal "test" --config /tmp/broken.json --mix 2>&1 | tail -5
echo ""

# ─── Test 8: Invalid model name ──────────────────────────
echo "═══ TEST 8: --model totally-fake-model-9999 ═══"
python3 -m swarm --goal "What is 2+2?" --model totally-fake-model-9999 2>&1 | tail -5
echo ""

# ─── Test 9: Unicode / emoji chaos ───────────────────────
echo "═══ TEST 9: Emoji + Unicode goal ═══"
python3 -m swarm --goal "🔥💯🐒 What does 🎉 mean in Japanese culture? 日本語も話せますか？" --mix 2>&1 | tail -8
echo ""

# ─── Test 10: SQL injection attempt ──────────────────────
echo "═══ TEST 10: SQL injection goal ═══"
python3 -m swarm --goal "'; DROP TABLE users; -- What is SQL injection?" --mix 2>&1 | tail -8
echo ""

# ─── Test 11: 10,000 char goal ───────────────────────────
echo "═══ TEST 11: 10,000 char goal ═══"
LONG_GOAL=$(python3 -c "print('A' * 10000)")
python3 -m swarm --goal "$LONG_GOAL" --mix 2>&1 | tail -8
echo ""

# ─── Test 12: --json output flag ─────────────────────────
echo "═══ TEST 12: --json output ═══"
python3 -m swarm --goal "What is 2+2?" --workers 2 --mix --json 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'JSON valid: ✅, workers: {d[\"num_workers\"]}, models: {d[\"models\"]}')" 2>&1
echo ""

# ─── Test 13: --auto flag ────────────────────────────────
echo "═══ TEST 13: --auto with simple query ═══"
python3 -m swarm --goal "What is the capital of France?" --auto --mix 2>&1 | tail -8
echo ""

# ─── Test 14: --auto with complex query ──────────────────
echo "═══ TEST 14: --auto with complex query ═══"
python3 -m swarm --goal "What validity is there to the claim the industrial revolution was a disaster for humanity?" --auto --mix 2>&1 | tail -8
echo ""

# ─── Test 15: Library import + programmatic use ──────────
echo "═══ TEST 15: Library import (from swarm import run_swarm) ═══"
python3 -c "
from swarm import run_swarm
from swarm.output import save_markdown
r = run_swarm('What is 2+2?', workers=1, mix=True)
print(f'Library OK: {r[\"num_workers\"]} worker, {r[\"wall_time_s\"]}s')
" 2>&1 | tail -5
echo ""

echo "═══════════════════════════════════════════════════"
echo "  🐒 CHAOS MONKEY COMPLETE"
echo "═══════════════════════════════════════════════════"
