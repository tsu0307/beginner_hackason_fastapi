from __future__ import annotations

import asyncio
import copy
import re
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from .branch_schemas import BranchCandidate, BranchResponse
from .llm_gateway import call_llm
from .openai_service import parse_json_text
from .prompt_builder import (
    build_branch_prompt,
    build_custom_branch_prompt,
    build_jump_prompt,
    build_result_prompt,
    build_story_prompt,
)


Level = Literal["high", "medium", "low"]
MAX_LIFESPAN_AGE = 100
RETIREMENT_BRANCH_AGE = 65
DEATH_BRANCH_AGE = 85


class JumpFutureNode(BaseModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    history_digest: str = Field(min_length=1)


class JumpChoice(BaseModel):
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    stability: Level
    challenge: Level
    happiness: int = Field(ge=0, le=100)

    @field_validator("stability", "challenge", mode="before")
    @classmethod
    def normalize_level(cls, value: str) -> str:
        mapping = {
            "high": "high",
            "medium": "medium",
            "low": "low",
            "高": "high",
            "中": "medium",
            "低": "low",
        }
        if not isinstance(value, str):
            return value
        return mapping.get(value.strip().lower(), mapping.get(value.strip(), value))


class JumpResponse(BaseModel):
    jump_years: int = Field(ge=1)
    future_age: int = Field(ge=1)
    future_year: int = Field(ge=1)
    future_node: JumpFutureNode
    choices: list[JumpChoice] = Field(min_length=2, max_length=2)


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
    mapping = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "高": "high",
        "中": "medium",
        "低": "low",
    }
    normalized = value.strip().lower()
    if normalized in mapping:
        return mapping[normalized]
    if "高" in value:
        return "high"
    if "中" in value:
        return "medium"
    if "低" in value:
        return "low"
    return "medium"


def _score_to_happiness(score: int) -> str:
    if score >= 70:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _sanitize_jump_title(title: Any) -> str:
    if not isinstance(title, str):
        return ""
    text = title.strip()
    patterns = [
        r"^\d{1,3}歳[、,\s]*",
        r"^\d{1,3}代(?:前半|後半)?(?:の)?",
        r"^\d{1,2}0代(?:前半|後半)?(?:の)?",
        r"^\d{4}年[、,\s]*",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text)
    return text.strip(" 、,") or title.strip()


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


def _history_for_path(path: list[dict[str, Any]]) -> list[str]:
    history: list[str] = []
    for node in path:
        if node.get("history_digest"):
            history.append(f"{node['event']}: {node['history_digest']}")
        elif node.get("result"):
            history.append(f"{node['event']}: {node['result']}")
        else:
            history.append(str(node["event"]))
    return history


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


def _build_death_branch(*, parent_id: str | None, current_year: int, current_age: int) -> dict[str, Any]:
    years_until_death = max(0, MAX_LIFESPAN_AGE - current_age)
    return {
        "id": _new_id(),
        "event": "人生の最期を迎える",
        "stability": "low",
        "challenge": "low",
        "event_type": "progression_event" if years_until_death > 0 else "instant_event",
        "duration_years": years_until_death,
        "year": current_year + years_until_death,
        "age": current_age + years_until_death,
        "parent_id": parent_id,
        "selected": False,
        "visited": False,
    }


def _has_retirement_branch(branches: list[dict[str, Any]]) -> bool:
    keywords = ("定年", "退職", "引退", "セカンドキャリア", "仕事を終える")
    return any(any(keyword in str(branch.get("event", "")) for keyword in keywords) for branch in branches)


def _is_retired_context(event: Any, history: list[str]) -> bool:
    keywords = ("定年", "退職", "引退", "セカンドキャリア", "仕事を終える")
    text = " ".join([str(event), *history])
    return any(keyword in text for keyword in keywords)


def _build_retirement_branch(*, parent_id: str | None, current_year: int, current_age: int) -> dict[str, Any]:
    return {
        "id": _new_id(),
        "event": "定年退職して今後の生活の軸を見直す",
        "stability": "medium",
        "challenge": "low",
        "event_type": "progression_event",
        "duration_years": 1,
        "year": current_year + 1,
        "age": current_age + 1,
        "parent_id": parent_id,
        "selected": False,
        "visited": False,
    }


def _build_death_node(*, parent_id: str | None, current_year: int, current_age: int) -> dict[str, Any]:
    years_until_death = max(0, MAX_LIFESPAN_AGE - current_age)
    return {
        "id": _new_id(),
        "event": "人生の最期を迎える",
        "stability": "low",
        "challenge": "low",
        "event_type": "progression_event" if years_until_death > 0 else "instant_event",
        "duration_years": years_until_death,
        "year": current_year + years_until_death,
        "age": current_age + years_until_death,
        "parent_id": parent_id,
        "selected": True,
        "visited": True,
        "result": "高齢となり、人生の最期を迎える時期に至りました。ここでシミュレーションは終点になります。",
        "history_digest": "人生の終点に到達した。",
        "happiness": "low",
        "is_terminal": True,
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


def _parse_jump_response(payload: Any) -> JumpResponse:
    try:
        return JumpResponse.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"未来ジャンプJSONの形式が不正です: {exc}") from exc


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
    if current_age >= DEATH_BRANCH_AGE:
        return [
            _build_death_branch(
                parent_id=parent_id,
                current_year=current_year,
                current_age=current_age,
            )
        ]
    if current_age >= RETIREMENT_BRANCH_AGE and not _is_retired_context(event, history):
        return [
            _build_retirement_branch(
                parent_id=parent_id,
                current_year=current_year,
                current_age=current_age,
            )
        ]

    runtime_profile = {
        **profile,
        "current_age": current_age,
        "current_year": current_year,
    }
    system, message = build_branch_prompt(runtime_profile, event, history)
    text = await asyncio.to_thread(call_llm, profile.get("provider", "openai"), system, message, True)
    parsed = parse_json_text(text)
    candidates = _parse_branch_response(parsed)
    branches = [
        _build_node_from_branch(
            candidate,
            parent_id=parent_id,
            current_year=current_year,
            current_age=current_age,
        )
        for candidate in candidates[:2]
    ]
    if current_age >= RETIREMENT_BRANCH_AGE and not _is_retired_context(event, history) and not _has_retirement_branch(branches):
        retirement_branch = _build_retirement_branch(
            parent_id=parent_id,
            current_year=current_year,
            current_age=current_age,
        )
        if branches:
            branches[-1] = retirement_branch
        else:
            branches.append(retirement_branch)
    return branches


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


async def _generate_jump(
    state: dict[str, Any],
    node: dict[str, Any],
    history: list[str],
    jump_years: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    profile = {
        **state["profile"],
        "current_age": int(node["age"]),
        "current_year": int(node["year"]),
    }
    system, message = build_jump_prompt(profile, node, history, jump_years)
    text = await asyncio.to_thread(call_llm, state.get("provider", "openai"), system, message, True)
    parsed = parse_json_text(text)
    jump = _parse_jump_response(parsed)
    future_year = int(node["year"]) + jump_years
    future_age = int(node["age"]) + jump_years

    if future_age >= MAX_LIFESPAN_AGE:
        death_node = _build_death_node(
            parent_id=node["id"],
            current_year=int(node["year"]),
            current_age=int(node["age"]),
        )
        last_jump = {
            "current_node_id": node["id"],
            "jump_years": jump_years,
            "summary": death_node["result"],
            "history_digest": death_node["history_digest"],
            "future_age": death_node["age"],
            "future_year": death_node["year"],
            "choices": [],
        }
        return death_node, [], last_jump

    jump_node = {
        "id": _new_id(),
        "event": _sanitize_jump_title(jump.future_node.title),
        "stability": "medium",
        "challenge": "medium",
        "event_type": "progression_event",
        "duration_years": jump_years,
        "year": future_year,
        "age": future_age,
        "parent_id": node["id"],
        "selected": True,
        "visited": True,
        "result": jump.future_node.summary,
        "history_digest": jump.future_node.history_digest,
        "is_jump_node": True,
        "jump_years": jump_years,
    }

    choices: list[dict[str, Any]] = []
    for choice in jump.choices:
        choices.append(
            {
                "id": _new_id(),
                "event": _sanitize_jump_title(choice.title),
                "stability": choice.stability,
                "challenge": choice.challenge,
                "event_type": "instant_event",
                "duration_years": 0,
                "year": future_year,
                "age": future_age,
                "parent_id": jump_node["id"],
                "selected": False,
                "visited": False,
                "result_preview": choice.summary,
                "jump_happiness_score": choice.happiness,
                "history_digest": jump.future_node.history_digest,
                "is_jump_choice": True,
            }
        )

    last_jump = {
        "current_node_id": node["id"],
        "jump_years": jump_years,
        "summary": jump.future_node.summary,
        "history_digest": jump.future_node.history_digest,
        "future_age": future_age,
        "future_year": future_year,
        "choices": [choice["event"] for choice in choices],
    }
    return jump_node, choices, last_jump


async def _resolve_node_result(
    state: dict[str, Any],
    node: dict[str, Any],
    history: list[str],
) -> dict[str, Any]:
    runtime_profile = {
        **state["profile"],
        "current_age": int(node["age"]),
        "current_year": int(node["year"]),
    }
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
        new_state["last_jump"] = None
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
        history = _history_for_path(path)
        if branch.get("result_preview"):
            selected_branch = {
                **branch,
                "selected": True,
                "result": branch["result_preview"],
                "happiness": _score_to_happiness(int(branch.get("jump_happiness_score", 50))),
            }
        else:
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
        history = _history_for_path(path)

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
        history = _history_for_path(path)
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
        history = _history_for_path(path)
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


async def generate_jump_branches(
    state: dict[str, Any],
    node_id: str,
    jump_years: int,
    *,
    panel: str = "tree",
) -> dict[str, Any]:
    new_state = copy.deepcopy(state)
    try:
        if jump_years not in {10, 20, 30}:
            raise ValueError("ジャンプ年数は 10, 20, 30 のいずれかにしてください。")
        target = next((node for node in new_state.get("nodes", []) if node["id"] == node_id), None)
        if not target:
            raise ValueError("指定されたノードが見つかりません。")

        path = _mark_selected_path(new_state["nodes"], node_id)
        _mark_visited_path(new_state["nodes"], node_id)
        history = _history_for_path(path)

        jump_node, choices, last_jump = await _generate_jump(new_state, target, history, jump_years)
        new_state["nodes"].append(jump_node)
        new_state["branches"] = choices
        new_state["current_node_id"] = jump_node["id"]
        _mark_selected_path(new_state["nodes"], jump_node["id"])
        _mark_visited_path(new_state["nodes"], jump_node["id"])
        new_state["stage"] = "branches" if choices else "result"
        new_state["panel"] = panel
        new_state["last_jump"] = last_jump
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
            history = _history_for_path(path[:-1])
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
