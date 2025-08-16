from typing import Dict, Any
from .models import ItemInput, MarketplaceCategoryResult
from .loaders import load_prompt
from ..config import MODEL_PROVIDER, OPENAI_API_KEY, OPENAI_MODEL, ANTHROPIC_API_KEY, ANTHROPIC_MODEL

# NOTE: Stubbed. Wire up to OpenAI/Anthropic later.
# Receives: item details, marketplace name, and its taxonomy JSON.
# Returns: best leaf (name + id).
def choose_category_for_marketplace(item: ItemInput, marketplace_name: str, taxonomy: Dict[str, Any]) -> MarketplaceCategoryResult:
    leaf = _first_leaf_node(taxonomy) or {"name": "UNMAPPED", "id": "N/A"}
    return MarketplaceCategoryResult(
        marketplace=marketplace_name,
        category_name=leaf["name"],
        category_id=str(leaf["id"])
    )

def _first_leaf_node(tree: Dict[str, Any]) -> Dict[str, Any] | None:
    def dfs(node):
        children = node.get("children", [])
        if not children:
            return node
        for c in children:
            found = dfs(c)
            if found:
                return found
        return None
    return dfs(tree)
