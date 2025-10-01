# src/core/categorizer.py
from typing import Dict, Any, List, Tuple
import os
import re

from .models import ItemInput, MarketplaceCategoryResult
from .loaders import load_prompt
from .taxonomy_store import flatten_to_leaves
from .llm import pick_category_via_llm

# --- config (tunable without redeploy) ---
_SHORTLIST_MAX = int(os.getenv("SHORTLIST_MAX_PER_MKT", "300"))
_MAX_NAME_CHARS = int(os.getenv("MAX_NAME_CHARS", "300"))
_MAX_DESC_CHARS = int(os.getenv("MAX_DESC_CHARS", "2000"))
_DEBUG = os.getenv("DEBUG", "").lower() in ("1", "true", "yes")

# --- simple heuristic scoring for pre-filtering ---
_WORD = re.compile(r"[A-Za-z0-9]+")

def _keywords(text: str) -> List[str]:
    return [w.lower() for w in _WORD.findall(text or "") if len(w) > 2]

def _score_leaf(product_name: str, product_desc: str, leaf: Dict[str, Any]) -> float:
    name_kw = set(_keywords(product_name))
    desc_kw = set(_keywords(product_desc))
    path = (leaf.get("path") or "") + " " + (leaf.get("name") or "")
    leaf_kw = set(_keywords(path))
    # Weighted overlap: name words weigh more than description; slight depth bonus
    return 2.0 * len(name_kw & leaf_kw) + 1.0 * len(desc_kw & leaf_kw) + 0.1 * float(leaf.get("depth", 0))

def _prefilter_candidates(item: ItemInput, leaves: List[Dict[str, Any]], top_k: int) -> List[Dict[str, Any]]:
    scored: List[Tuple[float, Dict[str, Any]]] = []
    # Truncate to keep tokens in check
    name = (item.name or "")[:_MAX_NAME_CHARS]
    desc = (item.description or "")[:_MAX_DESC_CHARS]
    for leaf in leaves:
        scored.append((_score_leaf(name, desc, leaf), leaf))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [leaf for _, leaf in scored[:max(1, top_k)]]

def _index_candidates(cands: List[Dict[str, Any]]) -> Tuple[Dict[str, Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    by_id = {str(c["id"]): c for c in cands if "id" in c}
    by_name = {}
    for c in cands:
        nm = str(c.get("name", "")).strip().lower()
        by_name.setdefault(nm, []).append(c)
    return by_id, by_name

def _truncate(text: str, limit: int) -> str:
    if not text:
        return text
    return text if len(text) <= limit else text[:limit]

# --- main entry used by the API ---
# ... existing imports & helpers ...

def choose_category_for_marketplace(
    item: ItemInput,
    marketplace_name: str,
    taxonomy: Dict[str, Any],
    *,
    id_field: str = "id",
    name_field: str = "name",
    children_field: str = "children",
    include_confidence: bool = False,
) -> Tuple[MarketplaceCategoryResult, Dict[str, int]]:
    system_prompt = load_prompt()

    zero_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    
    leaves = flatten_to_leaves(taxonomy, id_field=id_field, name_field=name_field, children_field=children_field)
    if not leaves:
        return MarketplaceCategoryResult(
            marketplace=marketplace_name,
            category_name="UNMAPPED",
            category_id="N/A",
            category_path="N/A",
        ), zero_usage

    candidates = _prefilter_candidates(item, leaves, top_k=_SHORTLIST_MAX)
    if not candidates:
        return MarketplaceCategoryResult(
            marketplace=marketplace_name,
            category_name="UNMAPPED",
            category_id="N/A",
            category_path="N/A",
        ), zero_usage

    safe_name = _truncate(item.name or "", _MAX_NAME_CHARS)
    safe_desc = _truncate(item.description or "", _MAX_DESC_CHARS)

    payload = {
        "product": {
            "sku": item.sku,
            "name": safe_name,
            "brand": item.brand,
            "description": safe_desc,
            "image_url": item.image_url,
            "attributes": item.attributes,
        },
        "marketplace": {
            "name": marketplace_name,
            "id_field": id_field,
            "name_field": name_field,
            "children_field": children_field,
        },
        "candidates": [
            {"id": str(c["id"]), "name": str(c["name"]), "path": str(c["path"]), "depth": int(c["depth"])}
            for c in candidates
        ],
        "output_format": {"category_id": "string", "category_name": "string"},
        "rules": [
            "Select exactly one leaf from candidates.",
            "Prefer deeper, more specific leaves.",
            "Match product name first, then description, to leaf path/name.",
            "If ties remain, pick the earliest candidate in the list.",
            "Return ONLY JSON with keys: category_id, category_name.",
        ],
    }
    if include_confidence:
        payload["output_format"]["confidence"] = "number between 0 and 1"
        payload["rules"].append("Return a confidence score between 0 and 1 indicating certainty.")
        payload["rules"][-2] = "Return ONLY JSON with keys: category_id, category_name, confidence."

    cat_id, cat_name, confidence, _raw, usage = pick_category_via_llm(
        system_prompt,
        payload,
        include_confidence=include_confidence,
    )

    by_id, by_name = _index_candidates(payload["candidates"])
    if cat_id and cat_name:
        cand = by_id.get(str(cat_id))
        if cand:
            return MarketplaceCategoryResult(
                marketplace=marketplace_name,
                category_name=str(cand["name"]),
                category_id=str(cand["id"]),
                category_path=str(cand["path"]),
                confidence=confidence,
            ), usage
        nm = str(cat_name).strip().lower()
        name_matches = by_name.get(nm, [])
        if name_matches:
            chosen = name_matches[0]
            return MarketplaceCategoryResult(
                marketplace=marketplace_name,
                category_name=str(chosen["name"]),
                category_id=str(chosen["id"]),
                category_path=str(chosen["path"]),
                confidence=confidence,
            ), usage

    # Fallback: top-scoring candidate
    best = candidates[0]
    if _DEBUG:
        print(f"[DEBUG] Fallback used for {item.sku} @ {marketplace_name}; candidates={len(candidates)}")
    return MarketplaceCategoryResult(
        marketplace=marketplace_name,
        category_name=str(best["name"]),
        category_id=str(best["id"]),
        category_path=str(best["path"]),
        confidence=confidence if include_confidence else None,
    ), usage
