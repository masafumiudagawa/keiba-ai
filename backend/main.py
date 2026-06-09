"""
KEIBA AI - FastAPI サーバー
"""
import sys
import os

# プロジェクトルートをパスに追加
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.predictions import router as predictions_router
from backend.api.simulation import router as simulation_router
from backend.api.betting import router as betting_router
from backend.api.data_status import router as status_router

app = FastAPI(title="KEIBA AI", version="1.0.0")

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
