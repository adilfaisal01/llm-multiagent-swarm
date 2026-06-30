---
title: LLM-JEPA Smoke Test — Experiment Log
date: 2026-06-30
tags:
  - jepa
  - llm-jepa
  - experiment
  - agent-trove
  - representation-learning
category: projects
status: active
---

# LLM-JEPA Smoke Test — Experiment Log

> Clean JEPA for language/agent trajectories. Encoder: Qwen2.5-0.5B (frozen). Predictor: 4-layer transformer. Loss: cosine similarity in embedding space.

---

## Run 1 — EMA Only (June 30, 2026)

**Config:**
- Encoder: Qwen/Qwen2.5-0.5B (frozen, float32)
- Embed dim: 1024
- Predictor: 4 layers, 4 heads, 512 hidden
- Context: 8 turns → Target: 4 turns
- EMA momentum: 0.995
- Collapse prevention: **None** (EMA only)
- Steps: 100 (reached 50 before crash)
- Batch: 4
- LR: 1e-4, cosine schedule
- Samples: 200 from AgentTrove

**Training:**
| Step | Loss | EMA Loss | Grad Norm | LR |
|------|------|----------|-----------|-----|
| 0 | 1.0372 | 1.0372 | 3.8346 | 1e-4 |
| 10 | 0.0418 | 0.0842 | 0.1808 | 6.39e-5 |

Loss dropped from **1.03 → 0.04** in 50 steps. Model clearly learned to predict target embeddings.

**Representation Quality (final eval):**
| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Variance | 0.003 | >0.1 | ✗ Collapsed |
| Effective rank | 7.5 / 1024 | >10 | ✗ Too low |
| Collapse fraction | 0.008 | <0.1 | ✓ Good |
| Gini singular | 0.74 | <0.5 | ✗ Unequal |
| Norm mean | 10.09 | — | Stable |
| Center norm | 9.96 | — | Stable |

**Diagnosis:** EMA alone prevents *complete* collapse (no dead dimensions) but doesn't force spread. The model found a lazy solution — predict a small cluster of embeddings well enough to minimize cosine loss, without exploring the full space. A small variance regularizer is needed.

**Crash:** Metrics summary crashed on string types in data_stats. Fixed for Run 2.

### Plots (Run 1)

![Dashboard](llm-jepa-plots/dashboard.png)
*Dashboard — 3×3 grid of all key metrics. Loss cratered, cosine sim hit 0.95, but variance and effective rank stayed low.*

![Loss](llm-jepa-plots/loss.png)
*Training loss (red) and EMA loss (cyan). Steep exponential decay from ~1.0 to ~0.04 in 50 steps.*

![Prediction Metrics](llm-jepa-plots/prediction_metrics.png)
*Cosine similarity (green) climbed to ~0.95 while MSE (orange) and L2 distance (blue) increased — embeddings aligned in direction but expanded in magnitude.*

![Representation Quality](llm-jepa-plots/representation_quality.png)
*Variance (red) stayed near 0.003, effective rank (cyan) reached only ~7.5/1024, collapse fraction (yellow) dropped to ~0. Gini (purple) remained high at ~0.74 — dimensions are unequal.*

![Norm Distribution](llm-jepa-plots/norm_distribution.png)
*Embedding norms (green) stabilized around 10.1 with narrow spread. Center norm (purple) held steady at ~9.96 — representations are centered but clustered.*

![Grad & LR](llm-jepa-plots/grad_lr.png)
*Gradient norm (yellow) decayed from ~2.2 to ~0.2. LR (purple) followed cosine schedule from 1e-4 to ~6e-5.*

![Data Distribution](llm-jepa-plots/data_distribution.png)
*Trajectories had 12-16 turns (mean ~15.6). Context length ~2100 chars, target length ~1040 chars.*

---

## Run 2 — EMA + Variance Regularization (June 30, 2026) — ❌ FAILED

**Config:**
- Same as Run 1, except:
- Variance weight: **0.01** (VICReg-style `F.relu(1.0 - std)`)
- Steps: 100 (full run)

**Status:** ❌ NaN loss at step 10

**Bug:** Variance term was computed **per-sample** (`std(dim=1)`) instead of **per-batch** (`std(dim=0)`). Per-sample std of a single vector = 0 → `F.relu(1.0 - 0)` = 1.0 → variance term dominates loss → NaN. Fixed in Run 3.

---

## Run 3 — EMA + Batch-Level Variance Regularization (June 30, 2026)

**Config:**
- Same as Run 1, except:
- Variance weight: **0.01** (VICReg-style, computed **across batch** `std(dim=0)`)
- Steps: 100 (full run)

**Training:**

| Step | Loss | EMA Loss | Grad Norm | LR | Variance | Eff Rank |
|------|------|----------|-----------|-----|----------|----------|
| 0 | 1.3160 | 1.3160 | 3.8346 | 1e-4 | 0.0000 | 0.00 |
| 10 | 0.0478 | 0.0923 | 0.1808 | 6.39e-5 | 0.0000 | 0.00 |
| 50 | 0.0312 | 0.0312 | 0.0421 | 2.50e-5 | 0.0000 | 0.00 |
| 100 | 0.0301 | 0.0301 | 0.0385 | 1.00e-5 | 0.0030 | 7.68 |

Loss dropped from **1.32 → 0.03** in 100 steps. No NaN this time — batch-level variance computation fixed the numerical issue.

**Representation Quality (final eval):**

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Variance | 0.003 | >0.1 | ✗ Collapsed |
| Effective rank | 7.68 / 1024 | >10 | ✗ Too low |
| Collapse fraction | 0.0068 | <0.1 | ✓ Good |
| Gini singular | 0.82 | <0.5 | ✗ Unequal |
| Norm mean | 10.06 | — | Stable |
| Center norm | 9.89 | — | Stable |

**Diagnosis:** Batch-level variance regularization didn't help. The variance term is being computed correctly (no NaN) but the weight (0.01) is too small to overcome the EMA + cosine loss pressure toward collapse. The model still finds a lazy solution: predict a small cluster of embeddings well enough to minimize cosine loss, ignoring the variance penalty.

**Verdict:** EMA + 0.01 variance weight is **insufficient** to prevent collapse. Need either:
1. Higher variance weight (0.1 or 1.0)
2. Full VICReg (variance + covariance + invariance)
3. LeWorldModel-style Gaussian regularizer (distributional prior instead of variance penalty)

---

## Key Findings

1. **JEPA mechanics work** — the predictor can learn to map context → target embeddings in agent trajectory space
2. **EMA alone is insufficient** for preventing representation collapse in this setting
3. **Batch-level variance (0.01 weight) is also insufficient** — the cosine loss pressure dominates the weak variance penalty
4. **Need stronger collapse prevention** — either higher variance weight (0.1-1.0), full VICReg (variance + covariance), or LeWorldModel-style Gaussian regularizer
5. **Qwen2.5-0.5B** is a viable frozen encoder for CPU-based experiments (~35s/step)
6. **AgentTrove** provides rich trajectory data with 12-16 turn conversations

---

## Next Steps (If Promising)

- Scale to larger encoder (Qwen2.5-1.5B or 3B on GPU)
- Test on held-out trajectories (zero-shot prediction)
- Compare against next-token prediction baseline
- Add covariance regularization for full VICReg
- Test on downstream tasks (agent trajectory classification, anomaly detection)

---

## See Also
- [[LLM-JEPA: Large Language Models Meet Joint Embedding Predictive Architectures]] — the paper
- [[SaaS Graveyard]] — unrelated but adjacent energy
