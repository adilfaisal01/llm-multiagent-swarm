"""Hermetic tests for provider resolution (swarm/providers.py).

Covers model-tag splitting, config provider lookup, env-var API key
expansion, bare-tag → ollama fallback, OLLAMA_HOST honoring, and the
LiteLLM detection/toggle logic.

Run with:
    python3 -m unittest tests.test_providers -v
"""

from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

from swarm.providers import (
    _split_tag,
    has_litellm,
    resolve_endpoint,
    should_use_litellm,
)


class TestSplitTag(unittest.TestCase):
    """swarm/providers.py — _split_tag."""

    def test_provider_name_split(self):
        self.assertEqual(_split_tag("openai/gpt-4o"), ("openai", "gpt-4o"))

    def test_bare_tag_falls_back_to_ollama(self):
        self.assertEqual(_split_tag("deepseek-v4-flash:cloud"), ("ollama", "deepseek-v4-flash:cloud"))

    def test_ollama_tag_with_slash(self):
        self.assertEqual(_split_tag("ollama/gpt-oss:120b-cloud"), ("ollama", "gpt-oss:120b-cloud"))


class TestResolveEndpoint(unittest.TestCase):
    """swarm/providers.py — resolve_endpoint."""

    def test_provider_lookup_with_api_key(self):
        cfg = {
            "providers": {
                "openai": {
                    "base_url": "https://api.openai.com/v1",
                    "api_key_env": "TEST_OPENAI_KEY",
                }
            }
        }
        with patch.dict("os.environ", {"TEST_OPENAI_KEY": "sk-secret"}):
            base, name, headers, key = resolve_endpoint("openai/gpt-4o", cfg)
        self.assertEqual(base, "https://api.openai.com/v1")
        self.assertEqual(name, "gpt-4o")
        self.assertEqual(key, "sk-secret")
        self.assertEqual(headers["Authorization"], "Bearer sk-secret")

    def test_no_api_key_env_means_no_auth_header(self):
        cfg = {"providers": {"openai": {"base_url": "https://api.openai.com/v1", "api_key_env": "TEST_MISSING_KEY"}}}
        with patch.dict("os.environ", {}, clear=True):
            base, name, headers, key = resolve_endpoint("openai/gpt-4o", cfg)
        self.assertIsNone(key)
        self.assertNotIn("Authorization", headers)

    def test_bare_tag_uses_ollama_provider(self):
        cfg = {"providers": {"ollama": {"base_url": "http://localhost:11434/v1"}}}
        base, name, headers, key = resolve_endpoint("deepseek-v4-flash:cloud", cfg)
        self.assertEqual(base, "http://localhost:11434/v1")
        self.assertEqual(name, "deepseek-v4-flash:cloud")

    def test_missing_providers_block_uses_ollama_default(self):
        with patch.dict("os.environ", {}, clear=True):
            base, name, headers, key = resolve_endpoint("gpt-oss:120b-cloud", {})
        self.assertEqual(base, "http://localhost:11434/v1")
        self.assertEqual(name, "gpt-oss:120b-cloud")

    def test_ollama_host_env_honored(self):
        with patch.dict("os.environ", {"OLLAMA_HOST": "http://ollama.local:8080"}, clear=True):
            base, _, _, _ = resolve_endpoint("gpt-oss:120b-cloud", {})
        self.assertEqual(base, "http://ollama.local:8080/v1")

    def test_ollama_host_without_scheme_normalized(self):
        with patch.dict("os.environ", {"OLLAMA_HOST": "ollama.local:8080"}, clear=True):
            base, _, _, _ = resolve_endpoint("gpt-oss:120b-cloud", {})
        self.assertEqual(base, "http://ollama.local:8080/v1")

    def test_unknown_provider_falls_back_to_default_base(self):
        cfg = {"providers": {"openai": {"base_url": "https://api.openai.com/v1"}}}
        base, name, _, _ = resolve_endpoint("unknown/model-x", cfg)
        self.assertEqual(base, "http://localhost:11434/v1")
        self.assertEqual(name, "model-x")


class TestLiteLlmDetection(unittest.TestCase):
    """swarm/providers.py — has_litellm / should_use_litellm."""

    def test_has_litellm_false_when_not_installed(self):
        with patch("swarm.providers._litellm_available", None), patch.dict(sys.modules, {"litellm": None}):
            self.assertFalse(has_litellm())

    def test_has_litellm_true_when_installed(self):
        with patch("swarm.providers._litellm_available", None), patch.dict(sys.modules, {"litellm": object()}):
            self.assertTrue(has_litellm())

    def test_should_use_litellm_explicit_true(self):
        self.assertTrue(should_use_litellm({"use_litellm": True}, "openai/gpt-4o"))

    def test_should_use_litellm_explicit_false(self):
        with patch("swarm.providers.has_litellm", return_value=True):
            self.assertFalse(should_use_litellm({"use_litellm": False}, "openai/gpt-4o"))

    def test_should_use_litellm_auto_detects(self):
        with patch("swarm.providers.has_litellm", return_value=True):
            self.assertTrue(should_use_litellm({}, "openai/gpt-4o"))
        with patch("swarm.providers.has_litellm", return_value=False):
            self.assertFalse(should_use_litellm({}, "openai/gpt-4o"))


if __name__ == "__main__":
    unittest.main()
