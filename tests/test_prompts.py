"""Unit tests for external markdown prompt templates."""

from __future__ import annotations

import unittest

from swarm.prompts import load_prompt, render_prompt


class TestPrompts(unittest.TestCase):
    """Verify prompt templates load and render."""

    def test_all_prompt_files_exist(self):
        names = [
            "preflight",
            "preflight_system",
            "worker",
            "default_worker",
            "synthesis",
            "synthesis_objective",
            "synthesis_subjective",
            "mode_objective",
            "mode_subjective",
            "bundle_default",
            "bundle_vision",
            "bundle_code",
            "bundle_files",
            "bundle_search",
            "fallback_system",
            "fallback_user",
        ]
        for name in names:
            with self.subTest(name=name):
                content = load_prompt(name)
                self.assertTrue(content, f"Prompt {name}.md is missing or empty")

    def test_worker_prompt_renders(self):
        text = render_prompt(
            "worker",
            worker_name="Vera",
            goal="What is X?",
            answer_type="PHRASE",
            answer_hint="The answer is a phrase.",
            search_plan="Search the web.",
            verification_hint="Cross-check.",
            mode_rules="OBJECTIVE",
            bundle_rules="DEFAULT",
        )
        self.assertIn("Vera", text)
        self.assertIn("What is X?", text)
        self.assertIn("OBJECTIVE", text)
        self.assertIn("DEFAULT", text)

    def test_synthesis_prompt_renders_both_modes(self):
        for mode in ("objective", "subjective"):
            with self.subTest(mode=mode):
                instructions = render_prompt(f"synthesis_{mode}")
                self.assertTrue(instructions)
                prompt = render_prompt(
                    "synthesis",
                    goal="g",
                    research_mode=mode.upper(),
                    num_workers=3,
                    worker_section="ws",
                    findings_section="fs",
                    synthesis_instructions=instructions,
                )
                self.assertIn(mode.upper(), prompt)
                self.assertIn("ws", prompt)

    def test_bundle_templates_render(self):
        for bundle in ("default", "vision", "code", "files", "search"):
            with self.subTest(bundle=bundle):
                text = render_prompt(f"bundle_{bundle}")
                self.assertTrue(text)


if __name__ == "__main__":
    unittest.main()
