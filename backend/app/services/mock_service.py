"""モック用のLLMレスポンスを生成するサービス。"""

import json
import random

def call_mock(system: str, user_message: str) -> str:
    """プロンプトの内容に応じて適当なJSONレスポップスを返す。"""
    
    # 分岐生成のプロンプトかどうかを判定
    if "分岐" in system or "branch" in user_message.lower():
        return json.dumps({
            "branches": [
                {
                    "event": "新しいスキルを習得するためにスクールに通い始める",
                    "stability": "medium",
                    "challenge": "high",
                    "event_type": "progression_event",
                    "duration_years": 2
                },
                {
                    "event": "現在の仕事を続けながら副業を探す",
                    "stability": "high",
                    "challenge": "medium",
                    "event_type": "instant_event",
                    "duration_years": 0
                },
                {
                    "event": "思い切って海外旅行に出かけ、自分を見つめ直す",
                    "stability": "low",
                    "challenge": "low",
                    "event_type": "instant_event",
                    "duration_years": 0
                }
            ]
        }, ensure_ascii=False)

    # 結果生成のプロンプトかどうかを判定
    if "結果" in system or "result" in user_message.lower() or "selected_branch" in user_message:
        return json.dumps({
            "result": "あなたの選択は思わぬ好機をもたらしました。周囲の協力もあり、順調に物事が進んでいます。",
            "happiness": random.choice(["high", "medium", "low"]),
            "reason": "主体的な行動がポジティブな連鎖を生んだため。"
        }, ensure_ascii=False)

    # ストーリー要約のプロンプトかどうかを判定
    if "要約" in system or "summary" in user_message.lower():
        return json.dumps({
            "summary": "あなたは波乱万丈ながらも、自身の信念に従って数々の選択を重ねてきました。その結果、独自の道を切り開き、充実した人生を歩んでいます。",
            "title": "自分だけの航路"
        }, ensure_ascii=False)

    # デフォルトのレスポンス
    return json.dumps({"message": "Mock response"}, ensure_ascii=False)
