from flask import Flask, request, jsonify
from pydantic import ValidationError
from ..config import DATA_DIR, MARKETPLACES_FILE
from ..core.models import ItemInput, CategorizationResponse
from ..core.loaders import load_marketplaces, load_taxonomy
from ..core.categorizer import choose_category_for_marketplace
import os

app = Flask(__name__)

@app.get("/health")
def health():
    return {"status": "ok", "data_dir": os.path.abspath(DATA_DIR), "marketplaces_file": os.path.abspath(MARKETPLACES_FILE)}

@app.post("/categorize")
def categorize():
    try:
        payload = request.get_json(force=True)
        item = ItemInput(**payload)
    except (TypeError, ValidationError) as e:
        return jsonify({"error": "Invalid input", "details": str(e)}), 400

    marketplaces = load_marketplaces()
    results = []

    for mp in marketplaces.get("marketplaces", []):
        name = mp["name"]
        taxonomy_path = mp["taxonomy_file"]
        taxonomy = load_taxonomy(taxonomy_path)
        result = choose_category_for_marketplace(item, name, taxonomy)
        results.append(result.model_dump())

    resp = CategorizationResponse(sku=item.sku, categories=results)
    return jsonify(resp.model_dump()), 200

if __name__ == "__main__":
    app.run(debug=True)
