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


# Available tool bundles and what they do — the LLM uses this to assign them
BUNDLE_INFO = {
    "vision": "Has read_image tool — use for questions with image attachments (.png/.jpg). Best model: gemma4:31b-cloud (multimodal).",
    "code": "Has python_exec tool — use for calculations, data processing, running code. Best model: deepseek-v4-flash or qwen3.5.",
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

    prompt = (
        f"You are a research strategist. Analyze this question and generate "
        f"{num_workers} workers with specific tool bundles.\n\n"
        f"QUESTION: {goal}\n\n"
        f"AVAILABLE TOOL BUNDLES:\n"
        f"{bundle_descriptions}\n\n"
        f"First, classify the answer type (one of: number, name, phrase, date, other).\n"
        f"Then decide the execution MODE:\n"
        f"  - \"parallel\": Workers are independent and can run simultaneously (web research, fact lookup)\n"
        f"  - \"pipeline\": Workers depend on each other's output (vision reads image → code computes)\n\n"
        f"For pipeline mode, set depends_on to the index of the worker whose output you need.\n"
        f"Example:\n"
        f"  worker 0: vision (reads image, extracts numbers)\n"
        f"  worker 1: code (depends_on: 0, takes the extracted numbers and computes)\n\n"
        f"For parallel mode, all workers have depends_on: null.\n\n"
        f"Then, for each of {num_workers} workers:\n"
        f"  1. Pick the best bundle from the list above\n"
        f"  2. Give them a specific search/action plan\n"
        f"  3. Give them a verification hint\n\n"
        f"IMPORTANT: Choose bundles that match the question:\n"
        f"  - Image file? → use \"vision\" bundle for at least one worker\n"
        f"  - Spreadsheet/doc? → use \"files\" bundle\n"
        f"  - Needs calculation? → use \"code\" bundle\n"
        f"  - General web research? → use \"default\" or \"search\" bundle\n\n"
        f"Respond with ONLY valid JSON in this exact format:\n"
        f"{{\n"
        f'  "answer_type": "number|name|phrase|date|other",\n'
        f'  "mode": "parallel|pipeline",\n'
        f'  "workers": [\n'
        f'    {{\n'
        f'      "bundle": "vision",\n'
        f'      "depends_on": null,\n'
        f'      "search_plan": "Read the image using read_image, extract numbers...",\n'
        f'      "verification_hint": "Cross-check..."\n'
        f'    }},\n'
        f'    {{\n'
        f'      "bundle": "code",\n'
        f'      "depends_on": 0,\n'
        f'      "search_plan": "Take extracted numbers and compute...",\n'
        f'      "verification_hint": "Verify with..."\n'
        f'    }}\n'
        f'  ]\n'
        f"}}\n"
        f"The workers array must have exactly {num_workers} entries.\n"
    )

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a precise research strategist. You output JSON only."},
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
                        worker_name: str, tool_bundle: str = "default") -> str:
    """Build a worker system prompt optimized for exact-answer finding.

    This is the key difference from the generic prompt: it tells the
    worker what kind of answer to look for and gives them a specific
    search plan. The rules are customized based on the tool bundle.
    """
    answer_type_hints = {
        "number": "The answer is a NUMBER. Be precise. Check for units, commas, and formatting.",
        "name": "The answer is a NAME (person, place, thing). Get the exact spelling.",
        "phrase": "The answer is a PHRASE or short sentence. Get the exact wording.",
        "date": "The answer is a DATE. Be specific about year/month/day format.",
        "other": "The answer is a specific fact. Get the exact wording.",
    }

    hint = answer_type_hints.get(answer_type, "The answer is a specific fact. Get the exact wording.")

    # Bundle-specific rules — aggressively force tool use
    if tool_bundle == "vision":
        bundle_rules = (
            f"CRITICAL INSTRUCTIONS — FOLLOW THESE EXACTLY:\n"
            f"1. CALL read_image NOW with the ATTACHED FILE path.\n"
            f"2. After reading the image, use scratchpad_add to log the raw data.\n"
            f"3. If you need to look something up, use web_search and web_extract.\n"
            f"4. Then state the answer CLEARLY at the TOP of your response.\n"
            f"5. Then explain your reasoning.\n"
            f"6. NEVER guess the file contents. You MUST call read_image.\n"
            f"7. Be precise. Exact names, exact numbers, exact dates.\n"
        )
    elif tool_bundle == "code":
        bundle_rules = (
            f"CRITICAL INSTRUCTIONS — FOLLOW THESE EXACTLY:\n"
            f"1. If there is an attached file, CALL read_image or read_file NOW to get the data.\n"
            f"2. CALL python_exec to run calculations. Do NOT compute in your head.\n"
            f"3. Use scratchpad_add to log the raw data and results.\n"
            f"4. Use web_search and web_extract if you need to look up information.\n"
            f"5. Then state the answer CLEARLY at the TOP of your response.\n"
            f"6. Then explain your reasoning.\n"
            f"7. NEVER guess the answer. You MUST call python_exec to compute.\n"
            f"8. Be precise. Exact numbers.\n"
        )
    elif tool_bundle == "files":
        bundle_rules = (
            f"CRITICAL INSTRUCTIONS — FOLLOW THESE EXACTLY:\n"
            f"1. CALL read_file or read_image NOW with the ATTACHED FILE path.\n"
            f"2. After reading the file, use scratchpad_add to log the raw data.\n"
            f"3. Use web_search and web_extract if you need to look up additional context.\n"
            f"4. Then state the answer CLEARLY at the TOP of your response.\n"
            f"5. Then explain your reasoning.\n"
            f"6. NEVER guess the file contents. You MUST call read_file or read_image.\n"
            f"7. Be precise. Exact names, exact numbers, exact dates.\n"
        )
    else:
        bundle_rules = (
            f"RULES:\n"
            f"1. Search the web to find the exact answer. Use web_search and web_extract.\n"
            f"2. For EVERY search result, use scratchpad_add to log the raw facts, quotes, "
            f"numbers, and source URLs you find.\n"
            f"3. After collecting data, state the answer CLEARLY at the TOP of your response.\n"
            f"4. Then explain your reasoning and cite your sources.\n"
            f"5. If you find conflicting information, note it and explain why you chose one answer.\n"
            f"6. Be precise. Exact names, exact numbers, exact dates.\n"
            f"7. Keep searching until you're confident in the answer.\n"
        )

    return (
        f"You are {worker_name}, a precise fact-finding agent.\n\n"
        f"QUESTION: {goal}\n\n"
        f"ANSWER TYPE: {answer_type.upper()}\n"
        f"{hint}\n\n"
        f"YOUR ASSIGNED SEARCH STRATEGY:\n{strategy['search_plan']}\n\n"
        f"VERIFICATION: {strategy.get('verification_hint', 'Verify with a second source.')}\n\n"
        f"{bundle_rules}"
    )