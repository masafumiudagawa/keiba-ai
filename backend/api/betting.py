"""買い目最適化 API（拡張版）"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter
from pydantic import BaseModel
from itertools import combinations, permutations
from backend.api.predictions import _build_predictions
from backend.core.optimizer import optimize_bets

router = APIRouter()


# ── リクエストモデル ──

class OptimizeRequest(BaseModel):
    budget: int = 10000
    risk_level: str = "medium"
    bet_types: list[str] = ["win", "quinella", "wide", "trio"]
    odds: dict = {}
    excluded_horses: list[str] = []
    pivot_horses: list[str] = []
    race_id: str = "takarazuka_2026"


class FormationRequest(BaseModel):
    bet_type: str = "trio"  # trio / trifecta
    first: list[str] = []
    second: list[str] = []
    third: list[str] = []
    amount_per_bet: int = 100


class BoxRequest(BaseModel):
    bet_type: str = "trio"  # quinella / wide / trio
    horses: list[str] = []
    amount_per_bet: int = 100


class SimulateResultRequest(BaseModel):
    bets: list[dict] = []  # [{type, selection, amount, odds}, ...]
    result_first: str = ""
    result_second: str = ""
    result_third: str = ""


# ── AI自動最適化 ──

def _add_payout(result: dict) -> dict:
    """各買い目に的中時払い戻し額を追加"""
    for r in result.get("recommendations", []):
        r["payout"] = int(r.get("amount", 0) * r.get("odds", 0))
    return result


def _get_predictions(race_id: str):
    """raceIdから予測データを取得"""
    try:
        from backend.api.races import get_features
        data = get_features(race_id)
        preds = []
        features = data.get("features", [])
        # スコア合計から確率を算出
        totals = [sum(h["scores"].values()) for h in features]
        min_t = min(totals) if totals else 0
        max_t = max(totals) if totals else 1
        rng = max_t - min_t or 1
        prob_sum = sum((t - min_t) / rng for t in totals) or 1
        for h, t in zip(features, totals):
            prob = ((t - min_t) / rng) / prob_sum
            preds.append({
                "horse_name": h["horse_name"],
                "win_probability": prob,
                "place_probability": min(prob * 2.5, 0.9),
            })
        return preds
    except Exception:
        predictions, _ = _build_predictions()
        return predictions


@router.post("/betting/optimize")
def optimize(req: OptimizeRequest):
    predictions = _get_predictions(req.race_id)

    if req.pivot_horses:
        return _add_payout(_pivot_optimize(predictions, req))

    return _add_payout(optimize_bets(
        predictions=predictions,
        budget=req.budget,
        risk_level=req.risk_level,
        bet_types=req.bet_types,
        odds=req.odds if req.odds else None,
        excluded_horses=req.excluded_horses,
    ))


# ── 3パターン一括比較 ──

@router.post("/betting/compare")
def compare(req: OptimizeRequest):
    """低/中/高の3パターンを一括で返す"""
    predictions = _get_predictions(req.race_id)
    patterns = {}
    for risk in ["low", "medium", "high"]:
        r = optimize_bets(
            predictions=predictions,
            budget=req.budget,
            risk_level=risk,
            bet_types=req.bet_types,
            odds=req.odds if req.odds else None,
            excluded_horses=req.excluded_horses,
        )
        _add_payout(r)
        label = {"low": "堅実", "medium": "バランス", "high": "大穴狙い"}[risk]
        patterns[risk] = {**r, "label": label}
    return {"patterns": patterns}


def _pivot_optimize(predictions, req):
    """軸馬指定の流し買い"""
    pivots = [p for p in predictions if p["horse_name"] in req.pivot_horses]
    others = [p for p in predictions
              if p["horse_name"] not in req.pivot_horses
              and p["horse_name"] not in req.excluded_horses]
    others.sort(key=lambda x: x["win_probability"], reverse=True)
    top_others = others[:6]

    recommendations = []

    if len(pivots) == 1:
        pv = pivots[0]
        # 単勝（軸馬）
        if "win" in req.bet_types:
            o = req.odds.get("win", {}).get(pv["horse_name"], round(0.8 / max(pv["win_probability"], 0.01) * 1.1, 1))
            recommendations.append({
                "bet_type": "win", "bet_type_ja": "単勝",
                "selection": pv["horse_name"],
                "odds": o, "hit_prob": round(pv["win_probability"], 4),
                "expected_value": round(pv["win_probability"] * o, 3),
            })
        # 馬連流し
        if "quinella" in req.bet_types:
            for other in top_others:
                sel = f"{pv['horse_name']} - {other['horse_name']}"
                p = pv["win_probability"] * other["win_probability"] * 8
                p = min(p, 0.3)
                o = req.odds.get("quinella", {}).get(sel, round(0.775 / max(p, 0.001) * 1.15, 1))
                recommendations.append({
                    "bet_type": "quinella", "bet_type_ja": "馬連",
                    "selection": sel, "odds": round(o, 1),
                    "hit_prob": round(p, 4),
                    "expected_value": round(p * o, 3),
                })
        # 三連複流し（軸1頭 + 相手から2頭）
        if "trio" in req.bet_types:
            for a, b in combinations(top_others[:5], 2):
                sel = f"{pv['horse_name']} - {a['horse_name']} - {b['horse_name']}"
                pp = pv.get("place_probability", pv["win_probability"] * 2.5)
                pa = a.get("place_probability", a["win_probability"] * 2.5)
                pb = b.get("place_probability", b["win_probability"] * 2.5)
                p = min(pp * pa * pb * 15, 0.3)
                o = req.odds.get("trio", {}).get(sel, round(0.75 / max(p, 0.0001) * 1.2, 1))
                recommendations.append({
                    "bet_type": "trio", "bet_type_ja": "三連複",
                    "selection": sel, "odds": round(o, 1),
                    "hit_prob": round(p, 4),
                    "expected_value": round(p * o, 3),
                })

    elif len(pivots) == 2:
        pv1, pv2 = pivots
        # 馬連（軸2頭）
        if "quinella" in req.bet_types:
            sel = f"{pv1['horse_name']} - {pv2['horse_name']}"
            p = pv1["win_probability"] * pv2["win_probability"] * 8
            o = req.odds.get("quinella", {}).get(sel, round(0.775 / max(p, 0.001) * 1.15, 1))
            recommendations.append({
                "bet_type": "quinella", "bet_type_ja": "馬連",
                "selection": sel, "odds": round(o, 1),
                "hit_prob": round(min(p, 0.3), 4),
                "expected_value": round(min(p, 0.3) * o, 3),
            })
        # 三連複流し（軸2頭 + 相手1頭）
        if "trio" in req.bet_types:
            for other in top_others:
                sel = f"{pv1['horse_name']} - {pv2['horse_name']} - {other['horse_name']}"
                pp1 = pv1.get("place_probability", pv1["win_probability"] * 2.5)
                pp2 = pv2.get("place_probability", pv2["win_probability"] * 2.5)
                po = other.get("place_probability", other["win_probability"] * 2.5)
                p = min(pp1 * pp2 * po * 15, 0.3)
                o = req.odds.get("trio", {}).get(sel, round(0.75 / max(p, 0.0001) * 1.2, 1))
                recommendations.append({
                    "bet_type": "trio", "bet_type_ja": "三連複",
                    "selection": sel, "odds": round(o, 1),
                    "hit_prob": round(p, 4),
                    "expected_value": round(p * o, 3),
                })

    # 金額配分
    n = len(recommendations)
    if n > 0:
        per = max(int(req.budget / n / 100) * 100, 100)
        for r in recommendations:
            r["amount"] = per

    total_amount = sum(r.get("amount", 0) for r in recommendations)
    expected_return = sum(r.get("amount", 0) * r.get("expected_value", 0) for r in recommendations)

    return {
        "recommendations": recommendations,
        "total_budget": total_amount,
        "expected_return": round(expected_return),
        "expected_roi": round(expected_return / max(total_amount, 1), 3),
        "risk_metrics": {
            "worst_case": -total_amount,
            "best_case": max((int(r.get("amount", 0) * r.get("odds", 0)) for r in recommendations), default=0),
        },
    }


# ── フォーメーション ──

@router.post("/betting/formation")
def formation(req: FormationRequest):
    predictions, _ = _build_predictions()
    pred_map = {p["horse_name"]: p for p in predictions}

    combos = set()
    for a in req.first:
        for b in req.second:
            for c in req.third:
                trio = tuple(sorted({a, b, c}))
                if len(trio) == 3:
                    combos.add(trio)

    result = []
    total_hit_prob = 0
    for a, b, c in sorted(combos):
        pa = pred_map.get(a, {}).get("place_probability", 0.1)
        pb = pred_map.get(b, {}).get("place_probability", 0.1)
        pc = pred_map.get(c, {}).get("place_probability", 0.1)
        p = min(pa * pb * pc * 15, 0.3)
        o = round(max(0.75 / max(p, 0.0001) * 1.2, 5.0), 1)
        total_hit_prob += p
        result.append({
            "selection": f"{a} - {b} - {c}",
            "hit_prob": round(p, 4),
            "odds": o,
            "payout": int(req.amount_per_bet * o),
        })

    total = len(result) * req.amount_per_bet
    expected_return = sum(r["hit_prob"] * r["payout"] for r in result)

    return {
        "combinations": result,
        "total_bets": len(result),
        "total_cost": total,
        "amount_per_bet": req.amount_per_bet,
        "total_hit_prob": round(min(total_hit_prob, 1.0), 4),
        "expected_return": round(expected_return),
        "expected_roi": round(expected_return / max(total, 1), 3),
        "best_payout": max((r["payout"] for r in result), default=0),
    }


# ── ボックス ──

@router.post("/betting/box")
def box(req: BoxRequest):
    predictions, _ = _build_predictions()
    pred_map = {p["horse_name"]: p for p in predictions}

    if req.bet_type in ("trio", "trifecta"):
        r = 3
    elif req.bet_type in ("quinella", "wide", "exacta"):
        r = 2
    else:
        r = 2

    combos = list(combinations(req.horses, r))
    result = []
    total_hit_prob = 0
    for combo in combos:
        if r == 3:
            pa = pred_map.get(combo[0], {}).get("place_probability", 0.1)
            pb = pred_map.get(combo[1], {}).get("place_probability", 0.1)
            pc = pred_map.get(combo[2], {}).get("place_probability", 0.1)
            p = min(pa * pb * pc * 15, 0.3)
            takeout = 0.75
        else:
            pa = pred_map.get(combo[0], {}).get("win_probability", 0.05)
            pb = pred_map.get(combo[1], {}).get("win_probability", 0.05)
            p = pa * pb * 8
            p = min(p, 0.3)
            takeout = 0.775

        o = round(max(takeout / max(p, 0.0001) * 1.15, 2.0), 1)
        total_hit_prob += p
        result.append({
            "selection": " - ".join(combo),
            "hit_prob": round(p, 4),
            "odds": o,
            "payout": int(req.amount_per_bet * o),
        })

    total = len(result) * req.amount_per_bet
    expected_return = sum(r["hit_prob"] * r["payout"] for r in result)

    return {
        "combinations": result,
        "total_bets": len(result),
        "total_cost": total,
        "amount_per_bet": req.amount_per_bet,
        "total_hit_prob": round(min(total_hit_prob, 1.0), 4),
        "expected_return": round(expected_return),
        "expected_roi": round(expected_return / max(total, 1), 3),
        "best_payout": max((r["payout"] for r in result), default=0),
    }


# ── 収支シミュレーション ──

@router.post("/betting/simulate-result")
def simulate_result(req: SimulateResultRequest):
    top3 = {req.result_first, req.result_second, req.result_third}
    top2 = {req.result_first, req.result_second}

    hit_bets = []
    total_return = 0

    for bet in req.bets:
        horses_in_bet = set(h.strip() for h in bet.get("selection", "").split("-"))
        bt = bet.get("type", bet.get("bet_type", ""))
        amount = bet.get("amount", 0)
        odds = bet.get("odds", 0)
        hit = False

        if bt == "win" and horses_in_bet == {req.result_first}:
            hit = True
        elif bt == "place" and horses_in_bet.issubset(top3) and len(horses_in_bet) == 1:
            hit = True
        elif bt == "quinella" and horses_in_bet == top2:
            hit = True
        elif bt == "wide" and horses_in_bet.issubset(top3) and len(horses_in_bet) == 2:
            hit = True
        elif bt == "trio" and horses_in_bet == top3:
            hit = True

        if hit:
            payout = int(amount * odds)
            hit_bets.append({**bet, "payout": payout})
            total_return += payout

    total_invested = sum(b.get("amount", 0) for b in req.bets)

    return {
        "hit_bets": hit_bets,
        "total_return": total_return,
        "total_invested": total_invested,
        "profit": total_return - total_invested,
        "roi": round(total_return / max(total_invested, 1), 3),
    }
