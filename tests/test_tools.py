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
import sqlite3
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


class TestGithubSearchTool(_ScratchpadTestCase):
    """swarm/tools/github_search.py — GithubSearch."""

    def test_no_query_returns_error(self):
        result = self.reg.execute("github_search", {})
        self.assertEqual(result, "Error: no query provided")

    def test_unsupported_type_returns_error(self):
        result = self.reg.execute("github_search", {"query": "zig", "type": "wiki"})
        self.assertIn("unsupported type", result)

    def test_repositories_search(self):
        data = {"items": [
            {"full_name": "tensorflow/tensorflow", "description": "ML framework",
             "stargazers_count": 180000, "html_url": "https://github.com/tensorflow/tensorflow"}
        ]}
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(data).encode()
            result = self.reg.execute("github_search", {"query": "tensorflow"})
        self.assertIn("tensorflow/tensorflow", result)
        self.assertIn("ML framework", result)
        self.assertIn("https://github.com/tensorflow/tensorflow", result)

    def test_issues_search(self):
        data = {"items": [
            {"number": 42, "title": "Bug: crash on startup", "state": "open",
             "repository_url": "https://api.github.com/repos/a/b",
             "html_url": "https://github.com/a/b/issues/42"}
        ]}
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(data).encode()
            result = self.reg.execute("github_search", {"query": "crash", "type": "issues"})
        self.assertIn("b#42", result)
        self.assertIn("Bug: crash on startup", result)

    def test_code_search(self):
        data = {"items": [
            {"path": "src/main.py", "html_url": "https://github.com/a/b/blob/main/src/main.py",
             "repository": {"full_name": "a/b"}}
        ]}
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(data).encode()
            result = self.reg.execute("github_search", {"query": "def main", "type": "code"})
        self.assertIn("main.py in a/b", result)

    def test_logs_sources_to_scratchpad(self):
        data = {"items": [
            {"full_name": "a/b", "description": "d", "stargazers_count": 1,
             "html_url": "https://github.com/a/b"}
        ]}
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(data).encode()
            self.reg.execute("github_search", {"query": "a b"}, worker_name="Cyrus")
        sources = self.sp.get_all_sources()
        self.assertEqual(len(sources), 1)
        self.assertEqual(sources[0][1], "https://github.com/a/b")

    def test_no_results_message(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = (
                json.dumps({"items": []}).encode()
            )
            result = self.reg.execute("github_search", {"query": "zzzznope"})
        self.assertIn("No GitHub", result)

    def test_http_error_returns_error_string(self):
        with patch("urllib.request.urlopen", side_effect=OSError("rate limited")):
            result = self.reg.execute("github_search", {"query": "zig"})
        self.assertIn("[GithubSearch error:", result)


class TestWaybackMachineTool(_ScratchpadTestCase):
    """swarm/tools/wayback_machine.py — WaybackMachine."""

    def test_no_url_returns_error(self):
        result = self.reg.execute("wayback_machine", {})
        self.assertEqual(result, "Error: no URL provided")

    def test_returns_closest_snapshot(self):
        data = {"archived_snapshots": {"closest": {
            "url": "https://web.archive.org/web/20200101000000/https://example.com",
            "timestamp": "20200101000000",
        }}}
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(data).encode()
            result = self.reg.execute("wayback_machine", {"url": "https://example.com"})
        self.assertIn("web.archive.org/web/20200101000000/https://example.com", result)
        self.assertIn("20200101000000", result)

    def test_logs_snapshot_to_scratchpad(self):
        data = {"archived_snapshots": {"closest": {
            "url": "https://web.archive.org/web/20200101000000/https://example.com",
            "timestamp": "20200101000000",
        }}}
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = json.dumps(data).encode()
            self.reg.execute("wayback_machine", {"url": "https://example.com"}, worker_name="Ash")
        sources = self.sp.get_all_sources()
        self.assertEqual(len(sources), 1)
        self.assertIn("web.archive.org", sources[0][1])
        self.assertEqual(len(self.sp.get_all_findings()), 1)

    def test_no_snapshot_message(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = (
                json.dumps({"archived_snapshots": {}}).encode()
            )
            result = self.reg.execute("wayback_machine", {"url": "https://example.com"})
        self.assertIn("No archive found", result)

    def test_http_error_returns_error_string(self):
        with patch("urllib.request.urlopen", side_effect=OSError("timeout")):
            result = self.reg.execute("wayback_machine", {"url": "https://example.com"})
        self.assertIn("[WaybackMachine error:", result)


class TestHttpRequestTool(_ScratchpadTestCase):
    """swarm/tools/http_request.py — HttpRequest."""

    def test_no_url_returns_error(self):
        result = self.reg.execute("http_request", {})
        self.assertEqual(result, "Error: no URL provided")

    def test_non_http_url_returns_error(self):
        result = self.reg.execute("http_request", {"url": "ftp://example.com"})
        self.assertIn("must start with http", result)

    def test_unsupported_method_returns_error(self):
        result = self.reg.execute("http_request", {"url": "https://example.com", "method": "TRACE"})
        self.assertIn("unsupported method", result)

    def test_get_returns_body(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = b'{"ok": true}'
            result = self.reg.execute("http_request", {"url": "https://api.example.com/data"})
        self.assertIn('"ok": true', result)

    def test_truncates_large_body(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = b"x" * 10000
            result = self.reg.execute("http_request", {"url": "https://api.example.com/big"})
        self.assertIn("truncated", result)

    def test_logs_finding(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value.__enter__.return_value.read.return_value = b"ok"
            self.reg.execute("http_request", {"url": "https://api.example.com"}, worker_name="Romy")
        findings = self.sp.get_all_findings()
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][0], "Romy")
        self.assertEqual(len(self.sp.get_all_sources()), 0)  # findings only, no sources

    def test_http_error_returns_error_string(self):
        with patch("urllib.request.urlopen", side_effect=OSError("refused")):
            result = self.reg.execute("http_request", {"url": "https://api.example.com"})
        self.assertIn("[HttpRequest error:", result)


class TestPdfExtractTool(unittest.TestCase):
    """swarm/tools/pdf_extract.py — PdfExtract."""

    def setUp(self):
        self.reg = _fresh_registry()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.pdf = self.dir / "paper.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 fake")

    def tearDown(self):
        self.tmp.cleanup()
        reset_registry()
        reset_skill_registry()

    def test_no_path_returns_error(self):
        result = self.reg.execute("pdf_extract", {})
        self.assertEqual(result, "Error: no path provided")

    def test_missing_file_returns_error(self):
        result = self.reg.execute("pdf_extract", {"path": "/nonexistent/x.pdf"})
        self.assertIn("file not found", result)

    def test_missing_pypdf_returns_clear_error(self):
        with patch.dict("sys.modules", {"pypdf": None}):
            result = self.reg.execute("pdf_extract", {"path": str(self.pdf)})
        self.assertIn("'pdf' extra", result)
        self.assertIn("pip install -e '.[pdf]'", result)

    def test_extracts_text_via_pypdf(self):
        class _FakePage:
            def extract_text(self):
                return "Abstract: attention mechanisms."

        class _FakeReader:
            def __init__(self, *a, **k):
                self.pages = [_FakePage()]

        with patch.dict("sys.modules", {"pypdf": type("pypdf", (), {"PdfReader": _FakeReader})()}):
            result = self.reg.execute("pdf_extract", {"path": str(self.pdf)})
        self.assertIn("Abstract: attention mechanisms", result)

    def test_single_page_selection(self):
        class _FakePage:
            def __init__(self, txt):
                self.txt = txt

            def extract_text(self):
                return self.txt

        class _FakeReader:
            def __init__(self, *a, **k):
                self.pages = [_FakePage("page one"), _FakePage("page two")]

        with patch.dict("sys.modules", {"pypdf": type("pypdf", (), {"PdfReader": _FakeReader})()}):
            result = self.reg.execute("pdf_extract", {"path": str(self.pdf), "page": 2})
        self.assertIn("page two", result)
        self.assertNotIn("page one", result)

    def test_scanned_pdf_message(self):
        class _FakePage:
            def extract_text(self):
                return ""

        class _FakeReader:
            def __init__(self, *a, **k):
                self.pages = [_FakePage()]

        with patch.dict("sys.modules", {"pypdf": type("pypdf", (), {"PdfReader": _FakeReader})()}):
            result = self.reg.execute("pdf_extract", {"path": str(self.pdf)})
        self.assertIn("scanned/image", result)


class TestSqlQueryTool(_ScratchpadTestCase):
    """swarm/tools/sql_query.py — SqlQuery."""

    def setUp(self):
        super().setUp()
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.db = self.dir / "data.db"
        conn = sqlite3.connect(str(self.db))
        conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT, price REAL)")
        conn.executemany(
            "INSERT INTO items (name, price) VALUES (?, ?)",
            [("apple", 1.0), ("banana", 0.5), ("cherry", 2.5)],
        )
        conn.commit()
        conn.close()

    def tearDown(self):
        self.tmp.cleanup()
        super().tearDown()

    def test_no_path_returns_error(self):
        result = self.reg.execute("sql_query", {"query": "SELECT 1"})
        self.assertEqual(result, "Error: no path provided")

    def test_missing_db_returns_error(self):
        result = self.reg.execute("sql_query", {"path": "/nonexistent/x.db", "query": "SELECT 1"})
        self.assertIn("database not found", result)

    def test_no_query_returns_error(self):
        result = self.reg.execute("sql_query", {"path": str(self.db)})
        self.assertEqual(result, "Error: no query provided")

    def test_select_returns_rows(self):
        result = self.reg.execute("sql_query", {"path": str(self.db), "query": "SELECT name, price FROM items ORDER BY id"})
        self.assertIn("apple", result)
        self.assertIn("1.0", result)
        self.assertIn("banana", result)
        self.assertIn("name | price", result)

    def test_write_query_rejected(self):
        result = self.reg.execute("sql_query", {"path": str(self.db), "query": "DELETE FROM items"})
        self.assertIn("only read-only", result)

    def test_no_rows_message(self):
        result = self.reg.execute(
            "sql_query", {"path": str(self.db), "query": "SELECT * FROM items WHERE price > 100"}
        )
        self.assertIn("no rows", result)

    def test_invalid_sql_returns_error(self):
        result = self.reg.execute("sql_query", {"path": str(self.db), "query": "SELECT * FROM nope"})
        self.assertIn("[SqlQuery error:", result)

    def test_logs_finding(self):
        self.reg.execute("sql_query", {"path": str(self.db), "query": "SELECT COUNT(*) FROM items"}, worker_name="Zara")
        findings = self.sp.get_all_findings()
        self.assertEqual(len(findings), 1)
        self.assertEqual(len(self.sp.get_all_sources()), 0)


class TestRegexExtractTool(unittest.TestCase):
    """swarm/tools/regex_extract.py — RegexExtract."""

    def setUp(self):
        self.reg = _fresh_registry()

    def tearDown(self):
        reset_registry()
        reset_skill_registry()

    def test_no_text_returns_error(self):
        result = self.reg.execute("regex_extract", {"pattern": r"\d+"})
        self.assertEqual(result, "Error: no text provided")

    def test_no_pattern_returns_error(self):
        result = self.reg.execute("regex_extract", {"text": "abc 123"})
        self.assertEqual(result, "Error: no pattern provided")

    def test_extracts_numbers(self):
        result = self.reg.execute("regex_extract", {"text": "orders: 10, 20, 30", "pattern": r"\d+"})
        self.assertEqual(result, "10\n20\n30")

    def test_capture_group(self):
        result = self.reg.execute(
            "regex_extract", {"text": "price=$5.25 qty=3", "pattern": r"price=\$(\d+\.\d+)"}
        )
        self.assertEqual(result, "5.25")

    def test_group_index_selects_subgroup(self):
        result = self.reg.execute(
            "regex_extract",
            {"text": "2023-01-15 and 2024-06-01", "pattern": r"(\d{4})-(\d{2})-(\d{2})", "group": 2},
        )
        self.assertEqual(result, "01\n06")
    def test_case_insensitive_flag(self):
        result = self.reg.execute(
            "regex_extract", {"text": "HeLLo world", "pattern": r"hello", "flags": "i"}
        )
        self.assertEqual(result, "HeLLo")  # whole match preserved as-is

    def test_no_matches_message(self):
        result = self.reg.execute("regex_extract", {"text": "abc", "pattern": r"\d+"})
        self.assertIn("No matches", result)

    def test_invalid_regex_returns_error(self):
        result = self.reg.execute("regex_extract", {"text": "abc", "pattern": r"("})
        self.assertIn("invalid regex", result)


class TestTextDiffTool(unittest.TestCase):
    """swarm/tools/text_diff.py — TextDiff."""

    def setUp(self):
        self.reg = _fresh_registry()

    def tearDown(self):
        reset_registry()
        reset_skill_registry()

    def test_no_original_returns_error(self):
        result = self.reg.execute("text_diff", {"changed": "x"})
        self.assertEqual(result, "Error: no original text provided")

    def test_no_changed_returns_error(self):
        result = self.reg.execute("text_diff", {"original": "x"})
        self.assertEqual(result, "Error: no changed text provided")

    def test_identical_texts(self):
        result = self.reg.execute("text_diff", {"original": "same", "changed": "same"})
        self.assertIn("identical", result)

    def test_shows_added_and_removed_lines(self):
        result = self.reg.execute(
            "text_diff",
            {"original": "apple\nbanana", "changed": "apple\ncherry"},
        )
        self.assertIn("-banana", result)
        self.assertIn("+cherry", result)

    def test_honors_labels(self):
        result = self.reg.execute(
            "text_diff",
            {"original": "one", "changed": "two", "label1": "claim", "label2": "source"},
        )
        self.assertIn("--- claim", result)
        self.assertIn("+++ source", result)


class TestDateCalculatorTool(unittest.TestCase):
    """swarm/tools/date_calculator.py — DateCalculator."""

    def setUp(self):
        self.reg = _fresh_registry()

    def tearDown(self):
        reset_registry()
        reset_skill_registry()

    def test_no_operation_returns_error(self):
        result = self.reg.execute("date_calculator", {"date1": "2020-01-01"})
        self.assertEqual(result, "Error: no operation provided")

    def test_no_date1_returns_error(self):
        result = self.reg.execute("date_calculator", {"operation": "weekday"})
        self.assertEqual(result, "Error: no date1 provided")

    def test_invalid_date_returns_error(self):
        result = self.reg.execute("date_calculator", {"operation": "weekday", "date1": "not-a-date"})
        self.assertIn("invalid date1", result)

    def test_days_between(self):
        result = self.reg.execute(
            "date_calculator", {"operation": "days_between", "date1": "2024-01-01", "date2": "2024-01-31"}
        )
        self.assertIn("30 days", result)

    def test_days_between_absolute(self):
        result = self.reg.execute(
            "date_calculator", {"operation": "days_between", "date1": "2024-01-31", "date2": "2024-01-01"}
        )
        self.assertIn("30 days", result)  # order-independent

    def test_weekday(self):
        result = self.reg.execute("date_calculator", {"operation": "weekday", "date1": "2024-07-04"})
        self.assertIn("Thursday", result)

    def test_age(self):
        result = self.reg.execute("date_calculator", {"operation": "age", "date1": "2000-01-01"})
        self.assertIn("years", result)

    def test_add_days(self):
        result = self.reg.execute("date_calculator", {"operation": "add_days", "date1": "2024-01-01", "days": 10})
        self.assertIn("2024-01-11", result)

    def test_subtract_days(self):
        result = self.reg.execute("date_calculator", {"operation": "add_days", "date1": "2024-01-11", "days": -10})
        self.assertIn("2024-01-01", result)

    def test_missing_days_returns_error(self):
        result = self.reg.execute("date_calculator", {"operation": "add_days", "date1": "2024-01-01"})
        self.assertIn("days must be provided", result)

    def test_unknown_operation_returns_error(self):
        result = self.reg.execute("date_calculator", {"operation": "nope", "date1": "2024-01-01"})
        self.assertIn("unknown operation", result)


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

    def test_reads_file_and_calls_vision_model(self):
        captured = {}

        def fake_call_llm(model, messages, **kwargs):
            captured["model"] = model
            captured["messages"] = messages
            return "a red square"

        with patch("swarm.tools.vision.call_llm", side_effect=fake_call_llm):
            result = self.reg.execute("read_image", {"path": str(self.img)})
        self.assertEqual(result, "a red square")
        self.assertEqual(captured["model"], "ollama/qwen3.5:397b-cloud")
        content = captured["messages"][0]["content"]
        self.assertEqual(content[0]["type"], "text")
        self.assertEqual(content[1]["type"], "image_url")
        self.assertTrue(content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,"))

    def test_empty_response_handled(self):
        with patch("swarm.tools.vision.call_llm", return_value=""):
            result = self.reg.execute("read_image", {"path": str(self.img)})
        self.assertEqual(result, "(vision model returned empty)")

    def test_llm_error_surfaced(self):
        with patch("swarm.tools.vision.call_llm", return_value="[LLM error: boom]"):
            result = self.reg.execute("read_image", {"path": str(self.img)})
        self.assertIn("[ReadImage error:", result)

    def test_vision_model_env_respected(self):
        captured = {}

        def fake_call_llm(model, messages, **kwargs):
            captured["model"] = model
            return "ok"

        with patch.dict(os.environ, {"SWARM_VISION_MODEL": "openai/gpt-4o"}):
            with patch("swarm.tools.vision.call_llm", side_effect=fake_call_llm):
                self.reg.execute("read_image", {"path": str(self.img)})
        self.assertEqual(captured["model"], "openai/gpt-4o")


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
