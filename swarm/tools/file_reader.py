"""File reader tool — read structured files (CSV, JSON, XML, TXT, XLSX)."""
from __future__ import annotations
import csv
import json
import os
import re
import xml.etree.ElementTree as ET
from .base import BaseTool


class ReadFile(BaseTool):
    name = "read_file"
    description = (
        "Read a file from disk and return its contents as text. "
        "Supports: .txt, .csv, .json, .xml, .jsonld, .py, .md, .docx (text extract). "
        "Use this when the question refers to an attached file, spreadsheet, "
        "or data file."
    )
    parameters = {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute path to the file",
            },
            "max_chars": {
                "type": "number",
                "description": "Maximum characters to return (default: 5000)",
            },
        },
        "required": ["path"],
    }

    def run(self, args: dict, worker_name: str = "") -> str:
        path = args.get("path", "")
        max_chars = int(args.get("max_chars", 5000))

        if not path:
            return "Error: no path provided"
        if not os.path.exists(path):
            return f"Error: file not found at {path}"

        ext = os.path.splitext(path)[1].lower()

        try:
            if ext == ".csv":
                return self._read_csv(path, max_chars)
            elif ext == ".json":
                return self._read_json(path, max_chars)
            elif ext == ".jsonld":
                return self._read_jsonld(path, max_chars)
            elif ext == ".xml":
                return self._read_xml(path, max_chars)
            elif ext == ".docx":
                return self._read_docx(path, max_chars)
            elif ext == ".xlsx":
                return self._read_xlsx(path, max_chars)
            else:
                # txt, md, py, etc. — just read as text
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read(max_chars)
                if os.path.getsize(path) > max_chars:
                    content += f"\n... (file truncated, {os.path.getsize(path)} bytes total)"
                return content
        except Exception as e:
            return f"[ReadFile error: {e}]"

    def _read_csv(self, path: str, max_chars: int) -> str:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            rows = list(reader)
        result = "\n".join([",".join(row) for row in rows[:50]])
        if len(rows) > 50:
            result += f"\n... ({len(rows) - 50} more rows)"
        return result[:max_chars]

    def _read_json(self, path: str, max_chars: int) -> str:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            data = json.load(f)
        return json.dumps(data, indent=2)[:max_chars]

    def _read_jsonld(self, path: str, max_chars: int) -> str:
        """JSON-LD: line-delimited JSON or array of objects."""
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        # Try parsing as array
        try:
            data = json.loads(content)
            return json.dumps(data, indent=2)[:max_chars]
        except json.JSONDecodeError:
            pass
        # Try line-delimited JSON
        lines = content.strip().split("\n")
        objs = []
        for line in lines[:50]:
            try:
                objs.append(json.loads(line))
            except json.JSONDecodeError:
                objs.append(line)
        return json.dumps(objs, indent=2)[:max_chars]

    def _read_xml(self, path: str, max_chars: int) -> str:
        tree = ET.parse(path)
        root = tree.getroot()
        return ET.tostring(root, encoding="unicode")[:max_chars]

    def _read_docx(self, path: str, max_chars: int) -> str:
        """Extract text from .docx files."""
        try:
            import zipfile
            text = []
            with zipfile.ZipFile(path) as z:
                with z.open("word/document.xml") as f:
                    xml_content = f.read().decode("utf-8", errors="ignore")
                    # Strip XML tags
                    text.append(re.sub(r"<[^>]+>", " ", xml_content))
            result = " ".join(text)
            return re.sub(r"\s+", " ", result).strip()[:max_chars]
        except ImportError:
            return "[ReadFile: zipfile module needed for .docx]"

    def _read_xlsx(self, path: str, max_chars: int) -> str:
        """Extract text from .xlsx files."""
        try:
            import zipfile
            import xml.etree.ElementTree as ET
            rows = []
            with zipfile.ZipFile(path) as z:
                # Find shared strings
                strings = {}
                if "xl/sharedStrings.xml" in z.namelist():
                    with z.open("xl/sharedStrings.xml") as f:
                        for si in ET.parse(f).getroot():
                            texts = [t.text or "" for t in si.iter("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}t")]
                            strings[len(strings)] = " ".join(texts)

                # Find sheets
                for name in z.namelist():
                    if name.startswith("xl/worksheets/sheet") and name.endswith(".xml"):
                        with z.open(name) as f:
                            tree = ET.parse(f)
                            sheet_rows = []
                            for row in tree.getroot():
                                row_data = []
                                for cell in row:
                                    v = cell.find("{http://schemas.openxmlformats.org/spreadsheetml/2006/main}v")
                                    val = v.text if v is not None else ""
                                    # Check if it's a shared string
                                    if val and val.isdigit() and int(val) in strings:
                                        val = strings[int(val)]
                                    row_data.append(val)
                                sheet_rows.append(",".join(row_data))
                            rows.extend(sheet_rows[:100])
            return "\n".join(rows)[:max_chars]
        except ImportError:
            return "[ReadFile: zipfile module needed for .xlsx]"


TOOLS = [ReadFile()]
BUNDLES = ["files", "all"]