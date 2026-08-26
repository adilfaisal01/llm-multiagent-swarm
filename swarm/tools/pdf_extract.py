"""PDF extract tool — read text from PDF files (optional pypdf extra)."""
from __future__ import annotations
import os
from swarm.scratchpad import get_scratchpad
from .base import BaseTool

_MAX_CHARS = 8000


class PdfExtract(BaseTool):
    """Extract text from a PDF file.

    Requires the optional ``pdf`` extra (``pip install -e ".[pdf]"``, which
    provides ``pypdf``). If the extra is missing, returns a clear error string
    instead of crashing — the tool loads fine without it.
    """

    name = "pdf_extract"
    description = (
        "Extract text from a PDF file (research papers, reports, forms). "
        "Use this when the question refers to an attached PDF document."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the .pdf file",
            },
            "page": {
                "type": "number",
                "description": "Optional page number (1-based); defaults to all pages",
            },
            "max_chars": {
                "type": "number",
                "description": "Maximum characters to return (default: 8000)",
            },
        },
        "required": ["path"],
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        """Extract text from a PDF.

        Args:
            args: Tool arguments. ``path`` is required; ``page`` optionally
                targets a single page (1-based); ``max_chars`` caps the
                returned length (default 8000).
            worker_name: Unused by this tool; accepted for interface parity.

        Returns:
            Extracted PDF text, or an error string starting with ``Error:`` /
            ``[PdfExtract error:`` on failure.
        """
        path = args.get("path", "")
        if not path:
            return "Error: no path provided"
        if not os.path.exists(path):
            return f"Error: file not found at {path}"

        try:
            from pypdf import PdfReader
        except ImportError:
            return (
                "[PdfExtract error: the optional 'pdf' extra is required. "
                "Install it with: pip install -e '.[pdf]'"
            )

        page = args.get("page")
        max_chars = int(args.get("max_chars", _MAX_CHARS))

        try:
            reader = PdfReader(path)
            if len(reader.pages) == 0:
                return "(PDF has no pages)"
            if page is not None:
                idx = max(0, min(int(page) - 1, len(reader.pages) - 1))
                pages = [reader.pages[idx]]
            else:
                pages = reader.pages
            text = "\n\n".join((p.extract_text() or "") for p in pages)
        except Exception as e:
            return f"[PdfExtract error: {e}]"

        if not text.strip():
            return "(PDF text extraction returned nothing — scanned/image PDF?)"

        sp = get_scratchpad()
        if sp:
            sp.add_finding(worker_name, f"Extracted PDF: {path}", "", "files", "medium")

        if len(text) > max_chars:
            return f"{text[:max_chars]}\n... (PDF truncated, {len(text)} chars total)"
        return text


TOOLS = [PdfExtract()]
BUNDLES = ["files", "all"]
