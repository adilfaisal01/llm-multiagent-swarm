#!/usr/bin/env python3
"""Generate a Keep a Changelog section from git history and prepend it to CHANGELOG.md.

Usage:
    python3 scripts/gen_changelog.py <tag> [--dry-run]

Reads commits since the previous tag (or full history if none), categorizes
them by conventional-commit prefix, and prepends a new section to
CHANGELOG.md. Prints the new section to stdout (used as the GitHub Release
body). With --dry-run, prints the section without writing the file.

Categories:
    feat:      Added
    fix:       Fixed
    test:      Changed (internal)
    docs:      Changed (internal)
    chore:     Changed (internal)
    refactor:  Changed (internal)
    perf:      Changed (internal)
    (other)    Changed
"""

from __future__ import annotations

import datetime
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANGELOG = ROOT / "CHANGELOG.md"

HEADER = """# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
"""

_CATEGORIES = {
    "Added": ("feat", "feature", "add"),
    "Fixed": ("fix", "bug", "bugfix"),
    "Changed": ("test", "docs", "chore", "refactor", "perf", "build", "ci", "style"),
}


def _git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()


def _previous_tag(current: str) -> str | None:
    """Return the tag before `current`, or None if there is no prior tag.

    Falls back to the latest existing tag when `current` is not yet
    resolvable (e.g. a dry-run before the tag is created).
    """
    try:
        return _git("describe", "--tags", "--abbrev=0", f"{current}^")
    except subprocess.CalledProcessError:
        pass
    try:
        return _git("describe", "--tags", "--abbrev=0", "HEAD")
    except subprocess.CalledProcessError:
        return None


def _commits_since(prev: str | None) -> list[str]:
    """Return commit lines (hash + subject) since prev, or full history."""
    if prev:
        return [ln for ln in _git("log", "--pretty=format:%h %s", f"{prev}..HEAD").splitlines() if ln]
    return [ln for ln in _git("log", "--pretty=format:%h %s").splitlines() if ln]


def _categorize(commits: list[str]) -> dict[str, list[str]]:
    """Bucket commits by conventional-commit prefix."""
    buckets: dict[str, list[str]] = {"Added": [], "Fixed": [], "Changed": []}
    for line in commits:
        m = re.match(r"^[0-9a-f]+\s+([a-z]+)(?:\([^)]*\))?:\s*(.*)$", line)
        if m:
            prefix, rest = m.group(1), m.group(2)
            for bucket, prefixes in _CATEGORIES.items():
                if prefix in prefixes:
                    buckets[bucket].append(f"{rest} ({line.split()[0]})")
                    break
            else:
                buckets["Changed"].append(f"{line} ({line.split()[0]})")
        else:
            buckets["Changed"].append(f"{line} ({line.split()[0]})")
    return buckets


def build_section(tag: str, commits: list[str]) -> str:
    """Build the markdown section for a version."""
    version = tag.lstrip("v")
    date = datetime.date.today().isoformat()
    buckets = _categorize(commits)
    lines = [f"## [{version}] - {date}", ""]
    for bucket in ("Added", "Fixed", "Changed"):
        items = buckets[bucket]
        if not items:
            continue
        lines.append(f"### {bucket}")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")
    if not any(buckets.values()):
        lines.append("- No notable changes.")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/gen_changelog.py <tag> [--dry-run]", file=sys.stderr)
        return 2
    tag = sys.argv[1]
    dry_run = "--dry-run" in sys.argv[2:]

    prev = _previous_tag(tag)
    commits = _commits_since(prev)
    section = build_section(tag, commits)

    if dry_run:
        print(section)
        return 0

    if CHANGELOG.exists():
        existing = CHANGELOG.read_text(encoding="utf-8")
        # Insert the new section after the header block, before the first
        # existing version heading (a line starting with "## ").
        idx = existing.find("\n## ")
        if idx != -1:
            new = existing[:idx] + "\n" + section + existing[idx + 1:]
        else:
            new = existing.rstrip() + "\n\n" + section
    else:
        new = f"{HEADER}\n{section}"

    CHANGELOG.write_text(new, encoding="utf-8")
    print(section)
    return 0


if __name__ == "__main__":
    sys.exit(main())
