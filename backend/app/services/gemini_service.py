"""Gemini API 呼び出しをまとめる。"""

from __future__ import annotations

import os

import google.generativeai as genai


def call_gemini(
    system: str,
    user_message: str,
    model: str | None = None,
    json_mode: bool = True,
) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY が設定されていません。")

    selected_model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
    print(f"DEBUG: Using Gemini model: {selected_model}")
    genai.configure(api_key=api_key)

    generation_config: dict[str, object] = {
        "temperature": 0.7,
        "max_output_tokens": 1200,
    }
    if json_mode:
        generation_config["response_mime_type"] = "application/json"

    prompt = f"{system}\n\n{user_message}"
    if json_mode and "json" not in prompt.lower():
        prompt = f"{prompt}\n\nReturn valid JSON only."

    try:
        model_instance = genai.GenerativeModel(
            model_name=selected_model,
            generation_config=generation_config,
            system_instruction=system,
        )
        response = model_instance.generate_content(user_message)
    except Exception as exc:
        raise RuntimeError(f"Gemini API エラー: {exc}") from exc

    text = getattr(response, "text", "") or ""
    if text.strip():
        return text.strip()

    raise RuntimeError("Gemini API の応答本文を取得できませんでした。")
