"""Regex extract tool — pull structured data out of text with a pattern."""
from __future__ import annotations
import re
from .base import BaseTool

_MAX_MATCHES = 100


class RegexExtract(BaseTool):
    """Extract structured data from text using a regular expression.

    Runs a regex pattern against a text blob (e.g. a `web_extract` or
    `read_file` result) and returns the matching groups. A pure transform —
    nothing is logged to the scratchpad.
    """

    name = "regex_extract"
    description = (
        "Extract structured data from text using a regular expression. "
        "Pass the text, a pattern with capturing groups, and optionally a "
        "group index. Use to pull dates, prices, emails, codes, or numbers "
        "out of scraped or read content."
    )
    parameters = {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The text to search",
            },
            "pattern": {
                "type": "string",
                "description": "Regular expression (use capturing groups)",
            },
            "group": {
                "type": "number",
                "description": "Which capture group to return per match (default 0 = whole match)",
            },
            "flags": {
                "type": "string",
                "description": "Optional regex flags: 'i' (ignore case), 'm' (multiline), 's' (dotall), combined e.g. 'ims'",
            },
        },
        "required": ["text", "pattern"],
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        """Execute a regex extraction.

        Args:
            args: Tool arguments. ``text`` and ``pattern`` are required;
                ``group`` selects a capture group (default 0); ``flags``
                enables regex flags.
            worker_name: Unused by this tool; accepted for interface parity.

        Returns:
            Matches (one per line), or an error string starting with
            ``Error:`` on failure.
        """
        text = args.get("text", "")
        pattern = args.get("pattern", "")
        if not text:
            return "Error: no text provided"
        if not pattern:
            return "Error: no pattern provided"

        try:
            group = int(args.get("group", 0))
        except (TypeError, ValueError):
            return "Error: group must be an integer"

        flag_str = args.get("flags", "")
        flags = 0
        for f in flag_str:
            if f == "i":
                flags |= re.IGNORECASE
            elif f == "m":
                flags |= re.MULTILINE
            elif f == "s":
                flags |= re.DOTALL
            elif f == "x":
                flags |= re.VERBOSE

        try:
            compiled = re.compile(pattern, flags)
            matches = compiled.findall(text)
        except re.error as e:
            return f"Error: invalid regex: {e}"

        if not matches:
            return "No matches found."

        # Regex capture groups are 1-based; group 0 = whole match.
        if isinstance(matches[0], tuple):
            out = []
            for m in matches[: _MAX_MATCHES]:
                idx = group - 1 if group > 0 else 0
                if 0 <= idx < len(m):
                    out.append(str(m[idx]))
                else:
                    out.append(str(m))
        else:
            out = [str(m) for m in matches[: _MAX_MATCHES]]

        return "\n".join(out) if out else "No matches found."


TOOLS = [RegexExtract()]
BUNDLES = ["files", "code", "all"]
