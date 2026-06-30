---
title: "LLM-JEPA: Large Language Models Meet Joint Embedding Predictive Architectures"
date: 2025-09-11
tags:
  - jepa
  - llm
  - paper-notes
  - language-models
  - representation-learning
  - self-supervised-learning
category: paper-notes
source: "https://arxiv.org/abs/2509.14252"
---

# LLM-JEPA: Large Language Models Meet Joint Embedding Predictive Architectures

**Authors:** Hai Huang (Atlassian), Yann LeCun (NYU), Randall Balestriero (Brown University)  
**Published:** arXiv, Sep 2025 (v1), Oct 2025 (v2)  
**Date Read:** 2026-06-30

---

## Core Idea

LLM-JEPA brings the Joint Embedding Predictive Architecture (JEPA) — proven superior to pixel-space objectives in vision — to language models. Instead of only predicting the next token (input-space reconstruction), it adds a **JEPA objective that predicts the embedding of one view (e.g., Code) from another view (e.g., Text) in latent space**, while preserving the LLM's generative capabilities through a combined loss. Across four model families (Llama3, Gemma2, OpenELM, OLMo) and four datasets, LLM-JEPA significantly outperforms standard next-token prediction fine-tuning, resists overfitting, and induces structured representations — all without sacrificing generative quality.

---

## How JEPA Is Adapted for Language (vs. Vision)

The core challenge: vision JEPAs (I-JEPA, V-JEPA) rely on **spatial masking** — predict a masked image block from visible context. Language has no natural spatial structure, so LLM-JEPA instead leverages **naturally occurring multi-view data**:

| Vision (I-JEPA) | Language (LLM-JEPA) |
|---|---|
| Masked image blocks as targets | Paired (Text, Code) as two views of same knowledge |
| Spatial context block | Natural language description |
| Predictor conditioned on mask tokens | [PRED] tokens appended to input |
| EMA-updated target encoder | Same encoder processes both views (no EMA) |
| Separate predictor network (narrow ViT) | Tied-weights predictor via LLM's own layers |
| L2 loss in embedding space | Cosine similarity in embedding space |

**Key examples of natural views:**
- Natural language description → Regular expression (NL-RX)
- Natural language → SQL query (Spider)
- Git issue description → Code diff (SWE-Bench)
- Math word problem → Program (GSM8K)
- Paraphrase pairs (cestwc/paraphrase)

---

## Architecture Differences from I-JEPA / V-JEPA

### 1. No Separate Predictor Network

I-JEPA uses a dedicated narrow ViT predictor. LLM-JEPA instead appends **k ∈ {0, ..., 4} special [PRED] tokens** to the input and uses the embedding of the last [PRED] token as the predictor output. This reuses the LLM's own self-attention layers for the prediction task — a **tied-weights predictor** that adds minimal architectural overhead.

When k = 0, the predictor is trivial: `Pred(x) = x`.

### 2. No EMA Target Encoder

I-JEPA's target encoder is updated via exponential moving average (EMA) of the context encoder to prevent collapse. LLM-JEPA uses the **same encoder** for both Text and Code views, with collapse prevention coming from the combined loss (the next-token prediction term anchors the representations).

### 3. Custom Attention Mask (Two Blocks, Causal per Block)

To compute embeddings of both views without cross-contamination, LLM-JEPA uses a **block-diagonal causal attention mask**:

```python
# Text and Code each get their own causal mask
mask[i, :, t_start:t_start+t_size, t_start:t_start+t_size] = causal_mask(t_size)
mask[i, :, c_start:c_start+c_size, c_start:c_start+c_size] = causal_mask(c_size)
# Cross-block attention is masked to -inf
```

This enables computing both `Enc(Text)` and `Enc(Code)` in **two forward passes** instead of three.

### 4. Combined Loss (Generative + JEPA)

$$L_{LLM-JEPA} = \sum_{\ell=2}^{L} L_{LLM}(\text{Text}_{1:\ell-1}, \text{Text}_\ell) + \lambda \times d(\text{Pred}(\text{Enc}(\text{Text})), \text{Enc}(\text{Code}))$$

- **First term:** Standard next-token prediction (cross-entropy) — preserves generative capabilities
- **Second term:** JEPA objective — cosine similarity between predicted Text embedding and actual Code embedding
- **λ:** Balances the two terms (typical range: 0.5–4, but can go up to 1024 on some tasks)

### 5. No Masking Strategy

Unlike I-JEPA's carefully designed multi-block masking (target blocks at scale 0.15–0.2, context at 0.85–1.0), LLM-JEPA uses the **full input** for both views. The "prediction difficulty" comes from the modality gap between Text and Code, not from masking.

---

## Key Results

### Fine-Tuning Across Model Families (NL-RX-SYNTH)

| Model | Baseline (NTP) | LLM-JEPA (Ours) | Δ | p-value |
|---|---|---|---|---|
| **Llama-3.2-1B-Instruct** | 57.29% | **71.46%** | +14.17% | 1.0e-3 |
| **gemma-2-2b-it** | 33.65% | **43.12%** | +9.47% | 5.5e-3 |
| **OpenELM-1_1B-Instruct** | 12.07% | **25.40%** | +13.33% | 5.1e-4 |
| **OLMo-2-0425-1B-Instruct** | 87.09% | **87.52%** | +0.43% | 2.5e-3 |

### Fine-Tuning Across Datasets (Llama-3.2-1B)

| Dataset | Baseline (NTP) | LLM-JEPA (Ours) | Δ | p-value |
|---|---|---|---|---|
| **NL-RX-TURK** | 22.49% | **30.94%** | +8.45% | 2.4e-4 |
| **GSM8K** | 32.36% | **36.36%** | +4.00% | 9.6e-5 |
| **Spider** | 47.52% | **50.55%** | +3.03% | 4.0e-3 |

### Across Model Sizes (NL-RX-SYNTH)

| Model | Baseline | LLM-JEPA | Δ |
|---|---|---|---|
| Llama-3.2-1B | 57.29% | **71.46%** | +14.17% |
| Llama-3.2-3B | 74.55% | **77.16%** | +2.61% |
| Llama-3.1-8B | 35.77% | **63.57%** | +27.80% |
| OLMo-2-7B | 87.26% | **87.75%** | +0.49% |

### Overfitting Resistance

LLM-JEPA **resists overfitting** — accuracy continues to improve with more epochs while baseline NTP accuracy peaks then degrades. This holds for both full fine-tuning and LoRA fine-tuning.

### Pretraining

- **From scratch on NL-RX-SYNTH:** 54.38% → **60.59%** (p = 2.94e-4)
- **Paraphrase pretraining → Rotten Tomatoes:** 56.57% → **57.76%** (p = 7.38e-4)
- **Paraphrase pretraining → Yelp:** 26.46% → **27.15%** (p = 1.00e-3)
- Note: JEPA loss is only used during pretraining, not during fine-tuning — benefits transfer

### QA and Reasoning Models

| Dataset / Model | Baseline | LLM-JEPA | Δ |
|---|---|---|---|
| NQ-Open (Llama-3.2-1B) | 20.12% | **21.59%** | +1.47% |
| HellaSwag (Llama-3.2-1B) | 69.40% | **70.51%** | +1.11% |
| GSM8K (Qwen3-1.7B) | 44.32% | **45.00%** | +0.68% |
| GSM8K (DeepSeek-R1-Distill-Qwen-1.5B) | 13.87% | **15.04%** | +1.17% |

### Structured Representations

- t-SNE plots show clear clustering of Text and Code embeddings after LLM-JEPA fine-tuning
- SVD of `Enc(Text) - Enc(Code)` shows **significantly smaller singular values** — the mapping between views is confined to a narrow subspace
- The mapping is **approximately linear** (low least-squares regression error)
- This structured representation is the hypothesized source of accuracy improvements

### Ablation Studies

| Variant | Accuracy |
|---|---|
| Baseline (NTP only) | 57.29% |
| **LLM-JEPA (cosine, k=1)** | **71.46%** |
| ℓ2-norm | 2.22% (collapsed) |
| MSE | 70.64% |
| Prepend [PRED] | 68.07% |
| Code → Text (reverse) | 65.70% |
| InfoNCE loss | 34.40% |

### Loss Dropout (Compute Efficiency)

Random JEPA-loss dropout (LD) at rate 0.5–0.75 reduces compute overhead while **improving accuracy at the same PFLOPs budget**. At LD=0.75, λ=2: 73.08% accuracy at ~1.25× the compute of baseline (vs. 2× without dropout).

---

## Connection to Our LLM-JEPA Smoke Test Experiment

Our [[LLM-JEPA Smoke Test — Experiment Log]] shares the same core hypothesis — that JEPA-style embedding-space prediction improves LLM representations — but differs in architectural approach:

| Aspect | Paper (LLM-JEPA) | Our Smoke Test |
|---|---|---|
| **Encoder** | Full LLM (fine-tuned) | Frozen Qwen2.5-0.5B |
| **Predictor** | Tied-weights ([PRED] tokens) | Separate 4-layer transformer |
| **Views** | (Text, Code) pairs | Context → Target (agent trajectory turns) |
| **Loss** | NTP + cosine JEPA | Cosine similarity only |
| **Collapse prevention** | NTP term anchors representations | EMA + variance regularization |
| **Training** | Full fine-tuning | Predictor-only training |

**Key shared findings:**
1. **JEPA mechanics work for language** — the predictor can learn to map one view's embedding to another's
2. **Collapse prevention is critical** — the paper uses the NTP loss as an anchor; our experiment found EMA alone insufficient, requiring variance regularization
3. **Structured representations emerge** — both approaches induce better-organized embedding spaces

**Key differences informing our next steps:**
- The paper's tied-weights predictor is more parameter-efficient than our separate predictor
- The combined NTP+JEPA loss is a natural design for maintaining generative capabilities
- Our approach (frozen encoder + separate predictor) is closer to the original I-JEPA architecture and may be more suitable for **representation learning without generation requirements**

---

## Why It Matters

1. **First JEPA for LLMs:** This paper bridges the gap between vision JEPAs (proven superior) and language model training, opening a new direction for LLM pretraining and fine-tuning.

2. **Simple, practical recipe:** Add a cosine similarity JEPA term to the standard NTP loss, use a custom attention mask, and get consistent improvements across models and datasets.

3. **Overfitting resistance:** The JEPA term acts as a regularizer that keeps improving even as NTP starts to overfit — valuable for limited-data scenarios.

4. **Structured representations:** The near-linear mapping between views suggests LLM-JEPA learns a more organized latent space, which may benefit downstream tasks beyond the training objective.

5. **Compute-efficient path:** Loss dropout makes LLM-JEPA practical at scale (1.25× compute for 0.75 dropout rate vs. 2× without).

---

## Limitations

- **Requires multi-view data:** The JEPA objective needs naturally paired views (Text, Code). Generalizing to single-view data (like standard pretraining corpora) requires a data augmentation mechanism akin to vision.
- **Two hyperparameters (λ, k):** The optimal configuration varies unpredictably across (λ, k) grid, requiring expensive tuning.
- **2× compute overhead** (mitigated by loss dropout but not eliminated).
- **No EMA target encoder:** Unlike I-JEPA, LLM-JEPA doesn't use an EMA-updated target encoder, which may limit representation quality in some settings.

---

## Cross-Links

- [[LLM-JEPA Smoke Test — Experiment Log]] — Our own experiment applying JEPA to LLM representations (agent trajectories)
- [[I-JEPA — Assran et al. 2023]] — The original I-JEPA paper that established the JEPA framework for vision
- [[LeCun AMI Paper Notes]] — The theoretical JEPA framework (LeCun 2022) that underpins both I-JEPA and LLM-JEPA
- [[TS-JEPA — Time Series JEPA 2025]] — Another JEPA adaptation to a non-vision domain

---

## Implementation Details

- **Code:** https://github.com/rbalestr-lab/llm-jepa
- **Custom attention mask:** Block-diagonal causal (2 blocks: Text, Code) — prevents cross-view information leakage
- **Encoder output:** Last token, last layer hidden state
- **Predictor:** k [PRED] tokens appended to input (k ∈ {0, 1, 2, 3, 4})
- **Metric:** Cosine similarity (ℓ2 and MSE also tested but cosine works best)
- **Loss dropout:** Randomly drop JEPA term at rate α ∈ {0, 0.5, 0.75} — guideline: keep λ × (1-α) approximately constant
- **Hyperparameter tuning:** Grid search over (k, λ) ∈ {0, 1, 2, 3, 4} × {0.5, 1, 2, 4}
- **Seeds:** 5 fixed seeds {82, 23, 37, 84, 4} for statistical significance testing
- **Evaluation:** Exact match accuracy (or execution match for Spider)

---

## Key Takeaways

> LLM-JEPA proves that JEPA objectives — already dominant in vision — can be adapted to language models with consistent, significant improvements. The recipe is simple: add a cosine similarity JEPA term to the standard next-token prediction loss, use a custom attention mask to handle multi-view inputs, and let the combined objective regularize the representation space. The result is better accuracy, resistance to overfitting, and more structured embeddings — all without sacrificing generative capabilities.
