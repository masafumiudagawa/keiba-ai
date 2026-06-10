"""レースシミュレーション API"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter
from pydantic import BaseModel
import pandas as pd

from backend.core.simulator import simulate_race

router = APIRouter()

RACES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "races")


class SimulationRequest(BaseModel):
    num_simulations: int = 500
    track_condition: str = "good"
    race_id: str = "takarazuka_2026"


@router.post("/simulate")
def run_simulation(req: SimulationRequest):
    # AI予測スコアを含む特徴量データを取得
    from backend.api.races import get_features
    try:
        data = get_features(req.race_id)
        features = data.get("features", [])
        if features:
            # スコアと脚質情報をシミュレーターに渡す
            horses = []
            for f in features:
                horse = {
                    "horse_name": f["horse_name"],
                    "gate_number": f.get("gate_number", 0),
                    "scores": f["scores"],
                    "running_style": f.get("running_style_label", "先行"),
                }
                # 脚質ラベル→コードの逆変換
                style_map = {"逃げ": "nige", "先行": "senko", "差し": "sashi", "追込": "oikomi"}
                horse["running_style"] = style_map.get(horse["running_style"], "senko")
                horses.append(horse)
        else:
            return {"error": "No entries found"}
    except Exception:
        # フォールバック: entries.csvから読み込み
        race_dir = os.path.join(RACES_DIR, req.race_id)
        entries_path = os.path.join(race_dir, "entries.csv")
        if os.path.exists(entries_path):
            df = pd.read_csv(entries_path, encoding="utf-8-sig")
            df = df.dropna(subset=["horse_name"])
            horses = df.to_dict("records")
        else:
            return {"error": "No entries found"}

    result = simulate_race(
        horses=horses,
        n_simulations=req.num_simulations,
        track_condition=req.track_condition,
    )
    return result
