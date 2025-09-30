from flask import Flask, request, jsonify, send_from_directory, send_file
from pydantic import ValidationError
from pathlib import Path
from ..config import (
    DATA_DIR,
    MARKETPLACES_FILE,
    MODEL_PROVIDER,
    OPENAI_MODEL,
    ANTHROPIC_MODEL,
    OPENAI_API_KEY,
    ANTHROPIC_API_KEY,
)
from ..core.models import ItemInput, CategorizationResponse, MarketplaceCategoryResult
from ..core.loaders import load_marketplaces, load_taxonomy
from ..core.categorizer import choose_category_for_marketplace
import os
from html import unescape as html_unescape
import re
from typing import Any, Dict, List

_TAG = re.compile(r"<[^>]+>")

def _strip_html(s: str | None) -> str:
    if not s:
        return ""
    s = html_unescape(s)
    s = _TAG.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _get_trim(obj: Dict[str, Any], key: str) -> str:
    if key in obj and obj[key] is not None:
        return str(obj[key]).strip()
    return ""

def _collect_images(obj: Dict[str, Any]) -> List[str]:
    imgs: List[str] = []
    for i in range(1, 11):
        k = f"Image{i}FullSource"
        if k in obj and obj[k] is not None:
            val = str(obj[k]).strip()
            if val:
                imgs.append(val)
    return imgs

def _lower(s: str) -> str:
    return s.lower() if isinstance(s, str) else s

def _map_external_item_to_iteminput(raw: Dict[str, Any]) -> ItemInput:
    # Required fields
    sku = _get_trim(raw, "ItemNumber")     # always present per your upstream guarantee
    name = _get_trim(raw, "ItemTitle")

    # Brand may be blank — pass through as empty string
    brand = _get_trim(raw, "Brand")

    # Description: strip HTML from both descriptions and combine
    desc_html = _get_trim(raw, "Description")
    listing_desc_html = _get_trim(raw, "Listing Description")
    description = " ".join([_strip_html(desc_html), _strip_html(listing_desc_html)]).strip()

    # Images: array of up to 10; first one becomes image_url
    images = _collect_images(raw)  # at least one per your upstream guarantee
    image_url = images[0] if images else None

    # Attributes: include keys if present in the payload (even if blank),
    # except "bulletpoints": if blank, omit it entirely.
    attrs: Dict[str, Any] = {}
    if "Price" in raw:
        attrs["price"] = _get_trim(raw, "Price")
    if "Country of Manufacture" in raw:
        com = _get_trim(raw, "Country of Manufacture")
        if com:
            attrs["country_of_manufacture"] = com
        else:
            # key present but blank → omit per your instruction to ignore blank country
            pass
    if "StockItemId" in raw:
        attrs["stock_item_id"] = _get_trim(raw, "StockItemId")
    bp_concat = _get_trim(raw, "bulletpoints")
    if bp_concat:  # include only if non-blank
        attrs["bulletpoints"] = bp_concat

    # Always include the full images array for context
    attrs["images"] = images

    # Build ItemInput (brand/description can be empty strings)
    return ItemInput(
        sku=sku,
        name=name,
        brand=brand or "",                # keep empty-string passthrough as requested
        description=description or "",
        image_url=image_url,
        attributes=attrs,
    )


app = Flask(__name__)

# Compute absolute path to UI directory
ui_dir = Path(__file__).resolve().parents[2] / 'ui'

# UI Routes - serve static files from ui/ directory
@app.route('/')
def index():
    """Serve the main UI page"""
    return send_file(ui_dir / 'index.html')

@app.route('/ui/<path:filename>')
def ui_static(filename):
    """Serve static files from ui directory"""
    return send_from_directory(ui_dir, filename)

@app.get("/health")
def health():
    return {
        "status": "ok",
        "data_dir": os.path.abspath(DATA_DIR),
        "marketplaces_file": os.path.abspath(MARKETPLACES_FILE),
    }

@app.get("/health/llm")
def health_llm():
    return {
        "provider": MODEL_PROVIDER,
        "openai": {"configured": bool(OPENAI_API_KEY), "model": OPENAI_MODEL},
        "anthropic": {"configured": bool(ANTHROPIC_API_KEY), "model": ANTHROPIC_MODEL},
    }

@app.post("/categorize")
def categorize():
    # Body must be a single JSON object (not an array)
    try:
        payload = request.get_json(force=True)
    except Exception as e:
        return jsonify({"error": "Invalid JSON body", "details": str(e)}), 400

    if not isinstance(payload, dict):
        return jsonify({"error": "Request body must be a single JSON object"}), 400

    # Map external → internal
    try:
        item = _map_external_item_to_iteminput(payload)
    except Exception as e:
        return jsonify({"error": "Invalid item payload", "details": str(e)}), 400

    # Load marketplaces config
    marketplaces_cfg = load_marketplaces()
    all_mps = marketplaces_cfg.get("marketplaces", []) or []

    # Optional query param: ?marketplace=Name (case-insensitive)
    mp_filter = request.args.get("marketplace")
    if mp_filter:
        target = next((m for m in all_mps if _lower(m.get("name")) == _lower(mp_filter)), None)
        if not target:
            return jsonify({
                "error": "Invalid marketplace name",
                "provided": mp_filter,
                "available": [m.get("name") for m in all_mps]
            }), 400
        mps = [target]
    else:
        mps = all_mps 

    test_flag = request.args.get("test", "false")
    include_confidence = str(test_flag).lower() in ("1", "true", "yes")

    # For each marketplace: skip missing taxonomy file with a note; otherwise categorize
    results = []
    for mp in mps:
        name = mp["name"]
        taxonomy_path = mp["taxonomy_file"]
        id_field = mp.get("id_field", "id")
        name_field = mp.get("name_field", "name")
        children_field = mp.get("children_field", "children")

        if not os.path.exists(taxonomy_path):
            missing = MarketplaceCategoryResult(
                marketplace=name,
                category_name="UNMAPPED",
                category_id="N/A",
                category_path="N/A",
                note=f"Skipped: taxonomy file not found at '{taxonomy_path}'"
            )
            results.append(missing.model_dump())
            continue

        taxonomy = load_taxonomy(taxonomy_path)
        result = choose_category_for_marketplace(
            item,
            name,
            taxonomy,
            id_field=id_field,
            name_field=name_field,
            children_field=children_field,
            include_confidence=include_confidence,
        )
        results.append(result.model_dump())

    # Transform results to new format
    categories = []
    for cat in results:
        products_obj = {
            "category_code": cat.get("category_id"),
            "category_label": cat.get("category_name"),
            "product_sku": item.sku,
            "category_path": cat.get("category_path"),
            "marketplace": cat.get("marketplace"),
            "note": cat.get("note")
        }
        if include_confidence:
            products_obj["confidence"] = cat.get("confidence")
        categories.append({"products": products_obj})
    resp = {"categories": categories}
    return jsonify(resp), 200


# replace your existing block at the very bottom
if __name__ == "__main__":
    import os
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        debug=False,
        use_reloader=False
    )
