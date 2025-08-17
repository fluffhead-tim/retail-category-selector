# src/core/taxonomy.py
from typing import Dict, Any, List

def flatten_to_leaves(
    taxonomy: Dict[str, Any],
    id_field: str = "id",
    name_field: str = "name",
    children_field: str = "children",
) -> List[Dict[str, Any]]:
    """Return list of leaves with id, name, path, depth."""
    leaves: List[Dict[str, Any]] = []

    def dfs(node: Dict[str, Any], path_parts: List[str]):
        name = str(node.get(name_field, ""))
        _id = str(node.get(id_field, ""))
        children = node.get(children_field, [])
        path_now = path_parts + [name] if name else path_parts
        if not children:
            leaves.append(
                {
                    "id": _id,
                    "name": name,
                    "path": " > ".join(p for p in path_now if p),
                    "depth": len(path_now),
                }
            )
            return
        for c in children:
            if isinstance(c, dict):
                dfs(c, path_now)

    dfs(taxonomy, [])
    # Deduplicate by (id, name, path) just in case
    seen = set()
    unique: List[Dict[str, Any]] = []
    for leaf in leaves:
        k = (leaf["id"], leaf["name"], leaf["path"])
        if k not in seen:
            seen.add(k)
            unique.append(leaf)
    return unique
