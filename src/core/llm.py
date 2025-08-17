# src/core/llm.py
import json
from typing import Any, Dict, Tuple, Optional

from ..config import (
    MODEL_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
)

def _try_parse_json(text: str) -> Optional[Dict[str, Any]]:
    text = text.strip()
    # Be forgiving: strip surrounding code fences if any
    if text.startswith("```"):
        text = text.strip("`")
        # Try to drop a possible leading language tag
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
    try:
        return json.loads(text)
    except Exception:
        return None

def choose_with_openai(system_prompt: str, payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    from openai import OpenAI
    client = OpenAI(api_key=OPENAI_API_KEY)
    msg = json.dumps(payload, ensure_ascii=False)
    completion = client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    msg
                    + "\n\nReturn ONLY JSON with keys: "
                      '"category_id" and "category_name". No extra text.'
                ),
            },
        ],
        temperature=0,
        max_tokens=200,
    )
    content = completion.choices[0].message.content or ""
    parsed = _try_parse_json(content)
    if parsed and "category_id" in parsed and "category_name" in parsed:
        return str(parsed["category_id"]), str(parsed["category_name"]), content
    return None, None, content

def choose_with_anthropic(system_prompt: str, payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    from anthropic import Anthropic
    client = Anthropic(api_key=ANTHROPIC_API_KEY)
    msg = json.dumps(payload, ensure_ascii=False)
    response = client.messages.create(
        model=ANTHROPIC_MODEL,
        system=system_prompt,
        messages=[{"role": "user", "content": [{"type": "text", "text": msg + "\n\nReturn ONLY JSON with keys: \"category_id\" and \"category_name\"."}]}],
        temperature=0,
        max_tokens=300,
    )
    content = "".join(part.text for part in response.content if hasattr(part, "text"))
    parsed = _try_parse_json(content)
    if parsed and "category_id" in parsed and "category_name" in parsed:
        return str(parsed["category_id"]), str(parsed["category_name"]), content
    return None, None, content

def pick_category_via_llm(system_prompt: str, payload: Dict[str, Any]) -> Tuple[Optional[str], Optional[str], str]:
    """Returns (category_id, category_name, raw_text)."""
    if MODEL_PROVIDER == "openai" and OPENAI_API_KEY:
        return choose_with_openai(system_prompt, payload)
    if MODEL_PROVIDER == "anthropic" and ANTHROPIC_API_KEY:
        return choose_with_anthropic(system_prompt, payload)
    # No provider/keys configured
    return None, None, ""
