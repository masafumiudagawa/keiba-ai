"""買い目最適化 API"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter
from pydantic import BaseModel
from backend.api.predictions import _build_predictions
from backend.core.optimizer import optimize_bets

router = APIRouter()


class BettingRequest(BaseModel):
    budget: int = 10000
    risk_level: str = "medium"
    bet_types: list[str] = ["win", "quinella", "wide", "trio"]
    odds: dict = {}
    excluded_horses: list[str] = []


@router.post("/betting/optimize")
def optimize(req: BettingRequest):
    predictions, _ = _build_predictions()
    result = optimize_bets(
        predictions=predictions,
        budget=req.budget,
        risk_level=req.risk_level,
        bet_types=req.bet_types,
        odds=req.odds if req.odds else None,
        excluded_horses=req.excluded_horses,
    )
    return result
