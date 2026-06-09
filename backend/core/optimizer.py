"""
買い目最適化エンジン（ケリー基準 + 期待値ベース）

JRA控除率:
  単勝/複勝: 20% → 還元率80%
  馬連/ワイド: 22.5% → 還元率77.5%
  三連複: 25% → 還元率75%
  三連単: 27.5% → 還元率72.5%
"""
from itertools import combinations

TAKEOUT = {
    "win": 0.80,
    "place": 0.80,
    "exacta": 0.775,     # 馬単
    "quinella": 0.775,    # 馬連
    "wide": 0.775,
    "trio": 0.75,         # 三連複
    "trifecta": 0.725,    # 三連単
}


def kelly_fraction(p: float, odds: float) -> float:
    """ケリー基準: f* = (p*b - q) / b"""
    if odds <= 1 or p <= 0 or p >= 1:
        return 0.0
    b = odds - 1
    q = 1 - p
    f = (p * b - q) / b
    return max(f, 0.0)


def _estimate_win_odds(p: float) -> float:
    """単勝オッズを確率から推定
    市場の歪みを考慮: 人気馬は実力より過小評価（オッズ高め）される傾向
    """
    if p <= 0:
        return 200.0
    # 人気薄ほどオッズが過大に付く（ロングショットバイアス逆転）
    market_adj = 1.1 if p > 0.15 else 1.0 if p > 0.08 else 0.9
    return round(max(TAKEOUT["win"] / p * market_adj, 1.1), 1)


def _estimate_place_odds(p: float) -> float:
    """複勝オッズを確率から推定"""
    if p <= 0:
        return 50.0
    return round(max(TAKEOUT["place"] / p * 1.05, 1.1), 1)


def _quinella_prob(p1: float, p2: float, pp1: float, pp2: float) -> float:
    """馬連の的中確率: A-Bが1-2着（順不同）"""
    # P(A1着)*P(B2着|A1着) + P(B1着)*P(A2着|B1着)
    # 近似: P(A1着) * P(B|残り馬で2着) + 逆
    pb_given_a = p2 / (1 - p1) if p1 < 1 else 0
    pa_given_b = p1 / (1 - p2) if p2 < 1 else 0
    return p1 * pb_given_a + p2 * pa_given_b


def _wide_prob(pp1: float, pp2: float, field: int) -> float:
    """ワイドの的中確率: 両方3着以内"""
    # 近似: P(A in top3) * P(B in top3 | A in top3)
    # 条件付確率で調整
    return pp1 * pp2 * (field / (field - 1)) * 0.85


def _trio_prob(pp1: float, pp2: float, pp3: float, field: int) -> float:
    """三連複の的中確率: 3頭が3着以内"""
    # P(A,B,C全て3着以内) ≈ 組合せ確率
    # 3!/C(field,3) * pp1 * pp2 * pp3 の調整版
    base = pp1 * pp2 * pp3
    # 条件付確率補正: 1頭入ると残り枠が減る
    correction = (3 / field) * (2 / (field - 1)) * (1 / (field - 2)) * (field ** 3) / 6
    return min(base * correction, 0.5)


def optimize_bets(predictions: list[dict], budget: int,
                  risk_level: str = "medium",
                  bet_types: list[str] = None,
                  odds: dict = None,
                  excluded_horses: list[str] = None) -> dict:
    if bet_types is None:
        bet_types = ["win", "quinella", "wide", "trio"]
    if odds is None:
        odds = {}
    if excluded_horses is None:
        excluded_horses = []

    kelly_scale = {"low": 0.15, "medium": 0.3, "high": 0.5}.get(risk_level, 0.3)

    horses = [p for p in predictions if p["horse_name"] not in excluded_horses]
    horses.sort(key=lambda x: x["win_probability"], reverse=True)
    field = len(horses)

    all_bets = []

    # ── 単勝 ──
    if "win" in bet_types:
        win_odds_map = odds.get("win", {})
        for h in horses[:6]:
            name = h["horse_name"]
            p = h["win_probability"]
            o = win_odds_map.get(name, _estimate_win_odds(p))
            ev = p * o
            kf = kelly_fraction(p, o) * kelly_scale
            all_bets.append({
                "bet_type": "win", "bet_type_ja": "単勝",
                "selection": name, "odds": round(o, 1),
                "hit_prob": round(p, 4), "expected_value": round(ev, 3),
                "kelly_fraction": kf,
            })

    # ── 複勝 ──
    if "place" in bet_types:
        place_odds_map = odds.get("place", {})
        for h in horses[:6]:
            name = h["horse_name"]
            pp = h.get("place_probability", min(h["win_probability"] * 2.5, 0.9))
            o = place_odds_map.get(name, _estimate_place_odds(pp))
            ev = pp * o
            kf = kelly_fraction(pp, o) * kelly_scale
            all_bets.append({
                "bet_type": "place", "bet_type_ja": "複勝",
                "selection": name, "odds": round(o, 1),
                "hit_prob": round(pp, 4), "expected_value": round(ev, 3),
                "kelly_fraction": kf,
            })

    # ── 馬連 ──
    if "quinella" in bet_types:
        quinella_odds_map = odds.get("quinella", {})
        for a, b in combinations(horses[:6], 2):
            key = f"{a['horse_name']}-{b['horse_name']}"
            pa, pb = a["win_probability"], b["win_probability"]
            ppa = a.get("place_probability", min(pa * 2.5, 0.9))
            ppb = b.get("place_probability", min(pb * 2.5, 0.9))
            p = _quinella_prob(pa, pb, ppa, ppb)
            o = quinella_odds_map.get(key, round(max(TAKEOUT["quinella"] / max(p, 0.001) * 1.15, 2.0), 1))
            ev = p * o
            kf = kelly_fraction(p, o) * kelly_scale
            all_bets.append({
                "bet_type": "quinella", "bet_type_ja": "馬連",
                "selection": f"{a['horse_name']} - {b['horse_name']}",
                "odds": round(o, 1), "hit_prob": round(p, 4),
                "expected_value": round(ev, 3), "kelly_fraction": kf,
            })

    # ── ワイド ──
    if "wide" in bet_types:
        wide_odds_map = odds.get("wide", {})
        for a, b in combinations(horses[:6], 2):
            key = f"{a['horse_name']}-{b['horse_name']}"
            ppa = a.get("place_probability", min(a["win_probability"] * 2.5, 0.9))
            ppb = b.get("place_probability", min(b["win_probability"] * 2.5, 0.9))
            p = _wide_prob(ppa, ppb, field)
            o = wide_odds_map.get(key, round(max(TAKEOUT["wide"] / max(p, 0.001) * 1.1, 1.5), 1))
            ev = p * o
            kf = kelly_fraction(p, o) * kelly_scale
            all_bets.append({
                "bet_type": "wide", "bet_type_ja": "ワイド",
                "selection": f"{a['horse_name']} - {b['horse_name']}",
                "odds": round(o, 1), "hit_prob": round(p, 4),
                "expected_value": round(ev, 3), "kelly_fraction": kf,
            })

    # ── 馬単（A→B 着順あり）──
    if "exacta" in bet_types:
        exacta_odds_map = odds.get("exacta", {})
        for a, b in combinations(horses[:6], 2):
            for first, second in [(a, b), (b, a)]:
                key = f"{first['horse_name']}→{second['horse_name']}"
                p1 = first["win_probability"]
                p2_given = second["win_probability"] / (1 - p1) if p1 < 1 else 0
                p = p1 * p2_given
                o = exacta_odds_map.get(key, round(max(TAKEOUT["exacta"] / max(p, 0.0001) * 1.15, 5.0), 1))
                ev = p * o
                kf = kelly_fraction(p, o) * kelly_scale
                all_bets.append({
                    "bet_type": "exacta", "bet_type_ja": "馬単",
                    "selection": f"{first['horse_name']} → {second['horse_name']}",
                    "odds": round(o, 1), "hit_prob": round(p, 4),
                    "expected_value": round(ev, 3), "kelly_fraction": kf,
                })

    # ── 三連複 ──
    if "trio" in bet_types:
        trio_odds_map = odds.get("trio", {})
        for a, b, c in combinations(horses[:7], 3):
            key = f"{a['horse_name']}-{b['horse_name']}-{c['horse_name']}"
            ppa = a.get("place_probability", min(a["win_probability"] * 2.5, 0.9))
            ppb = b.get("place_probability", min(b["win_probability"] * 2.5, 0.9))
            ppc = c.get("place_probability", min(c["win_probability"] * 2.5, 0.9))
            p = _trio_prob(ppa, ppb, ppc, field)
            o = trio_odds_map.get(key, round(max(TAKEOUT["trio"] / max(p, 0.0001) * 1.2, 5.0), 1))
            ev = p * o
            kf = kelly_fraction(p, o) * kelly_scale
            all_bets.append({
                "bet_type": "trio", "bet_type_ja": "三連複",
                "selection": f"{a['horse_name']} - {b['horse_name']} - {c['horse_name']}",
                "odds": round(o, 1), "hit_prob": round(p, 4),
                "expected_value": round(ev, 3), "kelly_fraction": kf,
            })

    # ── 三連単（A→B→C 着順あり）──
    if "trifecta" in bet_types:
        from itertools import permutations
        trifecta_odds_map = odds.get("trifecta", {})
        for combo in combinations(horses[:6], 3):
            for a, b, c in permutations(combo):
                key = f"{a['horse_name']}→{b['horse_name']}→{c['horse_name']}"
                p1 = a["win_probability"]
                p2 = b["win_probability"] / (1 - p1) if p1 < 1 else 0
                p3 = c["win_probability"] / (1 - p1 - b["win_probability"]) if (p1 + b["win_probability"]) < 1 else 0
                p = p1 * p2 * p3
                o = trifecta_odds_map.get(key, round(max(TAKEOUT["trifecta"] / max(p, 0.00001) * 1.2, 20.0), 1))
                ev = p * o
                kf = kelly_fraction(p, o) * kelly_scale
                all_bets.append({
                    "bet_type": "trifecta", "bet_type_ja": "三連単",
                    "selection": f"{a['horse_name']} → {b['horse_name']} → {c['horse_name']}",
                    "odds": round(o, 1), "hit_prob": round(p, 4),
                    "expected_value": round(ev, 3), "kelly_fraction": kf,
                })

    # ── リスクレベル別の戦略 ──
    # low:  的中率高い買い目中心、上位馬のみ、点数少なく厚く
    # medium: バランス型
    # high: 高配当狙い、穴馬含む、薄く広く
    risk_config = {
        "low": {
            "horse_range": 3,     # 上位3頭中心
            "max_bets": 5,        # 点数少なく
            "prefer_types": ["win", "place", "wide"],
            "weight_by": "hit_prob",  # 的中率重視
            "top_heavy": 0.5,     # 本命に厚く（上位に50%集中）
        },
        "medium": {
            "horse_range": 5,
            "max_bets": 8,
            "prefer_types": None,  # 全種別均等
            "weight_by": "expected_value",
            "top_heavy": 0.3,
        },
        "high": {
            "horse_range": 7,
            "max_bets": 12,
            "prefer_types": ["quinella", "trio"],  # 高配当中心
            "weight_by": "odds",  # 高オッズ重視
            "top_heavy": 0.1,     # 均等に近い
        },
    }
    rc = risk_config.get(risk_level, risk_config["medium"])

    # ── 各種別からリスクに応じて選出 ──
    selected = []
    types_requested = list(set(bet_types))

    for bt in types_requested:
        bt_bets = [b for b in all_bets if b["bet_type"] == bt]

        # リスクに応じたソート
        if rc["weight_by"] == "hit_prob":
            bt_bets.sort(key=lambda x: x["hit_prob"], reverse=True)
        elif rc["weight_by"] == "odds":
            bt_bets.sort(key=lambda x: x["odds"], reverse=True)
        else:
            bt_bets.sort(key=lambda x: x["expected_value"], reverse=True)

        # 優先種別でなければ少なく
        if rc["prefer_types"] and bt not in [t for t in rc["prefer_types"] if t in bet_types]:
            max_n = 1
        else:
            max_n = max(2, rc["max_bets"] // len(types_requested))

        selected.extend(bt_bets[:max_n])

    # 重複排除
    seen = set()
    unique = []
    for b in selected:
        key = f"{b['bet_type']}:{b['selection']}"
        if key not in seen:
            seen.add(key)
            unique.append(b)
    selected = unique[:rc["max_bets"]]

    # ── 金額配分（リスクに応じた傾斜） ──
    if not selected:
        selected = sorted(all_bets, key=lambda x: x["expected_value"], reverse=True)[:4]

    n = len(selected)
    weights = []
    for i in range(n):
        # 上位ほど厚く（top_heavyが大きいほど傾斜が急）
        w = 1.0 + rc["top_heavy"] * (n - i) / n
        weights.append(w)

    total_w = sum(weights)
    for i, b in enumerate(selected):
        raw = budget * (weights[i] / total_w)
        b["amount"] = max(int(round(raw / 100) * 100), 100)

    # 予算超過の調整
    total = sum(b["amount"] for b in selected)
    if total > budget and selected:
        scale = budget / total
        for b in selected:
            b["amount"] = max(int(round(b["amount"] * scale / 100) * 100), 100)

    total_amount = sum(b["amount"] for b in selected)
    expected_return = sum(b["amount"] * b["expected_value"] for b in selected)

    return {
        "recommendations": selected,
        "total_budget": total_amount,
        "expected_return": round(expected_return),
        "expected_roi": round(expected_return / max(total_amount, 1), 3),
        "risk_metrics": {
            "worst_case": -total_amount,
            "best_case": max((int(b["amount"] * b["odds"]) for b in selected), default=0),
        },
    }
