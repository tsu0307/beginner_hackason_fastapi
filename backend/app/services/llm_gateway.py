import os
import json
from .gemini_service import call_gemini
from .openai_service import call_openai


def call_llm(provider: str, system: str, user_message: str, json_mode: bool = True) -> str:
    # モックモードのチェック
    if os.getenv("MOCK_MODE", "false").lower() == "true":
        prompt_lower = user_message.lower() + system.lower()
        
        # 分岐生成のモック
        if "branch" in prompt_lower or "分岐" in prompt_lower:
            return json.dumps({
                "branches": [
                    {"event": "【MOCK】安定した道を選ぶ", "stability": "高", "challenge": "低"},
                    {"event": "【MOCK】未知の可能性に賭ける", "stability": "低", "challenge": "高"}
                ]
            }, ensure_ascii=False)
        
        # 結果生成のモック
        if "result" in prompt_lower or "結果" in prompt_lower:
            return json.dumps({
                "result_summary": "【MOCK】選択の結果、新しい環境にも慣れ、着実に一歩を踏み出しました。周囲からの信頼も得られています。",
                "happiness": "高"
            }, ensure_ascii=False)
        
        # ストーリー生成のモック
        if "story" in prompt_lower or "要約" in prompt_lower or "ストーリー" in prompt_lower:
            return json.dumps({
                "story_summary": "【MOCK】あなたは数々の選択を経て、自分らしい人生を歩んできました。時には迷いもありましたが、最終的には納得のいく結末を迎えました。"
            }, ensure_ascii=False)

        # デフォルトの空JSON
        return "{}"

    if provider == "gemini":
        return call_gemini(system, user_message, None, json_mode)
    return call_openai(system, user_message, None, json_mode)
