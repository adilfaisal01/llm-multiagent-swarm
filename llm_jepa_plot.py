#!/usr/bin/env python3
"""
LLM-JEPA Smoke Test — Plotting Script
Reads saved metrics from .pt file and generates visualizations.
"""

import os
import sys
import torch
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

SAVE_DIR = "/mnt/E/sabrina-sandbox/llm-jepa-plots"
os.makedirs(SAVE_DIR, exist_ok=True)

# ─── Load Data ──────────────────────────────────────────────────────────────

def load_metrics(path: str):
    data = torch.load(path, map_location="cpu", weights_only=False)
    config = data.get("config", {})
    raw = data.get("raw_metrics", {})
    summary = data.get("metrics", {})
    
    # Extract raw series
    step = raw.get("step", {})
    batch = raw.get("batch", {})
    eval_m = raw.get("eval", {})
    
    return config, step, batch, eval_m, summary


# ─── Plotting ───────────────────────────────────────────────────────────────

def plot_loss(step_metrics, save_path):
    """Training loss, EMA loss over steps."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    # Main loss
    if "loss" in step_metrics:
        vals = step_metrics["loss"]
        axes[0].plot(vals, label="Loss", color="#ff6b6b", linewidth=1.5)
        axes[0].set_xlabel("Step")
        axes[0].set_ylabel("Loss")
        axes[0].set_title("Training Loss")
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
    
    # EMA loss
    if "ema_loss" in step_metrics:
        vals = step_metrics["ema_loss"]
        axes[1].plot(vals, label="EMA Loss", color="#4ecdc4", linewidth=1.5)
        axes[1].set_xlabel("Step")
        axes[1].set_ylabel("EMA Loss")
        axes[1].set_title("EMA Smoothed Loss")
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close()
    print(f"  Saved: {save_path}")


def plot_grad_and_lr(step_metrics, save_path):
    """Gradient norm and learning rate over steps."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    if "grad_norm" in step_metrics:
        vals = step_metrics["grad_norm"]
        axes[0].plot(vals, label="Grad Norm", color="#f9ca24", linewidth=1.5)
        axes[0].set_xlabel("Step")
        axes[0].set_ylabel("Gradient Norm")
        axes[0].set_title("Gradient Norm")
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
    
    if "lr" in step_metrics:
        vals = step_metrics["lr"]
        axes[1].plot(vals, label="LR", color="#a29bfe", linewidth=1.5)
        axes[1].set_xlabel("Step")
        axes[1].set_ylabel("Learning Rate")
        axes[1].set_title("Learning Rate Schedule")
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close()
    print(f"  Saved: {save_path}")


def plot_prediction_metrics(batch_metrics, save_path):
    """Prediction quality metrics over steps."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    metrics_to_plot = [
        ("pred_cos_sim_mean", "Cosine Similarity", "#00b894", axes[0, 0]),
        ("pred_mse", "MSE", "#e17055", axes[0, 1]),
        ("pred_l2_mean", "L2 Distance", "#0984e3", axes[1, 0]),
        ("pred_angle_mean", "Angle (rad)", "#6c5ce7", axes[1, 1]),
    ]
    
    for key, label, color, ax in metrics_to_plot:
        if key in batch_metrics:
            vals = batch_metrics[key]
            ax.plot(vals, label=label, color=color, linewidth=1.5)
            ax.set_xlabel("Step")
            ax.set_ylabel(label)
            ax.set_title(label)
            ax.legend()
            ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close()
    print(f"  Saved: {save_path}")


def plot_representation_quality(eval_metrics, save_path):
    """Representation quality metrics over eval steps."""
    fig, axes = plt.subplots(2, 3, figsize=(16, 10))
    
    metrics_to_plot = [
        ("var_mean", "Variance", "#ff6b6b", axes[0, 0]),
        ("effective_rank", "Effective Rank", "#4ecdc4", axes[0, 1]),
        ("collapse_frac", "Collapse Fraction", "#f9ca24", axes[0, 2]),
        ("gini_singular", "Gini (Singular)", "#a29bfe", axes[1, 0]),
        ("isotropy", "Isotropy", "#00b894", axes[1, 1]),
        ("norm_std", "Norm Std Dev", "#e17055", axes[1, 2]),
    ]
    
    for key, label, color, ax in metrics_to_plot:
        if key in eval_metrics:
            vals = eval_metrics[key]
            ax.plot(vals, label=label, color=color, linewidth=2, marker='o', markersize=4)
            ax.set_xlabel("Eval Step")
            ax.set_ylabel(label)
            ax.set_title(label)
            ax.legend()
            ax.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close()
    print(f"  Saved: {save_path}")


def plot_norm_distribution(eval_metrics, save_path):
    """Norm distribution metrics over eval steps."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    if "norm_mean" in eval_metrics and "norm_std" in eval_metrics:
        means = eval_metrics["norm_mean"]
        stds = eval_metrics["norm_std"]
        steps = range(len(means))
        
        axes[0].plot(steps, means, label="Mean Norm", color="#00b894", linewidth=2, marker='o')
        axes[0].fill_between(steps, 
                             [m - s for m, s in zip(means, stds)],
                             [m + s for m, s in zip(means, stds)],
                             alpha=0.3, color="#00b894")
        axes[0].set_xlabel("Eval Step")
        axes[0].set_ylabel("Norm")
        axes[0].set_title("Embedding Norm Distribution")
        axes[0].legend()
        axes[0].grid(True, alpha=0.3)
    
    if "center_norm" in eval_metrics:
        vals = eval_metrics["center_norm"]
        axes[1].plot(vals, label="Center Norm", color="#6c5ce7", linewidth=2, marker='o')
        axes[1].set_xlabel("Eval Step")
        axes[1].set_ylabel("Center Norm")
        axes[1].set_title("Embedding Center Offset")
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close()
    print(f"  Saved: {save_path}")


def plot_data_distribution(data_metrics, save_path):
    """Data distribution histograms."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    
    if "total_turns" in data_metrics:
        vals = data_metrics["total_turns"]
        axes[0].hist(vals, bins=20, color="#4ecdc4", alpha=0.7, edgecolor="white")
        axes[0].set_xlabel("Total Turns")
        axes[0].set_ylabel("Count")
        axes[0].set_title("Trajectory Length Distribution")
        axes[0].grid(True, alpha=0.3)
    
    if "context_len" in data_metrics and "target_len" in data_metrics:
        ctx = data_metrics["context_len"]
        tgt = data_metrics["target_len"]
        axes[1].hist(ctx, bins=20, alpha=0.7, label="Context", color="#ff6b6b", edgecolor="white")
        axes[1].hist(tgt, bins=20, alpha=0.7, label="Target", color="#0984e3", edgecolor="white")
        axes[1].set_xlabel("Text Length (chars)")
        axes[1].set_ylabel("Count")
        axes[1].set_title("Context vs Target Length")
        axes[1].legend()
        axes[1].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close()
    print(f"  Saved: {save_path}")


def plot_summary_dashboard(step_metrics, batch_metrics, eval_metrics, save_path):
    """Single dashboard with key metrics."""
    fig, axes = plt.subplots(3, 3, figsize=(18, 14))
    
    # Row 1: Loss
    if "loss" in step_metrics:
        axes[0, 0].plot(step_metrics["loss"], color="#ff6b6b", linewidth=1.5)
        axes[0, 0].set_title("Training Loss")
        axes[0, 0].grid(True, alpha=0.3)
    
    if "ema_loss" in step_metrics:
        axes[0, 1].plot(step_metrics["ema_loss"], color="#4ecdc4", linewidth=1.5)
        axes[0, 1].set_title("EMA Loss")
        axes[0, 1].grid(True, alpha=0.3)
    
    if "grad_norm" in step_metrics:
        axes[0, 2].plot(step_metrics["grad_norm"], color="#f9ca24", linewidth=1.5)
        axes[0, 2].set_title("Gradient Norm")
        axes[0, 2].grid(True, alpha=0.3)
    
    # Row 2: Prediction
    if "pred_cos_sim_mean" in batch_metrics:
        axes[1, 0].plot(batch_metrics["pred_cos_sim_mean"], color="#00b894", linewidth=1.5)
        axes[1, 0].set_title("Cosine Similarity")
        axes[1, 0].grid(True, alpha=0.3)
    
    if "pred_mse" in batch_metrics:
        axes[1, 1].plot(batch_metrics["pred_mse"], color="#e17055", linewidth=1.5)
        axes[1, 1].set_title("MSE")
        axes[1, 1].grid(True, alpha=0.3)
    
    if "pred_l2_mean" in batch_metrics:
        axes[1, 2].plot(batch_metrics["pred_l2_mean"], color="#0984e3", linewidth=1.5)
        axes[1, 2].set_title("L2 Distance")
        axes[1, 2].grid(True, alpha=0.3)
    
    # Row 3: Representation
    if "var_mean" in eval_metrics:
        axes[2, 0].plot(eval_metrics["var_mean"], color="#ff6b6b", linewidth=2, marker='o')
        axes[2, 0].set_title("Variance")
        axes[2, 0].grid(True, alpha=0.3)
    
    if "effective_rank" in eval_metrics:
        axes[2, 1].plot(eval_metrics["effective_rank"], color="#4ecdc4", linewidth=2, marker='o')
        axes[2, 1].set_title("Effective Rank")
        axes[2, 1].grid(True, alpha=0.3)
    
    if "collapse_frac" in eval_metrics:
        axes[2, 2].plot(eval_metrics["collapse_frac"], color="#f9ca24", linewidth=2, marker='o')
        axes[2, 2].set_title("Collapse Fraction")
        axes[2, 2].grid(True, alpha=0.3)
    
    plt.suptitle("LLM-JEPA Smoke Test — Dashboard", fontsize=16, y=1.02)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches="tight", facecolor="#1a1a2e")
    plt.close()
    print(f"  Saved: {save_path}")


# ─── Main ───────────────────────────────────────────────────────────────────

def main():
    # Find the latest .pt file
    pt_dir = "/mnt/E/sabrina-sandbox"
    pt_files = sorted(Path(pt_dir).glob("llm-jepa-smoke-test*.pt"))
    
    if not pt_files:
        print("No .pt files found. Run the smoke test first.")
        return
    
    # Use the latest one
    pt_path = str(pt_files[-1])
    print(f"Loading: {pt_path}")
    
    config, step, batch, eval_m, summary = load_metrics(pt_path)
    
    print(f"Config: encoder={config.get('encoder_name', '?')}, embed_dim={config.get('embed_dim', '?')}")
    print(f"Steps: {len(step.get('loss', []))}")
    print(f"Eval points: {len(eval_m.get('var_mean', []))}")
    print(f"Batch points: {len(batch.get('pred_cos_sim_mean', []))}")
    
    # Generate plots
    print("\nGenerating plots...")
    
    plot_loss(step, os.path.join(SAVE_DIR, "loss.png"))
    plot_grad_and_lr(step, os.path.join(SAVE_DIR, "grad_lr.png"))
    plot_prediction_metrics(batch, os.path.join(SAVE_DIR, "prediction_metrics.png"))
    plot_representation_quality(eval_m, os.path.join(SAVE_DIR, "representation_quality.png"))
    plot_norm_distribution(eval_m, os.path.join(SAVE_DIR, "norm_distribution.png"))
    plot_data_distribution(step, os.path.join(SAVE_DIR, "data_distribution.png"))
    plot_summary_dashboard(step, batch, eval_m, os.path.join(SAVE_DIR, "dashboard.png"))
    
    print(f"\nAll plots saved to {SAVE_DIR}/")
    print("Files:")
    for f in sorted(os.listdir(SAVE_DIR)):
        print(f"  {f}")


if __name__ == "__main__":
    main()
