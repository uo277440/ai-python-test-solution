"""
LLM output sanitizer responsible for extracting and parsing structured JSON.

This module provides a defensive layer between the AI extraction step and
the business logic. It attempts to:
- Isolate a JSON object from potentially noisy model output.
- Parse strictly when possible.
- Apply minimal repairs for common formatting deviations.

It never fabricates data and returns None if the output cannot be safely parsed.
"""

import json
import re
from typing import Optional


# Extract a candidate JSON object from raw LLM output.
# Supports markdown code blocks and inline JSON fragments.
def _extract_json_block(raw: str) -> Optional[str]:
    """
    Extract a JSON object from raw LLM output.
    Handles markdown blocks and embedded JSON.
    """
    if not raw or not raw.strip():
        return None

    # 1. Markdown block ```json ... ```
    code_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if code_match:
        return code_match.group(1).strip()

    # If no markdown block is found, attempt to locate
    # the first syntactically balanced JSON object.
    # 2. Find first balanced {...}
    start = raw.find("{")
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    quote_char = None

    for i in range(start, len(raw)):
        c = raw[i]

        if escape:
            escape = False
            continue

        if c == "\\" and in_string:
            escape = True
            continue

        if not in_string:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return raw[start : i + 1]
            elif c in ('"', "'"):
                in_string = True
                quote_char = c
        else:
            if c == quote_char:
                in_string = False

    return None  # Unbalanced JSON


# Attempt strict JSON parsing without any transformation.
def _attempt_parse(candidate: str) -> Optional[dict]:
    """
    Try strict JSON parsing first.
    """
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


# Attempt minimal, controlled repairs for common LLM formatting issues.
# The goal is resilience, not aggressive correction.
def _attempt_repair(candidate: str) -> Optional[dict]:
    """
    Attempt simple repairs:
    - Single quotes → double quotes
    - Unquoted keys → quoted keys
    """
    # 1. Replace single quotes around values/keys
    repaired = re.sub(
        r"'([^']*)'",
        lambda m: json.dumps(m.group(1)),
        candidate,
    )

    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        pass

    # 2. Quote unquoted keys: {to: "x"} → {"to": "x"}
    repaired = re.sub(r"(\w+)\s*:", r'"\1":', candidate)

    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


# Public entry point for sanitizing model output.
# Returns a parsed dictionary only if it is safely recoverable.
def sanitize_llm_output(raw: str) -> Optional[dict]:
    """
    Convert LLM output into a Python dict if possible.
    Returns None if not recoverable.
    """
    candidate = _extract_json_block(raw)
    if not candidate:
        return None

    parsed = _attempt_parse(candidate)
    if isinstance(parsed, dict):
        return parsed

    repaired = _attempt_repair(candidate)
    if isinstance(repaired, dict):
        return repaired

    return None