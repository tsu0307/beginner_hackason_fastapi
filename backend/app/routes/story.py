from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from ..services.simulator import generate_story
from .shared import current_state, render_app, save_state


router = APIRouter()


@router.post("/story", response_class=HTMLResponse)
async def story_panel(request: Request) -> HTMLResponse:
    session_id, state = current_state(request)
    state = await generate_story(state)
    save_state(session_id, state)
    return render_app(request, session_id, state)
