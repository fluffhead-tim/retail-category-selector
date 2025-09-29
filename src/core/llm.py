"""
LLM adapter for per-marketplace category selection.

Public API:
    pick_category_via_llm(system_prompt: str, payload: Dict[str, Any])
        -> Tuple[Optional[str], Optional[str], str]

Behavior:
- Sends your system prompt + a compact JSON payload describing the product
  and candidate leaves for a single marketplace.
- Forces JSON responses where supported (OpenAI response_format=json_object).
- Parses responses robustly (strips code fences, accepts slight variations).
- Returns (category_id, category_name, raw_text). If parsing fails, returns (None, None, raw_text).
"""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple, Optional

from ..config import (
    MODEL_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_TEMPERATURE,
    OPENAI_TOP_P,
    OPENAI_MAX_TOKENS,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    ANTHROPIC_TEMPERATURE,
    ANTHROPIC_TOP_P,
    ANTHROPIC_MAX_TOKENS,
)

# ------------------------- parsing helpers ------------------------- #

def _strip_code_fences(text: str) -> str:
    text = (text or "").strip()
    if text.startswith("```"):
        # remove surrounding backticks and drop an optional language tag
        text = text.strip("`")
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
    return text.strip()

def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    text = _strip_code_fences(text)
    try:
        return json.loads(text)
    except Exception:
        # last ditch: try to find a top-level JSON object within text
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            frag = text[start : end + 1]
            try:
                return json.loads(frag)
            except Exception:
                pass
        return None

def _extract_category(parsed: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    """
    Accepts a few common shapes, returns (category_id, category_name) or (None, None).
    Expected/ideal:
        {"category_id":"...", "category_name":"..."}
    Also tolerate:
        {"selection": {"category_id":"...","category_name":"..."}}
        {"selections":[{"category_id":"...","category_name":"..."}]}  # take first
    """
    if not isinstance(parsed, dict):
        return None, None

    if "category_id" in parsed and "category_name" in parsed:
        return str(parsed["category_id"]), str(parsed["category_name"])

    sel = parsed.get("selection")
    if isinstance(sel, dict) and "category_id" in sel and "category_name" in sel:
        return str(sel["category_id"]), str(sel["category_name"])

    sels = parsed.get("selections")
    if isinstance(sels, list) and sels:
        first = sels[0]
        if isinstance(first, dict) and "category_id" in first and "category_name" in first:
            return str(first["category_id"]), str(first["category_name"])

    return None, None

# ------------------------- providers ------------------------- #

def choose_with_openai(system_prompt: str, payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    """
    Call OpenAI Chat Completions with JSON-only response mode where supported.
    Returns (category_id, category_name, raw_text).
    """
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)

    user_instructions = (
        "You MUST return ONLY a single JSON object with exactly these keys:\n"
        '  - \"category_id\": string\n'
        '  - \"category_name\": string\n'
        "No markdown, no extra fields, no explanations.\n"
    )

    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_instructions + "\n\n" + json.dumps(payload, ensure_ascii=False)},
        ],
        temperature=OPENAI_TEMPERATURE,
        top_p=OPENAI_TOP_P,
        response_format={"type": "json_object"},
        max_tokens=OPENAI_MAX_TOKENS,
    )

    content = completion.choices[0].message.content or ""
    parsed = _try_parse_json(content)
    cat_id, cat_name = _extract_category(parsed or {})
    if cat_id and cat_name:
        return cat_id, cat_name, content
    return None, None, content

def choose_with_anthropic(system_prompt: str, payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    """
    Call Anthropic Messages API. Anthropic does not have a strict JSON mode like OpenAI's,
    so we include strong instructions and then parse.
    """
    from anthropic import Anthropic

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    user_instructions = (
        "Return ONLY a JSON object with exactly:\n"
        '{\"category_id\": \"...\", \"category_name\": \"...\"}\n'
        "No prose, no markdown."
    )

    anthropic_params = {
        "temperature": ANTHROPIC_TEMPERATURE,
        "max_tokens": ANTHROPIC_MAX_TOKENS,
    }
    if ANTHROPIC_TOP_P is not None:
        anthropic_params["top_p"] = ANTHROPIC_TOP_P

    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_instructions},
                    {"type": "text", "text": json.dumps(payload, ensure_ascii=False)},
                ],
            }
        ],
        **anthropic_params,
    )

    # Concatenate text blocks
    content_parts = []
    for part in msg.content:
        if getattr(part, "type", None) == "text":
            content_parts.append(part.text)
    content = "\n".join(content_parts).strip()

    parsed = _try_parse_json(content)
    cat_id, cat_name = _extract_category(parsed or {})
    if cat_id and cat_name:
        return cat_id, cat_name, content
    return None, None, content

# ------------------------- public entrypoint ------------------------- #

def pick_category_via_llm(system_prompt: str, payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    """
    Returns (category_id, category_name, raw_text) for a SINGLE marketplace,
    using whichever provider is configured via env (MODEL_PROVIDER).

    - If MODEL_PROVIDER=openai and OPENAI_API_KEY is set → OpenAI path.
    - If MODEL_PROVIDER=anthropic and ANTHROPIC_API_KEY is set → Anthropic path.
    - If neither, returns (None, None, "").
    """
    if MODEL_PROVIDER == "openai" and OPENAI_API_KEY:
        print("[LLM] Using OpenAI:", OPENAI_MODEL)
        return choose_with_openai(system_prompt, payload)

    if MODEL_PROVIDER == "anthropic" and ANTHROPIC_API_KEY:
        print("[LLM] Using Anthropic:", ANTHROPIC_MODEL)
        return choose_with_anthropic(system_prompt, payload)

    # No provider/keys configured
    return None, None, ""
