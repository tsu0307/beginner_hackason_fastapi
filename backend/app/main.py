from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .routes import router


BASE_DIR = Path(__file__).resolve().parent
# プロジェクトルートにある .env.local を読み込む
env_path = BASE_DIR.parents[1] / ".env.local"
load_dotenv(dotenv_path=env_path, override=True)

app = FastAPI(title="Life Branches FastAPI")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.include_router(router)
