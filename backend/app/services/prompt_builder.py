from __future__ import annotations

from pathlib import Path


LVL_LABEL = {"high": "高", "medium": "中", "low": "低"}
REPO_ROOT = Path(__file__).resolve().parents[3]

BRANCH_OUTPUT_RULES = """
Return JSON only.
Use this schema:
{
  "branches": [
    {
      "event": "string",
      "stability": "high|medium|low",
      "challenge": "high|medium|low",
      "event_type": "instant_event|progression_event",
      "duration_years": 0
    }
  ]
}
Rules:
- instant_event must use duration_years = 0
- progression_event must use duration_years >= 1
- Do not include year or age in the output
- Each event must describe a concrete action or situation, not an abstract attitude
- Prefer event phrases with a clear object, place, or activity
- Avoid vague labels such as "安定志向になる", "頑張る", "挑戦する", "成長する"
- Good examples: "地元の福祉施設でアルバイトを始める", "高校の吹奏楽部で部長を引き受ける"
- Keep each event concise, but specific enough to imagine what actually happens
""".strip()

CUSTOM_BRANCH_OUTPUT_RULES = """
Return JSON only.
Use this schema:
{
  "event": "string",
  "stability": "high|medium|low",
  "challenge": "high|medium|low",
  "event_type": "instant_event|progression_event",
  "duration_years": 0
}
Rules:
- Keep the event meaning aligned with the user's input
- You may lightly rewrite the event to make it more natural and specific
- instant_event must use duration_years = 0
- progression_event must use duration_years >= 1
- Do not include year or age in the output
""".strip()

RESULT_OUTPUT_RULES = """
Return JSON only.
Use this schema:
{
  "result_summary": "string",
  "happiness": "high|medium|low"
}
Rules:
- Choose exactly one of high, medium, low
- Do not output Japanese labels for happiness
- Do not default to medium unless both positive and negative factors are genuinely balanced
- Use high when the outcome is clearly favorable overall
- Use low when the outcome is clearly unfavorable overall
- Use medium only for mixed or ambiguous outcomes
- result_summary must explain the main reason for the happiness level
""".strip()

JUMP_OUTPUT_RULES = """
Return JSON only.
Use this schema:
{
  "jump_years": 10,
  "future_age": 32,
  "future_year": 2036,
  "future_node": {
    "title": "string",
    "summary": "string",
    "history_digest": "string"
  },
  "choices": [
    {
      "title": "string",
      "summary": "string",
      "stability": "high|medium|low",
      "challenge": "high|medium|low",
      "happiness": 72
    }
  ]
}
Rules:
- choices must contain exactly 2 items
- future_age must equal current_age + jump_years
- future_year must equal current_year + jump_years
- happiness must be an integer from 0 to 100
- Do not include explicit ages, decades, or years in future_node.title or choices.title
- Each choice must be a concrete continuation from the generated future node
- The two choices must have clearly different directions
""".strip()

BRANCH_PROMPT_FILES = {
    "short": "bunki_prompt_short.txt",
    "normal": "bunki_prompt.txt",
    "long": "bunki_prompt_long.txt",
}


def _load_prompt_file(filename: str) -> str:
    path = REPO_ROOT / filename
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RuntimeError(f"{filename} が見つかりません。") from exc


def _fill_prompt(template: str, values: dict[str, str]) -> str:
    text = template
    for key, value in values.items():
        text = text.replace(f"{{{key}}}", value)
    return text


def build_branch_prompt(profile: dict[str, str], event: str, history: list[str]) -> tuple[str, str]:
    system = "人生分岐シミュレーションの分岐候補を JSON だけで生成してください。"
    story_summary = " -> ".join(history) if history else "まだ履歴はありません。"
    prompt_filename = BRANCH_PROMPT_FILES.get(profile.get("branch_timing", "normal"), "bunki_prompt.txt")
    message = _fill_prompt(
        _load_prompt_file(prompt_filename),
        {
            "age": str(profile["current_age"]),
            "current_year": str(profile.get("current_year", "")),
            "current_age": str(profile["current_age"]),
            "values": profile.get("values", ""),
            "interests": profile.get("interests", profile.get("values", "")),
            "personality": profile.get("personality", ""),
            "mbti": profile.get("mbti", ""),
            "current_event": event,
            "story_summary": story_summary,
        },
    )
    return system, f"{message}\n\n{BRANCH_OUTPUT_RULES}"


def build_result_prompt(profile: dict[str, str], event: str, history: list[str]) -> tuple[str, str]:
    system = "人生分岐シミュレーションの結果を JSON だけで生成してください。"
    story_summary = " -> ".join(history[-4:]) if history else "まだストーリー履歴はありません。"
    message = _fill_prompt(
        _load_prompt_file("out_prompt.txt"),
        {
            "age": str(profile["current_age"]),
            "values": profile.get("values", ""),
            "interests": profile.get("interests", profile.get("values", "")),
            "personality": profile.get("personality", ""),
            "mbti": profile.get("mbti", ""),
            "story_summary": story_summary,
            "selected_branch": event,
        },
    )
    return system, f"{message}\n\n{RESULT_OUTPUT_RULES}"


def build_custom_branch_prompt(profile: dict[str, str], event: str, history: list[str]) -> tuple[str, str]:
    system = "人生分岐シミュレーションの手動追加イベントを JSON だけで評価してください。"
    story_summary = " -> ".join(history[-4:]) if history else "まだ履歴はありません。"
    message = "\n".join(
        [
            "次の手動入力イベントについて、安定度・挑戦度・イベント種別・継続年数を判定してください。",
            f"- 現在年齢: {profile['current_age']}",
            f"- 現在年: {profile.get('current_year', '')}",
            f"- MBTI: {profile.get('mbti', '')}",
            f"- 興味関心: {profile.get('interests', profile.get('values', ''))}",
            f"- 性格傾向: {profile.get('personality', '')}",
            f"- 直前までの履歴: {story_summary}",
            f"- 手動入力イベント: {event}",
        ]
    )
    return system, f"{message}\n\n{CUSTOM_BRANCH_OUTPUT_RULES}"


def build_jump_prompt(
    profile: dict[str, str],
    current_node: dict[str, str],
    history: list[str],
    jump_years: int,
) -> tuple[str, str]:
    system = "人生分岐シミュレーションの未来ジャンプ候補を JSON だけで生成してください。"
    message = _fill_prompt(
        _load_prompt_file("jump_promp.txt"),
        {
            "jump_years": str(jump_years),
            "current_year": str(current_node["year"]),
            "current_age": str(current_node["age"]),
            "current_event": current_node["event"],
            "mbti": profile.get("mbti", ""),
            "interests": profile.get("interests", profile.get("values", "")),
            "personality": profile.get("personality", ""),
            "story_summary": " -> ".join(history) if history else "まだ履歴はありません。",
        },
    )
    return system, f"{message}\n\n{JUMP_OUTPUT_RULES}"


def build_story_prompt(profile: dict[str, str], nodes: list[dict[str, str]]) -> tuple[str, str]:
    system = "人生分岐シミュレーションの要約を JSON だけで生成してください。"
    start_age = str(nodes[0].get("age", profile["current_age"])) if nodes else str(profile["current_age"])
    route_history = " -> ".join(node["event"] for node in nodes)
    result_history = "\n".join(
        f"- {node['event']}: {node.get('result', '結果なし')} / 幸福度: {LVL_LABEL.get(node.get('happiness', 'medium'), '中')}"
        for node in nodes
    )
    message = _fill_prompt(
        _load_prompt_file("sum_prompt.txt"),
        {
            "age": start_age,
            "values": profile.get("values", ""),
            "interests": profile.get("interests", profile.get("values", "")),
            "personality": profile.get("personality", ""),
            "mbti": profile.get("mbti", ""),
            "route_history": route_history,
            "result_history": result_history,
        },
    )
    return system, message
