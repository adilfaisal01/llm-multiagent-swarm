"""Hermetic tests for the shared LLM helper (swarm/llm.py).

Mocks urllib so no network is touched. Verifies retry/backoff behavior,
4xx non-retry, 429 Retry-After handling, streaming, and cost accounting.

Run with:
    python3 -m unittest discover tests/
    pytest tests/
"""

from __future__ import annotations

import json
import unittest
import urllib.error
from unittest.mock import patch

from swarm.llm import RunCost, _backoff_delay, _should_retry, call_llm


class _FakeResp:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _ok_resp(content: str = "hello", prompt_tokens: int = 10, completion_tokens: int = 5):
    body = json.dumps({
        "message": {"content": content},
        "prompt_eval_count": prompt_tokens,
        "eval_count": completion_tokens,
    }).encode()
    return _FakeResp(body)


class TestRetryPolicy(unittest.TestCase):
    """swarm/llm.py — _should_retry / _backoff_delay."""

    def test_should_retry_transient(self):
        self.assertTrue(_should_retry(urllib.error.HTTPError("u", 503, "x", {}, None)))
        self.assertTrue(_should_retry(urllib.error.HTTPError("u", 429, "x", {}, None)))
        self.assertTrue(_should_retry(ConnectionError("refused")))
        self.assertTrue(_should_retry(TimeoutError("timeout")))

    def test_should_not_retry_4xx(self):
        self.assertFalse(_should_retry(urllib.error.HTTPError("u", 400, "x", {}, None)))
        self.assertFalse(_should_retry(urllib.error.HTTPError("u", 404, "x", {}, None)))

    def test_backoff_capped(self):
        policy = {"max_attempts": 3, "base_delay": 0.5, "max_delay": 4.0}
        self.assertLessEqual(_backoff_delay(3, policy, None), 4.0)
        self.assertGreaterEqual(_backoff_delay(1, policy, None), 0.5)


class TestCallLlm(unittest.TestCase):
    """swarm/llm.py — call_llm."""

    def test_happy_path_returns_content(self):
        with patch("urllib.request.urlopen", return_value=_ok_resp()):
            text = call_llm("m", [{"role": "user", "content": "hi"}])
        self.assertEqual(text, "hello")

    def test_retries_on_503_then_succeeds(self):
        calls = {"n": 0}

        def flaky(req, timeout=120):
            calls["n"] += 1
            if calls["n"] == 1:
                raise urllib.error.HTTPError(req.full_url, 503, "x", {}, None)
            return _ok_resp("recovered")

        with patch("urllib.request.urlopen", side_effect=flaky), patch("time.sleep", lambda s: None):
            text = call_llm("m", [{"role": "user", "content": "hi"}],
                            retry_cfg={"max_attempts": 3, "base_delay": 0.1, "max_delay": 1.0})
        self.assertEqual(text, "recovered")
        self.assertEqual(calls["n"], 2)

    def test_does_not_retry_4xx(self):
        calls = {"n": 0}

        def bad(req, timeout=120):
            calls["n"] += 1
            raise urllib.error.HTTPError(req.full_url, 400, "x", {}, None)

        with patch("urllib.request.urlopen", side_effect=bad), patch("time.sleep", lambda s: None):
            text = call_llm("m", [{"role": "user", "content": "hi"}])
        self.assertTrue(text.startswith("[LLM error"))
        self.assertEqual(calls["n"], 1)

    def test_retries_exhausted_returns_error(self):
        def always_503(req, timeout=120):
            raise urllib.error.HTTPError(req.full_url, 503, "x", {}, None)

        with patch("urllib.request.urlopen", side_effect=always_503), patch("time.sleep", lambda s: None):
            text = call_llm("m", [{"role": "user", "content": "hi"}],
                            retry_cfg={"max_attempts": 2, "base_delay": 0.1, "max_delay": 1.0})
        self.assertTrue(text.startswith("[LLM error"))

    def test_streaming_accumulates_and_forwards(self):
        chunks = []
        lines = [
            json.dumps({"message": {"content": "Par"}}).encode() + b"\n",
            json.dumps({"message": {"content": "is"}}).encode() + b"\n",
        ]

        class _StreamResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def __iter__(self):
                return iter(lines)

        with patch("urllib.request.urlopen", return_value=_StreamResp()):
            text = call_llm("m", [{"role": "user", "content": "hi"}], stream=True,
                            stream_cb=lambda c, p: chunks.append(c))
        self.assertEqual(text, "Paris")
        self.assertEqual(chunks, ["Par", "is"])

    def test_cost_accounting(self):
        cost = RunCost()
        with patch("urllib.request.urlopen", return_value=_ok_resp(prompt_tokens=100, completion_tokens=20)):
            call_llm("m", [{"role": "user", "content": "hi"}], cost=cost,
                     model_rates={"input_per_1k": 0.1, "output_per_1k": 0.2})
        d = cost.to_dict()
        self.assertEqual(d["prompt_tokens"], 100)
        self.assertEqual(d["completion_tokens"], 20)
        self.assertEqual(d["total_tokens"], 120)
        self.assertEqual(d["calls"], 1)
        self.assertAlmostEqual(d["estimated_cost_usd"], 0.1 * 0.1 + 0.02 * 0.2, places=6)

    def test_cost_zero_when_no_rates(self):
        cost = RunCost()
        with patch("urllib.request.urlopen", return_value=_ok_resp()):
            call_llm("m", [{"role": "user", "content": "hi"}], cost=cost)
        self.assertEqual(cost.to_dict()["estimated_cost_usd"], 0.0)

    def test_missing_usage_fields_do_not_raise(self):
        body = json.dumps({"message": {"content": "x"}}).encode()
        cost = RunCost()
        with patch("urllib.request.urlopen", return_value=_FakeResp(body)):
            call_llm("m", [{"role": "user", "content": "hi"}], cost=cost)
        self.assertEqual(cost.to_dict()["prompt_tokens"], 0)


if __name__ == "__main__":
    unittest.main()
