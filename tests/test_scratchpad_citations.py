"""Hermetic tests for source dedup + credibility scoring in the scratchpad.

Run with:
    python3 -m unittest discover tests/
    pytest tests/
"""

from __future__ import annotations

import unittest

from swarm.scratchpad import (
    Scratchpad,
    extract_domain,
    normalize_url,
    score_source,
)


class TestUrlNormalization(unittest.TestCase):
    """swarm/scratchpad.py — normalize_url / extract_domain."""

    def test_strips_tracking_params_and_fragment(self):
        url = "https://Example.com/paris?utm_source=x&utm_medium=y&q=1#section"
        self.assertEqual(normalize_url(url), "https://example.com/paris?q=1")

    def test_lowercases_host(self):
        self.assertEqual(normalize_url("HTTPS://WWW.Example.COM/Path"), "https://www.example.com/Path")

    def test_keeps_distinct_paths(self):
        a = normalize_url("https://example.com/a")
        b = normalize_url("https://example.com/b")
        self.assertNotEqual(a, b)

    def test_extract_domain_strips_www(self):
        self.assertEqual(extract_domain("https://www.example.com/x"), "example.com")
        self.assertEqual(extract_domain("https://en.wikipedia.org/wiki/Paris"), "en.wikipedia.org")


class TestCredibilityScoring(unittest.TestCase):
    """swarm/scratchpad.py — score_source."""

    def test_gov_domain_boosted(self):
        self.assertGreater(score_source("https://www.census.gov/data"), 0.5)

    def test_unknown_domain_not_boosted(self):
        self.assertLessEqual(score_source("https://random-blog.example/x"), 0.5)

    def test_corroboration_increases_score(self):
        base = score_source("https://example.com/x", corroboration=1)
        corroborated = score_source("https://example.com/x", corroboration=4)
        self.assertGreater(corroborated, base)

    def test_recency_decay(self):
        fresh = score_source("https://example.com/x", first_seen="2026-08-01 00:00:00")
        old = score_source("https://example.com/x", first_seen="2020-01-01 00:00:00")
        self.assertGreater(fresh, old)

    def test_score_in_range(self):
        for url in ["https://a.gov/x", "https://b.com/y", "https://c.edu/z"]:
            s = score_source(url)
            self.assertGreaterEqual(s, 0.0)
            self.assertLessEqual(s, 1.0)


class TestScratchpadDedup(unittest.TestCase):
    """swarm/scratchpad.py — add_source dedup + top_sources."""

    def setUp(self):
        self.sp = Scratchpad()

    def tearDown(self):
        self.sp.close()

    def test_duplicate_url_increments_corroboration(self):
        self.sp.add_source("Vera", "https://example.com/paris?utm_source=x", "A", "s")
        self.sp.add_source("Cyrus", "https://example.com/paris?utm_source=y", "B", "s")
        sources = self.sp.get_all_sources()
        self.assertEqual(len(sources), 1)  # deduplicated
        top = self.sp.top_sources()
        self.assertEqual(top[0]["corroboration"], 2)

    def test_distinct_urls_not_deduped(self):
        self.sp.add_source("Vera", "https://example.com/a", "A", "s")
        self.sp.add_source("Vera", "https://example.com/b", "B", "s")
        self.assertEqual(len(self.sp.get_all_sources()), 2)

    def test_top_sources_ranked_by_credibility(self):
        self.sp.add_source("Vera", "https://www.census.gov/data", "Gov", "s")
        self.sp.add_source("Vera", "https://random-blog.example/x", "Blog", "s")
        self.sp.score_sources()
        top = self.sp.top_sources()
        self.assertEqual(top[0]["domain"], "census.gov")
        self.assertGreater(top[0]["credibility"], top[1]["credibility"])

    def test_top_sources_limit_and_min_credibility(self):
        for i in range(5):
            self.sp.add_source("Vera", f"https://example.com/{i}", f"T{i}", "s")
        self.sp.score_sources()
        self.assertEqual(len(self.sp.top_sources(limit=3)), 3)
        self.assertEqual(len(self.sp.top_sources(min_credibility=0.9)), 0)

    def test_findings_for_source(self):
        self.sp.add_finding("Vera", "Paris is the capital", "https://example.com/paris", "general", "high")
        findings = self.sp.findings_for_source("https://example.com/paris")
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0][1], "Paris is the capital")


if __name__ == "__main__":
    unittest.main()
