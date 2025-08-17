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

    # only the loop body changes
    marketplaces = load_marketplaces()
    results = []

    for mp in marketplaces.get("marketplaces", []):
        name = mp["name"]
        taxonomy_path = mp["taxonomy_file"]
        id_field = mp.get("id_field", "id")
        name_field = mp.get("name_field", "name")
        children_field = mp.get("children_field", "children")

        taxonomy = load_taxonomy(taxonomy_path)
        result = choose_category_for_marketplace(
            item,
            name,
            taxonomy,
            id_field=id_field,
            name_field=name_field,
            children_field=children_field,
        )
        results.append(result.model_dump())


    resp = CategorizationResponse(sku=item.sku, categories=results)
    return jsonify(resp.model_dump()), 200

if __name__ == "__main__":
    app.run(debug=True)
