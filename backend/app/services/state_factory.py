from __future__ import annotations

from datetime import datetime
from typing import Any


def initial_state() -> dict[str, Any]:
    return {
        "stage": "setup",
        "panel": "main",
        "error": "",
        "provider": "openai",
        "branch_timing": "normal",
        "profile": None,
        "nodes": [],
        "branches": [],
        "current_node_id": None,
        "current_node": None,
        "selected_nodes": [],
        "story": "",
        "last_jump": None,
    }


def create_profile(
    name: str,
    birth_year: int,
    interests: list[str],
    personality: list[str],
    mbti: str,
    branch_timing: str,
) -> dict[str, Any]:
    current_year = datetime.now().year
    age = current_year - birth_year
    if not name.strip():
        raise ValueError("名前を入力してください。")
    if age <= 0 or age >= 100:
        raise ValueError("誕生年の入力値が不正です。")

    joined_interests = " / ".join(item.strip() for item in interests if item.strip())
    joined_personality = " / ".join(item.strip() for item in personality if item.strip())
    cleaned_mbti = mbti.strip().upper()
    selected_timing = branch_timing if branch_timing in {"short", "normal", "long"} else "normal"

    return {
        "stage": "event",
        "panel": "tree",
        "error": "",
        "provider": "openai",
        "branch_timing": selected_timing,
        "profile": {
            "name": name.strip(),
            "birth_year": birth_year,
            "current_age": age,
            "current_year": current_year,
            "values": joined_interests,
            "interests": joined_interests,
            "personality": joined_personality,
            "mbti": cleaned_mbti,
            "branch_timing": selected_timing,
        },
        "nodes": [],
        "branches": [],
        "current_node_id": None,
        "current_node": None,
        "selected_nodes": [],
        "story": "",
        "last_jump": None,
    }
