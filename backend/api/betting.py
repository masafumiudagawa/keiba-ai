"""買い目最適化 API v2（バリューベース）"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter
from pydantic import BaseModel
from itertools import combinations
import pandas as pd

from backend.core.optimizer import optimize_value_bets, _combo_odds_from_singles

router = APIRouter()

RACES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "races")


# ── リクエストモデル ──

class OptimizeRequest(BaseModel):
    budget: int = 10000
    risk_level: str = "medium"
    bet_types: list[str] = ["win", "quinella", "wide", "trio"]
    excluded_horses: list[str] = []
    pivot_horses: list[str] = []
    race_id: str = "takarazuka_2026"


class FormationRequest(BaseModel):
    bet_type: str = "trio"
    first: list[str] = []
    second: list[str] = []
    third: list[str] = []
    amount_per_bet: int = 100
    race_id: str = "takarazuka_2026"


class BoxRequest(BaseModel):
    bet_type: str = "trio"
    horses: list[str] = []
    amount_per_bet: int = 100
    race_id: str = "takarazuka_2026"


class SimulateResultRequest(BaseModel):
    bets: list[dict] = []
    result_first: str = ""
    result_second: str = ""
    result_third: str = ""


# ── データ取得 ──

def _load_horses_and_odds(race_id: str):
    """レースの馬データ + 実オッズを取得"""
    from backend.api.races import get_features
    data = get_features(race_id)
    features = data.get("features", [])

    # AI確率の算出
    totals = [sum(h["scores"].values()) for h in features]
    min_t = min(totals) if totals else 0
    max_t = max(totals) if totals else 1
    rng = max_t - min_t or 1
    prob_sum = sum((t - min_t) / rng for t in totals) or 1

    horses = []
    for h, t in zip(features, totals):
        prob = ((t - min_t) / rng) / prob_sum
        horses.append({
            "horse_name": h["horse_name"],
            "ai_win_prob": prob,
            "ai_place_prob": min(prob * 2.5, 0.9),
        })

    # 実オッズをodds.csvから読み込み
    actual_odds = {}
    odds_path = os.path.join(RACES_DIR, race_id, "odds.csv")
    if os.path.exists(odds_path):
        try:
            df = pd.read_csv(odds_path, encoding="utf-8-sig")
            for _, row in df.iterrows():
                name = str(row.get("horse_name", "")).strip()
                win_odds = float(row.get("win_odds", 0) or 0)
                if name and win_odds > 0:
                    actual_odds[name] = win_odds
        except Exception:
            pass

    return horses, actual_odds


# ── AI最適化 ──

@router.post("/betting/optimize")
def optimize(req: OptimizeRequest):
    horses, actual_odds = _load_horses_and_odds(req.race_id)

    # 除外馬を除く
    horses = [h for h in horses if h["horse_name"] not in req.excluded_horses]

    # 軸馬指定の場合
    if req.pivot_horses:
        return _pivot_optimize(horses, actual_odds, req)

    return optimize_value_bets(
        horses=horses,
        actual_odds=actual_odds,
        budget=req.budget,
        risk_level=req.risk_level,
        bet_types=req.bet_types,
    )


# ── 3パターン一括比較 ──

@router.post("/betting/compare")
def compare(req: OptimizeRequest):
    horses, actual_odds = _load_horses_and_odds(req.race_id)
    horses = [h for h in horses if h["horse_name"] not in req.excluded_horses]

    patterns = {}
    for risk in ["low", "medium", "high"]:
        r = optimize_value_bets(
            horses=horses,
            actual_odds=actual_odds,
            budget=req.budget,
            risk_level=risk,
            bet_types=req.bet_types,
        )
        label = {"low": "堅実", "medium": "バランス", "high": "大穴狙い"}[risk]
        patterns[risk] = {**r, "label": label}
    return {"patterns": patterns}


# ── 軸馬流し ──

def _pivot_optimize(horses, actual_odds, req):
    pivots = [h for h in horses if h["horse_name"] in req.pivot_horses]
    others = [h for h in horses if h["horse_name"] not in req.pivot_horses]
    others.sort(key=lambda x: x["ai_win_prob"], reverse=True)
    top_others = others[:6]

    from backend.core.optimizer import (
        kelly_fraction, _quinella_prob, _trio_prob,
        _estimate_combo_odds, TAKEOUT, value_score,
    )
    kelly_scale = {"low": 0.10, "medium": 0.20, "high": 0.35}.get(req.risk_level, 0.20)
    field = len(horses)
    recommendations = []

    if len(pivots) == 1:
        pv = pivots[0]
        pv_odds = actual_odds.get(pv["horse_name"], 0)

        if "win" in req.bet_types and pv_odds > 0:
            ev = pv["ai_win_prob"] * pv_odds
            kf = kelly_fraction(pv["ai_win_prob"], pv_odds, kelly_scale)
            recommendations.append({
                "bet_type": "win", "bet_type_ja": "単勝",
                "selection": pv["horse_name"], "odds": pv_odds,
                "hit_prob": round(pv["ai_win_prob"], 4),
                "expected_value": round(ev, 3), "kelly": kf,
            })

        if "quinella" in req.bet_types:
            for other in top_others:
                p = _quinella_prob(pv["ai_win_prob"], other["ai_win_prob"])
                oo = actual_odds.get(other["horse_name"], 0)
                if pv_odds > 0 and oo > 0:
                    odds = _combo_odds_from_singles([pv_odds, oo], "quinella")
                else:
                    odds = _estimate_combo_odds(p, TAKEOUT["quinella"])
                ev = p * odds
                kf = kelly_fraction(p, odds, kelly_scale)
                recommendations.append({
                    "bet_type": "quinella", "bet_type_ja": "馬連",
                    "selection": f"{pv['horse_name']} - {other['horse_name']}",
                    "odds": odds, "hit_prob": round(p, 4),
                    "expected_value": round(ev, 3), "kelly": kf,
                })

        if "trio" in req.bet_types:
            for a, b in combinations(top_others[:5], 2):
                p = _trio_prob(pv["ai_place_prob"], a["ai_place_prob"], b["ai_place_prob"], field)
                oa = actual_odds.get(a["horse_name"], 0)
                ob = actual_odds.get(b["horse_name"], 0)
                if pv_odds > 0 and oa > 0 and ob > 0:
                    odds = _combo_odds_from_singles([pv_odds, oa, ob], "trio")
                else:
                    odds = _estimate_combo_odds(p, TAKEOUT["trio"])
                ev = p * odds
                kf = kelly_fraction(p, odds, kelly_scale)
                recommendations.append({
                    "bet_type": "trio", "bet_type_ja": "三連複",
                    "selection": f"{pv['horse_name']} - {a['horse_name']} - {b['horse_name']}",
                    "odds": odds, "hit_prob": round(p, 4),
                    "expected_value": round(ev, 3), "kelly": kf,
                })

    elif len(pivots) == 2:
        pv1, pv2 = pivots
        o1 = actual_odds.get(pv1["horse_name"], 0)
        o2 = actual_odds.get(pv2["horse_name"], 0)

        if "quinella" in req.bet_types:
            p = _quinella_prob(pv1["ai_win_prob"], pv2["ai_win_prob"])
            if o1 > 0 and o2 > 0:
                odds = _combo_odds_from_singles([o1, o2], "quinella")
            else:
                odds = _estimate_combo_odds(p, TAKEOUT["quinella"])
            ev = p * odds
            kf = kelly_fraction(p, odds, kelly_scale)
            recommendations.append({
                "bet_type": "quinella", "bet_type_ja": "馬連",
                "selection": f"{pv1['horse_name']} - {pv2['horse_name']}",
                "odds": odds, "hit_prob": round(p, 4),
                "expected_value": round(ev, 3), "kelly": kf,
            })

        if "trio" in req.bet_types:
            for other in top_others:
                oo = actual_odds.get(other["horse_name"], 0)
                p = _trio_prob(pv1["ai_place_prob"], pv2["ai_place_prob"], other["ai_place_prob"], field)
                if o1 > 0 and o2 > 0 and oo > 0:
                    odds = _combo_odds_from_singles([o1, o2, oo], "trio")
                else:
                    odds = _estimate_combo_odds(p, TAKEOUT["trio"])
                ev = p * odds
                kf = kelly_fraction(p, odds, kelly_scale)
                recommendations.append({
                    "bet_type": "trio", "bet_type_ja": "三連複",
                    "selection": f"{pv1['horse_name']} - {pv2['horse_name']} - {other['horse_name']}",
                    "odds": odds, "hit_prob": round(p, 4),
                    "expected_value": round(ev, 3), "kelly": kf,
                })

    # バリュー順ソート + 金額配分
    recommendations.sort(key=lambda x: x["expected_value"], reverse=True)

    if recommendations:
        total_kelly = sum(b["kelly"] for b in recommendations) or 1
        for b in recommendations:
            raw = req.budget * (b["kelly"] / total_kelly)
            b["amount"] = max(int(round(raw / 100) * 100), 100)
            b["payout"] = int(b["amount"] * b["odds"])

        total = sum(b["amount"] for b in recommendations)
        if total > req.budget:
            scale = req.budget / total
            for b in recommendations:
                b["amount"] = max(int(round(b["amount"] * scale / 100) * 100), 100)
                b["payout"] = int(b["amount"] * b["odds"])

    total_amount = sum(b.get("amount", 0) for b in recommendations)
    expected_return = sum(b.get("amount", 0) * b.get("expected_value", 0) for b in recommendations)

    # バリュー分析も返す
    value_analysis = []
    for h in horses:
        name = h["horse_name"]
        ai_p = h["ai_win_prob"]
        mo = actual_odds.get(name, 0)
        mp = (1.0 / mo) if mo > 0 else 0
        ev = ai_p * mo if mo > 0 else 0
        value_analysis.append({
            "horse_name": name, "ai_win_prob": round(ai_p, 4),
            "market_odds": mo, "market_prob": round(mp, 4),
            "expected_value": round(ev, 3), "prob_gap": round(ai_p - mp, 4),
            "verdict": "BUY" if ev > 1.0 else "WATCH" if ev > 0.8 else "FADE",
        })
    value_analysis.sort(key=lambda x: x["expected_value"], reverse=True)

    return {
        "recommendations": recommendations,
        "value_analysis": value_analysis,
        "total_budget": total_amount,
        "expected_return": round(expected_return),
        "expected_roi": round(expected_return / max(total_amount, 1), 3),
        "has_real_odds": any(actual_odds.get(h["horse_name"], 0) > 0 for h in horses),
        "risk_metrics": {
            "worst_case": -total_amount,
            "best_case": max((b.get("payout", 0) for b in recommendations), default=0),
            "value_bet_count": len([b for b in recommendations if b["expected_value"] > 1.0]),
        },
    }


# ── フォーメーション ──

@router.post("/betting/formation")
def formation(req: FormationRequest):
    horses, actual_odds = _load_horses_and_odds(req.race_id)
    pred_map = {h["horse_name"]: h for h in horses}
    field = len(horses)

    from backend.core.optimizer import _trio_prob, _estimate_combo_odds, _combo_odds_from_singles, TAKEOUT

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
        ha = pred_map.get(a, {"ai_place_prob": 0.1})
        hb = pred_map.get(b, {"ai_place_prob": 0.1})
        hc = pred_map.get(c, {"ai_place_prob": 0.1})
        p = _trio_prob(ha["ai_place_prob"], hb["ai_place_prob"], hc["ai_place_prob"], field)

        oa = actual_odds.get(a, 0)
        ob = actual_odds.get(b, 0)
        oc = actual_odds.get(c, 0)
        if oa > 0 and ob > 0 and oc > 0:
            odds = _combo_odds_from_singles([oa, ob, oc], "trio")
        else:
            odds = _estimate_combo_odds(p, TAKEOUT["trio"])

        ev = p * odds
        total_hit_prob += p
        result.append({
            "selection": f"{a} - {b} - {c}",
            "hit_prob": round(p, 4), "odds": odds,
            "payout": int(req.amount_per_bet * odds),
            "expected_value": round(ev, 3),
        })

    result.sort(key=lambda x: x["expected_value"], reverse=True)
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
        "has_real_odds": any(actual_odds.get(h, 0) > 0 for h in req.first + req.second + req.third),
    }


# ── ボックス ──

@router.post("/betting/box")
def box(req: BoxRequest):
    horses, actual_odds = _load_horses_and_odds(req.race_id)
    pred_map = {h["horse_name"]: h for h in horses}
    field = len(horses)

    from backend.core.optimizer import (
        _quinella_prob, _wide_prob, _trio_prob,
        _estimate_combo_odds, _combo_odds_from_singles, TAKEOUT,
    )

    r = 3 if req.bet_type in ("trio", "trifecta") else 2
    combos = list(combinations(req.horses, r))
    result = []
    total_hit_prob = 0

    for combo in combos:
        hs = [pred_map.get(c, {"ai_win_prob": 0.05, "ai_place_prob": 0.15}) for c in combo]
        odds_vals = [actual_odds.get(c, 0) for c in combo]

        if r == 3:
            p = _trio_prob(hs[0]["ai_place_prob"], hs[1]["ai_place_prob"], hs[2]["ai_place_prob"], field)
            if all(o > 0 for o in odds_vals):
                odds = _combo_odds_from_singles(odds_vals, "trio")
            else:
                odds = _estimate_combo_odds(p, TAKEOUT["trio"])
        else:
            bt = "wide" if req.bet_type == "wide" else "quinella"
            if bt == "wide":
                p = _wide_prob(hs[0]["ai_place_prob"], hs[1]["ai_place_prob"], field)
            else:
                p = _quinella_prob(hs[0]["ai_win_prob"], hs[1]["ai_win_prob"])
            if all(o > 0 for o in odds_vals):
                odds = _combo_odds_from_singles(odds_vals, bt)
            else:
                odds = _estimate_combo_odds(p, TAKEOUT[bt])

        ev = p * odds
        total_hit_prob += p
        result.append({
            "selection": " - ".join(combo),
            "hit_prob": round(p, 4), "odds": odds,
            "payout": int(req.amount_per_bet * odds),
            "expected_value": round(ev, 3),
        })

    result.sort(key=lambda x: x["expected_value"], reverse=True)
    total = len(result) * req.amount_per_bet
    expected_return = sum(r_["hit_prob"] * r_["payout"] for r_ in result)

    return {
        "combinations": result,
        "total_bets": len(result),
        "total_cost": total,
        "amount_per_bet": req.amount_per_bet,
        "total_hit_prob": round(min(total_hit_prob, 1.0), 4),
        "expected_return": round(expected_return),
        "expected_roi": round(expected_return / max(total, 1), 3),
        "best_payout": max((r_["payout"] for r_ in result), default=0),
        "has_real_odds": any(actual_odds.get(h, 0) > 0 for h in req.horses),
    }


# ── 収支シミュレーション ──

@router.post("/betting/simulate-result")
def simulate_result(req: SimulateResultRequest):
    top3 = {req.result_first, req.result_second, req.result_third}
    top2 = {req.result_first, req.result_second}

    hit_bets = []
    total_return = 0

    for bet in req.bets:
        sel = bet.get("selection", "")
        # → で分割（馬単/三連単）または - で分割
        if "→" in sel:
            horses_in_bet = [h.strip() for h in sel.split("→")]
        else:
            horses_in_bet = [h.strip() for h in sel.split("-")]
        horses_set = set(horses_in_bet)

        bt = bet.get("type", bet.get("bet_type", ""))
        amount = bet.get("amount", 0)
        odds = bet.get("odds", 0)
        hit = False

        if bt == "win" and horses_set == {req.result_first}:
            hit = True
        elif bt == "place" and len(horses_set) == 1 and horses_set.issubset(top3):
            hit = True
        elif bt == "quinella" and horses_set == top2:
            hit = True
        elif bt == "wide" and horses_set.issubset(top3) and len(horses_set) == 2:
            hit = True
        elif bt == "exacta" and len(horses_in_bet) == 2 and horses_in_bet[0] == req.result_first and horses_in_bet[1] == req.result_second:
            hit = True
        elif bt == "trio" and horses_set == top3:
            hit = True
        elif bt == "trifecta" and len(horses_in_bet) == 3 and horses_in_bet[0] == req.result_first and horses_in_bet[1] == req.result_second and horses_in_bet[2] == req.result_third:
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
