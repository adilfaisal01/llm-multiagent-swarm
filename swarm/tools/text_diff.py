"""Text diff tool — compare two texts and show the differences."""
from __future__ import annotations
import difflib
from .base import BaseTool


class TextDiff(BaseTool):
    """Compare two text blobs and return a unified diff.

    A pure transform — nothing is logged to the scratchpad. Use for spotting
    differences between a claim and a source quote, two versions of a
    document, or two translations.
    """

    name = "text_diff"
    description = (
        "Compare two pieces of text and return a line-by-line diff. Pass "
        "both texts; lines prefixed with '-' are removed, '+' are added. "
        "Use to spot differences between a claim and its source, document "
        "versions, or two translations."
    )
    parameters = {
        "type": "object",
        "properties": {
            "original": {
                "type": "string",
                "description": "The first text (baseline)",
            },
            "changed": {
                "type": "string",
                "description": "The second text to compare against",
            },
            "label1": {
                "type": "string",
                "description": "Optional name for the first text (default 'original')",
            },
            "label2": {
                "type": "string",
                "description": "Optional name for the second text (default 'changed')",
            },
        },
        "required": ["original", "changed"],
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        """Execute a text diff.

        Args:
            args: Tool arguments. ``original`` and ``changed`` are required;
                ``label1``/``label2`` optionally name the two sides.
            worker_name: Unused by this tool; accepted for interface parity.

        Returns:
            A unified diff (or a note if identical), or an error string
            starting with ``Error:``.
        """
        original = args.get("original", "")
        changed = args.get("changed", "")
        if not original:
            return "Error: no original text provided"
        if not changed:
            return "Error: no changed text provided"

        label1 = args.get("label1", "original")
        label2 = args.get("label2", "changed")

        if original == changed:
            return "(texts are identical)"

        diff = difflib.unified_diff(
            original.splitlines(), changed.splitlines(),
            fromfile=label1, tofile=label2, lineterm="",
        )
        lines = list(diff)
        if not lines:
            return "(texts are identical)"
        return "\n".join(lines)


TOOLS = [TextDiff()]
BUNDLES = ["files", "code", "all"]
