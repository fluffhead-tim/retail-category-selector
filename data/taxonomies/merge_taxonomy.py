#!/usr/bin/env python3
"""
Build a hierarchical taxonomy from a single flattened file into BandQ-style output.

Usage:
  python3 merge_taxonomy.py --flat temp1.json --out BandQ_full_hierarchy_from_temp1.json

Notes:
- The flat file must contain records with: code, label, parent_code ('' or 'root' for root-level). 'level' is optional.
- The script nests each node under the node whose `code` == its `parent_code`.
- Unknown parents are deferred across passes; remaining orphans attach to Root unless --strict is used.
- The output includes BandQ-style fields: label, code, level, children, path (label_translations retained if present).
"""
import json
import argparse
from pathlib import Path
from collections import defaultdict

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def normalize_flat(nodes):
    # nodes may be a dict with "hierarchies" list or a list
    if isinstance(nodes, dict) and isinstance(nodes.get("hierarchies"), list):
        nodes = nodes["hierarchies"]
    elif isinstance(nodes, list):
        pass
    else:
        raise ValueError("Flattened file must be a list or a dict with 'hierarchies' list.")
    out = []
    for n in nodes:
        if not n or "code" not in n: 
            continue
        out.append({
            "code": n.get("code"),
            "label": n.get("label") or n.get("name") or n.get("code"),
            "label_translations": n.get("label_translations", []),
            "level": n.get("level"),
            "parent_code": (n.get("parent_code") or "").strip()
        })
    return out

def iter_nodes(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        stack.extend(node.get("children", []))

def build_code_index(root):
    idx = {}
    for n in iter_nodes(root):
        c = n.get("code")
        if c:
            idx[c] = n
    return idx

def get_or_create_node(code_index, code, label=None, level=None, label_translations=None):
    if code in code_index:
        node = code_index[code]
        if label and not node.get("label"):
            node["label"] = label
        if level is not None and node.get("level") is None:
            node["level"] = level
        if label_translations and not node.get("label_translations"):
            node["label_translations"] = label_translations
        node.setdefault("children", [])
        return node
    node = {
        "label": label or code,
        "code": code,
        "level": level,
        "children": []
    }
    if label_translations:
        node["label_translations"] = label_translations
    code_index[code] = node
    return node

def set_paths_and_levels(node, parent_path="", depth=0):
    label = node.get("label") or node.get("code") or ""
    node["path"] = f"{parent_path} > {label}" if parent_path else label
    if node.get("level") is None:
        node["level"] = depth
    for ch in node.get("children", []):
        set_paths_and_levels(ch, node["path"], depth + 1)

def sort_children(node):
    if "children" in node:
        node["children"].sort(key=lambda x: (x.get("level", 9999), x.get("label", ""), x.get("code", "")))
        for ch in node["children"]:
            sort_children(ch)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--flat", required=True, help="Path to a single flattened JSON file to build into a hierarchy.")
    ap.add_argument("--out", required=True, help="Output path for BandQ-style hierarchical JSON.")
    ap.add_argument("--root-label", default="Root", help="Label to use for the synthetic root node (default: Root).")
    ap.add_argument("--strict", action="store_true", help="Fail if any node's parent_code is unknown (instead of attaching to root).")
    args = ap.parse_args()

    # Initialize a fresh BandQ-style root
    base = {
        "label": args.root_label,
        "code": "root",
        "children": []
    }

    code_index = build_code_index(base)

    # Load and normalize the single flat source
    flat_nodes = normalize_flat(load_json(args.flat))

    # Order: parents first (by level if provided), then label/code
    flat_nodes.sort(key=lambda n: (n.get("level", 9999), n.get("label") or "", n["code"]))

    pending = flat_nodes[:]
    progress = True
    unknown_parents = set()

    def find_parent(parent_code):
        if not parent_code or parent_code.lower() == "root":
            return base
        return code_index.get(parent_code)

    while pending and progress:
        next_pending = []
        progress = False
        for n in pending:
            parent = find_parent(n["parent_code"])
            if parent is None:
                next_pending.append(n)
                unknown_parents.add(n["parent_code"])
                continue
            child = get_or_create_node(code_index, n["code"], n.get("label"), n.get("level"), n.get("label_translations"))
            parent.setdefault("children", [])
            if all(ch.get("code") != child["code"] for ch in parent["children"]):
                parent["children"].append(child)
            progress = True
        pending = next_pending

    if pending:
        if args.strict:
            missing = sorted(set([n["parent_code"] for n in pending if n.get("parent_code")]))
            raise SystemExit(f"Aborting due to unknown parent_code(s): {missing[:20]} (and possibly more).")
        # Attach orphans to root to avoid data loss
        for n in pending:
            child = get_or_create_node(code_index, n["code"], n.get("label"), n.get("level"), n.get("label_translations"))
            if all(ch.get("code") != child["code"] for ch in base.get("children", [])):
                base.setdefault("children", []).append(child)

    # Finalize with BandQ-style path + level
    set_paths_and_levels(base, "", 0)
    sort_children(base)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(base, f, indent=2, ensure_ascii=False)

    print(f"✅ Wrote hierarchical taxonomy to {out_path}")

if __name__ == "__main__":
    main()
