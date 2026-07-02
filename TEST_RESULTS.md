# Swarm v2 — Test Results

**Date:** July 1, 2026  
**Config:** `swarm_config.json` (5-agent mix mode)  
**Models:** Vera (gpt-oss:120b), Cyrus (nemotron-3-nano:30b), Romy (qwen3.5:397b), Ash (deepseek-v4-flash), Zara (gpt-oss:120b)  
**Search backend:** SearXNG (localhost:8080)  
**Ollama host:** 127.0.0.1:11434

---

## Test 1 — Easy: "What is the capital of France and what is its population?"

| Worker | Model | Time | Searches | Chars | Status |
|--------|-------|------|----------|-------|--------|
| Ash | deepseek-v4-flash | 18.9s | 3 | 5,815 | ✅ |
| Vera | gpt-oss:120b | 22.7s | 3 | 5,728 | ✅ |
| Cyrus | nemotron-3-nano:30b | 29.3s | 3 | 5,927 | ✅ |
| Zara | gpt-oss:120b | 30.8s | 3 | 6,471 | ✅ |
| Romy | qwen3.5:397b | 62.3s | 3 | 2,918 | ✅ |

**Total wall time:** 164.0s  
**Verdict:** All workers returned correct answer (Paris, ~2.1M city proper). Each angle produced unique content — Vera covered history, Cyrus covered economics, Romy covered urban density implications, Ash covered controversies (centralization criticism), Zara covered technical data sources.

---

## Test 2 — Medium: "Explain the key differences between REST and GraphQL APIs for a junior developer"

| Worker | Model | Time | Searches | Chars | Status |
|--------|-------|------|----------|-------|--------|
| Ash | deepseek-v4-flash | 15.3s | 3 | 4,640 | ✅ |
| Vera | gpt-oss:120b | 29.2s | 3 | 10,316 | ✅ |
| Cyrus | nemotron-3-nano:30b | 31.3s | 2 | 3,625 | ✅ |
| Zara | gpt-oss:120b | 45.3s | 3 | 16,036 | ✅ |
| Romy | qwen3.5:397b | 77.5s | 2 | 7,459 | ✅ |

**Total wall time:** 198.6s  
**Verdict:** All workers produced junior-dev-appropriate explanations. Vera traced origins (Fielding 2000 vs Facebook 2012), Cyrus covered industry adoption, Romy discussed career implications, Ash debunked hype, Zara gave the deepest technical breakdown (16K chars).

---

## Test 3 — Hard: "What are the economic implications of the US-China trade war on semiconductor supply chains?"

| Worker | Model | Time | Searches | Chars | Status |
|--------|-------|------|----------|-------|--------|
| Cyrus | nemotron-3-nano:30b | 15.6s | 3 | 5,263 | ✅ |
| Ash | deepseek-v4-flash | 23.1s | 3 | 7,864 | ✅ |
| Vera | gpt-oss:120b | 40.3s | 2 | 13,645 | ✅ |
| Zara | gpt-oss:120b | 49.1s | 3 | 12,039 | ✅ |
| Romy | qwen3.5:397b | 58.3s | 3 | 6,235 | ✅ |

**Total wall time:** 186.4s  
**Verdict:** Strongest test. Vera produced a detailed timeline of export controls (CHIPS Act $52B, Entity List), Cyrus covered financial impacts, Romy discussed future reshoring, Ash noted the "backfire" controversy (US companies hurt too), Zara gave a technical breakdown of the 4-layer semiconductor value chain.

---

## Test 4 — Fun: "Why did Blockbuster fail while Netflix succeeded? Analyze the business strategy differences"

| Worker | Model | Time | Searches | Chars | Status |
|--------|-------|------|----------|-------|--------|
| Ash | deepseek-v4-flash | 17.8s | 3 | 5,502 | ✅ |
| Vera | gpt-oss:120b | 26.9s | 3 | 11,051 | ✅ |
| Cyrus | nemotron-3-nano:30b | 30.0s | 3 | 6,841 | ✅ |
| Zara | gpt-oss:120b | 41.4s | 3 | 12,864 | ✅ |
| Romy | qwen3.5:397b | 91.2s | 2 | 6,834 | ✅ |

**Total wall time:** 207.3s  
**Verdict:** Best narrative test. Vera covered founding stories (1985 vs 1997), Cyrus broke down the $50M acquisition offer that Blockbuster rejected, Romy analyzed the $200B market cap gap, Ash debunked the "Blockbuster was stupid" myth, Zara dove into the tech stack differences (POS systems vs recommendation algorithms).

---

## Test 5 — Deep: "How does the Linux kernel handle memory management with NUMA architectures?"

| Worker | Model | Time | Searches | Chars | Status |
|--------|-------|------|----------|-------|--------|
| Ash | deepseek-v4-flash | 14.1s | 3 | 5,691 | ✅ |
| Cyrus | nemotron-3-nano:30b | 30.1s | 3 | 9,082 | ✅ |
| Zara | gpt-oss:120b | 42.3s | 2 | 13,739 | ✅ |
| Vera | gpt-oss:120b | 42.3s | 3 | 10,966 | ✅ |
| Romy | qwen3.5:397b | 123.6s | 3 | 5,178 | ✅ |

**Total wall time:** 252.4s  
**Verdict:** Most technically demanding test. Vera traced NUMA support from kernel 2.0 (1995) through 6.8+, Cyrus covered key contributors (Ingo Molnar, Peter Zijlstra), Romy discussed NUMA balancing overhead controversy, Ash criticized automatic NUMA balancing thrashing, Zara gave the deepest technical dive (node abstraction, distance matrix, memory policies, zone allocation).

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| **Tests run** | 5 |
| **Total workers launched** | 25 |
| **Successful responses** | 25/25 (100%) |
| **Fallbacks triggered** | 0 |
| **Average wall time** | 201.7s |
| **Fastest worker** | Ash (deepseek-v4-flash) — avg 17.8s |
| **Slowest worker** | Romy (qwen3.5:397b) — avg 82.6s |
| **Most verbose** | Zara (gpt-oss:120b) — avg 12,236 chars |
| **Most concise** | Romy (qwen3.5:397b) — avg 5,730 chars |
| **Search calls total** | 70 |
| **Zero-dependency** | ✅ Pure Python stdlib |

## Performance Notes

- **Ash (deepseek-v4-flash)** is consistently the fastest worker (14-23s) — great for quick first-pass research
- **Zara (gpt-oss:120b)** is the most verbose and technically detailed — best for deep dives
- **Romy (qwen3.5:397b)** is the slowest but produces well-structured, future-looking analysis
- **Cyrus (nemotron-3-nano:30b)** is fast and focused on financial/economic angles
- **Vera (gpt-oss:120b)** consistently produces the best historical timelines
- No worker failed or returned empty content across all 5 tests
- All 5 angles (origins, money, implications, controversies, technical) produced distinct, non-overlapping content

---

## Chaos Monkey Tests

**Date:** July 1, 2026  
**Purpose:** Edge cases, failure modes, and adversarial inputs

| # | Test | Input | Result | Notes |
|---|------|-------|--------|-------|
| 1 | Empty goal | `--goal ""` | 🛡️ Guarded | `[ERROR] --goal cannot be empty` — exits with code 1 |
| 2 | Missing --goal | no `--goal` | 🛡️ Guarded | argparse rejects: `error: the following arguments are required: --goal` |
| 3 | Zero workers | `--workers 0` | ✅ Clamped to 1 | Vera ran with "test" goal, 27.1s, 9,407 chars |
| 4 | Single worker | `--workers 1 --mix` | ✅ Works | Vera alone, 21.5s, 7,141 chars on "What is 2+2?" |
| 5 | 20 workers (wrap) | `--workers 20 --mix` | ⚠️ Timed out | Clamped to 5, but 5 workers on a trivial goal still took >120s |
| 6 | Non-existent config | `--config /tmp/nope.json` | ✅ Graceful | Falls back to defaults, prints `[INFO] Config not found` |
| 7 | Malformed JSON config | `echo "{broken json" > /tmp/broken.json` | 🛡️ Guarded | `json.JSONDecodeError` caught, exits with error |
| 8 | Invalid model | `--model totally-fake-model-9999` | ⚠️ Passes through | Ollama returns error, worker reports `[ERR]` |
| 9 | Emoji + Unicode | `🔥💯🐒 What does 🎉 mean in Japanese culture? 日本語も話せますか？` | ✅ All 5 workers | 145.3s, all returned Japanese cultural analysis |
| 10 | SQL injection | `'; DROP TABLE users; -- What is SQL injection?` | ✅ All 5 workers | 139.8s, all returned SQL injection explanations — no injection occurred |
| 11 | 10,000 char goal | `'A' * 10000` | ✅ Graceful | Workers asked for clarification instead of crashing |
| 12 | JSON output | `--json` piped to parser | ✅ Fixed | Clean JSON on stdout, human output on stderr |

### Fixes Applied During Chaos Testing

| Issue | Fix |
|-------|-----|
| Empty goal hangs workers | Added `if not args.goal.strip(): sys.exit(1)` guard |
| JSON mode mixed human text into stdout | All human-readable output goes to `stderr` when `--json` is set; only clean JSON on `stdout` |
| Malformed config crashes | `json.JSONDecodeError` caught in `load_swarm_config()` |

### Verdict

The swarm handles chaos gracefully. No crashes, no data corruption, no infinite loops. The two edge cases that needed hardening (empty goal, JSON output) were quick fixes. The 10K-char goal was handled elegantly — workers recognized it as nonsense and asked for clarification rather than hallucinating.
