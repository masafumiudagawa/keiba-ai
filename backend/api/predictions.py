"""予測結果 API"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter
import pandas as pd
import numpy as np

from config.settings import RAW_DIR, PROCESSED_DIR, REGISTERED_HORSES_2026
from features.feature_engineering import FeatureEngineer
from models.predictor import TakarazukaPredictor

router = APIRouter()


def _get_track_condition() -> str:
    weather_path = os.path.join(RAW_DIR, "weather_forecast.csv")
    if os.path.exists(weather_path):
        wdf = pd.read_csv(weather_path, encoding="utf-8-sig")
        if not wdf.empty:
            return str(wdf.iloc[-1].get("predicted_track_condition", "良"))
    return "良"


def _build_predictions():
    """予測を実行して結果dictリストを返す"""
    entries_path = os.path.join(RAW_DIR, "thursday_entries.csv")
    if os.path.exists(entries_path):
        entries = pd.read_csv(entries_path, encoding="utf-8-sig")
        entries = entries.dropna(subset=["horse_name"])
    else:
        entries = pd.DataFrame(REGISTERED_HORSES_2026)

    condition = _get_track_condition()
    entries["track_condition"] = condition
    entries["field_size"] = len(entries)

    fe = FeatureEngineer()
    fe.load_data()
    feature_matrix = fe.build_feature_matrix(entries)

    predictor = TakarazukaPredictor()
    results = predictor.predict(feature_matrix)

    # スコア内訳を計算
    predictions = []
    marks = {1: "◎", 2: "○", 3: "▲", 4: "△", 5: "△"}

    for _, row in results.iterrows():
        name = row["horse_name"]
        rank = int(row["rank"])
        win_prob = float(row["win_probability"])

        # entriesから追加情報
        entry = entries[entries["horse_name"] == name]
        ei = entry.iloc[0].to_dict() if not entry.empty else {}

        # feature_matrixから因子情報
        fm_row = feature_matrix[feature_matrix["horse_name"] == name]
        factors = {}
        if not fm_row.empty:
            fr = fm_row.iloc[0]
            factors = {
                "recent_form": round(float(fr.get("career_win_rate", 0) or 0) * 100, 1),
                "course_aptitude": round(float(fr.get("win_rate_2000_2400", 0) or 0) * 100, 1),
                "jockey_factor": round(float(fr.get("jockey_win_rate", 0) or 0) * 100, 1),
                "public_opinion": round(float(fr.get("yt_score", 0) or 0) + float(fr.get("news_score", 0) or 0), 1),
                "training": round(float(fr.get("training_intensity", 3) or 3) * 20, 1),
                "g1_wins": int(fr.get("g1_wins", 0) or 0),
            }

        def _safe(v):
            if v is None or (isinstance(v, float) and np.isnan(v)):
                return None
            return v

        predictions.append({
            "rank": rank,
            "horse_name": name,
            "jockey": _safe(ei.get("jockey_name")),
            "gate_number": _safe(ei.get("gate_number")),
            "post_position": _safe(ei.get("post_position")),
            "age": _safe(ei.get("age")),
            "sex": _safe(ei.get("sex")),
            "weight_carried": _safe(ei.get("weight_carried")),
            "sire": _safe(ei.get("sire")),
            "prev_race": _safe(ei.get("prev_race")),
            "prev_finish": _safe(ei.get("prev_finish")),
            "win_probability": round(win_prob, 4),
            "place_probability": round(min(win_prob * 2.5, 0.95), 4),
            "ai_score": round(win_prob * 400, 1),
            "mark": marks.get(rank, ""),
            "factors": factors,
        })

    return predictions, condition


@router.get("/predictions")
def get_predictions():
    predictions, condition = _build_predictions()
    return {
        "race_info": {
            "name": "遠賀川賞",
            "date": "2026-07-11",
            "venue": "佐賀",
            "distance": 1400,
            "surface": "ダート",
            "grade": "A1",
            "post_time": "17:00",
            "track_condition": condition,
            "field_size": len(predictions),
        },
        "predictions": predictions,
    }
