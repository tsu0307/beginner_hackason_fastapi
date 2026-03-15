from __future__ import annotations

from typing import Any


def build_tree_view_model(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    if not nodes:
        return {"width": 320, "height": 160, "nodes": [], "edges": []}

    min_width = 220
    max_width = 360
    base_height = 92
    col_gap = 120
    row_gap = 34
    pad_x = 28
    pad_y = 28

    children_by_parent: dict[str | None, list[dict[str, Any]]] = {}
    for node in nodes:
        children_by_parent.setdefault(node.get("parent_id"), []).append(node)

    root = next((node for node in nodes if node.get("parent_id") is None), nodes[0])
    positions: dict[str, dict[str, int]] = {}
    dimensions: dict[str, dict[str, int]] = {}
    next_row = 0

    def measure(node: dict[str, Any]) -> dict[str, int]:
        title = node.get("event", "")
        title_len = max(len(title), 1)
        width = min(max(min_width, 120 + title_len * 12), max_width)
        chars_per_line = max(10, (width - 32) // 16)
        title_lines = max(1, (title_len + chars_per_line - 1) // chars_per_line)
        meta_lines = 3 + (1 if node.get("happiness") else 0)
        height = base_height + max(0, title_lines - 1) * 24 + meta_lines * 10
        dimensions[node["id"]] = {"width": width, "height": height}
        return dimensions[node["id"]]

    def place(node: dict[str, Any], depth: int) -> int:
        nonlocal next_row
        size = measure(node)
        children = children_by_parent.get(node["id"], [])
        if not children:
            row = next_row
            next_row += 1
        else:
            child_rows = [place(child, depth + 1) for child in children]
            row = (child_rows[0] + child_rows[-1]) // 2
        positions[node["id"]] = {
            "x": pad_x + depth * (max_width + col_gap),
            "y": pad_y + row * (size["height"] + row_gap),
        }
        return row

    place(root, 0)

    view_nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for node in nodes:
        pos = positions[node["id"]]
        size = dimensions[node["id"]]
        view_nodes.append(
            {
                "id": node["id"],
                "x": pos["x"],
                "y": pos["y"],
                "width": size["width"],
                "height": size["height"],
                "title": node.get("event", ""),
                "status": "選択済み" if node.get("selected") else "未選択",
                "selected": node.get("selected", False),
                "happiness": node.get("happiness", ""),
                "result": node.get("result", ""),
                "year": node.get("year"),
                "age": node.get("age"),
                "event_type": node.get("event_type"),
                "duration_years": node.get("duration_years"),
            }
        )

        parent_id = node.get("parent_id")
        if parent_id and parent_id in positions:
            parent = positions[parent_id]
            parent_size = dimensions[parent_id]
            edges.append(
                {
                    "id": f"{parent_id}-{node['id']}",
                    "selected": node.get("selected", False),
                    "x1": parent["x"] + parent_size["width"],
                    "y1": parent["y"] + parent_size["height"] // 2,
                    "x2": pos["x"],
                    "y2": pos["y"] + size["height"] // 2,
                }
            )

    max_x = max(item["x"] + item["width"] for item in view_nodes)
    max_y = max(item["y"] + item["height"] for item in view_nodes)
    return {
        "width": max_x + pad_x,
        "height": max_y + pad_y,
        "nodes": view_nodes,
        "edges": edges,
    }
