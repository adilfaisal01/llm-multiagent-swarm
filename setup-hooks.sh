#!/bin/bash
# Install git hooks for Swarm v2
# Run this after cloning the repo to enable post-commit tests.

set -e
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "  🔧 Installing git hooks..."

for hook in .githooks/*; do
    name=$(basename "$hook")
    ln -sf "../../.githooks/$name" "$REPO_DIR/.git/hooks/$name"
    echo "     ✅ $name"
done

echo "  ✅ Hooks installed. Every commit will now run chaos monkey + benchmark."
echo "     Results go to test-results/<commit-hash>/"
