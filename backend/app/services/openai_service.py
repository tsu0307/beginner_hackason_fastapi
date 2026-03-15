from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any


OPENAI_API_URL = "https://api.openai.com/v1/responses"


def _clean_json(text: str) -> str:
    return text.replace("```json", "").replace("```", "").strip()


def parse_json_text(text: str) -> Any:
    if not text:
        raise ValueError("AI からの応答が空です。")

    cleaned = _clean_json(text)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            return json.loads(match.group(0))
        raise ValueError("AI の JSON 応答を解釈できませんでした。")


def _extract_output_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    chunks: list[str] = []
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                chunks.append(text)
    return "\n".join(chunks).strip()


def call_openai(
    system: str,
    user_message: str,
    model: str | None = None,
    json_mode: bool = True,
) -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY が設定されていません。")

    selected_model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    effective_user_message = user_message
    if json_mode and "json" not in f"{system}\n{user_message}".lower():
        effective_user_message = f"{user_message}\n\nReturn valid JSON only."

    payload: dict[str, Any] = {
        "model": selected_model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": effective_user_message}],
            },
        ],
    }
    if json_mode:
        payload["text"] = {"format": {"type": "json_object"}}

    request = urllib.request.Request(
        OPENAI_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"OpenAI API エラー: HTTP {exc.code} {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI API へ接続できませんでした: {exc.reason}") from exc

    parsed = json.loads(body)
    text = _extract_output_text(parsed)
    if not text:
        raise RuntimeError("OpenAI API の応答本文を取得できませんでした。")
    return text
