"""FastAPI アプリの起動エントリ。

このファイルは Web アプリ全体の初期化を担当する。
リポジトリ直下の `.env.local` を読み込み、OpenAI や Gemini の API キーを
プロセス環境変数へ設定したうえで、FastAPI 本体を生成する。
さらに `/static` に静的ファイル配信をマウントし、routes パッケージで
定義した各画面・各操作用のルーターをアプリへ登録する。
"""

from pathlib import Path
import os

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import router


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parents[1]
ENV_FILE = PROJECT_ROOT / ".env.local"


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


load_env_file(ENV_FILE)

app = FastAPI(title="Life Branches FastAPI")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(router)
