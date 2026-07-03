#!/usr/bin/env python3
"""GAIA Benchmark Evaluation Harness — run our swarm against GAIA validation set.

Usage:
    python3 gaia_eval.py                          # Run sample (10 per level)
    python3 gaia_eval.py --samples 5               # 5 per level
    python3 gaia_eval.py --full                    # All 165 validation questions
    python3 gaia_eval.py --levels 1,2             # Only level 1 and 2
    python3 gaia_eval.py --output results.json     # Save results to file
"""

import argparse
import json
import os
import sys
import time
import re
from collections import Counter

# ──────────────────────────────────────────────────────────────────────
# Imports — fail early with helpful message
# ──────────────────────────────────────────────────────────────────────
try:
    from datasets import load_dataset
except ImportError:
    print("  [ERROR] Install datasets: pip install datasets")
    sys.exit(1)

try:
    from swarm.runner import run_swarm
except ImportError:
    print("  [ERROR] Must be run from the swarm repo root: /mnt/E/github-projects/llm-multiagent-swarm")
    sys.exit(1)


# ──────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────
REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(REPO_ROOT, "test-results", "gaia")
os.makedirs(RESULTS_DIR, exist_ok=True)

DEFAULT_SAMPLES_PER_LEVEL = 10


# ──────────────────────────────────────────────────────────────────────
# Dataset loading
# ──────────────────────────────────────────────────────────────────────
def load_gaia_validation(levels: list[int | str] | None = None) -> list[dict]:
    """Load GAIA validation set, optionally filtered by level."""
    print("  [GAIA] Loading GAIA validation set...", file=sys.stderr)
    ds = load_dataset("gaia-benchmark/GAIA", "2023_all", split="validation")

    # Dataset stores levels as strings; normalize to int for comparison
    level_filter: set[int] | None = None
    if levels is not None:
        level_filter = {int(l) for l in levels}

    questions = []
    for ex in ds:
        level = int(ex["Level"])
        if level_filter is not None and level not in level_filter:
            continue
        # Parse annotator metadata
        meta = ex.get("Annotator Metadata", {})
        if isinstance(meta, str) and meta:
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                meta = {}

        # Handle attached files — download if needed
        file_path = ex.get("file_path", "") or ""
        file_name = ex.get("file_name", "") or ""
        if file_path and not os.path.exists(file_path) and not os.path.isabs(file_path):
            # Relative path — resolve from dataset cache
            file_path = os.path.join(RESULTS_DIR, "files", str(ex["task_id"]), file_name)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

        questions.append(
            {
                "task_id": ex["task_id"],
                "question": ex["Question"],
                "answer": ex["Final answer"].strip() if ex["Final answer"] else "",
                "level": level,
                "file_name": file_name,
                "file_path": file_path,
                "has_file": bool(file_name),
                "steps": meta.get("Steps", meta.get("steps", [])),
            }
        )

    print(f"  [GAIA] Loaded {len(questions)} questions", file=sys.stderr)
    return questions


def sample_questions(
    questions: list[dict], samples_per_level: int
) -> list[dict]:
    """Sample N questions per level."""
    by_level: dict[int, list[dict]] = {}
    for q in questions:
        by_level.setdefault(q["level"], []).append(q)

    sampled = []
    for level in sorted(by_level.keys()):
        pool = by_level[level]
        # Prefer questions without file attachments (simpler to eval)
        no_file = [q for q in pool if not q["has_file"]]
        with_file = [q for q in pool if q["has_file"]]
        # Take 70% without files, 30% with files
        n_no_file = min(int(samples_per_level * 0.7), len(no_file), samples_per_level)
        n_with_file = min(samples_per_level - n_no_file, len(with_file))
        selected = no_file[:n_no_file] + with_file[:n_with_file]
        # Pad if short
        if len(selected) < samples_per_level:
            remaining = [q for q in pool if q not in selected]
            selected.extend(remaining[: samples_per_level - len(selected)])
        sampled.extend(selected[:samples_per_level])
        print(
            f"  [GAIA] Level {level}: {len(selected[:samples_per_level])} questions"
            f" ({n_no_file} no-file, {n_with_file} with-file)",
            file=sys.stderr,
        )

    return sampled


# ──────────────────────────────────────────────────────────────────────
# Answer matching
# ──────────────────────────────────────────────────────────────────────
def normalize_answer(text: str) -> str:
    """Normalize answer for comparison."""
    text = text.strip().lower()
    # Remove articles
    text = re.sub(r"\b(a|an|the)\b", " ", text)
    # Normalize whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Remove trailing punctuation
    text = text.rstrip(".,;:!?")
    # Normalize numbers: remove commas
    text = re.sub(r"(\d),(\d)", r"\1\2", text)
    # Remove leading zeros in numbers
    text = re.sub(r"\b0+(\d+)", r"\1", text)
    return text.strip()


def exact_match(predicted: str, expected: str) -> bool:
    """Check exact match after normalization."""
    return normalize_answer(predicted) == normalize_answer(expected)


def contains_answer(predicted: str, expected: str) -> bool:
    """Check if expected answer appears as a standalone token in predicted text."""
    expected_norm = normalize_answer(expected)
    predicted_norm = normalize_answer(predicted)
    # Use word boundaries to avoid matching "3" inside "2003"
    pattern = r"(?<!\w)" + re.escape(expected_norm) + r"(?!\w)"
    return bool(re.search(pattern, predicted_norm))


def extract_answer_from_swarm_output(output: dict) -> str:
    """Extract the best answer from swarm output.

    Priority:
    1. Orchestrator synthesis
    2. Concatenated worker responses
    """
    # Check orchestrator take
    synthesis = output.get("orchestrator", {}).get("synthesis", "")
    if synthesis:
        return synthesis

    # Fall back to worker responses
    workers = output.get("workers", [])
    responses = []
    for w in workers:
        resp = w.get("response", "")
        if resp:
            responses.append(resp)
    return "\n\n".join(responses)


def llm_judge_answer(
    predicted: str, expected: str, question: str
) -> tuple[bool, str]:
    """Judge if predicted answer matches expected.

    Uses exact match, contains-answer, and word-bounded numeric
    matching. Avoids false positives by only accepting numbers that
    appear as standalone tokens (not embedded in dates or larger numbers).

    Returns (correct, explanation).
    """
    norm_pred = normalize_answer(predicted)
    norm_exp = normalize_answer(expected)

    # 1. Exact match after normalization
    if exact_match(predicted, expected):
        return True, "Exact match"

    # 2. Contains answer as standalone word
    if contains_answer(predicted, expected):
        return True, "Contains exact answer"

    # 3. Word-bounded exact match on individual lines
    pred_lines = predicted.strip().split("\n")
    for line in pred_lines:
        line = line.strip()
        if line and exact_match(line, expected):
            return True, f"Exact match on line: {line.strip()[:80]}"

    # 4. Word-bounded numeric matching
    expected_num = _try_parse_number(expected)
    if expected_num is not None:
        # Match numbers that appear as standalone tokens (word boundaries)
        # This avoids matching "3" inside "2003" or "3,000" matching "3"
        nums_in_pred = re.findall(r"(?<!\d)(-?\d+(?:,\d{3})*(?:\.\d+)?)(?!\d)", predicted)
        for n_str in nums_in_pred:
            try:
                n = float(n_str.replace(",", ""))
                if abs(n - expected_num) / max(abs(expected_num), 1) < 0.01:
                    return True, f"Numeric match: {n} ≈ {expected_num}"
            except ValueError:
                continue

    return False, "No match found"


def _try_parse_number(s: str) -> float | None:
    """Try to parse a number from string."""
    s = s.strip().replace(",", "").replace("$", "").replace("€", "").replace("£", "")
    try:
        return float(s)
    except ValueError:
        pass
    # Try to find a number in the string
    nums = re.findall(r"-?\d+\.?\d*", s)
    if nums:
        try:
            return float(nums[0])
        except ValueError:
            pass
    return None


# ──────────────────────────────────────────────────────────────────────
# Eval runner
# ──────────────────────────────────────────────────────────────────────
def evaluate_question(
    question: dict, swarm_args: dict | None = None
) -> dict:
    """Run a single GAIA question through the swarm and return results."""
    q_text = question["question"]
    expected = question["answer"]
    level = question["level"]
    task_id = question["task_id"]

    print(f"\n  [EVAL] Q{task_id} (L{level}): {q_text[:80]}...", file=sys.stderr)

    args = swarm_args or {}
    start = time.time()
    try:
        result = run_swarm(
            goal=q_text,
            workers=args.get("workers", 3),
            mix=args.get("mix", True),
            synthesize=args.get("synthesize", True),
            json_mode=True,
        )
        elapsed = time.time() - start
    except Exception as e:
        print(f"  [ERROR] Swarm failed: {e}", file=sys.stderr)
        return {
            "task_id": task_id,
            "level": level,
            "question": q_text[:200],
            "expected": expected,
            "predicted": "",
            "correct": False,
            "error": str(e),
            "elapsed_s": 0,
            "num_workers": 0,
        }

    # Extract prediction
    predicted = extract_answer_from_swarm_output(result)

    # Evaluate
    correct = False
    method = "none"
    try:
        correct, method = llm_judge_answer(predicted, expected, q_text)
    except Exception as e:
        print(f"  [WARN] Judge failed: {e}", file=sys.stderr)
        # Fall back to exact match
        correct = exact_match(predicted, expected)
        method = "fallback_exact"

    print(
        f"  [RESULT] {'✅' if correct else '❌'} Expected: '{expected[:60]}' | "
        f"Method: {method} | {elapsed:.1f}s",
        file=sys.stderr,
    )

    return {
        "task_id": task_id,
        "level": level,
        "question": q_text[:300],
        "expected": expected,
        "predicted": predicted[:500],
        "correct": correct,
        "method": method,
        "elapsed_s": round(elapsed, 1),
        "num_workers": result.get("num_workers", 0),
        "models": result.get("models", []),
    }


# ──────────────────────────────────────────────────────────────────────
# Report
# ──────────────────────────────────────────────────────────────────────
def print_report(results: list[dict]):
    """Print a formatted report of evaluation results."""
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    accuracy = correct / total * 100 if total else 0
    total_time = sum(r["elapsed_s"] for r in results)
    avg_time = total_time / total if total else 0

    # Per-level
    by_level: dict[int, list[dict]] = {}
    for r in results:
        by_level.setdefault(r["level"], []).append(r)

    print("\n" + "=" * 70)
    print("  🏆 GAIA EVALUATION REPORT")
    print("=" * 70)
    print(f"  Total questions: {total}")
    print(f"  Correct: {correct}/{total} ({accuracy:.1f}%)")
    print(f"  Total time: {total_time:.0f}s ({avg_time:.1f}s avg)")
    print()

    for level in sorted(by_level.keys()):
        l_results = by_level[level]
        l_correct = sum(1 for r in l_results if r["correct"])
        l_accuracy = l_correct / len(l_results) * 100
        l_time = sum(r["elapsed_s"] for r in l_results)
        l_avg = l_time / len(l_results)
        print(f"  📊 Level {level}: {l_correct}/{len(l_results)} ({l_accuracy:.1f}%) — {l_avg:.1f}s avg")
        # Show individual results
        for r in l_results:
            mark = "✅" if r["correct"] else "❌"
            expected_short = r["expected"][:50]
            print(f"    {mark} Q{r['task_id']}: expected='{expected_short}' | {r['elapsed_s']:.1f}s")
        print()

    print("=" * 70)

    # Error analysis
    errors = [r for r in results if not r["correct"]]
    if errors:
        print("  ❌ Error Analysis:")
        for r in errors:
            print(f"    Q{r['task_id']} (L{r['level']}): expected='{r['expected'][:60]}'")
            print(f"      predicted='{r['predicted'][:200]}'")
            print()


def save_results(results: list[dict], path: str):
    """Save results to JSON file."""
    with open(path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"  [SAVED] Results to {path}", file=sys.stderr)


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="GAIA Benchmark Evaluation Harness")
    parser.add_argument(
        "--samples", type=int, default=DEFAULT_SAMPLES_PER_LEVEL,
        help=f"Questions per level (default: {DEFAULT_SAMPLES_PER_LEVEL})",
    )
    parser.add_argument("--full", action="store_true", help="Run all 165 validation questions")
    parser.add_argument(
        "--levels", type=str, default="1,2,3",
        help="Comma-separated levels to evaluate (default: 1,2,3)",
    )
    parser.add_argument("--output", type=str, help="Save results to JSON file")
    parser.add_argument(
        "--workers", type=int, default=3, help="Number of swarm workers (default: 3)"
    )
    parser.add_argument(
        "--no-mix", action="store_true", help="Use uniform models instead of mix"
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed for sampling")
    args = parser.parse_args()

    # Parse levels
    levels = [int(l.strip()) for l in args.levels.split(",") if l.strip()]

    # Load questions
    all_questions = load_gaia_validation(levels)

    # Sample
    if args.full:
        questions = all_questions
        print(f"  [GAIA] Running ALL {len(questions)} questions", file=sys.stderr)
    else:
        import random

        random.seed(args.seed)
        questions = sample_questions(all_questions, args.samples)
        print(f"  [GAIA] Running {len(questions)} questions ({args.samples} per level)", file=sys.stderr)

    # Run evaluation
    swarm_args = {
        "workers": args.workers,
        "mix": not args.no_mix,
        "synthesize": True,
    }

    print(f"  [GAIA] Swarm config: {json.dumps(swarm_args)}", file=sys.stderr)
    print(f"  [GAIA] Starting evaluation...", file=sys.stderr)
    print("=" * 70, file=sys.stderr)

    results = []
    for i, q in enumerate(questions):
        q_result = evaluate_question(q, swarm_args)
        results.append(q_result)
        # Progress
        done = i + 1
        correct_so_far = sum(1 for r in results if r["correct"])
        print(
            f"  [PROGRESS] {done}/{len(questions)} ({correct_so_far}/{done} correct)"
            f" — {correct_so_far/max(done,1)*100:.0f}%",
            file=sys.stderr,
        )
        # Save checkpoint every 5 questions
        if done % 5 == 0:
            checkpoint_path = os.path.join(RESULTS_DIR, f"checkpoint_{done}.json")
            save_results(results, checkpoint_path)

    # Report
    print_report(results)

    # Save
    output_path = args.output or os.path.join(
        RESULTS_DIR,
        f"gaia_results_{'full' if args.full else f'sample{args.samples}'}.json",
    )
    save_results(results, output_path)

    # Summary line for parsing
    total = len(results)
    correct = sum(1 for r in results if r["correct"])
    accuracy = correct / total * 100 if total else 0
    print(f"\n  SUMMARY: {correct}/{total} correct ({accuracy:.1f}%)", file=sys.stderr)


if __name__ == "__main__":
    main()