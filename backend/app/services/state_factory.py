"""役割: シミュレーション初期状態とプロフィール生成を担当する。"""

from __future__ import annotations

from datetime import datetime
from typing import Any


def initial_state() -> dict[str, Any]:
    return {
        "stage": "setup",
        "panel": "main",
        "error": "",
        "provider": "openai",
        "profile": None,
        "nodes": [],
        "branches": [],
        "current_node_id": None,
        "current_node": None,
        "selected_nodes": [],
        "story": "",
    }


def create_profile(name: str, birth_year: int, interests: list[str], personality: list[str]) -> dict[str, Any]:
    current_year = datetime.now().year
    age = current_year - birth_year
    if not name.strip():
        raise ValueError("名前を入力してください。")
    if age <= 0 or age >= 100:
        raise ValueError("生年の入力値が不正です。")

    joined_interests = "、".join(item.strip() for item in interests if item.strip())
    joined_personality = "、".join(item.strip() for item in personality if item.strip())

    return {
        "stage": "event",
        "panel": "tree",
        "error": "",
        "provider": "openai",
        "profile": {
            "name": name.strip(),
            "birth_year": birth_year,
            "current_age": age,
            "values": joined_interests,
            "interests": joined_interests,
            "personality": joined_personality,
        },
        "nodes": [],
        "branches": [],
        "current_node_id": None,
        "current_node": None,
        "selected_nodes": [],
        "story": "",
    }
