"""Preflight — the orchestrator analyzes the question and generates worker strategies.

Instead of hardcoded angles like "Cover ORIGINS and HISTORY," the
preflight pass uses the orchestrator model to:
1. Figure out what kind of answer is needed (number, name, phrase, etc.)
2. Generate specific search strategies for each worker
3. Give workers a clear, actionable plan for finding the exact answer
"""

import json
import re
import urllib.request


def analyze_question(goal: str, model: str,
                     ollama_base: str = "http://localhost:11434",
                     num_workers: int = 3) -> dict:
    """Use the orchestrator model to analyze a question and generate strategies.

    Returns:
        dict with:
        - answer_type: "number", "name", "phrase", "date", "other"
        - strategies: list of N dicts, each with:
            - worker_name: suggested name
            - search_plan: specific search strategy
            - verification_hint: how to verify the answer
    """
    prompt = (
        f"You are a research strategist. Analyze this question and generate "
        f"{num_workers} specific search strategies to find the exact answer.\n\n"
        f"QUESTION: {goal}\n\n"
        f"First, classify the answer type (one of: number, name, phrase, date, other).\n"
        f"Then, for each of {num_workers} workers, generate a specific search plan.\n\n"
        f"Respond with ONLY valid JSON in this exact format:\n"
        f"{{\n"
        f'  "answer_type": "number|name|phrase|date|other",\n'
        f'  "strategies": [\n'
        f'    {{\n'
        f'      "worker_name": "Vera",\n'
        f'      "search_plan": "Search Wikipedia for X, then find Y...",\n'
        f'      "verification_hint": "Cross-check with source Z"\n'
        f'    }}\n'
        f"  ]\n"
        f"}}\n\n"
        f"Make each search_plan concrete and actionable. Include specific terms to search for."
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
            "strategies": [
                {"worker_name": f"Worker {i+1}", "search_plan": "Search for the answer directly.", "verification_hint": "Verify with a second source."}
                for i in range(num_workers)
            ],
        }

    # Try to extract JSON from the response
    try:
        parsed = _extract_json(content)
        if parsed and "strategies" in parsed:
            # Ensure we have exactly num_workers strategies
            strategies = parsed["strategies"][:num_workers]
            while len(strategies) < num_workers:
                strategies.append({
                    "worker_name": f"Worker {len(strategies)+1}",
                    "search_plan": "Search for the answer directly.",
                    "verification_hint": "Verify with a second source."
                })
            return {
                "answer_type": parsed.get("answer_type", "other"),
                "strategies": strategies,
            }
    except Exception:
        pass

    # Fallback
    return {
        "answer_type": "other",
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
    match = re.search(r"\{.*\"strategies\".*}", text, re.DOTALL)
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

    # Bundle-specific rules
    if tool_bundle == "vision":
        bundle_rules = (
            f"RULES:\n"
            f"1. The attached file data (if any) is ALREADY in this prompt above. Do not search for it. Use it directly.\n"
            f"2. Use read_image to examine additional image content if needed.\n"
            f"3. For EVERY finding from the image, use scratchpad_add to log the raw data.\n"
            f"4. Use web_search and web_extract if you need to look up additional context.\n"
            f"5. After collecting data, state the answer CLEARLY at the TOP of your response.\n"
            f"6. Then explain your reasoning.\n"
            f"7. If you find conflicting information, note it.\n"
            f"8. Be precise. Exact names, exact numbers, exact dates.\n"
        )
    elif tool_bundle == "code":
        bundle_rules = (
            f"RULES:\n"
            f"1. The attached file data (if any) is ALREADY in this prompt above. Do not search for it. Use it directly.\n"
            f"2. Use python_exec to run calculations and data processing on the data provided.\n"
            f"3. Use web_search and web_extract if you need to look up information.\n"
            f"4. For EVERY finding, use scratchpad_add to log the raw facts.\n"
            f"5. After collecting data, state the answer CLEARLY at the TOP of your response.\n"
            f"6. Then explain your reasoning and cite your sources.\n"
            f"7. If you find conflicting information, note it and explain why you chose one answer.\n"
            f"8. Be precise. Exact numbers, exact dates.\n"
        )
    elif tool_bundle == "files":
        bundle_rules = (
            f"RULES:\n"
            f"1. The attached file data (if any) is ALREADY in this prompt above. Do not search for it. Use it directly.\n"
            f"2. Use read_file to read additional file content. Use read_image if the file is an image.\n"
            f"3. For EVERY finding, use scratchpad_add to log the raw facts.\n"
            f"4. Use web_search and web_extract if you need to look up additional context.\n"
            f"5. After collecting data, state the answer CLEARLY at the TOP of your response.\n"
            f"6. Then explain your reasoning.\n"
            f"7. If you find conflicting information, note it.\n"
            f"8. Be precise. Exact names, exact numbers, exact dates.\n"
        )
    else:
        bundle_rules = (
            f"RULES:\n"
            f"1. The attached file data (if any) is ALREADY in this prompt above. Do not search for it. Use it directly.\n"
            f"2. Search the web to find the exact answer. Use web_search and web_extract.\n"
            f"3. For EVERY search result, use scratchpad_add to log the raw facts, quotes, "
            f"numbers, and source URLs you find.\n"
            f"4. After collecting data, state the answer CLEARLY at the TOP of your response.\n"
            f"5. Then explain your reasoning and cite your sources.\n"
            f"6. If you find conflicting information, note it and explain why you chose one answer.\n"
            f"7. Be precise. Exact names, exact numbers, exact dates.\n"
            f"8. Keep searching until you're confident in the answer.\n"
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