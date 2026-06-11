"""
KEIBA AI - FastAPI サーバー
"""
import sys
import os
import threading
import time

# プロジェクトルートをパスに追加
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager


def _keep_alive_worker():
    """Renderのスリープ防止: 10分ごとに自分自身にリクエスト"""
    import urllib.request
    url = os.environ.get("RENDER_EXTERNAL_URL", "")
    if not url:
        return  # ローカル環境では動かさない
    health_url = f"{url}/api/health"
    while True:
        time.sleep(600)  # 10分
        try:
            urllib.request.urlopen(health_url, timeout=10)
        except Exception:
            pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup: keep-aliveスレッド起動
    t = threading.Thread(target=_keep_alive_worker, daemon=True)
    t.start()
    yield
    # shutdown

from backend.api.predictions import router as predictions_router
from backend.api.simulation import router as simulation_router
from backend.api.betting import router as betting_router
from backend.api.data_status import router as status_router
from backend.api.races import router as races_router

app = FastAPI(title="KEIBA AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(predictions_router, prefix="/api")
app.include_router(simulation_router, prefix="/api")
app.include_router(betting_router, prefix="/api")
app.include_router(status_router, prefix="/api")
app.include_router(races_router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}


# 本番環境: ビルド済みフロントエンドを配信
FRONTEND_DIR = os.path.join(ROOT, "frontend", "dist")
if os.path.isdir(FRONTEND_DIR):
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        file_path = os.path.join(FRONTEND_DIR, full_path)
        if os.path.isfile(file_path):
            return FileResponse(file_path)
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))
