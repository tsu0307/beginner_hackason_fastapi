"""役割: ツリー画面での分岐生成と選択を扱う。"""

from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse

from ..services.simulator import generate_branches_for_node, get_branch_by_id, select_branch, start_simulation
from .shared import current_state, render_app, save_state


router = APIRouter()


@router.post("/tree", response_class=HTMLResponse)
async def tree_panel(request: Request) -> HTMLResponse:
    session_id, state = current_state(request)
    state["panel"] = "tree"
    save_state(session_id, state)
    return render_app(request, session_id, state)


@router.post("/tree/start", response_class=HTMLResponse)
async def tree_start(
    request: Request,
    event: str = Form(...),
    event_year: int = Form(...),
    event_age: int = Form(...),
) -> HTMLResponse:
    session_id, state = current_state(request)
    state = await start_simulation(state, event, event_year, event_age, panel="tree")
    save_state(session_id, state)
    return render_app(request, session_id, state)


@router.post("/tree/generate", response_class=HTMLResponse)
async def tree_generate(request: Request, node_id: str = Form(...)) -> HTMLResponse:
    session_id, state = current_state(request)
    state = await generate_branches_for_node(state, node_id, panel="tree")
    save_state(session_id, state)
    return render_app(request, session_id, state)


@router.post("/tree/select-branch", response_class=HTMLResponse)
async def tree_select_branch(request: Request, branch_id: str = Form(...)) -> HTMLResponse:
    session_id, state = current_state(request)
    branch = get_branch_by_id(state, branch_id)
    state = await select_branch(state, branch, panel="tree")
    save_state(session_id, state)
    return render_app(request, session_id, state)
