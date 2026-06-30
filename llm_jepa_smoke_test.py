#!/usr/bin/env python3
"""
LLM-JEPA Smoke Test — Clean JEPA with EMA target encoder.
Full instrumentation: every metric that can be measured, will be.

Architecture:
  - Encoder: frozen LM + trainable MLP projector
  - Target encoder: EMA copy of projector
  - Predictor: small transformer
  - Loss: cosine similarity in embedding space

Metrics tracked:
  Training: loss, EMA loss, grad norm, param update norm, LR
  Representations: variance, covariance, effective rank, isotropy, norm distribution
  Prediction: cosine sim, MSE, correlation with trajectory complexity
  Data: trajectory length, turn count, token distribution
"""

import os
import sys
import json
import math
import random
import numpy as np
from tqdm import tqdm
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List
from collections import defaultdict
import time

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, IterableDataset

from datasets import load_dataset
from transformers import AutoTokenizer, AutoModel


# ─── Config ────────────────────────────────────────────────────────────────

@dataclass
class Config:
    # Model
    encoder_name: str = "Qwen/Qwen2.5-0.5B"  # already cached, actual LLM, CPU-friendly
    
    # JEPA
    embed_dim: int = 1024       # Qwen2.5-0.5B hidden size
    context_turns: int = 8
    target_turns: int = 4
    ema_momentum: float = 0.995
    
    # Predictor
    predictor_layers: int = 4
    predictor_heads: int = 4
    predictor_dim: int = 512
    
    # Training
    batch_size: int = 4
    lr: float = 1e-4
    weight_decay: float = 1e-5
    max_steps: int = 100        # CPU smoke test
    log_every: int = 10
    eval_every: int = 25
    grad_clip: float = 1.0
    variance_weight: float = 1.0  # variance regularizer to prevent collapse (cranked up from 0.01)
    
    # Data
    max_samples: int = 200      # smoke test size (CPU-limited)
    max_turn_length: int = 256   # shorter for speed
    
    # Device
    device: str = "cpu"


# ─── Metrics ───────────────────────────────────────────────────────────────

class MetricsTracker:
    """Tracks everything. Every step, every batch, every signal."""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.step_metrics = defaultdict(list)  # per-step
        self.batch_metrics = defaultdict(list)   # per-batch
        self.epoch_metrics = defaultdict(list)   # per-eval
        self.repr_metrics = defaultdict(list)    # representation quality
        self.data_stats = defaultdict(list)      # data distribution
    
    def log_step(self, **kwargs):
        for k, v in kwargs.items():
            if isinstance(v, torch.Tensor):
                v = v.item()
            self.step_metrics[k].append(v)
    
    def log_batch(self, **kwargs):
        for k, v in kwargs.items():
            if isinstance(v, torch.Tensor):
                v = v.item()
            self.batch_metrics[k].append(v)
    
    def log_eval(self, **kwargs):
        for k, v in kwargs.items():
            if isinstance(v, torch.Tensor):
                v = v.item()
            self.epoch_metrics[k].append(v)
    
    def log_repr(self, **kwargs):
        for k, v in kwargs.items():
            if isinstance(v, torch.Tensor):
                v = v.detach().cpu().numpy().tolist()
            self.repr_metrics[k].append(v)
    
    def log_data(self, **kwargs):
        for k, v in kwargs.items():
            self.data_stats[k].append(v)
    
    def summary(self) -> Dict:
        """Return a summary dict of all metrics."""
        s = {}
        for name, d in [
            ("training", self.step_metrics),
            ("batch", self.batch_metrics),
            ("eval", self.epoch_metrics),
            ("representations", self.repr_metrics),
            ("data", self.data_stats),
        ]:
            s[name] = {}
            for k, vals in d.items():
                if len(vals) == 0:
                    continue
                # Skip non-numeric values
                numeric_vals = [v for v in vals if isinstance(v, (int, float, np.floating, np.integer))]
                if len(numeric_vals) == 0:
                    continue
                arr = np.array(numeric_vals)
                s[name][k] = {
                    "mean": float(np.mean(arr)),
                    "std": float(np.std(arr)),
                    "min": float(np.min(arr)),
                    "max": float(np.max(arr)),
                    "last": float(arr[-1]),
                    "first": float(arr[0]),
                    "trend": float(arr[-1] - arr[0]) if len(arr) > 1 else 0,
                }
        return s
    
    def print_summary(self):
        s = self.summary()
        print("\n" + "=" * 70)
        print("METRICS SUMMARY")
        print("=" * 70)
        
        for section_name, section in s.items():
            if not section:
                continue
            print(f"\n── {section_name.upper()} ──")
            for k, v in section.items():
                print(f"  {k}:")
                print(f"    mean={v['mean']:.4f}  std={v['std']:.4f}")
                print(f"    min={v['min']:.4f}  max={v['max']:.4f}")
                print(f"    first={v['first']:.4f} → last={v['last']:.4f}  trend={v['trend']:+.4f}")


# ─── Representation Quality Diagnostics ────────────────────────────────────

@torch.no_grad()
def compute_repr_metrics(embeddings: torch.Tensor) -> Dict:
    """
    Compute representation quality metrics from a batch of embeddings.
    
    Args:
        embeddings: (N, D) tensor of embeddings
    
    Returns:
        dict of metrics
    """
    N, D = embeddings.shape
    metrics = {}
    
    # 1. Variance (VICReg-style)
    std = embeddings.std(dim=0)  # (D,)
    metrics["var_mean"] = std.pow(2).mean().item()
    metrics["var_min"] = std.pow(2).min().item()
    metrics["var_max"] = std.pow(2).max().item()
    metrics["std_mean"] = std.mean().item()
    metrics["std_min"] = std.min().item()
    metrics["std_max"] = std.max().item()
    
    # 2. Collapse detection: fraction of dimensions with near-zero variance
    collapse_threshold = 0.01
    metrics["collapse_frac"] = (std < collapse_threshold).float().mean().item()
    
    # 3. Covariance (VICReg-style)
    emb_centered = embeddings - embeddings.mean(dim=0, keepdim=True)
    cov = (emb_centered.T @ emb_centered) / (N - 1)  # (D, D)
    off_diag = cov - torch.diag(torch.diag(cov))
    metrics["cov_off_diag_mean"] = off_diag.abs().mean().item()
    metrics["cov_off_diag_max"] = off_diag.abs().max().item()
    metrics["cov_off_diag_std"] = off_diag.abs().std().item()
    
    # 4. Effective rank (SVD-based)
    try:
        S = torch.linalg.svdvals(embeddings)
        S_norm = S / S.sum()
        entropy = -(S_norm * torch.log(S_norm + 1e-10)).sum()
        metrics["effective_rank"] = torch.exp(entropy).item()
        metrics["rank_ratio"] = torch.exp(entropy).item() / D  # fraction of dims used
    except:
        metrics["effective_rank"] = 0.0
        metrics["rank_ratio"] = 0.0
    
    # 5. Isotropy: how uniform is the variance across dimensions?
    metrics["isotropy"] = (std.mean() / (std + 1e-8)).mean().item()
    # Gini coefficient of singular values
    if D > 1:
        S_sorted = torch.sort(S)[0]
        n = len(S_sorted)
        gini = (2 * torch.sum(torch.arange(1, n+1, device=S_sorted.device) * S_sorted) / (n * S_sorted.sum()) - (n + 1) / n)
        metrics["gini_singular"] = gini.item()
    
    # 6. Norm distribution
    norms = embeddings.norm(dim=1)
    metrics["norm_mean"] = norms.mean().item()
    metrics["norm_std"] = norms.std().item()
    metrics["norm_min"] = norms.min().item()
    metrics["norm_max"] = norms.max().item()
    
    # 7. Centering
    center = embeddings.mean(dim=0)
    metrics["center_norm"] = center.norm().item()
    metrics["center_max_abs"] = center.abs().max().item()
    
    return metrics


@torch.no_grad()
def compute_prediction_metrics(predicted: torch.Tensor, target: torch.Tensor) -> Dict:
    """Compute prediction quality metrics."""
    metrics = {}
    
    # Cosine similarity
    cos_sim = F.cosine_similarity(predicted, target, dim=-1)
    metrics["pred_cos_sim_mean"] = cos_sim.mean().item()
    metrics["pred_cos_sim_std"] = cos_sim.std().item()
    metrics["pred_cos_sim_min"] = cos_sim.min().item()
    metrics["pred_cos_sim_max"] = cos_sim.max().item()
    
    # MSE
    mse = F.mse_loss(predicted, target)
    metrics["pred_mse"] = mse.item()
    
    # L2 distance
    l2_dist = (predicted - target).norm(dim=-1)
    metrics["pred_l2_mean"] = l2_dist.mean().item()
    metrics["pred_l2_std"] = l2_dist.std().item()
    
    # Angle between predicted and target
    angle = torch.acos(cos_sim.clamp(-1, 1))
    metrics["pred_angle_mean"] = angle.mean().item()
    metrics["pred_angle_std"] = angle.std().item()
    
    # Prediction norm ratio
    pred_norm = predicted.norm(dim=-1)
    target_norm = target.norm(dim=-1)
    metrics["pred_norm_ratio"] = (pred_norm / (target_norm + 1e-8)).mean().item()
    
    return metrics


# ─── Data ───────────────────────────────────────────────────────────────────

class AgentTroveJEPA(IterableDataset):
    """Streaming dataset yielding (context_texts, target_texts) pairs."""
    
    def __init__(self, config: Config, split: str = "train", metrics: Optional[MetricsTracker] = None):
        self.config = config
        self.split = split
        self.metrics = metrics
        self._ds = None
    
    def _init_ds(self):
        if self._ds is None:
            self._ds = load_dataset("open-thoughts/AgentTrove", split=self.split, streaming=True)
    
    def __iter__(self):
        self._init_ds()
        count = 0
        for sample in self._ds:
            if count >= self.config.max_samples:
                break
            
            conversations = sample.get("conversations", [])
            if not conversations or len(conversations) < self.config.context_turns + self.config.target_turns:
                continue
            
            context_turns = conversations[:self.config.context_turns]
            target_turns = conversations[self.config.context_turns:self.config.context_turns + self.config.target_turns]
            
            context_text = self._format_turns(context_turns)
            target_text = self._format_turns(target_turns)
            
            # Track data stats
            if self.metrics:
                self.metrics.log_data(
                    total_turns=len(conversations),
                    context_turns=len(context_turns),
                    target_turns=len(target_turns),
                    context_len=len(context_text),
                    target_len=len(target_text),
                    source=sample.get("original_source", "unknown"),
                )
            
            count += 1
            yield context_text, target_text
    
    def _format_turns(self, turns):
        parts = []
        for turn in turns:
            role = turn.get("role", "unknown")
            content = turn.get("content", "")
            if isinstance(content, str) and len(content) > 0:
                parts.append(f"<{role}>: {content[:self.config.max_turn_length]}")
        return "\n".join(parts)


# ─── Model ───────────────────────────────────────────────────────────────────

class MLPProjector(nn.Module):
    def __init__(self, input_dim: int, output_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, output_dim),
            nn.LayerNorm(output_dim),
            nn.GELU(),
            nn.Linear(output_dim, output_dim),
        )
    
    def forward(self, x):
        return self.net(x)


class TransformerPredictor(nn.Module):
    def __init__(self, embed_dim: int, hidden_dim: int, num_layers: int, num_heads: int):
        super().__init__()
        self.input_proj = nn.Linear(embed_dim, hidden_dim)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=hidden_dim,
            nhead=num_heads,
            dim_feedforward=hidden_dim * 4,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        self.output_proj = nn.Linear(hidden_dim, embed_dim)
    
    def forward(self, x):
        x = x.unsqueeze(1)
        x = self.input_proj(x)
        x = self.transformer(x)
        x = x.squeeze(1)
        x = self.output_proj(x)
        return x


class LLMJEPA(nn.Module):
    def __init__(self, config: Config):
        super().__init__()
        self.config = config
        self.device = config.device
        
        print(f"Loading encoder: {config.encoder_name}...")
        self.tokenizer = AutoTokenizer.from_pretrained(config.encoder_name)
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        
        self.encoder = AutoModel.from_pretrained(config.encoder_name, torch_dtype=torch.float32)
        self.encoder.eval()
        for p in self.encoder.parameters():
            p.requires_grad = False
        
        hidden_dim = self.encoder.config.hidden_size
        
        self.projector = MLPProjector(hidden_dim, config.embed_dim)
        
        self.target_projector = MLPProjector(hidden_dim, config.embed_dim)
        self.target_projector.load_state_dict(self.projector.state_dict())
        for p in self.target_projector.parameters():
            p.requires_grad = False
        
        self.predictor = TransformerPredictor(
            embed_dim=config.embed_dim,
            hidden_dim=config.predictor_dim,
            num_layers=config.predictor_layers,
            num_heads=config.predictor_heads,
        )
        
        self.to(config.device)
        print(f"Model on {config.device}")
        print(f"  Encoder: {config.encoder_name} (frozen)")
        print(f"  Embed dim: {config.embed_dim}")
        print(f"  Predictor: {config.predictor_layers} layers, {config.predictor_heads} heads")
    
    @torch.no_grad()
    def _encode_text(self, text: str, use_target: bool = False) -> torch.Tensor:
        tokens = self.tokenizer(
            text, return_tensors="pt", truncation=True,
            max_length=self.config.max_turn_length, padding=True,
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.encoder(**tokens)
            hidden = outputs.last_hidden_state
            attention_mask = tokens.attention_mask.unsqueeze(-1)
            hidden = hidden * attention_mask
            emb = hidden.sum(dim=1) / attention_mask.sum(dim=1).clamp(min=1)
        
        if use_target:
            emb = self.target_projector(emb)
        else:
            emb = self.projector(emb)
        
        return emb
    
    def encode_trajectory(self, texts: list, use_target: bool = False) -> torch.Tensor:
        embs = []
        for text in texts:
            emb = self._encode_text(text, use_target=use_target)
            embs.append(emb)
        traj_emb = torch.stack(embs).mean(dim=0)
        return traj_emb
    
    def forward(self, context_texts: list, target_texts: list):
        context_emb = self.encode_trajectory(context_texts, use_target=False)
        predicted_emb = self.predictor(context_emb)
        
        with torch.no_grad():
            target_emb = self.encode_trajectory(target_texts, use_target=True)
        
        # Cosine similarity loss
        cos_loss = 1.0 - F.cosine_similarity(predicted_emb, target_emb, dim=-1).mean()
        
        return cos_loss, context_emb, predicted_emb, target_emb
    
    def compute_variance_loss(self, embeddings: torch.Tensor) -> torch.Tensor:
        """
        Compute variance regularization across a batch of embeddings.
        embeddings: (B, D) — batch of predicted embeddings
        """
        std = embeddings.std(dim=0)  # (D,) — std across batch
        var_loss = torch.mean(F.relu(1.0 - std))
        return var_loss
    
    @torch.no_grad()
    def update_target_encoder(self, momentum: float):
        for online_param, target_param in zip(
            self.projector.parameters(), self.target_projector.parameters()
        ):
            target_param.data.mul_(momentum).add_(online_param.data, alpha=1.0 - momentum)
    
    @torch.no_grad()
    def compute_param_update_norm(self) -> float:
        """Compute the norm of parameter updates (how much weights changed)."""
        total_norm = 0.0
        for p in self.projector.parameters():
            if p.grad is not None:
                total_norm += p.grad.norm().item() ** 2
        return math.sqrt(total_norm)


# ─── Collation ──────────────────────────────────────────────────────────────

def collate_jepa(batch):
    context_batch = []
    target_batch = []
    for ctx, tgt in batch:
        ctx_turns = [t for t in ctx.split("\n") if t.strip()]
        tgt_turns = [t for t in tgt.split("\n") if t.strip()]
        if ctx_turns and tgt_turns:
            context_batch.append(ctx_turns)
            target_batch.append(tgt_turns)
    return context_batch, target_batch


# ─── Training ───────────────────────────────────────────────────────────────

def train():
    config = Config()
    metrics = MetricsTracker()
    
    print("=" * 70)
    print("LLM-JEPA SMOKE TEST — Full Instrumentation")
    print("=" * 70)
    print(f"Encoder: {config.encoder_name}")
    print(f"Embed dim: {config.embed_dim}")
    print(f"Context: {config.context_turns} turns → Target: {config.target_turns} turns")
    print(f"Samples: {config.max_samples} | Steps: {config.max_steps} | Batch: {config.batch_size}")
    print(f"EMA momentum: {config.ema_momentum}")
    print(f"Device: {config.device}")
    print("=" * 70)
    
    # Data
    print("\n[1/4] Loading AgentTrove dataset...")
    dataset = AgentTroveJEPA(config, metrics=metrics)
    dataloader = DataLoader(
        dataset, batch_size=config.batch_size,
        collate_fn=collate_jepa, num_workers=0,
    )
    
    # Model
    print("\n[2/4] Initializing model...")
    model = LLMJEPA(config)
    
    trainable_params = [p for p in model.parameters() if p.requires_grad]
    n_params = sum(p.numel() for p in trainable_params)
    print(f"Trainable parameters: {n_params:,}")
    
    optimizer = torch.optim.AdamW(
        trainable_params, lr=config.lr, weight_decay=config.weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=config.max_steps,
    )
    
    # Training
    print("\n[3/4] Training...")
    print(f"{'Step':>6} | {'Loss':>8} | {'EMA':>8} | {'Grad':>8} | {'LR':>8} | {'Var':>8} | {'EffRank':>8}")
    print("-" * 70)
    
    step = 0
    ema_loss = None
    repr_embeddings = []  # collect for periodic eval
    
    progress = tqdm(total=config.max_steps, desc="Training")
    
    for batch in dataloader:
        if step >= config.max_steps:
            break
        
        context_batch, target_batch = batch
        if not context_batch or not target_batch:
            continue
        
        # Forward — collect all embeddings for batch-level variance
        batch_cos_loss = 0.0
        all_predicted = []
        all_target = []
        
        for ctx_turns, tgt_turns in zip(context_batch, target_batch):
            cos_loss, ctx_emb, pred_emb, tgt_emb = model(ctx_turns, tgt_turns)
            batch_cos_loss = batch_cos_loss + cos_loss
            all_predicted.append(pred_emb)
            all_target.append(tgt_emb)
            repr_embeddings.append(ctx_emb.detach())
        
        batch_cos_loss = batch_cos_loss / len(context_batch)
        
        # Variance regularization across the batch
        if len(all_predicted) > 1:
            pred_stack = torch.cat(all_predicted, dim=0)  # (B, D)
            var_loss = model.compute_variance_loss(pred_stack)
            total_loss = batch_cos_loss + config.variance_weight * var_loss
        else:
            var_loss = torch.tensor(0.0)
            total_loss = batch_cos_loss
        
        # Backward
        optimizer.zero_grad()
        total_loss.backward()
        
        grad_norm = torch.nn.utils.clip_grad_norm_(trainable_params, config.grad_clip)
        param_update_norm = model.compute_param_update_norm()
        
        optimizer.step()
        scheduler.step()
        
        # EMA update
        model.update_target_encoder(config.ema_momentum)
        
        # Metrics
        loss_val = total_loss.item()
        cos_val = batch_cos_loss.item()
        var_val = var_loss.item() if isinstance(var_loss, torch.Tensor) and var_loss.dim() == 0 else var_loss
        lr_val = scheduler.get_last_lr()[0]
        
        if ema_loss is None:
            ema_loss = loss_val
        else:
            ema_loss = 0.9 * ema_loss + 0.1 * loss_val
        
        metrics.log_step(
            loss=loss_val, cos_loss=cos_val, var_loss=var_val, ema_loss=ema_loss,
            grad_norm=grad_norm, param_update_norm=param_update_norm,
            lr=lr_val,
        )
        
        # Prediction metrics
        if all_predicted and all_target:
            pred_cat = torch.cat(all_predicted, dim=0)
            tgt_cat = torch.cat(all_target, dim=0)
            pred_met = compute_prediction_metrics(pred_cat, tgt_cat)
            metrics.log_batch(**pred_met)
        
        # Periodic eval
        if step % config.eval_every == 0 and len(repr_embeddings) > 1:
            repr_stack = torch.cat(repr_embeddings[-config.eval_every:], dim=0)
            repr_met = compute_repr_metrics(repr_stack)
            metrics.log_eval(**repr_met)
            
            var_mean = repr_met.get("var_mean", 0)
            eff_rank = repr_met.get("effective_rank", 0)
        else:
            var_mean = 0
            eff_rank = 0
        
        # Logging
        if step % config.log_every == 0:
            print(f"{step:>6} | {loss_val:>8.4f} | {ema_loss:>8.4f} | {grad_norm:>8.4f} | {lr_val:>.2e} | {var_mean:>8.4f} | {eff_rank:>8.2f}")
        
        step += 1
        progress.update(1)
    
    progress.close()
    
    # Final evaluation
    print("\n[4/4] Final evaluation...")
    if len(repr_embeddings) > 1:
        repr_stack = torch.cat(repr_embeddings, dim=0)
        final_repr_met = compute_repr_metrics(repr_stack)
        metrics.log_eval(**final_repr_met)
    
    # Summary
    metrics.print_summary()
    
    # Save everything
    save_path = "/mnt/E/sabrina-sandbox/llm-jepa-smoke-test-run4.pt"
    summary = metrics.summary()
    
    torch.save({
        "config": asdict(config),
        "projector": model.projector.state_dict(),
        "predictor": model.predictor.state_dict(),
        "metrics": summary,
        "raw_metrics": {
            "step": dict(metrics.step_metrics),
            "batch": dict(metrics.batch_metrics),
            "eval": dict(metrics.epoch_metrics),
            "repr": dict(metrics.repr_metrics),
            "data": dict(metrics.data_stats),
        },
    }, save_path)
    print(f"\nModel + metrics saved to {save_path}")
    
    # Verdict
    print("\n" + "=" * 70)
    print("VERDICT")
    print("=" * 70)
    
    train_s = summary.get("training", {})
    repr_s = summary.get("representations", {})
    eval_s = summary.get("eval", {})
    
    # Check if loss decreased
    loss_trend = train_s.get("loss", {}).get("trend", 0)
    if loss_trend < 0:
        print("✓ Loss decreased — model is learning")
    else:
        print("✗ Loss did not decrease — model may not be learning")
    
    # Check representation quality
    var_mean = eval_s.get("var_mean", {}).get("mean", 0)
    eff_rank = eval_s.get("effective_rank", {}).get("mean", 0)
    collapse = eval_s.get("collapse_frac", {}).get("mean", 1)
    
    print(f"  Variance: {var_mean:.4f} (target: >0.1)")
    print(f"  Effective rank: {eff_rank:.2f} / {config.embed_dim} (target: >10)")
    print(f"  Collapse fraction: {collapse:.4f} (target: <0.1)")
    
    if var_mean > 0.1 and eff_rank > 10 and collapse < 0.1:
        print("✓ Representations are well-structured — JEPA is working!")
    elif var_mean > 0.01:
        print("~ Representations are marginal — may need more training or tuning")
    else:
        print("✗ Representations are collapsed — EMA alone may not be sufficient")
    
    return metrics


if __name__ == "__main__":
    metrics = train()
