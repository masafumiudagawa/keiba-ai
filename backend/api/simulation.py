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
    # race_idからエントリーを読み込む
    race_dir = os.path.join(RACES_DIR, req.race_id)
    entries_path = os.path.join(race_dir, "entries.csv")

    if os.path.exists(entries_path):
        df = pd.read_csv(entries_path, encoding="utf-8-sig")
        df = df.dropna(subset=["horse_name"])
        horses = df.to_dict("records")
    else:
        # フォールバック: 旧パス
        from config.settings import RAW_DIR
        fallback = os.path.join(RAW_DIR, "thursday_entries.csv")
        if os.path.exists(fallback):
            df = pd.read_csv(fallback, encoding="utf-8-sig")
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
