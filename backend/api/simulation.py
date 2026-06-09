"""レースシミュレーション API"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter
from pydantic import BaseModel
import pandas as pd

from config.settings import RAW_DIR, REGISTERED_HORSES_2026
from backend.core.simulator import simulate_race

router = APIRouter()


class SimulationRequest(BaseModel):
    num_simulations: int = 1000
    track_condition: str = "良"
    pace_scenario: str = "auto"


@router.post("/simulate")
def run_simulation(req: SimulationRequest):
    entries_path = os.path.join(RAW_DIR, "thursday_entries.csv")
    if os.path.exists(entries_path):
        df = pd.read_csv(entries_path, encoding="utf-8-sig")
        df = df.dropna(subset=["horse_name"])
        horses = df.to_dict("records")
    else:
        horses = REGISTERED_HORSES_2026

    result = simulate_race(
        horses=horses,
        n_simulations=req.num_simulations,
        track_condition=req.track_condition,
    )
    return result
