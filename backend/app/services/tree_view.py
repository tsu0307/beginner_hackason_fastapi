from __future__ import annotations

from typing import Any


def _normalize_happiness(value: Any) -> str:
    if not isinstance(value, str):
        return ""

    normalized = value.strip().lower()
    mapping = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "高": "high",
        "中": "medium",
        "低": "low",
    }
    if normalized in mapping:
        return mapping[normalized]
    if "高" in value:
        return "high"
    if "中" in value:
        return "medium"
    if "低" in value:
        return "low"
    return normalized


def _normalize_level(value: Any) -> str:
    if not isinstance(value, str):
        return ""

    normalized = value.strip().lower()
    mapping = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "高": "high",
        "中": "medium",
        "低": "low",
    }
    return mapping.get(normalized, normalized)


def build_tree_view_model(nodes: list[dict[str, Any]], current_node_id: str | None = None) -> dict[str, Any]:
    if not nodes:
        return {"width": 320, "height": 160, "nodes": [], "edges": []}

    min_width = 220
    max_width = 360
    base_height = 92
    col_gap = 48
    row_gap = 72
    pad_x = 28
    pad_y = 28

    children_by_parent: dict[str | None, list[dict[str, Any]]] = {}
    for node in nodes:
        children_by_parent.setdefault(node.get("parent_id"), []).append(node)

    root = next((node for node in nodes if node.get("parent_id") is None), nodes[0])
    positions: dict[str, dict[str, int]] = {}
    dimensions: dict[str, dict[str, int]] = {}
    next_col = 0
    max_depth = 0

    def measure(node: dict[str, Any]) -> dict[str, int]:
        title = node.get("event", "")
        title_len = max(len(title), 1)
        width = min(max(min_width, 120 + title_len * 12), max_width)
        chars_per_line = max(10, (width - 32) // 16)
        title_lines = max(1, (title_len + chars_per_line - 1) // chars_per_line)

        meta_lines = 2
        if node.get("stability") or node.get("challenge"):
            meta_lines += 1
        if node.get("happiness"):
            meta_lines += 1

        height = base_height + max(0, title_lines - 1) * 24 + meta_lines * 18

        helper_text = ""
        if node.get("is_branch_candidate"):
            helper_text = "クリックするとこの候補を確定します。"
        elif not node.get("result"):
            helper_text = "クリックするとこの地点から次の二択を生成します。"
        if helper_text:
            helper_lines = max(1, (len(helper_text) + chars_per_line - 1) // chars_per_line)
            height += helper_lines * 18

        if node.get("result") and node.get("id") == current_node_id:
            result_len = len(str(node.get("result", "")))
            result_lines = max(2, (result_len + chars_per_line - 1) // chars_per_line)
            height += 34 + result_lines * 18

        dimensions[node["id"]] = {"width": width, "height": height}
        return dimensions[node["id"]]

    for node in nodes:
        measure(node)

    global_col_width = max(size["width"] for size in dimensions.values())
    global_row_height = max(size["height"] for size in dimensions.values())

    def place(node: dict[str, Any], depth: int) -> int:
        nonlocal next_col, max_depth
        max_depth = max(max_depth, depth)
        size = dimensions[node["id"]]
        children = children_by_parent.get(node["id"], [])
        if not children:
            col = next_col
            next_col += 1
        else:
            child_cols = [place(child, depth + 1) for child in children]
            col = (child_cols[0] + child_cols[-1]) // 2
        x = pad_x + col * (global_col_width + col_gap) + (global_col_width - size["width"]) // 2
        positions[node["id"]] = {"x": x, "depth": depth}
        return col

    place(root, 0)

    for node in nodes:
        depth = positions[node["id"]]["depth"]
        positions[node["id"]]["y"] = pad_y + (max_depth - depth) * (global_row_height + row_gap)

    view_nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []

    for node in nodes:
        pos = positions[node["id"]]
        size = dimensions[node["id"]]
        happiness = _normalize_happiness(node.get("happiness", ""))
        stability = _normalize_level(node.get("stability", ""))
        challenge = _normalize_level(node.get("challenge", ""))

        view_nodes.append(
            {
                "id": node["id"],
                "x": pos["x"],
                "y": pos["y"],
                "width": size["width"],
                "height": size["height"],
                "title": node.get("event", ""),
                "status": "候補" if node.get("is_branch_candidate") else "選択済み" if node.get("selected") else "未選択",
                "selected": node.get("selected", False),
                "visited": node.get("visited", False),
                "is_branch_candidate": node.get("is_branch_candidate", False),
                "happiness": happiness,
                "stability": stability,
                "challenge": challenge,
                "result": node.get("result", ""),
                "is_current": node.get("id") == current_node_id,
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
                    "visited": node.get("visited", False),
                    "x1": parent["x"] + parent_size["width"] // 2,
                    "y1": parent["y"],
                    "x2": pos["x"] + size["width"] // 2,
                    "y2": pos["y"] + size["height"],
                    "mid_y": parent["y"] - ((parent["y"] - (pos["y"] + size["height"])) // 2),
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
