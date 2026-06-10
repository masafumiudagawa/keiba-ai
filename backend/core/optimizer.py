"""
買い目最適化エンジン v2（バリューベース）

核心: 期待値 = AI確率 × 実オッズ
  期待値 > 1.0 → バリューあり（市場が過小評価）
  期待値 < 1.0 → バリューなし（市場が過大評価）

JRA控除率:
  単勝/複勝: 20%  → 還元率80%
  馬連/ワイド: 22.5% → 還元率77.5%
  馬単: 22.5%
  三連複: 25%  → 還元率75%
  三連単: 27.5% → 還元率72.5%
"""
from itertools import combinations, permutations

TAKEOUT = {
    "win": 0.80, "place": 0.80,
    "exacta": 0.775, "quinella": 0.775, "wide": 0.775,
    "trio": 0.75, "trifecta": 0.725,
}


def kelly_fraction(p: float, odds: float, scale: float = 0.25) -> float:
    """ケリー基準: f* = (p*b - q) / b  (scale で保守的に)"""
    if odds <= 1 or p <= 0 or p >= 1:
        return 0.0
    b = odds - 1
    q = 1 - p
    f = (p * b - q) / b
    return max(f * scale, 0.0)


def implied_prob(odds: float) -> float:
    """オッズから市場の想定確率（控除前）を算出"""
    if odds <= 0:
        return 0.0
    return 1.0 / odds


def value_score(ai_prob: float, market_odds: float) -> float:
    """バリュースコア = AI確率 × オッズ（= 期待値）"""
    return ai_prob * market_odds


# ── 複合馬券の確率計算 ──

def _quinella_prob(p1: float, p2: float) -> float:
    """馬連: A-Bが1-2着（順不同）"""
    if p1 + p2 >= 1:
        return min(p1 * p2 * 8, 0.5)
    pb_given_a = p2 / (1 - p1)
    pa_given_b = p1 / (1 - p2)
    return p1 * pb_given_a + p2 * pa_given_b


def _wide_prob(pp1: float, pp2: float, field: int) -> float:
    """ワイド: 両方3着以内"""
    return pp1 * pp2 * (field / max(field - 1, 1)) * 0.85


def _trio_prob(pp1: float, pp2: float, pp3: float, field: int) -> float:
    """三連複: 3頭が3着以内"""
    base = pp1 * pp2 * pp3
    correction = (3 / field) * (2 / max(field - 1, 1)) * (1 / max(field - 2, 1)) * (field ** 3) / 6
    return min(base * correction, 0.5)


def _exacta_prob(p1: float, p2: float) -> float:
    """馬単: A→B（着順あり）"""
    if p1 >= 1:
        return 0.0
    return p1 * (p2 / (1 - p1))


def _trifecta_prob(p1: float, p2: float, p3: float) -> float:
    """三連単: A→B→C（着順あり）"""
    if p1 >= 1 or p1 + p2 >= 1:
        return 0.0
    return p1 * (p2 / (1 - p1)) * (p3 / (1 - p1 - p2))


# ── 連勝式オッズの推定（実オッズがない場合） ──

def _estimate_combo_odds(prob: float, takeout: float, max_odds: float = 9999.9) -> float:
    """確率から推定オッズを算出（実オッズがない場合のフォールバック）"""
    if prob <= 0:
        return max_odds
    return round(min(max(takeout / prob, 1.5), max_odds), 1)


# 連勝式オッズの上限
MAX_ODDS = {
    "win": 999.9, "place": 200.0,
    "quinella": 5000.0, "wide": 1000.0,
    "exacta": 10000.0, "trio": 50000.0, "trifecta": 200000.0,
}


def _combo_odds_from_singles(singles: list[float], bet_type: str) -> float:
    """単勝オッズの積から連勝式オッズを推定（上限付き）"""
    product = 1.0
    for o in singles:
        product *= o

    coefficients = {
        "quinella": 0.35, "wide": 0.12, "exacta": 0.7,
        "trio": 0.08, "trifecta": 0.15,
    }
    coeff = coefficients.get(bet_type, 0.1)
    min_odds = {"quinella": 2.0, "wide": 1.2, "exacta": 5.0, "trio": 5.0, "trifecta": 20.0}

    raw = product * coeff
    return round(min(max(raw, min_odds.get(bet_type, 1.5)), MAX_ODDS.get(bet_type, 9999.9)), 1)


# ── メイン最適化関数 ──

def optimize_value_bets(
    horses: list[dict],
    actual_odds: dict,
    budget: int,
    risk_level: str = "medium",
    bet_types: list[str] = None,
) -> dict:
    """
    バリューベースの買い目最適化

    horses: [{horse_name, ai_win_prob, ai_place_prob}, ...]
    actual_odds: {horse_name: win_odds} (odds.csvから)
    """
    if bet_types is None:
        bet_types = ["win", "quinella", "wide", "trio"]

    field = len(horses)
    kelly_scale = {"low": 0.10, "medium": 0.20, "high": 0.35}.get(risk_level, 0.20)

    # ── バリュー分析（単勝ベース） ──
    value_analysis = []
    for h in horses:
        name = h["horse_name"]
        ai_p = h["ai_win_prob"]
        ai_pp = h["ai_place_prob"]
        market_odds = actual_odds.get(name, 0)
        market_p = implied_prob(market_odds) if market_odds > 0 else 0

        ev = value_score(ai_p, market_odds) if market_odds > 0 else 0
        gap = ai_p - market_p  # 正なら過小評価（買い）、負なら過大評価（消し）

        value_analysis.append({
            "horse_name": name,
            "ai_win_prob": round(ai_p, 4),
            "ai_place_prob": round(ai_pp, 4),
            "market_odds": market_odds,
            "market_prob": round(market_p, 4),
            "expected_value": round(ev, 3),
            "prob_gap": round(gap, 4),
            "verdict": "BUY" if ev > 1.0 else "WATCH" if ev > 0.8 else "FADE",
        })

    value_analysis.sort(key=lambda x: x["expected_value"], reverse=True)

    # ── 全買い目候補の生成 ──
    all_bets = []

    # 単勝
    if "win" in bet_types:
        for h in horses:
            name = h["horse_name"]
            ai_p = h["ai_win_prob"]
            odds = actual_odds.get(name, 0)
            if odds <= 0:
                continue
            ev = ai_p * odds
            kf = kelly_fraction(ai_p, odds, kelly_scale)
            all_bets.append({
                "bet_type": "win", "bet_type_ja": "単勝",
                "selection": name, "odds": odds,
                "hit_prob": round(ai_p, 4),
                "expected_value": round(ev, 3),
                "kelly": kf,
            })

    # 複勝
    if "place" in bet_types:
        for h in horses:
            name = h["horse_name"]
            ai_pp = h["ai_place_prob"]
            win_odds = actual_odds.get(name, 0)
            if win_odds <= 0:
                continue
            # 複勝オッズ推定: 単勝オッズの約1/3〜1/4
            place_odds = round(max(win_odds * 0.3, 1.1), 1)
            ev = ai_pp * place_odds
            kf = kelly_fraction(ai_pp, place_odds, kelly_scale)
            all_bets.append({
                "bet_type": "place", "bet_type_ja": "複勝",
                "selection": name, "odds": place_odds,
                "hit_prob": round(ai_pp, 4),
                "expected_value": round(ev, 3),
                "kelly": kf,
            })

    # 馬連
    if "quinella" in bet_types:
        top_n = _top_n_for_risk(risk_level, field)
        sorted_h = sorted(horses, key=lambda x: x["ai_win_prob"], reverse=True)[:top_n]
        for a, b in combinations(sorted_h, 2):
            p = _quinella_prob(a["ai_win_prob"], b["ai_win_prob"])
            oa = actual_odds.get(a["horse_name"], 0)
            ob = actual_odds.get(b["horse_name"], 0)
            if oa <= 0 or ob <= 0:
                odds = _estimate_combo_odds(p, TAKEOUT["quinella"])
            else:
                # 単勝オッズの積から馬連オッズを推定
                odds = _combo_odds_from_singles([oa, ob], "quinella")
            ev = p * odds
            kf = kelly_fraction(p, odds, kelly_scale)
            all_bets.append({
                "bet_type": "quinella", "bet_type_ja": "馬連",
                "selection": f"{a['horse_name']} - {b['horse_name']}",
                "odds": odds, "hit_prob": round(p, 4),
                "expected_value": round(ev, 3), "kelly": kf,
            })

    # ワイド
    if "wide" in bet_types:
        top_n = _top_n_for_risk(risk_level, field)
        sorted_h = sorted(horses, key=lambda x: x["ai_win_prob"], reverse=True)[:top_n]
        for a, b in combinations(sorted_h, 2):
            p = _wide_prob(a["ai_place_prob"], b["ai_place_prob"], field)
            oa = actual_odds.get(a["horse_name"], 0)
            ob = actual_odds.get(b["horse_name"], 0)
            if oa <= 0 or ob <= 0:
                odds = _estimate_combo_odds(p, TAKEOUT["wide"])
            else:
                odds = _combo_odds_from_singles([oa, ob], "wide")
            ev = p * odds
            kf = kelly_fraction(p, odds, kelly_scale)
            all_bets.append({
                "bet_type": "wide", "bet_type_ja": "ワイド",
                "selection": f"{a['horse_name']} - {b['horse_name']}",
                "odds": odds, "hit_prob": round(p, 4),
                "expected_value": round(ev, 3), "kelly": kf,
            })

    # 馬単
    if "exacta" in bet_types:
        top_n = _top_n_for_risk(risk_level, field)
        sorted_h = sorted(horses, key=lambda x: x["ai_win_prob"], reverse=True)[:top_n]
        for a, b in combinations(sorted_h, 2):
            for first, second in [(a, b), (b, a)]:
                p = _exacta_prob(first["ai_win_prob"], second["ai_win_prob"])
                of_ = actual_odds.get(first["horse_name"], 0)
                os_ = actual_odds.get(second["horse_name"], 0)
                if of_ <= 0 or os_ <= 0:
                    odds = _estimate_combo_odds(p, TAKEOUT["exacta"])
                else:
                    odds = _combo_odds_from_singles([of_, os_], "exacta")
                ev = p * odds
                kf = kelly_fraction(p, odds, kelly_scale)
                all_bets.append({
                    "bet_type": "exacta", "bet_type_ja": "馬単",
                    "selection": f"{first['horse_name']} → {second['horse_name']}",
                    "odds": odds, "hit_prob": round(p, 4),
                    "expected_value": round(ev, 3), "kelly": kf,
                })

    # 三連複
    if "trio" in bet_types:
        top_n = _top_n_for_risk(risk_level, field)
        sorted_h = sorted(horses, key=lambda x: x["ai_win_prob"], reverse=True)[:top_n]
        for a, b, c in combinations(sorted_h, 3):
            p = _trio_prob(a["ai_place_prob"], b["ai_place_prob"], c["ai_place_prob"], field)
            oa = actual_odds.get(a["horse_name"], 0)
            ob = actual_odds.get(b["horse_name"], 0)
            oc = actual_odds.get(c["horse_name"], 0)
            if oa <= 0 or ob <= 0 or oc <= 0:
                odds = _estimate_combo_odds(p, TAKEOUT["trio"])
            else:
                odds = _combo_odds_from_singles([oa, ob, oc], "trio")
            ev = p * odds
            kf = kelly_fraction(p, odds, kelly_scale)
            all_bets.append({
                "bet_type": "trio", "bet_type_ja": "三連複",
                "selection": f"{a['horse_name']} - {b['horse_name']} - {c['horse_name']}",
                "odds": odds, "hit_prob": round(p, 4),
                "expected_value": round(ev, 3), "kelly": kf,
            })

    # 三連単
    if "trifecta" in bet_types:
        top_n = min(_top_n_for_risk(risk_level, field), 6)
        sorted_h = sorted(horses, key=lambda x: x["ai_win_prob"], reverse=True)[:top_n]
        for combo in combinations(sorted_h, 3):
            for a, b, c in permutations(combo):
                p = _trifecta_prob(a["ai_win_prob"], b["ai_win_prob"], c["ai_win_prob"])
                oa = actual_odds.get(a["horse_name"], 0)
                ob = actual_odds.get(b["horse_name"], 0)
                oc = actual_odds.get(c["horse_name"], 0)
                if oa <= 0 or ob <= 0 or oc <= 0:
                    odds = _estimate_combo_odds(p, TAKEOUT["trifecta"])
                else:
                    odds = _combo_odds_from_singles([oa, ob, oc], "trifecta")
                ev = p * odds
                kf = kelly_fraction(p, odds, kelly_scale)
                all_bets.append({
                    "bet_type": "trifecta", "bet_type_ja": "三連単",
                    "selection": f"{a['horse_name']} → {b['horse_name']} → {c['horse_name']}",
                    "odds": odds, "hit_prob": round(p, 4),
                    "expected_value": round(ev, 3), "kelly": kf,
                })

    # ── バリューのある買い目のみ選出 ──
    value_bets = [b for b in all_bets if b["expected_value"] > 0.8]
    value_bets.sort(key=lambda x: x["expected_value"], reverse=True)

    # リスク別の点数制限
    max_bets = {"low": 5, "medium": 10, "high": 15}.get(risk_level, 10)
    selected = value_bets[:max_bets]

    # フォールバック: バリュー買い目が少ない場合、期待値順で補完
    if len(selected) < 3:
        all_bets.sort(key=lambda x: x["expected_value"], reverse=True)
        for b in all_bets:
            key = f"{b['bet_type']}:{b['selection']}"
            if not any(f"{s['bet_type']}:{s['selection']}" == key for s in selected):
                selected.append(b)
            if len(selected) >= 3:
                break

    # ── ケリー基準で金額配分 ──
    if selected:
        total_kelly = sum(b["kelly"] for b in selected) or 1
        for b in selected:
            raw = budget * (b["kelly"] / total_kelly)
            b["amount"] = max(int(round(raw / 100) * 100), 100)

        # 予算調整
        total = sum(b["amount"] for b in selected)
        if total > budget:
            scale = budget / total
            for b in selected:
                b["amount"] = max(int(round(b["amount"] * scale / 100) * 100), 100)

    # ── 結果集計 ──
    for b in selected:
        b["payout"] = int(b.get("amount", 0) * b.get("odds", 0))

    total_amount = sum(b["amount"] for b in selected)
    expected_return = sum(b["amount"] * b["expected_value"] for b in selected)

    return {
        "recommendations": selected,
        "value_analysis": value_analysis,
        "total_budget": total_amount,
        "expected_return": round(expected_return),
        "expected_roi": round(expected_return / max(total_amount, 1), 3),
        "has_real_odds": any(actual_odds.get(h["horse_name"], 0) > 0 for h in horses),
        "risk_metrics": {
            "worst_case": -total_amount,
            "best_case": max((b.get("payout", 0) for b in selected), default=0),
            "value_bet_count": len([b for b in selected if b["expected_value"] > 1.0]),
        },
    }


def _top_n_for_risk(risk_level: str, field: int) -> int:
    """リスク別の検討馬数"""
    base = {"low": 4, "medium": 6, "high": 8}.get(risk_level, 6)
    return min(base, field)
