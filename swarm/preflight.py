"""Preflight — the orchestrator analyzes the question and generates worker strategies.

Instead of hardcoded angles like "Cover ORIGINS and HISTORY," the
preflight pass uses the orchestrator model to:
1. Figure out what kind of answer is needed (number, name, phrase, etc.)
2. Assign the right tool bundles to each worker
3. Generate specific search strategies for each worker
4. Give workers a clear, actionable plan for finding the exact answer
"""

import json
import re
import urllib.request

from .prompts import load_prompt, render_prompt


# Available tool bundles and what they do — the LLM uses this to assign them
BUNDLE_INFO = {
    "vision": "Has read_image tool — use for questions with image attachments (.png/.jpg). Best model: gemma4:31b-cloud (multimodal).",
    "code": "Has python_exec tool — use for calculations, data processing, running code. Best model: deepseek-v4-flash.",
    "files": "Has read_file tool — use for .docx, .xlsx, .csv, .txt, .json, .xml attachments. Best model: gpt-oss:120b-cloud.",
    "search": "Web search only — use for simple fact lookups. Fast model: nemotron-3-nano:30b-cloud.",
    "default": "Web search + scratchpad + web_extract — use for general research. Best model: gpt-oss:120b-cloud.",
}

BUNDLE_NAMES = sorted(BUNDLE_INFO.keys())


def analyze_question(goal: str, model: str,
                     ollama_base: str = "http://localhost:11434",
                     num_workers: int = 3) -> dict:
    """Use the orchestrator model to analyze a question and generate strategies.

    Returns:
        dict with:
        - answer_type: "number", "name", "phrase", "date", "other"
        - research_mode: "objective" or "subjective"
        - bundles: list of N bundle names, one per worker
        - model_for_bundle: dict mapping bundle name to recommended model
        - strategies: list of N dicts, each with:
            - worker_name: suggested name
            - search_plan: specific search strategy
            - verification_hint: how to verify the answer
    """
    bundle_descriptions = "\n".join(
        f"  - \"{name}\": {desc}"
        for name, desc in sorted(BUNDLE_INFO.items())
    )

    prompt = render_prompt(
        "preflight",
        goal=goal,
        num_workers=num_workers,
        bundle_descriptions=bundle_descriptions,
    )
    system_prompt = load_prompt("preflight_system")

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "options": {"temperature": 0.2, "num_predict": 2048},
    }

    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{ollama_base}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
            content = result.get("message", {}).get("content", "").strip()
    except Exception as e:
        return {
            "answer_type": "other",
            "bundles": ["default"] * num_workers,
            "strategies": [
                {"worker_name": f"Worker {i+1}", "search_plan": "Search for the answer directly.", "verification_hint": "Verify with a second source."}
                for i in range(num_workers)
            ],
        }

    # Try to extract JSON from the response
    try:
        parsed = _extract_json(content)
        # Support both old format (strategies + bundles) and new format (workers array)
        if parsed:
            if "workers" in parsed:
                # New format: workers array with bundle, depends_on, search_plan
                workers = parsed["workers"][:num_workers]
                while len(workers) < num_workers:
                    workers.append({"bundle": "default", "depends_on": None,
                                    "search_plan": "Search for the answer directly.",
                                    "verification_hint": "Verify with a second source."})

                bundles = [w.get("bundle", "default") for w in workers]
                valid_bundles = [b if b in BUNDLE_INFO else "default" for b in bundles]
                depends_on = [w.get("depends_on") for w in workers]

                strategies = []
                for i, w in enumerate(workers):
                    strategies.append({
                        "worker_name": f"Worker {i+1}",
                        "search_plan": w.get("search_plan", "Search for the answer directly."),
                        "verification_hint": w.get("verification_hint", "Verify with a second source."),
                    })

                return {
                    "answer_type": parsed.get("answer_type", "other"),
                    "research_mode": parsed.get("research_mode", "objective"),
                    "mode": parsed.get("mode", "parallel"),
                    "bundles": valid_bundles,
                    "depends_on": depends_on,
                    "strategies": strategies,
                }

            elif "strategies" in parsed:
                # Old format: strategies array + bundles array (backward compat)
                strategies = parsed["strategies"][:num_workers]
                while len(strategies) < num_workers:
                    strategies.append({
                        "worker_name": f"Worker {len(strategies)+1}",
                        "search_plan": "Search for the answer directly.",
                        "verification_hint": "Verify with a second source."
                    })

                bundles = parsed.get("bundles", [])
                valid_bundles = [b if b in BUNDLE_INFO else "default" for b in bundles[:num_workers]]
                while len(valid_bundles) < num_workers:
                    valid_bundles.append("default")

                return {
                    "answer_type": parsed.get("answer_type", "other"),
                    "research_mode": parsed.get("research_mode", "objective"),
                    "mode": "parallel",
                    "bundles": valid_bundles,
                    "depends_on": [None] * num_workers,
                    "strategies": strategies,
                }
    except Exception:
        pass

    # Fallback
    return {
        "answer_type": "other",
        "research_mode": "objective",
        "mode": "parallel",
        "bundles": ["default"] * num_workers,
        "depends_on": [None] * num_workers,
        "strategies": [
            {"worker_name": f"Worker {i+1}", "search_plan": "Search for the answer directly.", "verification_hint": "Verify with a second source."}
            for i in range(num_workers)
        ],
    }


def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from text, handling markdown fences."""
    # Try to find a JSON block
    match = re.search(r"```(?:json)?\s*\n?({.*?})\n?\s*```", text, re.DOTALL)
    if match:
        return json.loads(match.group(1))

    # Try to find a JSON object directly
    match = re.search(r"\{.*\"strategies\".*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group(0))

    # Try parsing the whole thing
    return json.loads(text)


def build_worker_prompt(goal: str, strategy: dict, answer_type: str,
                        worker_name: str, tool_bundle: str = "default",
                        research_mode: str = "objective") -> str:
    """Build a worker system prompt optimized for exact-answer finding.

    This is the key difference from the generic prompt: it tells the
    worker what kind of answer to look for and gives them a specific
    search plan. The rules are customized based on the tool bundle
    and the research mode (objective vs subjective).
    """
    answer_type_hints = {
        "number": "The answer is a NUMBER. Be precise. Check for units, commas, and formatting.",
        "name": "The answer is a NAME (person, place, thing). Get the exact spelling.",
        "phrase": "The answer is a PHRASE or short sentence. Get the exact wording.",
        "date": "The answer is a DATE. Be specific about year/month/day format.",
        "other": "The answer is a specific fact. Get the exact wording.",
    }

    hint = answer_type_hints.get(answer_type, "The answer is a specific fact. Get the exact wording.")

    mode_rules = render_prompt(f"mode_{research_mode}")
    bundle_template = f"bundle_{tool_bundle}"
    if load_prompt(bundle_template):
        bundle_rules = render_prompt(bundle_template)
    else:
        bundle_rules = render_prompt("bundle_default")

    return render_prompt(
        "worker",
        worker_name=worker_name,
        goal=goal,
        answer_type=answer_type.upper(),
        answer_hint=hint,
        search_plan=strategy['search_plan'],
        verification_hint=strategy.get('verification_hint', 'Verify with a second source.'),
        mode_rules=mode_rules,
        bundle_rules=bundle_rules,
    )