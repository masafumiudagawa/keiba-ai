"""
買い目最適化エンジン v3（順位比較 + バリュー比率ベース）

核心:
  バリュー比率 = AI確率 ÷ 市場確率
    > 1.5 → AIが市場より大幅に高評価 → 狙い目
    > 1.2 → 妙味あり
    0.8〜1.2 → 適正評価
    < 0.8 → 市場が過大評価 → 消し

  買い目は「AIが高く評価 & AI確率がそれなりにある馬」の組み合わせのみ推奨。
  999倍の超人気薄はAI確率も低いため自動的に除外される。

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


# ── 複合馬券の確率計算 ──

def _quinella_prob(p1: float, p2: float) -> float:
    if p1 + p2 >= 1:
        return min(p1 * p2 * 8, 0.5)
    pb_given_a = p2 / (1 - p1)
    pa_given_b = p1 / (1 - p2)
    return p1 * pb_given_a + p2 * pa_given_b


def _wide_prob(pp1: float, pp2: float, field: int) -> float:
    return pp1 * pp2 * (field / max(field - 1, 1)) * 0.85


def _trio_prob(pp1: float, pp2: float, pp3: float, field: int) -> float:
    base = pp1 * pp2 * pp3
    correction = (3 / field) * (2 / max(field - 1, 1)) * (1 / max(field - 2, 1)) * (field ** 3) / 6
    return min(base * correction, 0.5)


def _exacta_prob(p1: float, p2: float) -> float:
    if p1 >= 1:
        return 0.0
    return p1 * (p2 / (1 - p1))


def _trifecta_prob(p1: float, p2: float, p3: float) -> float:
    if p1 >= 1 or p1 + p2 >= 1:
        return 0.0
    return p1 * (p2 / (1 - p1)) * (p3 / (1 - p1 - p2))


# ── 連勝式オッズの推定 ──

MAX_ODDS = {
    "win": 999.9, "place": 200.0,
    "quinella": 5000.0, "wide": 1000.0,
    "exacta": 10000.0, "trio": 50000.0, "trifecta": 200000.0,
}


def _estimate_combo_odds(prob: float, takeout: float, max_odds: float = 9999.9) -> float:
    if prob <= 0:
        return max_odds
    return round(min(max(takeout / prob, 1.5), max_odds), 1)


def _combo_odds_from_singles(singles: list[float], bet_type: str) -> float:
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


# ── バリュー分析 ──

def build_value_analysis(horses: list[dict], actual_odds: dict) -> list[dict]:
    """
    全馬のバリュー分析を行う。
    バリュー比率 = AI確率 / 市場確率（高いほどAIが市場より高評価）
    """
    # AI順位を算出
    sorted_by_ai = sorted(horses, key=lambda x: x["ai_win_prob"], reverse=True)
    ai_rank_map = {h["horse_name"]: i + 1 for i, h in enumerate(sorted_by_ai)}

    # 市場順位（オッズ低い順 = 人気順）
    horses_with_odds = [(h["horse_name"], actual_odds.get(h["horse_name"], 9999)) for h in horses]
    horses_with_odds.sort(key=lambda x: x[1])
    market_rank_map = {name: i + 1 for i, (name, _) in enumerate(horses_with_odds)}

    analysis = []
    for h in horses:
        name = h["horse_name"]
        ai_p = h["ai_win_prob"]
        ai_pp = h["ai_place_prob"]
        market_odds = actual_odds.get(name, 0)
        market_p = (1.0 / market_odds) if market_odds > 0 else 0

        ai_rank = ai_rank_map.get(name, 99)
        market_rank = market_rank_map.get(name, 99)
        rank_diff = market_rank - ai_rank  # 正 = AIが市場より高く評価

        # バリュー比率 = AI確率 / 市場確率
        if market_p > 0:
            value_ratio = ai_p / market_p
        else:
            value_ratio = 0

        # 判定ロジック
        # AI確率が一定以上あり、かつバリュー比率が高い → 狙い目
        if market_odds <= 0:
            verdict = "NO_ODDS"
        elif ai_p >= 0.05 and value_ratio >= 1.5:
            verdict = "STRONG_BUY"  # 狙い目
        elif ai_p >= 0.03 and value_ratio >= 1.2:
            verdict = "BUY"  # 妙味あり
        elif 0.8 <= value_ratio <= 1.2:
            verdict = "FAIR"  # 適正
        else:
            verdict = "OVERVALUED"  # 過大評価

        analysis.append({
            "horse_name": name,
            "ai_win_prob": round(ai_p, 4),
            "ai_place_prob": round(ai_pp, 4),
            "ai_rank": ai_rank,
            "market_odds": market_odds,
            "market_prob": round(market_p, 4),
            "market_rank": market_rank,
            "rank_diff": rank_diff,
            "value_ratio": round(value_ratio, 2),
            "expected_value": round(ai_p * market_odds, 3) if market_odds > 0 else 0,
            "verdict": verdict,
        })

    # バリュー比率順でソート（高い = AIが市場より高評価）
    analysis.sort(key=lambda x: x["value_ratio"], reverse=True)
    return analysis


# ── メイン最適化関数 ──

def optimize_value_bets(
    horses: list[dict],
    actual_odds: dict,
    budget: int,
    risk_level: str = "medium",
    bet_types: list[str] = None,
) -> dict:
    if bet_types is None:
        bet_types = ["win", "quinella", "wide", "trio"]

    field = len(horses)
    kelly_scale = {"low": 0.10, "medium": 0.20, "high": 0.35}.get(risk_level, 0.20)

    # バリュー分析
    value_analysis = build_value_analysis(horses, actual_odds)

    # AI確率の閾値（リスク別）: この確率以上の馬のみ買い目候補
    ai_prob_threshold = {"low": 0.06, "medium": 0.04, "high": 0.02}.get(risk_level, 0.04)

    # バリュー馬を抽出（買い目候補になる馬）
    # 条件: AI確率が閾値以上 & バリュー比率が0.8以上（過大評価でない）
    value_horses = []
    for h in horses:
        name = h["horse_name"]
        ai_p = h["ai_win_prob"]
        odds = actual_odds.get(name, 0)
        market_p = (1.0 / odds) if odds > 0 else 0
        vr = (ai_p / market_p) if market_p > 0 else 1.0

        if ai_p >= ai_prob_threshold and (vr >= 0.8 or odds <= 0):
            value_horses.append(h)

    # フォールバック: バリュー馬が少なすぎる場合、AI上位馬を補完
    if len(value_horses) < 3:
        sorted_by_ai = sorted(horses, key=lambda x: x["ai_win_prob"], reverse=True)
        for h in sorted_by_ai:
            if h not in value_horses:
                value_horses.append(h)
            if len(value_horses) >= 5:
                break

    # ── 全買い目候補の生成 ──
    all_bets = []

    # 単勝
    if "win" in bet_types:
        for h in value_horses:
            name = h["horse_name"]
            ai_p = h["ai_win_prob"]
            odds = actual_odds.get(name, 0)
            if odds <= 0:
                continue
            ev = ai_p * odds
            kf = kelly_fraction(ai_p, odds, kelly_scale)
            if kf <= 0:
                continue
            all_bets.append({
                "bet_type": "win", "bet_type_ja": "単勝",
                "selection": name, "odds": odds,
                "hit_prob": round(ai_p, 4),
                "expected_value": round(ev, 3), "kelly": kf,
            })

    # 複勝
    if "place" in bet_types:
        for h in value_horses:
            name = h["horse_name"]
            ai_pp = h["ai_place_prob"]
            win_odds = actual_odds.get(name, 0)
            if win_odds <= 0:
                continue
            place_odds = round(max(win_odds * 0.3, 1.1), 1)
            ev = ai_pp * place_odds
            kf = kelly_fraction(ai_pp, place_odds, kelly_scale)
            if kf <= 0:
                continue
            all_bets.append({
                "bet_type": "place", "bet_type_ja": "複勝",
                "selection": name, "odds": place_odds,
                "hit_prob": round(ai_pp, 4),
                "expected_value": round(ev, 3), "kelly": kf,
            })

    # 馬連
    if "quinella" in bet_types:
        for a, b in combinations(value_horses, 2):
            p = _quinella_prob(a["ai_win_prob"], b["ai_win_prob"])
            oa = actual_odds.get(a["horse_name"], 0)
            ob = actual_odds.get(b["horse_name"], 0)
            if oa <= 0 or ob <= 0:
                odds = _estimate_combo_odds(p, TAKEOUT["quinella"])
            else:
                odds = _combo_odds_from_singles([oa, ob], "quinella")
            ev = p * odds
            kf = kelly_fraction(p, odds, kelly_scale)
            if kf <= 0:
                continue
            all_bets.append({
                "bet_type": "quinella", "bet_type_ja": "馬連",
                "selection": f"{a['horse_name']} - {b['horse_name']}",
                "odds": odds, "hit_prob": round(p, 4),
                "expected_value": round(ev, 3), "kelly": kf,
            })

    # ワイド
    if "wide" in bet_types:
        for a, b in combinations(value_horses, 2):
            p = _wide_prob(a["ai_place_prob"], b["ai_place_prob"], field)
            oa = actual_odds.get(a["horse_name"], 0)
            ob = actual_odds.get(b["horse_name"], 0)
            if oa <= 0 or ob <= 0:
                odds = _estimate_combo_odds(p, TAKEOUT["wide"])
            else:
                odds = _combo_odds_from_singles([oa, ob], "wide")
            ev = p * odds
            kf = kelly_fraction(p, odds, kelly_scale)
            if kf <= 0:
                continue
            all_bets.append({
                "bet_type": "wide", "bet_type_ja": "ワイド",
                "selection": f"{a['horse_name']} - {b['horse_name']}",
                "odds": odds, "hit_prob": round(p, 4),
                "expected_value": round(ev, 3), "kelly": kf,
            })

    # 馬単
    if "exacta" in bet_types:
        for a, b in combinations(value_horses, 2):
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
                if kf <= 0:
                    continue
                all_bets.append({
                    "bet_type": "exacta", "bet_type_ja": "馬単",
                    "selection": f"{first['horse_name']} → {second['horse_name']}",
                    "odds": odds, "hit_prob": round(p, 4),
                    "expected_value": round(ev, 3), "kelly": kf,
                })

    # 三連複
    if "trio" in bet_types:
        for a, b, c in combinations(value_horses, 3):
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
            if kf <= 0:
                continue
            all_bets.append({
                "bet_type": "trio", "bet_type_ja": "三連複",
                "selection": f"{a['horse_name']} - {b['horse_name']} - {c['horse_name']}",
                "odds": odds, "hit_prob": round(p, 4),
                "expected_value": round(ev, 3), "kelly": kf,
            })

    # 三連単
    if "trifecta" in bet_types:
        top_vh = value_horses[:6]
        for combo in combinations(top_vh, 3):
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
                if kf <= 0:
                    continue
                all_bets.append({
                    "bet_type": "trifecta", "bet_type_ja": "三連単",
                    "selection": f"{a['horse_name']} → {b['horse_name']} → {c['horse_name']}",
                    "odds": odds, "hit_prob": round(p, 4),
                    "expected_value": round(ev, 3), "kelly": kf,
                })

    # ── 買い目選出: ケリー値順（= 本当にベットすべき順） ──
    all_bets.sort(key=lambda x: x["kelly"], reverse=True)

    max_bets = {"low": 5, "medium": 10, "high": 15}.get(risk_level, 10)
    selected = all_bets[:max_bets]

    # ── ケリー基準で金額配分 ──
    if selected:
        total_kelly = sum(b["kelly"] for b in selected) or 1
        for b in selected:
            raw = budget * (b["kelly"] / total_kelly)
            b["amount"] = max(int(round(raw / 100) * 100), 100)

        total = sum(b["amount"] for b in selected)
        if total > budget:
            scale = budget / total
            for b in selected:
                b["amount"] = max(int(round(b["amount"] * scale / 100) * 100), 100)

    for b in selected:
        b["payout"] = int(b.get("amount", 0) * b.get("odds", 0))

    total_amount = sum(b.get("amount", 0) for b in selected)
    expected_return = sum(b.get("amount", 0) * b.get("expected_value", 0) for b in selected)

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
