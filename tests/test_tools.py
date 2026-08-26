"""Hermetic per-tool tests for the modular tool system (swarm/tools/).

Every tool is exercised in isolation with network and Ollama calls mocked,
so this suite runs offline in CI. It complements the live smoke script at
the repo root (test_tools.py), which hits real ddgs/Ollama.

Run with:
    python3 -m unittest discover tests/
    pytest tests/
"""

from __future__ import annotations

import csv
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm.scratchpad import Scratchpad, set_scratchpad
from swarm.skills import get_skill_registry, reset_skill_registry
from swarm.tools import get_registry, reset_registry
from swarm.tools.base import BaseTool

# The result cache is a process-wide singleton; hermetic tool tests must not
# leak cached values between tests (the cache has its own dedicated suite).
os.environ["SWARM_CACHE"] = "0"


def _fresh_registry():
    """Reset global registries and return a freshly discovered registry."""
    reset_registry()
    reset_skill_registry()
    return get_registry()


class _ScratchpadTestCase(unittest.TestCase):
    """Base for tools that write to the global scratchpad."""

    def setUp(self):
        self.reg = _fresh_registry()
        self.sp = Scratchpad()
        set_scratchpad(self.sp)

    def tearDown(self):
        set_scratchpad(None)
        self.sp.close()
        reset_registry()
        reset_skill_registry()


class TestWebSearchTool(_ScratchpadTestCase):
    """swarm/tools/web_search.py — WebSearch."""

    def test_no_query_returns_error(self):
        result = self.reg.execute("web_search", {})
        self.assertEqual(result, "Error: no query provided")

    def test_runs_via_ddgs(self):
        fake_results = [
            {"title": "Paris", "body": "Capital of France", "href": "https://example.com/paris"},
        ]
        with patch("ddgs.DDGS") as mock_ddgs:
            mock_ddgs.return_value.__enter__.return_value.text.return_value = fake_results
            result = self.reg.execute("web_search", {"query": "capital of France"})
        self.assertIn("Paris", result)
        self.assertIn("https://example.com/paris", result)

    def test_ddgs_logs_source_to_scratchpad(self):
        fake_results = [
            {"title": "Paris", "body": "Capital of France", "href": "https://example.com/paris"},
        ]
        with patch("ddgs.DDGS") as mock_ddgs:
            mock_ddgs.return_value.__enter__.return_value.text.return_value = fake_results
            self.reg.execute("web_search", {"query": "capital of France"}, worker_name="Vera")
        sources = self.sp.get_all_sources()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0][1], "https://example.com/paris")
        findings = self.sp.get_all_findings()
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][0], "Vera")

    def test_unknown_backend_returns_error(self):
        with patch.dict(os.environ, {"SEARCH_BACKEND": "bogus"}):
            result = self.reg.execute("web_search", {"query": "anything"})
        self.assertIn("unknown backend", result)

    def test_ddgs_import_error_falls_back_to_html_scrape(self):
        html = (
            '<a class="result__a" href="https://example.com/x">Title X</a>'
            '<a class="result__snippet">Snippet X</a>'
        )
        with patch("ddgs.DDGS", side_effect=ImportError("no ddgs")):
            with patch("urllib.request.urlopen") as mock_urlopen:
                mock_urlopen.return_value.__enter__.return_value.read.return_value = html.encode()
                result = self.reg.execute("web_search", {"query": "fallback test"})
        self.assertIn("Title X", result)
        self.assertIn("https://example.com/x", result)


class TestWebExtractTool(_ScratchpadTestCase):
    """swarm/tools/web_extract.py — WebExtract."""

    def test_no_url_returns_error(self):
        result = self.reg.execute("web_extract", {})
        self.assertEqual(result, "Error: no URL provided")

    def test_extracts_and_cleans_html(self):
        html = "<html><body><p>Hello <b>world</b>  with   spaces</p></body></html>"
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = html.encode()
            result = self.reg.execute("web_extract", {"url": "https://example.com"})
        self.assertIn("Hello world with spaces", result)
        self.assertLessEqual(len(result), 3000)

    def test_logs_to_scratchpad(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = b"<p>hi</p>"
            self.reg.execute("web_extract", {"url": "https://example.com"}, worker_name="Cyrus")
        sources = self.sp.get_all_sources()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0][1], "https://example.com")
        self.assertEqual(len(self.sp.get_all_findings()), 1)

    def test_http_error_returns_error_string(self):
        with patch("urllib.request.urlopen", side_effect=OSError("connection refused")):
            result = self.reg.execute("web_extract", {"url": "https://example.com"})
        self.assertIn("[Extract error:", result)


class TestWikipediaSearchTool(_ScratchpadTestCase):
    """swarm/tools/wikipedia_search.py — WikipediaSearch."""

    def _fake_query(self, titles_and_snippets):
        data = {
            "query": {
                "search": [
                    {"title": t, "snippet": f'<span class="searchmatch">{s}</span>'}
                    for t, s in titles_and_snippets
                ]
            }
        }
        return json.dumps(data).encode()

    def test_no_query_returns_error(self):
        result = self.reg.execute("wikipedia_search", {})
        self.assertEqual(result, "Error: no query provided")

    def test_returns_titles_and_cleaned_snippets(self):
        payload = self._fake_query([("Quantum computing", "uses qubits"), ("Qubit", "basic unit")])
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = payload
            result = self.reg.execute("wikipedia_search", {"query": "quantum computing"})
        self.assertIn("Quantum computing", result)
        self.assertIn("uses qubits", result)  # markup stripped
        self.assertIn("https://en.wikipedia.org/wiki/Quantum_computing", result)
        self.assertNotIn("<span", result)

    def test_logs_sources_to_scratchpad(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = self._fake_query(
                [("Paris", "capital of France")]
            )
            self.reg.execute("wikipedia_search", {"query": "Paris"}, worker_name="Vera")
        sources = self.sp.get_all_sources()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0][1], "https://en.wikipedia.org/wiki/Paris")
        self.assertEqual(len(self.sp.get_all_findings()), 1)

    def test_no_results_message(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = (
                json.dumps({"query": {"search": []}}).encode()
            )
            result = self.reg.execute("wikipedia_search", {"query": "zzzznope"})
        self.assertIn("No Wikipedia results", result)

    def test_http_error_returns_error_string(self):
        with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            result = self.reg.execute("wikipedia_search", {"query": "Paris"})
        self.assertIn("[WikipediaSearch error:", result)


class TestArxivSearchTool(_ScratchpadTestCase):
    """swarm/tools/arxiv_search.py — ArxivSearch."""

    ATOM = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<feed xmlns="http://www.w3.org/2005/Atom">'
        "<entry><id>http://arxiv.org/abs/1706.03762</id>"
        "<title>Attention Is All You Need</title>"
        "<summary>  The dominant sequence transduction models are based on complex "
        "recurrent networks.  </summary>"
        "<published>2017-06-12T00:00:00Z</published></entry>"
        "</feed>"
    )

    def test_no_query_returns_error(self):
        result = self.reg.execute("arxiv_search", {})
        self.assertEqual(result, "Error: no query provided")

    def test_returns_papers(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = self.ATOM.encode()
            result = self.reg.execute("arxiv_search", {"query": "attention is all you need"})
        self.assertIn("Attention Is All You Need", result)
        self.assertIn("2017-06-12", result)
        self.assertIn("http://arxiv.org/abs/1706.03762", result)
        self.assertIn("sequence transduction", result)  # whitespace collapsed

    def test_logs_sources_to_scratchpad(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = self.ATOM.encode()
            self.reg.execute("arxiv_search", {"query": "transformers"}, worker_name="Zara")
        sources = self.sp.get_all_sources()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0][1], "http://arxiv.org/abs/1706.03762")
        self.assertEqual(len(self.sp.get_all_findings()), 1)

    def test_no_results_message(self):
        empty_feed = '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = empty_feed.encode()
            result = self.reg.execute("arxiv_search", {"query": "zzzznope"})
        self.assertIn("No arXiv papers", result)

    def test_http_error_returns_error_string(self):
        with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            result = self.reg.execute("arxiv_search", {"query": "transformers"})
        self.assertIn("[ArxivSearch error:", result)

    def test_malformed_xml_returns_error(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = b"not xml"
            result = self.reg.execute("arxiv_search", {"query": "transformers"})
        self.assertIn("[ArxivSearch error:", result)


class TestScratchpadAddTool(_ScratchpadTestCase):
    """swarm/tools/scratchpad.py — ScratchpadAdd."""

    def test_no_finding_returns_not_available(self):
        set_scratchpad(None)
        result = self.reg.execute("scratchpad_add", {})
        self.assertEqual(result, "[Scratchpad: not available]")

    def test_saves_finding_round_trip(self):
        result = self.reg.execute(
            "scratchpad_add",
            {"finding": "GDP grew 3%", "source_url": "https://example.com", "category": "money", "confidence": "high"},
            worker_name="Romy",
        )
        self.assertIn("saved finding", result)
        findings = self.sp.get_all_findings()
        self.assertEqual(len(findings), 1)
        worker, source_url, finding, category, confidence = findings[0]
        self.assertEqual(worker, "Romy")
        self.assertEqual(source_url, "https://example.com")
        self.assertEqual(finding, "GDP grew 3%")
        self.assertEqual(category, "money")
        self.assertEqual(confidence, "high")

    def test_default_category_and_confidence(self):
        self.reg.execute("scratchpad_add", {"finding": "just a fact"})
        findings = self.sp.get_all_findings()
        self.assertEqual(findings[0][3], "general")
        self.assertEqual(findings[0][4], "medium")


class TestPythonExecTool(unittest.TestCase):
    """swarm/tools/python_exec.py — PythonExec."""

    def setUp(self):
        self.reg = _fresh_registry()

    def tearDown(self):
        reset_registry()
        reset_skill_registry()

    def test_no_code_returns_error(self):
        result = self.reg.execute("python_exec", {})
        self.assertEqual(result, "Error: no code provided")

    def test_print_output_returned(self):
        result = self.reg.execute("python_exec", {"code": "print('hello')"})
        self.assertEqual(result, "hello")

    def test_math_module_available(self):
        result = self.reg.execute("python_exec", {"code": "import math; print(math.sqrt(144))"})
        self.assertEqual(result, "12.0")

    def test_no_output_message(self):
        result = self.reg.execute("python_exec", {"code": "x = 1 + 1"})
        self.assertIn("no output", result)

    def test_error_surfaced(self):
        result = self.reg.execute("python_exec", {"code": "1/0"})
        self.assertIn("Error:", result)
        self.assertIn("division by zero", result)

    def test_open_blocked(self):
        result = self.reg.execute("python_exec", {"code": "open('/tmp/x', 'w')"})
        self.assertIn("Error:", result)

    def test_nested_exec_blocked(self):
        result = self.reg.execute("python_exec", {"code": "exec('print(1)')"})
        self.assertIn("Error:", result)

    def test_stdout_captured_not_leaked(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            self.reg.execute("python_exec", {"code": "print('captured')"})
        self.assertNotIn("captured", buf.getvalue())


class TestReadFileTool(unittest.TestCase):
    """swarm/tools/file_reader.py — ReadFile."""

    def setUp(self):
        self.reg = _fresh_registry()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()
        reset_registry()
        reset_skill_registry()

    def _write(self, name: str, content: str) -> str:
        path = self.dir / name
        path.write_text(content, encoding="utf-8")
        return str(path)

    def test_no_path_returns_error(self):
        result = self.reg.execute("read_file", {})
        self.assertEqual(result, "Error: no path provided")

    def test_missing_file_returns_error(self):
        result = self.reg.execute("read_file", {"path": "/nonexistent/file.txt"})
        self.assertIn("file not found", result)

    def test_txt_read_and_truncated(self):
        path = self._write("data.txt", "line one\nline two\n")
        result = self.reg.execute("read_file", {"path": path, "max_chars": 5})
        self.assertIn("line ", result)
        self.assertIn("truncated", result)
        result_full = self.reg.execute("read_file", {"path": path})
        self.assertIn("line one", result_full)

    def test_csv_round_trip(self):
        path = self.dir / "data.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "x"])
            for i in range(1, 4):
                writer.writerow([i, i * 10])
        result = self.reg.execute("read_file", {"path": str(path)})
        self.assertIn("id,x", result)
        self.assertIn("2,20", result)

    def test_csv_truncation_note(self):
        path = self.dir / "big.csv"
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["id"])
            for i in range(1, 60):
                writer.writerow([i])
        result = self.reg.execute("read_file", {"path": str(path)})
        self.assertIn("more rows", result)

    def test_json_indented(self):
        path = self._write("data.json", json.dumps({"a": 1, "b": [1, 2]}))
        result = self.reg.execute("read_file", {"path": path})
        self.assertIn('"a": 1', result)
        self.assertIn("\n", result)

    def test_jsonld_array(self):
        path = self._write("data.jsonld", json.dumps([{"a": 1}, {"a": 2}]))
        result = self.reg.execute("read_file", {"path": path})
        self.assertIn('"a": 1', result)

    def test_jsonld_line_delimited(self):
        path = self._write("data.jsonld", '{"a": 1}\n{"a": 2}\n')
        result = self.reg.execute("read_file", {"path": path})
        self.assertIn('"a": 1', result)
        self.assertIn('"a": 2', result)

    def test_xml_round_trip(self):
        path = self._write("data.xml", "<root><item>hello</item></root>")
        result = self.reg.execute("read_file", {"path": path})
        self.assertIn("<root>", result)
        self.assertIn("hello", result)

    def test_unknown_extension_falls_back_to_text(self):
        path = self._write("notes.md", "# Title\nbody text")
        result = self.reg.execute("read_file", {"path": path})
        self.assertIn("# Title", result)
        self.assertIn("body text", result)


class TestReadImageTool(unittest.TestCase):
    """swarm/tools/vision.py — ReadImage."""

    def setUp(self):
        self.reg = _fresh_registry()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.img = self.dir / "test.png"
        self.img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)

    def tearDown(self):
        self.tmp.cleanup()
        reset_registry()
        reset_skill_registry()

    def test_missing_file_returns_error(self):
        result = self.reg.execute("read_image", {"path": "/nonexistent/img.png"})
        self.assertIn("file not found", result)

    def test_reads_file_and_calls_ollama(self):
        captured = {}

        def fake_urlopen(req, timeout=120):
            captured["url"] = req.full_url
            captured["payload"] = json.loads(req.data)
            return io.BytesIO(json.dumps({"message": {"content": "a red square"}}).encode())

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            result = self.reg.execute("read_image", {"path": str(self.img)})
        self.assertEqual(result, "a red square")
        self.assertIn("images", captured["payload"]["messages"][0])
        self.assertTrue(captured["payload"]["messages"][0]["images"][0])

    def test_empty_response_handled(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = (
                json.dumps({"message": {"content": ""}}).encode()
            )
            result = self.reg.execute("read_image", {"path": str(self.img)})
        self.assertEqual(result, "(vision model returned empty)")

    def test_ollama_http_error_surfaced(self):
        with patch("urllib.request.urlopen", side_effect=OSError("boom")):
            result = self.reg.execute("read_image", {"path": str(self.img)})
        self.assertIn("[ReadImage error:", result)

    def test_ollama_host_env_respected(self):
        captured = {}

        def fake_urlopen(req, timeout=120):
            captured["url"] = req.full_url
            return io.BytesIO(json.dumps({"message": {"content": "ok"}}).encode())

        with patch.dict(os.environ, {"OLLAMA_HOST": "http://example:9999"}):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                self.reg.execute("read_image", {"path": str(self.img)})
        self.assertIn("http://example:9999", captured["url"])


class TestSkillToolCoverage(unittest.TestCase):
    """Every skill's declared tools must resolve to real BaseTool instances."""

    def setUp(self):
        self.reg = _fresh_registry()

    def tearDown(self):
        reset_registry()
        reset_skill_registry()

    def test_all_skills_resolve_their_tools(self):
        sr = get_skill_registry()
        self.assertTrue(sr.names(), "expected at least one discovered skill")
        for name in sr.names():
            tools = sr.tools_for(name)
            self.assertTrue(tools, f"skill '{name}' resolves to zero tools")
            for tool in tools:
                self.assertIsInstance(tool, BaseTool, f"skill '{name}' resolved a non-tool: {tool!r}")

    def test_every_declared_tool_name_is_registered(self):
        sr = get_skill_registry()
        for name in sr.names():
            skill = sr.get(name)
            if skill is None:
                self.fail(f"skill '{name}' not found in registry")
            for tool_name in skill.tools:
                self.assertIsNotNone(
                    self.reg.get(tool_name),
                    f"skill '{name}' references unregistered tool '{tool_name}'",
                )


if __name__ == "__main__":
    unittest.main()
