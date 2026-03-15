"""役割: 分割済み services の互換エントリポイント。"""

"""サービス公開 API の再エクスポート。

routes 層から必要になる関数を 1 か所に集め、import 先を単純化するための
窓口モジュール。実際の処理は simulation_flow.py、state_factory.py、
tree_view.py に委譲し、このファイルでは公開対象をまとめている。
"""

from .simulation_flow import (
    add_custom_branch,
    continue_simulation,
    generate_story,
    get_branch_by_id,
    select_branch,
    start_simulation,
)
from .state_factory import create_profile, initial_state
from .tree_view import build_tree_view_model


__all__ = [
    "add_custom_branch",
    "build_tree_view_model",
    "continue_simulation",
    "create_profile",
    "generate_story",
    "get_branch_by_id",
    "initial_state",
    "select_branch",
    "start_simulation",
]
