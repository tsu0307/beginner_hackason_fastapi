from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from .shared import current_state, render_app, save_state


router = APIRouter()


@router.post("/tree", response_class=HTMLResponse)
async def tree_panel(request: Request) -> HTMLResponse:
    session_id, state = current_state(request)
    state["panel"] = "tree"
    save_state(session_id, state)
    return render_app(request, session_id, state)
