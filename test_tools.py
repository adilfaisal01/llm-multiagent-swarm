#!/usr/bin/env python3
"""
Tool smoke test — generates random files and exercises every tool path.

Usage:
    python3 test_tools.py                # quick test (small files)
    python3 test_tools.py --verbose      # show all tool outputs
    python3 test_tools.py --samples=100  # bigger test image
"""

import argparse
import csv
import os
import random
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, REPO_ROOT)

PASS = "✅"
FAIL = "❌"
SKIP = "⏭️"

# ──────────────────────────────────────────────────────────────────────
# Test file generators
# ──────────────────────────────────────────────────────────────────────

def make_text_file(n_lines: int = 10) -> str:
    """Create a temporary text file with structured data."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
    tmp.write("EMPLOYEE DIRECTORY\n")
    tmp.write("=" * 40 + "\n")
    for i in range(1, n_lines + 1):
        name = random.choice(["Alice", "Bob", "Charlie", "Diana", "Eve", "Frank", "Grace", "Hank", "Ivy", "Jack"])
        dept = random.choice(["Engineering", "Marketing", "Sales", "HR", "Finance"])
        salary = random.randint(50000, 150000)
        tmp.write(f"{i}. {name} — {dept} — ${salary:,}\n")
    tmp.close()
    return tmp.name


def make_csv_file(n_rows: int = 20) -> str:
    """Create a temporary CSV file with numeric data."""
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False)
    writer = csv.writer(tmp)
    writer.writerow(["id", "x", "y", "label"])
    for i in range(1, n_rows + 1):
        writer.writerow([i, random.randint(0, 100), random.randint(0, 100), random.choice(["A", "B", "C"])])
    tmp.close()
    return tmp.name


def make_image_file(width: int = 100, height: int = 100, n_numbers: int = 30) -> str:
    """Create a tiny PNG image with a grid of numbers using raw bytes.

    This uses the Python Imaging Library if available, or falls back to a
    PPM (portable pixmap) format which is trivially parseable.
    """
    tmp = tempfile.NamedTemporaryFile(suffix=".ppm", delete=False)
    # PPM format: P3 width height maxval RGB data
    # We'll draw a grid of numbers as colored pixels
    tmp.write(f"P3\n{width} {height}\n255\n".encode())
    for y in range(height):
        for x in range(width):
            # Checkerboard pattern with numbers embedded
            section = (x // 10) + (y // 10) * (width // 10)
            r = (section * 37) % 256
            g = (section * 73) % 256
            b = (section * 127) % 256
            tmp.write(f"{r} {g} {b} ".encode())
    tmp.close()
    return tmp.name


# ──────────────────────────────────────────────────────────────────────
# Tool tests
# ──────────────────────────────────────────────────────────────────────

def test_tool(name: str, args: dict, expected_prefix: str | None = None) -> bool:
    """Run a tool and return True if it succeeds."""
    from swarm.tools import get_registry
    reg = get_registry()
    tool = reg.get(name)
    if not tool:
        print(f"  {FAIL} Tool '{name}' not found in registry")
        return False
    try:
        result = tool.run(args, worker_name="test")
        ok = not result.startswith("[Error") and not result.startswith("Error:")
        if expected_prefix:
            ok = ok and result.startswith(expected_prefix)
        print(f"  {'✅' if ok else '❌'} {name}({list(args.keys())}) → {len(result)} chars")
        if not ok:
            print(f"     First 100 chars: {result[:100]}")
        return ok
    except Exception as e:
        print(f"  {FAIL} {name} crashed: {e}")
        return False


def test_orchestrator_preload(file_path: str) -> bool:
    """Test the orchestrator's file preloading function."""
    from swarm.orchestrator import _preload_file_content
    content = _preload_file_content(file_path)
    if content:
        print(f"  ✅ orchestrator._preload_file_content({os.path.basename(file_path)}) → {len(content)} chars")
        return True
    print(f"  ❌ orchestrator._preload_file_content() returned None for {file_path}")
    return False


def test_orchestrator_compute(file_content: str) -> bool:
    """Test orchestrator's numeric computation from file data."""
    from swarm.orchestrator import _compute_answer_from_data
    result = _compute_answer_from_data("test", file_content, "/tmp/test.txt")
    if result:
        print(f"  ✅ orchestrator._compute_answer_from_data() → {len(result)} chars")
        return True
    print(f"  ❌ orchestrator._compute_answer_from_data() returned None")
    return False


def test_swarm_with_file(goal: str, file_path: str, timeout_s: int = 120) -> bool:
    """Run the full swarm with a file attachment."""
    from swarm.runner import run_swarm
    import time

    enhanced_goal = f"{goal} [ATTACHED FILE: {file_path}]"
    print(f"  🐝 run_swarm(goal='{goal[:50]}...', file='{os.path.basename(file_path)}')")
    start = time.time()
    try:
        result = run_swarm(
            goal=enhanced_goal,
            workers=2,
            mix=True,
            synthesize=True,
            json_mode=True,
        )
        elapsed = time.time() - start
        synth = result.get("synthesis", "")
        ok = len(synth) > 10
        print(f"  {'✅' if ok else '❌'} → {elapsed:.1f}s, synthesis={len(synth)} chars, workers={len(result['workers'])}")
        return ok
    except Exception as e:
        elapsed = time.time() - start
        print(f"  ❌ → {elapsed:.1f}s, error: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Tool smoke test")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show full tool outputs")
    parser.add_argument("--samples", type=int, default=30, help="Number of data points in test files")
    parser.add_argument("--skip-swarm", action="store_true", help="Skip full swarm tests (faster)")
    args = parser.parse_args()

    VERBOSE = args.verbose
    N_SAMPLES = args.samples

    print(f"\n{'='*60}")
    print(f"  🛠️  TOOL SMOKE TEST")
    print(f"  Samples: {N_SAMPLES} | Verbose: {VERBOSE} | Skip swarm: {args.skip_swarm}")
    print(f"{'='*60}")

    results = []

    # ── Phase 1: Generate test files ──
    print(f"\n{'─'*60}")
    print(f"  📁 PHASE 1: Generate test files")
    print(f"{'─'*60}")

    txt_path = make_text_file(N_SAMPLES)
    csv_path = make_csv_file(N_SAMPLES)
    img_path = make_image_file(100, 100, N_SAMPLES)
    print(f"  Text file: {os.path.basename(txt_path)} ({os.path.getsize(txt_path)} bytes)")
    print(f"  CSV file:  {os.path.basename(csv_path)} ({os.path.getsize(csv_path)} bytes)")
    print(f"  Image file: {os.path.basename(img_path)} ({os.path.getsize(img_path)} bytes)")

    # ── Phase 2: Direct tool tests ──
    print(f"\n{'─'*60}")
    print(f"  🔧 PHASE 2: Direct tool tests")
    print(f"{'─'*60}")

    # read_file on text
    r = test_tool("read_file", {"path": txt_path, "max_chars": 2000})
    results.append(("read_file (.txt)", r))

    # read_file on CSV
    r = test_tool("read_file", {"path": csv_path, "max_chars": 2000})
    results.append(("read_file (.csv)", r))

    # read_image
    r = test_tool("read_image", {
        "path": img_path,
        "question": "What patterns do you see in this image? Describe the colors."
    })
    results.append(("read_image (.ppm)", r))

    # python_exec
    r = test_tool("python_exec", {
        "code": "import math; print(f'pi={math.pi:.4f}, sqrt(144)={math.sqrt(144):.0f}')"
    })
    results.append(("python_exec (basic)", r))

    # python_exec with stats
    r = test_tool("python_exec", {
        "code": "import statistics, math; data=[1,2,3,4,5,6,7,8,9,10]; print(f'mean={statistics.mean(data):.2f}, stdev={statistics.stdev(data):.2f}')"
    })
    results.append(("python_exec (stats)", r))

    # web_search
    r = test_tool("web_search", {"query": "capital of France"})
    results.append(("web_search", r))

    # scratchpad_add
    r = test_tool("scratchpad_add", {"finding": "Test finding from tool smoke test", "source": "test_tools.py"})
    results.append(("scratchpad_add", r))

    # ── Phase 3: Orchestrator-level tests ──
    print(f"\n{'─'*60}")
    print(f"  🧠 PHASE 3: Orchestrator-level tests")
    print(f"{'─'*60}")

    # Preload text file
    r = test_orchestrator_preload(txt_path)
    results.append(("orchestrator preload (.txt)", r))

    # Preload CSV
    r = test_orchestrator_preload(csv_path)
    results.append(("orchestrator preload (.csv)", r))

    # Preload image
    r = test_orchestrator_preload(img_path)
    results.append(("orchestrator preload (image)", r))

    # Compute from text data
    with open(txt_path) as f:
        content = f.read()
    r = test_orchestrator_compute(content)
    results.append(("orchestrator compute", r))

    # ── Phase 4: Full swarm tests ──
    if not args.skip_swarm:
        print(f"\n{'─'*60}")
        print(f"  🐝 PHASE 4: Full swarm with file attachments")
        print(f"{'─'*60}")

        r = test_swarm_with_file(
            "What is the average salary in this employee directory?",
            txt_path,
            timeout_s=180,
        )
        results.append(("swarm with .txt file", r))

        r = test_swarm_with_file(
            "What is the average of the x values in this CSV?",
            csv_path,
            timeout_s=180,
        )
        results.append(("swarm with .csv file", r))
    else:
        print(f"  {SKIP} Swarm tests skipped (--skip-swarm)")

    # ── Summary ──
    print(f"\n{'='*60}")
    print(f"  📊 SUMMARY")
    print(f"{'='*60}")
    n_pass = sum(1 for _, ok in results if ok)
    n_total = len(results)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
    print(f"\n  {n_pass}/{n_total} passed ({n_pass/n_total*100:.0f}%)")

    # Cleanup
    for path in [txt_path, csv_path, img_path]:
        try:
            os.unlink(path)
        except Exception:
            pass

    return 0 if n_pass == n_total else 1


if __name__ == "__main__":
    sys.exit(main())