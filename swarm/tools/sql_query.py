"""SQL query tool — run read-only SQL against a local SQLite database."""
from __future__ import annotations
import os
import sqlite3
from swarm.scratchpad import get_scratchpad
from .base import BaseTool

_MAX_ROWS = 50
_MAX_CHARS = 8000
# Hard allowlist: only read-only statements. No writes, no pragma tricks.
_ALLOWED_PREFIXES = ("select", "with", "pragma table_info", "pragma database_list")


class SqlQuery(BaseTool):
    """Run a read-only SQL query against a local SQLite database file.

    Lets workers inspect and query a referenced ``.db``/``.sqlite`` data file.
    Only ``SELECT`` (and safe ``WITH``/``PRAGMA table_info``) statements are
    allowed — writes are rejected. Results are returned as a text table.
    """

    name = "sql_query"
    description = (
        "Run a read-only SQL query against a local SQLite database file "
        "(.db/.sqlite). Use when the question references a database file and "
        "you need to inspect or analyze its data."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the SQLite database file",
            },
            "query": {
                "type": "string",
                "description": "Read-only SQL query (SELECT only)",
            },
            "max_rows": {
                "type": "number",
                "description": "Max result rows to return (default 50)",
            },
        },
        "required": ["path", "query"],
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        """Execute a read-only SQL query.

        Args:
            args: Tool arguments. ``path`` (database file) and ``query`` are
                required; ``max_rows`` caps the returned rows (default 50).
            worker_name: Unused by this tool; accepted for interface parity.

        Returns:
            Query results as a text table, or an error string starting with
            ``Error:`` / ``[SqlQuery error:`` on failure.
        """
        path = args.get("path", "")
        query = args.get("query", "")
        if not path:
            return "Error: no path provided"
        if not os.path.exists(path):
            return f"Error: database not found at {path}"
        if not query:
            return "Error: no query provided"

        stripped = query.lstrip()
        lowered = stripped.lower()
        if not any(lowered.startswith(p) for p in _ALLOWED_PREFIXES):
            return "Error: only read-only SELECT queries are allowed"

        max_rows = max(1, min(int(args.get("max_rows", _MAX_ROWS)), 200))

        try:
            conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5)
            conn.row_factory = sqlite3.Row
            cur = conn.execute(query)
            rows = cur.fetchmany(max_rows)
            cols = [d[0] for d in cur.description] if cur.description else []
            conn.close()
        except Exception as e:
            return f"[SqlQuery error: {e}]"

        if not cols:
            return "(query returned no columns)"
        if not rows:
            return "(query returned no rows)"

        header = " | ".join(cols)
        lines = [header, "-" * len(header)]
        for row in rows:
            lines.append(" | ".join(str(v) if v is not None else "" for v in row))
        out = "\n".join(lines)

        sp = get_scratchpad()
        if sp:
            sp.add_finding(worker_name, f"SQL query on {path}: {query}", "", "data", "medium")

        if len(out) > _MAX_CHARS:
            return f"{out[: _MAX_CHARS]}\n... (results truncated, {len(out)} chars total)"
        return out


TOOLS = [SqlQuery()]
BUNDLES = ["files", "code", "all"]
