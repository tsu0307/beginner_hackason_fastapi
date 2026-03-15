"""役割: シミュレーション本体タブのルートをまとめる。"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from ..services.simulator import (
    add_custom_branch,
    continue_simulation,
    create_profile,
    get_branch_by_id,
    initial_state,
    jump_to_node,
    select_branch,
    start_simulation,
)
from .shared import current_state, ensure_session_id, render_app, render_index, save_state


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    session_id = ensure_session_id(request)
    state = initial_state()
    save_state(session_id, state)
    return render_index(request, session_id, state)


@router.post("/reset", response_class=HTMLResponse)
async def reset(request: Request) -> HTMLResponse:
    session_id = ensure_session_id(request)
    state = initial_state()
    save_state(session_id, state)
    return render_app(request, session_id, state)


@router.post("/setup", response_class=HTMLResponse)
async def setup(
    request: Request,
    name: str = Form(...),
    birth_year: int = Form(...),
    interests: list[str] = Form([]),
    personality: list[str] = Form([]),
    provider: str = Form("openai"),
) -> HTMLResponse:
    session_id, state = current_state(request)
    state.update(create_profile(name, birth_year, interests, personality))
    state["provider"] = provider if provider in {"openai", "gemini"} else "openai"
    if state.get("profile"):
        state["profile"]["provider"] = state["provider"]
    save_state(session_id, state)
    return render_app(request, session_id, state)


@router.post("/event", response_class=HTMLResponse)
async def submit_event(
    request: Request,
    event: str = Form(...),
    event_year: int = Form(...),
    event_age: int = Form(...),
) -> HTMLResponse:
    session_id, state = current_state(request)
    state = await start_simulation(state, event, event_year, event_age)
    save_state(session_id, state)
    return render_app(request, session_id, state)


@router.post("/branch/select", response_class=HTMLResponse)
async def choose_branch(request: Request, branch_id: str = Form(...)) -> HTMLResponse:
    session_id, state = current_state(request)
    branch = get_branch_by_id(state, branch_id)
    state = await select_branch(state, branch)
    save_state(session_id, state)
    return render_app(request, session_id, state)


@router.post("/branch/custom", response_class=HTMLResponse)
async def custom_branch(request: Request, event: str = Form(...)) -> HTMLResponse:
    session_id, state = current_state(request)
    state = add_custom_branch(state, event)
    save_state(session_id, state)
    return render_app(request, session_id, state)


@router.post("/continue", response_class=HTMLResponse)
async def continue_route(request: Request) -> HTMLResponse:
    session_id, state = current_state(request)
    state = await continue_simulation(state)
    save_state(session_id, state)
    return render_app(request, session_id, state)


@router.post("/main", response_class=HTMLResponse)
async def main_panel(request: Request) -> HTMLResponse:
    session_id, state = current_state(request)
    state["panel"] = "main"
    save_state(session_id, state)
    return render_app(request, session_id, state)


@router.post("/tree/jump", response_class=HTMLResponse)
async def jump_to_tree_node(request: Request, node_id: str = Form(...)) -> HTMLResponse:
    session_id, state = current_state(request)
    state = await jump_to_node(state, node_id)
    save_state(session_id, state)
    return render_app(request, session_id, state)
