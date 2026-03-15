from __future__ import annotations

import asyncio
import copy
import uuid
from typing import Any

from pydantic import ValidationError

from .branch_schemas import BranchCandidate, BranchResponse
from .llm_gateway import call_llm
from .openai_service import parse_json_text
from .prompt_builder import (
    build_branch_prompt,
    build_custom_branch_prompt,
    build_result_prompt,
    build_story_prompt,
)


def _refresh_derived(state: dict[str, Any]) -> dict[str, Any]:
    nodes = state.get("nodes", [])
    current_node = next((node for node in nodes if node["id"] == state.get("current_node_id")), None)
    state["current_node"] = current_node
    state["selected_nodes"] = [node for node in nodes if node.get("selected")]
    return state


def _new_id() -> str:
    return uuid.uuid4().hex[:8]


def _node_lookup(nodes: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {node["id"]: node for node in nodes}


def _normalize_happiness(value: Any) -> str:
    if not isinstance(value, str):
        return "medium"

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
    return "medium"


def _path_to_node(nodes: list[dict[str, Any]], node_id: str | None) -> list[dict[str, Any]]:
    if not node_id:
        return []
    by_id = _node_lookup(nodes)
    ordered: list[dict[str, Any]] = []
    current = by_id.get(node_id)
    while current:
        ordered.append(current)
        parent_id = current.get("parent_id")
        current = by_id.get(parent_id) if parent_id else None
    ordered.reverse()
    return ordered


def _mark_selected_path(nodes: list[dict[str, Any]], node_id: str | None) -> list[dict[str, Any]]:
    path = _path_to_node(nodes, node_id)
    active_ids = {node["id"] for node in path}
    for node in nodes:
        node["selected"] = node["id"] in active_ids
    return path


def _mark_visited_path(nodes: list[dict[str, Any]], node_id: str | None) -> list[dict[str, Any]]:
    path = _path_to_node(nodes, node_id)
    for node in path:
        node["visited"] = True
    return path


def _build_node_from_branch(
    branch: BranchCandidate,
    *,
    parent_id: str | None,
    current_year: int,
    current_age: int,
    selected: bool = False,
) -> dict[str, Any]:
    return {
        "id": _new_id(),
        "event": branch.event,
        "stability": branch.stability,
        "challenge": branch.challenge,
        "event_type": branch.event_type,
        "duration_years": branch.duration_years,
        "year": current_year + branch.duration_years,
        "age": current_age + branch.duration_years,
        "parent_id": parent_id,
        "selected": selected,
        "visited": selected,
    }


def _parse_branch_response(payload: Any) -> list[BranchCandidate]:
    try:
        return BranchResponse.model_validate(payload).branches
    except ValidationError as exc:
        raise ValueError(f"分岐候補JSONの形式が不正です: {exc}") from exc


def _parse_branch_candidate(payload: Any) -> BranchCandidate:
    try:
        return BranchCandidate.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"手動分岐JSONの形式が不正です: {exc}") from exc


async def _generate_branches(
    state: dict[str, Any],
    profile: dict[str, Any],
    event: str,
    history: list[str],
    *,
    parent_id: str | None,
    current_year: int,
    current_age: int,
) -> list[dict[str, Any]]:
    runtime_profile = {
        **profile,
        "current_age": current_age,
        "current_year": current_year,
    }
    system, message = build_branch_prompt(runtime_profile, event, history)
    text = await asyncio.to_thread(call_llm, profile.get("provider", "openai"), system, message, True)
    parsed = parse_json_text(text)
    candidates = _parse_branch_response(parsed)
    return [
        _build_node_from_branch(
            candidate,
            parent_id=parent_id,
            current_year=current_year,
            current_age=current_age,
        )
        for candidate in candidates[:2]
    ]


async def _classify_custom_branch(
    state: dict[str, Any],
    event: str,
    history: list[str],
    *,
    parent_id: str,
    current_year: int,
    current_age: int,
) -> dict[str, Any]:
    runtime_profile = {
        **state["profile"],
        "current_age": current_age,
        "current_year": current_year,
    }
    system, message = build_custom_branch_prompt(runtime_profile, event, history)
    text = await asyncio.to_thread(call_llm, state.get("provider", "openai"), system, message, True)
    parsed = parse_json_text(text)
    candidate = _parse_branch_candidate(parsed)
    return _build_node_from_branch(
        candidate,
        parent_id=parent_id,
        current_year=current_year,
        current_age=current_age,
    )


async def _resolve_node_result(
    state: dict[str, Any],
    node: dict[str, Any],
    history: list[str],
) -> dict[str, Any]:
    runtime_profile = {**state["profile"], "current_age": node["age"]}
    system, message = build_result_prompt(runtime_profile, node["event"], history)
    text = await asyncio.to_thread(call_llm, state.get("provider", "openai"), system, message, True)
    parsed = parse_json_text(text)
    node["result"] = parsed.get("result_summary", parsed.get("result", "結果を生成できませんでした。"))
    node["happiness"] = _normalize_happiness(parsed.get("happiness", "medium"))
    return node


async def start_simulation(
    state: dict[str, Any],
    event: str,
    event_year: int,
    event_age: int,
    *,
    panel: str = "main",
) -> dict[str, Any]:
    new_state = copy.deepcopy(state)
    try:
        if event_age <= 0 or event_age >= 100:
            raise ValueError("イベント時の年齢は 1 から 99 の範囲で入力してください。")

        root = {
            "id": _new_id(),
            "event": event.strip(),
            "stability": "medium",
            "challenge": "medium",
            "event_type": "instant_event",
            "duration_years": 0,
            "year": event_year,
            "age": event_age,
            "selected": True,
            "visited": True,
            "parent_id": None,
        }
        new_state["nodes"] = [root]
        new_state["current_node_id"] = root["id"]
        new_state = _refresh_derived(new_state)
        new_state["branches"] = await _generate_branches(
            new_state,
            new_state["profile"],
            root["event"],
            [],
            parent_id=root["id"],
            current_year=root["year"],
            current_age=root["age"],
        )
        new_state["stage"] = "branches"
        new_state["panel"] = panel
        new_state["error"] = ""
    except Exception as exc:
        new_state["stage"] = "event"
        new_state["panel"] = panel
        new_state["error"] = str(exc)
    return _refresh_derived(new_state)


def get_branch_by_id(state: dict[str, Any], branch_id: str) -> dict[str, Any]:
    branch = next((branch for branch in state.get("branches", []) if branch["id"] == branch_id), None)
    if not branch:
        raise ValueError("指定された分岐候補が見つかりません。")
    return branch


async def select_branch(state: dict[str, Any], branch: dict[str, Any], *, panel: str = "main") -> dict[str, Any]:
    new_state = copy.deepcopy(state)
    try:
        path = _mark_selected_path(new_state["nodes"], branch.get("parent_id"))
        history = [node["event"] for node in path]
        selected_branch = await _resolve_node_result(
            new_state,
            {**branch, "selected": True},
            history,
        )
        ordered_children = [
            selected_branch if item["id"] == branch["id"] else {**item, "selected": False}
            for item in new_state["branches"]
        ]
        new_state["nodes"].extend(ordered_children)
        new_state["branches"] = []
        new_state["current_node_id"] = selected_branch["id"]
        _mark_selected_path(new_state["nodes"], selected_branch["id"])
        _mark_visited_path(new_state["nodes"], selected_branch["id"])
        new_state["stage"] = "result"
        new_state["panel"] = panel
        new_state["error"] = ""
    except Exception as exc:
        new_state["error"] = str(exc)
    return _refresh_derived(new_state)


async def add_custom_branch(state: dict[str, Any], event: str, *, panel: str = "main") -> dict[str, Any]:
    new_state = copy.deepcopy(state)
    try:
        current = next((node for node in new_state.get("nodes", []) if node["id"] == new_state.get("current_node_id")), None)
        if not current:
            raise ValueError("現在のノードが見つかりません。")

        path = _mark_selected_path(new_state["nodes"], current["id"])
        _mark_visited_path(new_state["nodes"], current["id"])
        history = [node["event"] for node in path]

        custom_branch = await _classify_custom_branch(
            new_state,
            event.strip(),
            history,
            parent_id=current["id"],
            current_year=int(current["year"]),
            current_age=int(current["age"]),
        )
        new_state["branches"].append(custom_branch)
        new_state["stage"] = "branches"
        new_state["panel"] = panel
        new_state["error"] = ""
    except Exception as exc:
        new_state["error"] = str(exc)
    return _refresh_derived(new_state)


async def continue_simulation(state: dict[str, Any]) -> dict[str, Any]:
    new_state = copy.deepcopy(state)
    try:
        current = next((node for node in new_state["nodes"] if node["id"] == new_state["current_node_id"]), None)
        if not current:
            raise ValueError("現在のノードが見つかりません。")
        path = _mark_selected_path(new_state["nodes"], current["id"])
        _mark_visited_path(new_state["nodes"], current["id"])
        history = [node["event"] for node in path]
        new_state["branches"] = await _generate_branches(
            new_state,
            new_state["profile"],
            current["event"],
            history,
            parent_id=current["id"],
            current_year=int(current["year"]),
            current_age=int(current["age"]),
        )
        new_state["stage"] = "branches"
        new_state["panel"] = "main"
        new_state["error"] = ""
    except Exception as exc:
        new_state["error"] = str(exc)
    return _refresh_derived(new_state)


async def generate_branches_for_node(state: dict[str, Any], node_id: str, *, panel: str = "tree") -> dict[str, Any]:
    new_state = copy.deepcopy(state)
    try:
        target = next((node for node in new_state.get("nodes", []) if node["id"] == node_id), None)
        if not target:
            raise ValueError("指定されたノードが見つかりません。")
        path = _mark_selected_path(new_state["nodes"], node_id)
        _mark_visited_path(new_state["nodes"], node_id)
        history = [node["event"] for node in path]
        new_state["branches"] = await _generate_branches(
            new_state,
            new_state["profile"],
            target["event"],
            history,
            parent_id=target["id"],
            current_year=int(target["year"]),
            current_age=int(target["age"]),
        )
        new_state["current_node_id"] = target["id"]
        new_state["stage"] = "branches"
        new_state["panel"] = panel
        new_state["error"] = ""
    except Exception as exc:
        new_state["error"] = str(exc)
    return _refresh_derived(new_state)


async def activate_existing_node(state: dict[str, Any], node_id: str, *, panel: str = "tree") -> dict[str, Any]:
    new_state = copy.deepcopy(state)
    try:
        target = next((node for node in new_state.get("nodes", []) if node["id"] == node_id), None)
        if not target:
            raise ValueError("指定されたノードが見つかりません。")

        path = _mark_selected_path(new_state["nodes"], node_id)
        _mark_visited_path(new_state["nodes"], node_id)
        if not target.get("result") and target.get("parent_id") is not None:
            history = [node["event"] for node in path[:-1]]
            await _resolve_node_result(new_state, target, history)

        new_state["branches"] = []
        new_state["current_node_id"] = node_id
        new_state["stage"] = "result"
        new_state["panel"] = panel
        new_state["error"] = ""
    except Exception as exc:
        new_state["error"] = str(exc)
    return _refresh_derived(new_state)


async def generate_story(state: dict[str, Any]) -> dict[str, Any]:
    new_state = copy.deepcopy(state)
    try:
        if not new_state.get("profile"):
            new_state["panel"] = "story"
            new_state["story"] = ""
            new_state["error"] = ""
            return _refresh_derived(new_state)

        selected_nodes = [node for node in new_state["nodes"] if node.get("selected")]
        if not selected_nodes:
            new_state["panel"] = "story"
            new_state["story"] = ""
            new_state["error"] = ""
            return _refresh_derived(new_state)

        system, message = build_story_prompt(new_state["profile"], selected_nodes)
        text = await asyncio.to_thread(call_llm, new_state.get("provider", "openai"), system, message, True)
        parsed = parse_json_text(text)
        new_state["story"] = parsed.get("story_summary", "")
        new_state["panel"] = "story"
        new_state["error"] = ""
    except Exception as exc:
        new_state["error"] = str(exc)
    return _refresh_derived(new_state)


async def jump_to_node(state: dict[str, Any], node_id: str) -> dict[str, Any]:
    new_state = copy.deepcopy(state)
    try:
        target = next((node for node in new_state.get("nodes", []) if node["id"] == node_id), None)
        if not target:
            raise ValueError("指定されたノードが見つかりません。")
        _mark_selected_path(new_state["nodes"], node_id)
        _mark_visited_path(new_state["nodes"], node_id)
        new_state["current_node_id"] = node_id
        new_state["stage"] = "result"
        new_state["panel"] = "main"
        new_state["error"] = ""
    except Exception as exc:
        new_state["error"] = str(exc)
    return _refresh_derived(new_state)
