# src/core/taxonomy_store.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Any, Iterable, Tuple, Optional
import json
import os
import re

from rapidfuzz import fuzz, process

# ---------------------------- utils ---------------------------- #

def _norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

# ---------------------------- leaf model ---------------------------- #

@dataclass(frozen=True)
class Leaf:
    id: str
    name: str
    path: str           # e.g., "Electronics > Computer Accessories > Mice > Wireless"
    depth: int          # number of segments in path
    tokens: str         # normalized string used for fuzzy scoring

@dataclass
class MarketplaceTaxonomy:
    name: str                      # marketplace display name
    file: Path                     # source JSON path
    id_field: str = "id"
    name_field: str = "name"
    children_field: str = "children"
    leaves: List[Leaf] = None      # populated after load

# ---------------------------- flatten function (kept public) ---------------------------- #

def flatten_to_leaves(
    taxonomy: Dict[str, Any],
    id_field: str = "id",
    name_field: str = "name",
    children_field: str = "children",
) -> List[Dict[str, Any]]:
    """
    Return list of leaves with id, name, path, depth.
    If a node already includes 'path', prefer it (normalized),
    else compute from ancestor names (also normalized).
    """
    leaves: List[Dict[str, Any]] = []

    def dfs(node: Dict[str, Any], path_parts: List[str]):
        name = str(node.get(name_field, ""))
        _id = str(node.get(id_field, ""))
        children = node.get(children_field, []) or []

        # prefer node-provided path; else build from ancestors + current
        node_path_raw = node.get("path")
        if node_path_raw:
            path_str = _normalize_path(str(node_path_raw))
            depth = len([p for p in path_str.split(" > ") if p])
        else:
            path_now = path_parts + ([name] if name else [])
            path_str = _normalize_path(" > ".join(p for p in path_now if p))
            depth = len([p for p in path_str.split(" > ") if p])

        if not children:
            leaves.append(
                {
                    "id": _id,
                    "name": name,
                    "path": path_str,
                    "depth": depth,
                }
            )
            return
        for c in children:
            if isinstance(c, dict):
                dfs(c, path_parts + ([name] if name else []))

    dfs(taxonomy, [])

    # Deduplicate by tuple just in case
    seen = set()
    unique: List[Dict[str, Any]] = []
    for leaf in leaves:
        k = (leaf["id"], leaf["name"], leaf["path"])
        if k not in seen:
            seen.add(k)
            unique.append(leaf)
    return unique


# ---------------------------- store ---------------------------- #

class TaxonomyStore:
    """
    Loads/holds market taxonomies and offers a fuzzy shortlist for a product query string.
    Prefer load_all_from_marketplaces(config_dict) so you honor per-marketplace field names.
    """
    def __init__(self, taxonomy_dir: Optional[Path | str] = None):
        self.dir = Path(taxonomy_dir) if taxonomy_dir else None
        self.marketplaces: Dict[str, MarketplaceTaxonomy] = {}

    # ---- Preferred: load from marketplaces.json structure ---- #
    def load_all_from_marketplaces(self, marketplaces_cfg: Dict[str, Any]) -> None:
        """
        marketplaces_cfg shape:
        {
          "marketplaces": [
            {
              "name": "Marketplace A",
              "taxonomy_file": "data/taxonomies/marketplaceA.json",
              "id_field": "id",
              "name_field": "name",
              "children_field": "children"
            },
            ...
          ]
        }
        """
        mps = marketplaces_cfg.get("marketplaces", []) or []
        self.marketplaces.clear()
        for mp in mps:
            name = str(mp["name"])
            file = Path(mp["taxonomy_file"])
            id_field = mp.get("id_field", "id")
            name_field = mp.get("name_field", "name")
            children_field = mp.get("children_field", "children")

            if not file.exists():
                raise FileNotFoundError(f"Taxonomy file not found for {name}: {file}")

            data = json.loads(file.read_text(encoding="utf-8"))
            roots = data if isinstance(data, list) else [data]
            leaves_flat: List[Dict[str, Any]] = []
            for r in roots:
                leaves_flat.extend(
                    flatten_to_leaves(r, id_field=id_field, name_field=name_field, children_field=children_field)
                )

            leaves: List[Leaf] = [
                Leaf(
                    id=str(L["id"]),
                    name=str(L["name"]),
                    path=str(L["path"]),
                    depth=int(L["depth"]),
                    tokens=_norm(f'{L["path"]} {L["name"]}'),
                )
                for L in leaves_flat
            ]

            self.marketplaces[name] = MarketplaceTaxonomy(
                name=name,
                file=file,
                id_field=id_field,
                name_field=name_field,
                children_field=children_field,
                leaves=leaves,
            )

    # ---- Fallback: scan a directory of *.json (if you don't rely on marketplaces.json) ---- #
    def load_all_from_dir(self) -> None:
        if not self.dir:
            raise ValueError("TaxonomyStore: no taxonomy_dir was provided.")
        self.marketplaces.clear()
        for p in sorted(self.dir.glob("*.json")):
            name = p.stem
            data = json.loads(p.read_text(encoding="utf-8"))
            roots = data if isinstance(data, list) else [data]
            leaves_flat = []
            for r in roots:
                leaves_flat.extend(flatten_to_leaves(r))
            leaves: List[Leaf] = [
                Leaf(
                    id=str(L["id"]),
                    name=str(L["name"]),
                    path=str(L["path"]),
                    depth=int(L["depth"]),
                    tokens=_norm(f'{L["path"]} {L["name"]}'),
                )
                for L in leaves_flat
            ]
            self.marketplaces[name] = MarketplaceTaxonomy(name=name, file=p, leaves=leaves)

    # ---- Accessors ---- #
    def list_marketplaces(self) -> List[str]:
        return list(self.marketplaces.keys())

    def get_leaves(self, marketplace: str) -> List[Dict[str, Any]]:
        mp = self.marketplaces.get(marketplace)
        if not mp or not mp.leaves:
            return []
        return [
            {"id": lf.id, "name": lf.name, "path": lf.path, "depth": lf.depth}
            for lf in mp.leaves
        ]

    # ---- Shortlist ---- #
    def shortlist(self, marketplace: str, query_text: str, k: int = 50) -> List[Dict[str, Any]]:
        mp = self.marketplaces.get(marketplace)
        if not mp or not mp.leaves:
            return []

        corpus = [lf.tokens for lf in mp.leaves]
        # partial_ratio handles short item titles well
        result = process.extract(_norm(query_text), corpus, scorer=fuzz.partial_ratio, limit=min(k, len(corpus)))

        picks: List[Dict[str, Any]] = []
        for _, score, idx in result:
            leaf = mp.leaves[idx]
            picks.append({"id": leaf.id, "name": leaf.name, "path": leaf.path, "depth": leaf.depth, "score": int(score)})

        # Deduplicate by path, keep highest score
        unique: Dict[str, Dict[str, Any]] = {}
        for r in picks:
            key = r["path"]
            if key not in unique or r["score"] > unique[key]["score"]:
                unique[key] = r
        return list(unique.values())

# ... existing imports ...

def _normalize_path(raw: str) -> str:
    """
    Normalize any taxonomy path to use ' > ' as the delimiter,
    trim spaces, and drop a leading 'Root' segment if present.
    """
    if not raw:
        return ""
    s = str(raw).strip()

    # unify common delimiters to '>'
    # handles '/', ' / ', '>', ' > ', '→', '»', '|' etc.
    s = re.sub(r"\s*[/|>→»]\s*", ">", s)
    # collapse multiple '>' and spaces
    parts = [p.strip() for p in s.split(">") if p.strip()]
    if parts and parts[0].lower() == "root":
        parts = parts[1:]
    return " > ".join(parts)

