import os
from .gemini_service import call_gemini
from .openai_service import call_openai
from .mock_service import call_mock


def call_llm(provider: str, system: str, user_message: str, json_mode: bool = True) -> str:
    # 環境変数 MOCK_MODE が true の場合は強制的に mock を使用
    if os.getenv("MOCK_MODE", "").lower() == "true":
        return call_mock(system, user_message)

    if provider == "mock":
        return call_mock(system, user_message)
    if provider == "gemini":
        return call_gemini(system, user_message, None, json_mode)
    return call_openai(system, user_message, None, json_mode)
