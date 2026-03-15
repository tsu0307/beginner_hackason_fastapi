from __future__ import annotations

from pathlib import Path
import uuid
from typing import Any

from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..services.simulator import build_tree_view_model, initial_state


BASE_DIR = Path(__file__).resolve().parents[1]
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
SESSION_COOKIE_NAME = "life_branches_session_id"
SESSION_STORE: dict[str, dict[str, Any]] = {}

PROVIDER_OPTIONS = [
    {"value": "openai", "label": "OpenAI"},
    {"value": "gemini", "label": "Gemini"},
]

INTEREST_OPTIONS = [
    "お金",
    "ものづくり",
    "ファッション",
    "音楽",
    "スポーツ",
    "読書",
    "社会課題",
    "自然・アウトドア",
    "科学",
    "料理",
    "旅行",
    "AI",
    "デザイン",
    "美容",
    "語学",
    "歴史",
    "リーダーシップ",
    "教育",
    "福祉",
    "心理学",
    "地域活動",
    "ゲーム",
    "プログラミング",
    "データ分析",
]

PERSONALITY_OPTIONS = [
    "好奇心が強い",
    "面倒見が良い",
    "慎重",
    "社交的",
    "行動力がある",
    "柔軟性がある",
    "挑戦的",
    "協調的",
    "論理的",
    "感情豊か",
    "責任感が強い",
    "負けず嫌い",
    "想像力が豊か",
    "自立心がある",
    "聞き上手",
    "共感力がある",
    "芯が強い",
    "素直",
    "集中力が高い",
    "計画性がある",
    "努力家",
    "前向き",
    "マイペース",
    "楽観的",
]


def ensure_session_id(request: Request) -> str:
    return request.cookies.get(SESSION_COOKIE_NAME) or uuid.uuid4().hex


def current_state(request: Request) -> tuple[str, dict[str, Any]]:
    session_id = ensure_session_id(request)
    state = SESSION_STORE.get(session_id)
    if not state:
        state = initial_state()
        SESSION_STORE[session_id] = state
    return session_id, state


def save_state(session_id: str, state: dict[str, Any]) -> None:
    SESSION_STORE[session_id] = state


def build_context(request: Request, state: dict[str, Any]) -> dict[str, Any]:
    pending_nodes = [{**branch, "is_branch_candidate": True} for branch in state.get("branches", [])]
    tree_nodes = [*state.get("nodes", []), *pending_nodes]
    return {
        "request": request,
        "state": state,
        "stage": state.get("stage", "setup"),
        "panel": state.get("panel", "main"),
        "error": state.get("error", ""),
        "profile": state.get("profile"),
        "branches": state.get("branches", []),
        "current_node": state.get("current_node"),
        "selected_nodes": state.get("selected_nodes", []),
        "tree_nodes": tree_nodes,
        "tree_view": build_tree_view_model(tree_nodes, current_node_id=state.get("current_node_id")),
        "story": state.get("story", ""),
        "provider_options": PROVIDER_OPTIONS,
        "interest_options": INTEREST_OPTIONS,
        "personality_options": PERSONALITY_OPTIONS,
    }


def attach_session_cookie(response: HTMLResponse, session_id: str) -> HTMLResponse:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        httponly=True,
        samesite="lax",
    )
    return response


def render_app(request: Request, session_id: str, state: dict[str, Any], status_code: int = 200) -> HTMLResponse:
    response = templates.TemplateResponse(
        request=request,
        name="partials/app.html",
        context=build_context(request, state),
        status_code=status_code,
    )
    return attach_session_cookie(response, session_id)


def render_index(request: Request, session_id: str, state: dict[str, Any]) -> HTMLResponse:
    response = templates.TemplateResponse(
        request=request,
        name="index.html",
        context=build_context(request, state),
    )
    return attach_session_cookie(response, session_id)
