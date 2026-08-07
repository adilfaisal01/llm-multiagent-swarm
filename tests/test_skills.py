"""Unit tests for the skill system (swarm/skills/)."""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from swarm.preflight import _valid_skill, build_worker_prompt
from swarm.runner import run_swarm
from swarm.skills import Skill, SkillRegistry, get_skill_registry, reset_skill_registry
from swarm.skills._base import parse_frontmatter
from swarm.tools import get_registry, reset_registry


class TestFrontmatterParser(unittest.TestCase):
    """Verify the hand-rolled YAML subset parser."""

    def test_parses_scalars_and_lists(self):
        text = """---
name: vision
description: "Has read_image tool"
triggers: [image, png, jpg]
tools: [read_image, web_search]
recommended_model: gemma4:31b-cloud
---

# Body
"""
        data, body = parse_frontmatter(text)
        self.assertEqual(data["name"], "vision")
        self.assertEqual(data["description"], "Has read_image tool")
        self.assertEqual(data["triggers"], ["image", "png", "jpg"])
        self.assertEqual(data["tools"], ["read_image", "web_search"])
        self.assertEqual(data["recommended_model"], "gemma4:31b-cloud")
        self.assertEqual(body, "# Body")

    def test_quoted_description_with_commas_stays_scalar(self):
        text = '---\ndescription: "a, b, c"\n---\nbody'
        data, _ = parse_frontmatter(text)
        self.assertEqual(data["description"], "a, b, c")

    def test_no_frontmatter_returns_empty(self):
        data, body = parse_frontmatter("# just a body")
        self.assertEqual(data, {})
        self.assertEqual(body, "# just a body")

    def test_comments_skipped(self):
        text = "---\n# comment\nname: x\n---\nbody"
        data, _ = parse_frontmatter(text)
        self.assertEqual(data["name"], "x")

    def test_hermes_style_fields_parse(self):
        text = """---
name: reverse-engineering
version: 1.0.0
category: security
tags: [reverse-engineering, malware]
trigger: "When analyzing an obfuscated file."
related_skills: [lightweight-swarm]
platforms: [linux, macos]
team: team.json
mode: parallel
---
body
"""
        data, _ = parse_frontmatter(text)
        self.assertEqual(data["version"], "1.0.0")
        self.assertEqual(data["category"], "security")
        self.assertEqual(data["tags"], ["reverse-engineering", "malware"])
        self.assertEqual(data["trigger"], "When analyzing an obfuscated file.")
        self.assertEqual(data["related_skills"], ["lightweight-swarm"])
        self.assertEqual(data["platforms"], ["linux", "macos"])
        self.assertEqual(data["team"], "team.json")
        self.assertEqual(data["mode"], "parallel")


class TestSkillRegistry(unittest.TestCase):
    """Verify discovery, tool resolution, and team loading."""

    def setUp(self):
        reset_registry()
        reset_skill_registry()

    def tearDown(self):
        reset_registry()
        reset_skill_registry()

    def test_discovers_all_builtin_skills(self):
        sr = get_skill_registry()
        names = sr.names()
        for expected in ("default", "research", "search", "vision", "code", "files", "reverse-engineering"):
            self.assertIn(expected, names)

    def test_descriptions_include_triggers(self):
        sr = get_skill_registry()
        desc = sr.descriptions_for_llm()
        self.assertIn("vision", desc)
        self.assertIn("triggers: image", desc)

    def test_tools_for_vision(self):
        sr = get_skill_registry()
        tools = sr.tools_for("vision")
        names = [t.name for t in tools]
        self.assertIn("read_image", names)
        self.assertIn("web_search", names)

    def test_tools_for_research(self):
        sr = get_skill_registry()
        tools = sr.tools_for("research")
        names = [t.name for t in tools]
        self.assertIn("web_search", names)
        self.assertIn("scratchpad_add", names)
        self.assertNotIn("read_image", names)

    def test_ollama_tools_for_skill(self):
        sr = get_skill_registry()
        ollama = sr.ollama_tools_for("search")
        self.assertTrue(ollama)
        self.assertEqual(ollama[0]["type"], "function")

    def test_load_team_research(self):
        sr = get_skill_registry()
        team = sr.load_team("research")
        self.assertIsNotNone(team)
        names = [m["name"] for m in team["team"]]
        self.assertEqual(names, ["Vera", "Cyrus", "Romy", "Ash", "Zara"])

    def test_load_team_reverse_engineering(self):
        sr = get_skill_registry()
        team = sr.load_team("reverse-engineering")
        self.assertIsNotNone(team)
        names = [m["name"] for m in team["team"]]
        self.assertEqual(names, ["Vera", "Cyrus", "Ash", "Zara", "Romy"])

    def test_load_team_default_returns_none(self):
        sr = get_skill_registry()
        self.assertIsNone(sr.load_team("default"))

    def test_unknown_skill_returns_none(self):
        sr = get_skill_registry()
        self.assertIsNone(sr.get("does-not-exist"))
        self.assertEqual(sr.tools_for("does-not-exist"), [])

    def test_unknown_tool_dropped_with_warning(self):
        sr = get_skill_registry()
        skill = Skill(
            name="test-skill",
            description="test",
            tools=["web_search", "definitely-not-a-tool"],
        )
        sr._skills["test-skill"] = skill
        stderr = io.StringIO()
        old = sys.stderr
        sys.stderr = stderr
        try:
            tools = sr.tools_for("test-skill")
        finally:
            sys.stderr = old
        names = [t.name for t in tools]
        self.assertIn("web_search", names)
        self.assertNotIn("definitely-not-a-tool", names)
        self.assertIn("WARN", stderr.getvalue())

    def test_malformed_frontmatter_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "bad-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text("---\nname: [unclosed\n---\nbody")
            sr = SkillRegistry()
            stderr = io.StringIO()
            old = sys.stderr
            sys.stderr = stderr
            try:
                sr.discover(tmp)
            finally:
                sys.stderr = old
            self.assertNotIn("bad-skill", sr.names())
            self.assertIn("WARN", stderr.getvalue())

    def test_skill_without_team_file_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "no-team"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\nname: no-team\nteam: missing.json\n---\nbody"
            )
            sr = SkillRegistry()
            sr.discover(tmp)
            stderr = io.StringIO()
            old = sys.stderr
            sys.stderr = stderr
            try:
                team = sr.load_team("no-team")
            finally:
                sys.stderr = old
            self.assertIsNone(team)
            self.assertIn("WARN", stderr.getvalue())


class TestRegistryWiring(unittest.TestCase):
    """Verify ToolRegistry delegates bundle lookups to the SkillRegistry."""

    def setUp(self):
        reset_registry()
        reset_skill_registry()

    def tearDown(self):
        reset_registry()
        reset_skill_registry()

    def test_get_tools_for_bundle_delegates_to_skills(self):
        reg = get_registry()
        tools = reg.get_tools_for_bundle("vision")
        names = [t.name for t in tools]
        self.assertIn("read_image", names)

    def test_get_ollama_tools_for_bundle_delegates_to_skills(self):
        reg = get_registry()
        ollama = reg.get_ollama_tools_for_bundle("research")
        names = [t["function"]["name"] for t in ollama]
        self.assertIn("web_search", names)

    def test_get_bundle_names_returns_skills(self):
        reg = get_registry()
        names = reg.get_bundle_names()
        self.assertIn("research", names)
        self.assertIn("reverse-engineering", names)


class TestSkillPromptInjection(unittest.TestCase):
    """Verify worker prompts come from skill bodies, not old bundle files."""

    def setUp(self):
        reset_registry()
        reset_skill_registry()

    def tearDown(self):
        reset_registry()
        reset_skill_registry()

    def test_build_worker_prompt_uses_skill_prompt(self):
        strategy = {
            "search_plan": "Search the web for the answer.",
            "verification_hint": "Cross-check with a second source.",
        }
        prompt = build_worker_prompt(
            goal="What is in this image?",
            strategy=strategy,
            answer_type="other",
            worker_name="Vera",
            tool_bundle="vision",
            research_mode="objective",
        )
        self.assertIn("CALL read_image NOW", prompt)
        self.assertNotIn("bundle_vision", prompt)

    def test_build_worker_prompt_falls_back_to_default_for_unknown_skill(self):
        strategy = {"search_plan": "s", "verification_hint": "v"}
        prompt = build_worker_prompt(
            goal="g", strategy=strategy, answer_type="other",
            worker_name="W", tool_bundle="does-not-exist", research_mode="objective",
        )
        self.assertTrue(prompt)
        self.assertIn("web_search", prompt)


class TestValidSkillFallback(unittest.TestCase):
    """Verify unknown preflight skills warn and fall back to 'default'."""

    def setUp(self):
        reset_skill_registry()

    def tearDown(self):
        reset_skill_registry()

    def test_valid_skill_warns_and_falls_back_for_unknown(self):
        stderr = io.StringIO()
        old = sys.stderr
        sys.stderr = stderr
        try:
            result = _valid_skill("does-not-exist")
        finally:
            sys.stderr = old
        self.assertEqual(result, "default")
        self.assertIn("WARN", stderr.getvalue())
        self.assertIn("does-not-exist", stderr.getvalue())

    def test_valid_skill_keeps_known_skill(self):
        stderr = io.StringIO()
        old = sys.stderr
        sys.stderr = stderr
        try:
            result = _valid_skill("research")
        finally:
            sys.stderr = old
        self.assertEqual(result, "research")
        self.assertEqual(stderr.getvalue(), "")


class TestSkillRunnerWiring(unittest.TestCase):
    """Verify run_swarm honors the skill flag and config skill field."""

    def setUp(self):
        reset_registry()
        reset_skill_registry()

    def tearDown(self):
        reset_registry()
        reset_skill_registry()

    @patch("swarm.runner.orchestrate")
    def test_skill_flag_passed_through_to_orchestrate(self, mock_orchestrate):
        mock_orchestrate.return_value = {"workers": [], "goal": "g", "num_workers": 3}
        run_swarm(goal="g", skill="reverse-engineering", mix=True)
        kwargs = mock_orchestrate.call_args.kwargs
        self.assertEqual(kwargs["skill"], "reverse-engineering")
        self.assertEqual(kwargs["mix"], True)

    @patch("swarm.runner.orchestrate")
    def test_skill_with_team_auto_enables_mix(self, mock_orchestrate):
        mock_orchestrate.return_value = {"workers": [], "goal": "g", "num_workers": 3}
        stderr = io.StringIO()
        old = sys.stderr
        sys.stderr = stderr
        try:
            run_swarm(goal="g", skill="research")
        finally:
            sys.stderr = old
        kwargs = mock_orchestrate.call_args.kwargs
        self.assertEqual(kwargs["skill"], "research")
        self.assertEqual(kwargs["mix"], True)
        self.assertIn("ships a team", stderr.getvalue())

    @patch("swarm.runner.orchestrate")
    def test_config_skill_field_honored(self, mock_orchestrate):
        mock_orchestrate.return_value = {"workers": [], "goal": "g", "num_workers": 3}
        cfg = {
            "skill": "research",
            "team": [
                {"name": "Alpha", "model": "deepseek-v4-flash:cloud",
                 "angle": "a", "prompt": "You are Alpha. MAIN QUESTION: {goal} YOUR ANGLE: {angle}"}
            ],
            "angles": ["a"],
            "fallback_models": ["deepseek-v4-flash:cloud"],
        }
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(cfg, f)
            path = f.name
        try:
            run_swarm(goal="g", config_path=path)
        finally:
            os.unlink(path)
        kwargs = mock_orchestrate.call_args.kwargs
        self.assertEqual(kwargs["skill"], "research")

    @patch("swarm.runner.orchestrate")
    def test_config_unknown_skill_field_ignored(self, mock_orchestrate):
        mock_orchestrate.return_value = {"workers": [], "goal": "g", "num_workers": 3}
        cfg = {"skill": "nope", "team": [], "angles": [], "fallback_models": []}
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
            json.dump(cfg, f)
            path = f.name
        try:
            run_swarm(goal="g", config_path=path)
        finally:
            os.unlink(path)
        kwargs = mock_orchestrate.call_args.kwargs
        self.assertIsNone(kwargs["skill"])


if __name__ == "__main__":
    unittest.main()
