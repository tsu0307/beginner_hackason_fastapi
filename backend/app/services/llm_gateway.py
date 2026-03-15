from __future__ import annotations

from .gemini_service import call_gemini
from .openai_service import call_openai


def call_llm(provider: str, system: str, user_message: str, json_mode: bool = True) -> str:
    if provider == "gemini":
        return call_gemini(system, user_message, None, json_mode)
    return call_openai(system, user_message, None, json_mode)
