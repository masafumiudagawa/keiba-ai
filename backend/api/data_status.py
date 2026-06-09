"""データ収集状況 API"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter
from config.settings import RAW_DIR

router = APIRouter()

DATA_FILES = {
    "takarazuka_history.csv": "宝塚記念過去データ",
    "hanshin_2200_history.csv": "阪神芝2200m過去データ",
    "thursday_entries.csv": "確定出馬表",
    "youtube_predictions.csv": "YouTube予想",
    "news_predictions.csv": "ニュース予想",
    "odds_history.csv": "オッズデータ",
    "training_data.csv": "調教データ",
    "weather_forecast.csv": "天気予報",
    "manual_horse_history.csv": "各馬戦績",
    "manual_jockey_stats.csv": "騎手成績",
}


@router.get("/status")
def get_status():
    sources = {}
    for filename, label in DATA_FILES.items():
        path = os.path.join(RAW_DIR, filename)
        if os.path.exists(path):
            sources[filename] = {
                "label": label,
                "available": True,
                "size_bytes": os.path.getsize(path),
            }
        else:
            sources[filename] = {"label": label, "available": False, "size_bytes": 0}

    return {"sources": sources}
