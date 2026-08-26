"""Hermetic tests for the result cache (swarm/cache.py).

Uses a temp directory so no real cache file is touched. Verifies round-trip,
TTL expiry, size sweep, and concurrency safety.

Run with:
    python3 -m unittest discover tests/
    pytest tests/
"""

from __future__ import annotations

import os
import tempfile
import threading
import unittest

from swarm.cache import Cache, cache_key, cache_enabled, reset_cache


class TestCache(unittest.TestCase):
    """swarm/cache.py — Cache."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache = Cache(path=os.path.join(self._tmp.name, "c.db"))

    def tearDown(self):
        self.cache.close()
        self._tmp.cleanup()
        reset_cache()

    def test_round_trip(self):
        key = cache_key("ddgs", "capital of france")
        self.assertIsNone(self.cache.get(key))
        self.cache.set(key, '{"results": []}', ttl=3600)
        self.assertEqual(self.cache.get(key), '{"results": []}')

    def test_ttl_expiry(self):
        key = cache_key("ddgs", "q")
        self.cache.set(key, "v", ttl=1)
        self.assertEqual(self.cache.get(key), "v")
        self.cache.set(key, "v", ttl=-1)  # already expired
        self.assertIsNone(self.cache.get(key))

    def test_overwrite(self):
        key = cache_key("ddgs", "q")
        self.cache.set(key, "v1", ttl=3600)
        self.cache.set(key, "v2", ttl=3600)
        self.assertEqual(self.cache.get(key), "v2")

    def test_key_differs_by_backend(self):
        a = cache_key("ddgs", "q")
        b = cache_key("searxng", "q")
        self.assertNotEqual(a, b)

    def test_key_differs_by_query(self):
        a = cache_key("ddgs", "q1")
        b = cache_key("ddgs", "q2")
        self.assertNotEqual(a, b)

    def test_size_sweep_caps_rows(self):
        cache = Cache(path=os.path.join(self._tmp.name, "c2.db"), max_rows=5)
        for i in range(20):
            cache.set(cache_key("ddgs", f"q{i}"), f"v{i}", ttl=3600)
        count = cache._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        self.assertLessEqual(count, 5)
        cache.close()

    def test_concurrent_writes_do_not_corrupt(self):
        errors = []

        def writer(i):
            try:
                for j in range(20):
                    self.cache.set(cache_key("ddgs", f"w{i}-{j}"), f"v{i}-{j}", ttl=3600)
            except Exception as e:  # pragma: no cover
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        # All 100 keys present (no corruption / lost writes)
        count = self.cache._conn.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
        self.assertEqual(count, 100)

    def test_clear(self):
        key = cache_key("ddgs", "q")
        self.cache.set(key, "v", ttl=3600)
        self.cache.clear()
        self.assertIsNone(self.cache.get(key))

    def test_cache_enabled_env(self):
        old = os.environ.get("SWARM_CACHE")
        try:
            os.environ["SWARM_CACHE"] = "1"
            self.assertTrue(cache_enabled())
            os.environ["SWARM_CACHE"] = "0"
            self.assertFalse(cache_enabled())
        finally:
            if old is None:
                os.environ.pop("SWARM_CACHE", None)
            else:
                os.environ["SWARM_CACHE"] = old


if __name__ == "__main__":
    unittest.main()
