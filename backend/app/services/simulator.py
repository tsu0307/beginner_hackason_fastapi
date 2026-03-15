"""役割: 分割済み services の互換エントリポイント。"""

from .simulation_flow import (
    add_custom_branch,
    continue_simulation,
    generate_story,
    get_branch_by_id,
    jump_to_node,
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
    "jump_to_node",
    "select_branch",
    "start_simulation",
]
