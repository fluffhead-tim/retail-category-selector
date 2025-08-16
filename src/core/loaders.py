import json
from typing import Dict, Any
from ..config import MARKETPLACES_FILE, PROMPT_FILE

def load_marketplaces() -> Dict[str, Any]:
    with open(MARKETPLACES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_taxonomy(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_prompt() -> str:
    with open(PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()
