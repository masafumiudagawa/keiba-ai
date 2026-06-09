"""
買い目最適化エンジン（ケリー基準 + 期待値ベース）
"""
from itertools import combinations


def kelly_fraction(p: float, odds: float) -> float:
    """ケリー基準で最適投資比率を計算

    f* = (p * b - q) / b
    p = 的中確率, q = 1-p, b = オッズ-1
    """
    if odds <= 1 or p <= 0 or p >= 1:
        return 0.0
    b = odds - 1
    q = 1 - p
    f = (p * b - q) / b
    return max(f, 0.0)


def optimize_bets(predictions: list[dict], budget: int,
                  risk_level: str = "medium",
                  bet_types: list[str] = None,
                  odds: dict = None,
                  excluded_horses: list[str] = None) -> dict:
    """買い目を最適化する

    Args:
        predictions: 予測結果 [{"horse_name", "win_probability", "place_probability"}, ...]
        budget: 投資予算（円）
        risk_level: "low" / "medium" / "high"
        bet_types: ["win", "place", "quinella", "wide", "trio", "trifecta"]
        odds: {"win": {"馬名": float}, "quinella": {"馬A-馬B": float}, ...}
        excluded_horses: 除外馬リスト
    """
    if bet_types is None:
        bet_types = ["win", "quinella", "wide", "trio"]
    if odds is None:
        odds = {}
    if excluded_horses is None:
        excluded_horses = []

    # リスクに応じたケリー係数
    kelly_scale = {"low": 0.25, "medium": 0.5, "high": 0.75}.get(risk_level, 0.5)

    # 予測データをフィルタ
    horses = [p for p in predictions if p["horse_name"] not in excluded_horses]
    horses.sort(key=lambda x: x["win_probability"], reverse=True)

    recommendations = []

    # ── 単勝 ──
    if "win" in bet_types:
        win_odds = odds.get("win", {})
        for h in horses[:5]:
            name = h["horse_name"]
            o = win_odds.get(name, _estimate_odds(h["win_probability"]))
            p = h["win_probability"]
            ev = p * o
            kf = kelly_fraction(p, o) * kelly_scale
            if ev > 0.8 or kf > 0:
                recommendations.append({
                    "bet_type": "win",
                    "bet_type_ja": "単勝",
                    "selection": name,
                    "odds": round(o, 1),
                    "hit_prob": round(p, 4),
                    "expected_value": round(ev, 3),
                    "kelly_fraction": round(kf, 4),
                })

    # ── 複勝 ──
    if "place" in bet_types:
        place_odds = odds.get("place", {})
        for h in horses[:5]:
            name = h["horse_name"]
            pp = h.get("place_probability", h["win_probability"] * 2.5)
            o = place_odds.get(name, _estimate_place_odds(pp))
            ev = pp * o
            kf = kelly_fraction(pp, o) * kelly_scale
            if ev > 0.8 or kf > 0:
                recommendations.append({
                    "bet_type": "place",
                    "bet_type_ja": "複勝",
                    "selection": name,
                    "odds": round(o, 1),
                    "hit_prob": round(pp, 4),
                    "expected_value": round(ev, 3),
                    "kelly_fraction": round(kf, 4),
                })

    # ── 馬連 ──
    if "quinella" in bet_types:
        quinella_odds = odds.get("quinella", {})
        top = horses[:6]
        for a, b in combinations(top, 2):
            key = f"{a['horse_name']}-{b['horse_name']}"
            p = a["win_probability"] * b.get("place_probability", b["win_probability"] * 2.5) + \
                b["win_probability"] * a.get("place_probability", a["win_probability"] * 2.5)
            p = min(p * 0.7, 0.5)
            o = quinella_odds.get(key, _estimate_combo_odds(a["win_probability"], b["win_probability"], 2))
            ev = p * o
            kf = kelly_fraction(p, o) * kelly_scale
            if ev > 0.9:
                recommendations.append({
                    "bet_type": "quinella",
                    "bet_type_ja": "馬連",
                    "selection": f"{a['horse_name']} - {b['horse_name']}",
                    "odds": round(o, 1),
                    "hit_prob": round(p, 4),
                    "expected_value": round(ev, 3),
                    "kelly_fraction": round(kf, 4),
                })

    # ── ワイド ──
    if "wide" in bet_types:
        wide_odds = odds.get("wide", {})
        top = horses[:6]
        for a, b in combinations(top, 2):
            key = f"{a['horse_name']}-{b['horse_name']}"
            pa = a.get("place_probability", a["win_probability"] * 2.5)
            pb = b.get("place_probability", b["win_probability"] * 2.5)
            p = pa * pb * 1.2
            p = min(p, 0.6)
            o = wide_odds.get(key, _estimate_combo_odds(a["win_probability"], b["win_probability"], 1.5))
            ev = p * o
            kf = kelly_fraction(p, o) * kelly_scale
            if ev > 0.9:
                recommendations.append({
                    "bet_type": "wide",
                    "bet_type_ja": "ワイド",
                    "selection": f"{a['horse_name']} - {b['horse_name']}",
                    "odds": round(o, 1),
                    "hit_prob": round(p, 4),
                    "expected_value": round(ev, 3),
                    "kelly_fraction": round(kf, 4),
                })

    # ── 三連複 ──
    if "trio" in bet_types:
        trio_odds = odds.get("trio", {})
        top = horses[:6]
        for a, b, c in combinations(top, 3):
            key = f"{a['horse_name']}-{b['horse_name']}-{c['horse_name']}"
            pa = a.get("place_probability", a["win_probability"] * 2.5)
            pb = b.get("place_probability", b["win_probability"] * 2.5)
            pc = c.get("place_probability", c["win_probability"] * 2.5)
            p = pa * pb * pc * 6
            p = min(p, 0.4)
            o = trio_odds.get(key, _estimate_combo_odds(a["win_probability"], b["win_probability"], 5) * (1 / max(c["win_probability"], 0.01)) * 0.3)
            o = max(o, 3.0)
            ev = p * o
            kf = kelly_fraction(p, o) * kelly_scale
            if ev > 1.0:
                recommendations.append({
                    "bet_type": "trio",
                    "bet_type_ja": "三連複",
                    "selection": f"{a['horse_name']} - {b['horse_name']} - {c['horse_name']}",
                    "odds": round(o, 1),
                    "hit_prob": round(p, 4),
                    "expected_value": round(ev, 3),
                    "kelly_fraction": round(kf, 4),
                })

    # ケリー比率で金額配分
    recommendations.sort(key=lambda x: x["expected_value"], reverse=True)
    recommendations = recommendations[:15]  # 上位15件に絞る

    total_kelly = sum(r["kelly_fraction"] for r in recommendations)
    if total_kelly > 0:
        for r in recommendations:
            raw_amount = budget * (r["kelly_fraction"] / total_kelly)
            r["amount"] = max(int(round(raw_amount / 100) * 100), 100)
    else:
        per = max(int(budget / max(len(recommendations), 1) / 100) * 100, 100)
        for r in recommendations:
            r["amount"] = per

    # 合計が予算を超えないよう調整
    total = sum(r["amount"] for r in recommendations)
    if total > budget and recommendations:
        scale = budget / total
        for r in recommendations:
            r["amount"] = max(int(round(r["amount"] * scale / 100) * 100), 100)

    total_amount = sum(r["amount"] for r in recommendations)
    expected_return = sum(r["amount"] * r["expected_value"] for r in recommendations)

    return {
        "recommendations": recommendations,
        "total_budget": total_amount,
        "expected_return": round(expected_return),
        "expected_roi": round(expected_return / max(total_amount, 1), 3),
        "risk_metrics": {
            "worst_case": -total_amount,
            "best_case": max((int(r["amount"] * r["odds"]) for r in recommendations), default=0),
        },
    }


def _estimate_odds(win_prob: float) -> float:
    if win_prob <= 0:
        return 100.0
    raw = 0.8 / win_prob
    return round(max(raw, 1.1), 1)


def _estimate_place_odds(place_prob: float) -> float:
    if place_prob <= 0:
        return 30.0
    raw = 0.8 / place_prob
    return round(max(raw, 1.1), 1)


def _estimate_combo_odds(p1: float, p2: float, multiplier: float = 2) -> float:
    combined = p1 * p2
    if combined <= 0:
        return 100.0
    raw = 0.75 / combined * multiplier
    return round(max(raw, 2.0), 1)
