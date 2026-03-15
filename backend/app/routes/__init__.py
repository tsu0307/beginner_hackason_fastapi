"""役割: 分割した各ルーターをまとめて FastAPI に公開する。"""

"""ルーター統合モジュール。

シミュレーション本体、ツリー表示、ストーリー要約の各ルーターを 1 つの
APIRouter にまとめ、main.py からまとめて登録できるようにする。
URL パスの追加先をここで一元化することで、画面遷移に必要な HTTP エンドポイントを
整理して扱えるようにしている。
"""

from fastapi import APIRouter

from .simulation import router as simulation_router
from .story import router as story_router
from .tree import router as tree_router


router = APIRouter()
router.include_router(simulation_router)
router.include_router(tree_router)
router.include_router(story_router)
