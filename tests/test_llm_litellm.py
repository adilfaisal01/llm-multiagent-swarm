"""Hermetic tests for the LiteLLM transport (swarm/llm.py _call_via_litellm).

Mocks ``litellm.completion`` so no network is touched. Verifies response
mapping, streaming, cost accounting, api_base/api_key passthrough, and
the max_tokens safety cap. Skipped when litellm is not installed.

Run with:
    python3 -m unittest tests.test_llm_litellm -v
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from litellm import Choices, Message, ModelResponse, Usage

from swarm.llm import RunCost, call_llm
from swarm.providers import has_litellm


def _make_response(content: str = "hello", prompt_tokens: int = 10, completion_tokens: int = 5):
    return ModelResponse(
        choices=[Choices(message=Message(content=content), finish_reason="stop")],
        usage=Usage(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
        model="gpt-4o",
    )


@unittest.skipUnless(has_litellm(), "litellm not installed")
class TestCallLlmLiteLlm(unittest.TestCase):
    """swarm/llm.py — call_llm via the LiteLLM transport."""

    def test_happy_path_returns_content(self):
        with patch("litellm.completion", return_value=_make_response()):
            text = call_llm("openai/gpt-4o", [{"role": "user", "content": "hi"}],
                            config={"use_litellm": True})
        self.assertEqual(text, "hello")

    def test_passes_api_base_and_key(self):
        captured = {}

        def fake_completion(**kwargs):
            captured.update(kwargs)
            return _make_response()

        cfg = {"use_litellm": True, "providers": {"openai": {"base_url": "https://api.openai.com/v1", "api_key_env": "TEST_OPENAI_KEY"}}}
        with patch("litellm.completion", side_effect=fake_completion), patch.dict("os.environ", {"TEST_OPENAI_KEY": "sk-secret"}):
            call_llm("openai/gpt-4o", [{"role": "user", "content": "hi"}], config=cfg)
        self.assertEqual(captured["api_base"], "https://api.openai.com/v1")
        self.assertEqual(captured["api_key"], "sk-secret")
        self.assertEqual(captured["model"], "gpt-4o")

    def test_max_tokens_none_applies_safety_cap(self):
        captured = {}

        def fake_completion(**kwargs):
            captured.update(kwargs)
            return _make_response()

        with patch("litellm.completion", side_effect=fake_completion):
            call_llm("openai/gpt-4o", [{"role": "user", "content": "hi"}],
                     config={"use_litellm": True})
        self.assertEqual(captured["max_tokens"], 32768)

    def test_max_tokens_set_overrides_safety_cap(self):
        captured = {}

        def fake_completion(**kwargs):
            captured.update(kwargs)
            return _make_response()

        with patch("litellm.completion", side_effect=fake_completion):
            call_llm("openai/gpt-4o", [{"role": "user", "content": "hi"}],
                     config={"use_litellm": True}, max_tokens=512)
        self.assertEqual(captured["max_tokens"], 512)

    def test_cost_accounting_from_usage(self):
        cost = RunCost()
        with patch("litellm.completion", return_value=_make_response(prompt_tokens=100, completion_tokens=20)):
            call_llm("openai/gpt-4o", [{"role": "user", "content": "hi"}],
                     config={"use_litellm": True}, cost=cost)
        d = cost.to_dict()
        self.assertEqual(d["prompt_tokens"], 100)
        self.assertEqual(d["completion_tokens"], 20)
        self.assertEqual(d["calls"], 1)

    def test_streaming_accumulates_and_forwards(self):
        chunks = []

        class _Chunk:
            def __init__(self, content):
                self.choices = [type("C", (), {"delta": type("D", (), {"content": content})()})()]

        def fake_completion(**kwargs):
            return iter([_Chunk("Par"), _Chunk("is")])

        with patch("litellm.completion", side_effect=fake_completion):
            text = call_llm("openai/gpt-4o", [{"role": "user", "content": "hi"}],
                            config={"use_litellm": True}, stream=True,
                            stream_cb=lambda c, p: chunks.append(c))
        self.assertEqual(text, "Paris")
        self.assertEqual(chunks, ["Par", "is"])

    def test_return_message_returns_dict(self):
        resp = ModelResponse(
            choices=[Choices(message=Message(content="hi", tool_calls=None), finish_reason="tool_calls")],
            usage=Usage(prompt_tokens=1, completion_tokens=1),
            model="gpt-4o",
        )
        with patch("litellm.completion", return_value=resp):
            msg = call_llm("openai/gpt-4o", [{"role": "user", "content": "hi"}],
                           config={"use_litellm": True}, return_message=True)
        self.assertIsInstance(msg, dict)
        self.assertEqual(msg["content"], "hi")

    def test_retries_on_transient_error_then_succeeds(self):
        from litellm.exceptions import RateLimitError

        calls = {"n": 0}

        def flaky(**kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RateLimitError("rate limited", llm_provider="openai", model="gpt-4o")
            return _make_response("recovered")

        with patch("litellm.completion", side_effect=flaky), patch("time.sleep", lambda s: None):
            text = call_llm("openai/gpt-4o", [{"role": "user", "content": "hi"}],
                            config={"use_litellm": True},
                            retry_cfg={"max_attempts": 3, "base_delay": 0.1, "max_delay": 1.0})
        self.assertEqual(text, "recovered")
        self.assertEqual(calls["n"], 2)

    def test_raises_when_litellm_missing(self):
        with patch("builtins.__import__", side_effect=ImportError("no litellm")):
            with self.assertRaises(RuntimeError):
                call_llm("openai/gpt-4o", [{"role": "user", "content": "hi"}],
                         config={"use_litellm": True})


if __name__ == "__main__":
    unittest.main()
