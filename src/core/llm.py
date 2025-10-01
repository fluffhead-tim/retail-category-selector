"""
LLM adapter for per-marketplace category selection.

Public API:
    pick_category_via_llm(system_prompt: str, payload: Dict[str, Any], *, include_confidence: bool = False)
        -> Tuple[Optional[str], Optional[str], Optional[float], str, Dict[str, int]]

Behavior:
- Sends your system prompt + a compact JSON payload describing the product
  and candidate leaves for a single marketplace.
- Forces JSON responses where supported (OpenAI response_format=json_object).
- Parses responses robustly (strips code fences, accepts slight variations).
- Returns (category_id, category_name, confidence, raw_text, usage_dict). 
  If parsing fails, returns (None, None, None, raw_text, usage_dict).
  usage_dict contains {prompt_tokens, completion_tokens, total_tokens}, defaults to zeros if unavailable.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple, Optional

def _extract_usage(usage_obj: Any) -> Dict[str, int]:
    """Extract token usage from API response, return zeros if unavailable"""
    try:
        if hasattr(usage_obj, 'prompt_tokens') and hasattr(usage_obj, 'completion_tokens'):
            prompt = int(usage_obj.prompt_tokens or 0)
            completion = int(usage_obj.completion_tokens or 0)
            total = int(getattr(usage_obj, 'total_tokens', prompt + completion))
            return {
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": total,
            }
    except Exception:
        pass
    return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

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

def _normalize_confidence(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        conf = float(value)
    except (TypeError, ValueError):
        return None
    if conf < 0.0 or conf > 1.0:
        return None
    return conf


def _extract_category(parsed: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], Optional[float]]:
    """
    Accepts a few common shapes, returns (category_id, category_name, confidence) or (None, None, None).
    Expected/ideal:
        {"category_id":"...", "category_name":"..."}
    Also tolerate:
        {"selection": {"category_id":"...","category_name":"..."}}
        {"selections":[{"category_id":"...","category_name":"..."}]}  # take first
    """
    if not isinstance(parsed, dict):
        return None, None, None

    if "category_id" in parsed and "category_name" in parsed:
        return (
            str(parsed["category_id"]),
            str(parsed["category_name"]),
            _normalize_confidence(parsed.get("confidence")),
        )

    sel = parsed.get("selection")
    if isinstance(sel, dict) and "category_id" in sel and "category_name" in sel:
        return (
            str(sel["category_id"]),
            str(sel["category_name"]),
            _normalize_confidence(sel.get("confidence")),
        )

    sels = parsed.get("selections")
    if isinstance(sels, list) and sels:
        first = sels[0]
        if isinstance(first, dict) and "category_id" in first and "category_name" in first:
            return (
                str(first["category_id"]),
                str(first["category_name"]),
                _normalize_confidence(first.get("confidence")),
            )

    return None, None, None

# ------------------------- providers ------------------------- #

def choose_with_openai(
    system_prompt: str,
    payload: Dict[str, Any],
    *,
    include_confidence: bool = False,
) -> Tuple[Optional[str], Optional[str], Optional[float], str, Dict[str, int]]:
    """
    Call OpenAI Chat Completions with JSON-only response mode where supported.
    Returns (category_id, category_name, confidence, raw_text, usage_dict).
    """
    from openai import OpenAI

    client = OpenAI(api_key=OPENAI_API_KEY)

    if include_confidence:
        user_instructions = (
            "You MUST return ONLY a single JSON object with exactly these keys:\n"
            '  - \"category_id\": string\n'
            '  - \"category_name\": string\n'
            '  - \"confidence\": number between 0 and 1\n'
            "No markdown, no extra fields, no explanations.\n"
        )
    else:
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
    usage = _extract_usage(completion.usage)
    parsed = _try_parse_json(content)
    cat_id, cat_name, confidence = _extract_category(parsed or {})
    if cat_id and cat_name:
        return cat_id, cat_name, confidence, content, usage
    return None, None, None, content, usage

def choose_with_anthropic(
    system_prompt: str,
    payload: Dict[str, Any],
    *,
    include_confidence: bool = False,
) -> Tuple[Optional[str], Optional[str], Optional[float], str, Dict[str, int]]:
    """
    Call Anthropic Messages API. Anthropic does not have a strict JSON mode like OpenAI's,
    so we include strong instructions and then parse.
    Returns (category_id, category_name, confidence, raw_text, usage_dict).
    """
    from anthropic import Anthropic

    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    if include_confidence:
        user_instructions = (
            "Return ONLY a JSON object with exactly:\n"
            '{\"category_id\": \"...\", \"category_name\": \"...\", \"confidence\": number between 0 and 1}\n'
            "No prose, no markdown."
        )
    else:
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

    usage = _extract_usage(msg.usage)
    parsed = _try_parse_json(content)
    cat_id, cat_name, confidence = _extract_category(parsed or {})
    if cat_id and cat_name:
        return cat_id, cat_name, confidence, content, usage
    return None, None, None, content, usage

# ------------------------- public entrypoint ------------------------- #

def pick_category_via_llm(
    system_prompt: str,
    payload: Dict[str, Any],
    *,
    include_confidence: bool = False,
) -> Tuple[Optional[str], Optional[str], Optional[float], str, Dict[str, int]]:
    """
    Returns (category_id, category_name, confidence, raw_text, usage_dict) for a SINGLE marketplace,
    using whichever provider is configured via env (MODEL_PROVIDER).

    - If MODEL_PROVIDER=openai and OPENAI_API_KEY is set → OpenAI path.
    - If MODEL_PROVIDER=anthropic and ANTHROPIC_API_KEY is set → Anthropic path.
    - If neither, returns (None, None, None, "", {prompt_tokens:0, completion_tokens:0, total_tokens:0}).
    """
    if MODEL_PROVIDER == "openai" and OPENAI_API_KEY:
        print("[LLM] Using OpenAI:", OPENAI_MODEL)
        return choose_with_openai(system_prompt, payload, include_confidence=include_confidence)

    if MODEL_PROVIDER == "anthropic" and ANTHROPIC_API_KEY:
        print("[LLM] Using Anthropic:", ANTHROPIC_MODEL)
        return choose_with_anthropic(system_prompt, payload, include_confidence=include_confidence)

    # No provider/keys configured
    return None, None, None, "", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
