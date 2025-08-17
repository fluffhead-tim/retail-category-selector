# src/core/categorizer.py
from typing import Dict, Any, List, Tuple
import re

from .models import ItemInput, MarketplaceCategoryResult
from .loaders import load_prompt
from .taxonomy import flatten_to_leaves
from .llm import pick_category_via_llm

# --- simple heuristic scoring for pre-filtering ---
_WORD = re.compile(r"[A-Za-z0-9]+")

def _keywords(text: str) -> List[str]:
    return [w.lower() for w in _WORD.findall(text or "") if len(w) > 2]

def _score_leaf(product_name: str, product_desc: str, leaf: Dict[str, Any]) -> float:
    name_kw = set(_keywords(product_name))
    desc_kw = set(_keywords(product_desc))
    path = (leaf.get("path") or "") + " " + (leaf.get("name") or "")
    leaf_kw = set(_keywords(path))
    # Weighted overlap: name words weigh more than description
    return 2.0 * len(name_kw & leaf_kw) + 1.0 * len(desc_kw & leaf_kw) + 0.1 * float(leaf.get("depth", 0))

def _prefilter_candidates(item: ItemInput, leaves: List[Dict[str, Any]], top_k: int = 300) -> List[Dict[str, Any]]:
    scored = []
    name = item.name or ""
    desc = item.description or ""
    for leaf in leaves:
        scored.append(( _score_leaf(name, desc, leaf), leaf ))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [leaf for _, leaf in scored[:top_k]]

# --- main entry used by the API ---
def choose_category_for_marketplace(
    item: ItemInput,
    marketplace_name: str,
    taxonomy: Dict[str, Any],
    *,
    id_field: str = "id",
    name_field: str = "name",
    children_field: str = "children",
) -> MarketplaceCategoryResult:
    # Load prompt
    system_prompt = load_prompt()

    # Flatten leaves and pre-filter (controls tokens & cost)
    leaves = flatten_to_leaves(taxonomy, id_field=id_field, name_field=name_field, children_field=children_field)
    if not leaves:
        return MarketplaceCategoryResult(marketplace=marketplace_name, category_name="UNMAPPED", category_id="N/A")

    candidates = _prefilter_candidates(item, leaves, top_k=300)

    # Build payload for LLM (per marketplace to keep context small)
    payload = {
        "product": {
            "sku": item.sku,
            "name": item.name,
            "brand": item.brand,
            "description": item.description,
            "image_url": item.image_url,
            "attributes": item.attributes,
        },
        "marketplace": {
            "name": marketplace_name,
            "id_field": id_field,
            "name_field": name_field,
            "children_field": children_field,
        },
        # Send only necessary fields for leaves
        "candidates": [
            {"id": c["id"], "name": c["name"], "path": c["path"], "depth": c["depth"]}
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

    # Ask LLM (if keys configured); otherwise fallback
    cat_id, cat_name, _raw = pick_category_via_llm(system_prompt, payload)
    if cat_id and cat_name:
        return MarketplaceCategoryResult(marketplace=marketplace_name, category_name=cat_name, category_id=cat_id)

    # Fallback: choose top-scoring candidate deterministically
    best = candidates[0]
    return MarketplaceCategoryResult(marketplace=marketplace_name, category_name=str(best["name"]), category_id=str(best["id"]))
