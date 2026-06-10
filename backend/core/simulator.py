"""
モンテカルロ レースシミュレーター

阪神芝2200m のレース展開を確率的にシミュレーションする。
各馬に脚質パラメータを設定し、200mごとのポジションを生成。
"""
import numpy as np
from dataclasses import dataclass, field


# 脚質タイプ
STYLES = {
    "nige":   {"early": 1.015, "mid": 0.995, "late": 0.990, "label": "逃げ"},
    "senko":  {"early": 1.005, "mid": 1.000, "late": 0.995, "label": "先行"},
    "sashi":  {"early": 0.985, "mid": 0.995, "late": 1.015, "label": "差し"},
    "oikomi": {"early": 0.975, "mid": 0.990, "late": 1.025, "label": "追込"},
}

CHECKPOINTS = list(range(0, 2400, 200))  # 0,200,...,2200

# 各馬のパラメータ（実際のG1は1-2%差で決まる）
# base_speed: 1.000中心 ±0.015の範囲に収める
DEFAULT_HORSE_PARAMS = {
    "クロワデュノール":   {"style": "senko",  "base_speed": 1.012, "stamina": 1.005},
    "ミュージアムマイル": {"style": "sashi",   "base_speed": 1.009, "stamina": 1.003},
    "メイショウタバル":   {"style": "nige",    "base_speed": 1.008, "stamina": 1.006},
    "レガレイラ":         {"style": "sashi",   "base_speed": 1.007, "stamina": 1.002},
    "ダノンデサイル":     {"style": "senko",   "base_speed": 1.006, "stamina": 1.004},
    "タガノデュード":     {"style": "sashi",   "base_speed": 1.002, "stamina": 1.003},
    "シンエンペラー":     {"style": "senko",   "base_speed": 1.003, "stamina": 1.000},
    "ジューンテイク":     {"style": "sashi",   "base_speed": 1.000, "stamina": 1.002},
    "マイユニバース":     {"style": "senko",   "base_speed": 1.001, "stamina": 1.001},
    "コスモキュランダ":   {"style": "senko",   "base_speed": 1.001, "stamina": 1.001},
    "ビザンチンドリーム": {"style": "oikomi",  "base_speed": 1.000, "stamina": 1.002},
    "マイネルエンペラー": {"style": "senko",   "base_speed": 0.998, "stamina": 0.999},
    "スティンガーグラス": {"style": "sashi",   "base_speed": 0.997, "stamina": 0.999},
    "シュガークン":       {"style": "senko",   "base_speed": 0.997, "stamina": 0.998},
    "ミクニインスパイア": {"style": "sashi",   "base_speed": 0.996, "stamina": 0.999},
    "シェイクユアハート": {"style": "nige",    "base_speed": 0.995, "stamina": 0.998},
    "ファミリータイム":   {"style": "sashi",   "base_speed": 0.994, "stamina": 0.997},
    "ミステリーウェイ":   {"style": "senko",   "base_speed": 0.993, "stamina": 0.996},
}

# 枠色
GATE_COLORS = {
    1: "#ffffff", 2: "#000000", 3: "#e74c3c", 4: "#3498db",
    5: "#f1c40f", 6: "#2ecc71", 7: "#e67e22", 8: "#e91e63",
}


def simulate_race(horses: list[dict], n_simulations: int = 1000,
                  track_condition: str = "良") -> dict:
    """モンテカルロシミュレーションを実行

    Args:
        horses: [{"horse_name": str, "gate_number": int, ...}, ...]
        n_simulations: 試行回数
        track_condition: 馬場状態

    Returns:
        シミュレーション結果dict
    """
    import math

    def _safe_int(v, default=0):
        if v is None:
            return default
        try:
            f = float(v)
            return default if math.isnan(f) else int(f)
        except (ValueError, TypeError):
            return default

    n_horses = len(horses)
    n_checkpoints = len(CHECKPOINTS)

    # 馬場補正
    condition_map = {"良": 1.0, "稍重": 0.99, "重": 0.97, "不良": 0.95,
                     "good": 1.0, "slightly_heavy": 0.99, "heavy": 0.97, "bad": 0.95}
    condition_factor = condition_map.get(track_condition, 1.0)

    # 各馬のパラメータ設定
    # AI予測スコアが渡されている場合、スコアからbase_speedを算出
    horse_params = []
    for i, h in enumerate(horses):
        name = h.get("horse_name", "")

        # ハードコード値があればそれを使う（宝塚記念等の手動チューニング済み馬）
        if name in DEFAULT_HORSE_PARAMS:
            params = DEFAULT_HORSE_PARAMS[name]
        elif "scores" in h:
            # AI予測スコアからシミュレーションパラメータを算出
            scores = h["scores"]
            total = sum(scores.values()) if scores else 100
            # base_speed: スコア合計を0.985〜1.015の範囲にマッピング
            # 全馬の中央値を1.000として、上下±0.015に分布させる
            params = {
                "style": str(h.get("running_style", scores.get("running_style_raw", "senko"))),
                "base_speed": total,  # 後で全馬の分布から正規化
                "stamina": total,
            }
        else:
            params = {"style": "senko", "base_speed": 0.97, "stamina": 0.98}

        # running_styleの名前解決
        style_name = params.get("style", "senko")
        if style_name not in STYLES:
            style_name = "senko"
        style = STYLES[style_name]

        horse_params.append({
            "name": name,
            "gate": _safe_int(h.get("gate_number"), i + 1),
            "base_speed": params["base_speed"],
            "stamina": params.get("stamina", 0.998),
            "style": style_name,
            "early_mult": style["early"],
            "mid_mult": style["mid"],
            "late_mult": style["late"],
        })

    # スコアベースの馬がいる場合、base_speed/staminaを正規化
    score_based = [hp for hp in horse_params if hp["base_speed"] > 10]  # スコア値は100+
    if score_based:
        totals = [hp["base_speed"] for hp in score_based]
        mn, mx = min(totals), max(totals)
        rng = mx - mn or 1
        for hp in score_based:
            # 0.985 〜 1.015 にマッピング
            normalized = (hp["base_speed"] - mn) / rng
            hp["base_speed"] = (0.985 + normalized * 0.030) * condition_factor
            # staminaも同様: 0.995 〜 1.005
            normalized_s = (hp["stamina"] - mn) / rng
            hp["stamina"] = 0.995 + normalized_s * 0.010
    else:
        # ハードコード馬のみ: 馬場補正だけ適用
        for hp in horse_params:
            hp["base_speed"] *= condition_factor

    # シミュレーション実行
    all_finish_positions = np.zeros((n_simulations, n_horses), dtype=int)
    all_finish_times = np.zeros((n_simulations, n_horses))
    all_positions = np.zeros((n_simulations, n_horses, n_checkpoints))

    base_section_time = 12.0  # 200mあたり基準タイム（秒）

    for sim in range(n_simulations):
        # ペースシナリオ（ランダム）
        pace_var = np.random.normal(0, 0.2)

        # 各馬に「当日の調子」をランダムに付与（±0.5%程度）
        daily_form = np.random.normal(0, 0.005, n_horses)

        cumulative_times = np.zeros(n_horses)
        positions = np.zeros((n_horses, n_checkpoints))

        for cp_idx in range(n_checkpoints):
            progress = cp_idx / (n_checkpoints - 1)  # 0.0 ~ 1.0

            for hi in range(n_horses):
                hp = horse_params[hi]

                # 区間ごとの速度決定
                if progress < 0.35:
                    phase_mult = hp["early_mult"]
                elif progress < 0.7:
                    phase_mult = hp["mid_mult"]
                else:
                    phase_mult = hp["late_mult"]

                # スタミナ消耗
                stamina_decay = 1.0 - (1.0 - hp["stamina"]) * progress

                # ランダム要素（区間ごとのブレ + 展開運 + 当日の調子）
                noise = np.random.normal(0, 0.25)

                # 馬群での不利（中団〜後方は不利を受けやすい）
                traffic = np.random.uniform(0, 0.1) if 0.3 < progress < 0.8 else 0

                # 区間タイム
                speed = (hp["base_speed"] + daily_form[hi]) * phase_mult * stamina_decay
                section_time = base_section_time / speed + noise + pace_var * 0.05 + traffic

                cumulative_times[hi] += max(section_time, 10.5)
                positions[hi, cp_idx] = cumulative_times[hi]

        # 着順決定
        finish_times = cumulative_times
        finish_order = np.argsort(finish_times) + 1
        ranking = np.empty_like(finish_order)
        ranking[np.argsort(finish_times)] = np.arange(1, n_horses + 1)

        all_finish_positions[sim] = ranking
        all_finish_times[sim] = finish_times
        all_positions[sim] = positions

    # 集計
    win_counts = {}
    place_counts = {}
    for hi in range(n_horses):
        name = horse_params[hi]["name"]
        wins = int((all_finish_positions[:, hi] == 1).sum())
        places = int((all_finish_positions[:, hi] <= 3).sum())
        win_counts[name] = wins
        place_counts[name] = places

    # 代表レース: 中央値パターンに最も近い試行を選択
    median_times = np.median(all_finish_times, axis=0)
    diffs = np.sum((all_finish_times - median_times) ** 2, axis=1)
    representative_idx = int(np.argmin(diffs))

    rep_positions = all_positions[representative_idx]
    rep_finish = all_finish_positions[representative_idx]
    rep_times = all_finish_times[representative_idx]

    # 代表レースのデータ構築
    # 各馬の進行度を0〜1の範囲で表現（アニメーション用）
    # rep_positions[hi, cp] = 累積タイム → これを最遅タイムで正規化して順位感を出す
    leader_times = np.min(rep_positions, axis=0)  # 各CPでの先頭タイム
    slowest_times = np.max(rep_positions, axis=0)  # 各CPでの最後方タイム

    horse_results = []
    for hi in range(n_horses):
        hp = horse_params[hi]

        # 先頭からの差（秒）→ 各CPで
        gaps_sec = rep_positions[hi] - leader_times
        # 差を相対位置に変換: 0=先頭, 1=最後方
        spread = slowest_times - leader_times
        relative_positions = []
        for cp in range(n_checkpoints):
            if spread[cp] > 0:
                relative_positions.append(round(float(gaps_sec[cp] / spread[cp]), 3))
            else:
                relative_positions.append(0.0)

        section_times = []
        for cp in range(1, n_checkpoints):
            st = float(rep_positions[hi, cp] - rep_positions[hi, cp - 1])
            section_times.append(round(st, 1))

        gate = hp["gate"] if hp["gate"] > 0 else hi + 1
        horse_results.append({
            "gate_number": int(gate),
            "horse_name": hp["name"],
            "color": GATE_COLORS.get((gate - 1) // 2 + 1, "#999999"),
            "style": hp["style"],
            "positions": relative_positions,
            "gaps_sec": [round(float(g), 2) for g in gaps_sec],
            "section_times": section_times,
            "finish_time": f"{int(rep_times[hi] // 60)}:{rep_times[hi] % 60:04.1f}",
            "finish_position": int(rep_finish[hi]),
        })

    horse_results.sort(key=lambda x: x["finish_position"])

    # ペース算出
    leader_sections = []
    for cp in range(1, n_checkpoints):
        leader_sections.append(float(leader_times[cp] - leader_times[cp - 1]))
    first_1000m = sum(leader_sections[:5])
    last_600m = sum(leader_sections[-3:])

    return {
        "summary": {
            "num_simulations": n_simulations,
            "win_counts": win_counts,
            "place_counts": place_counts,
            "avg_winning_time": f"{int(np.mean(all_finish_times[:, np.argmin(median_times)]) // 60)}:{np.mean(all_finish_times[:, np.argmin(median_times)]) % 60:04.1f}",
        },
        "representative_race": {
            "total_distance": 2200,
            "checkpoints": CHECKPOINTS,
            "horses": horse_results,
            "pace": {
                "first_1000m": f"{first_1000m:.1f}",
                "last_600m": f"{last_600m:.1f}",
                "type": "H" if first_1000m < 58 else "S" if first_1000m > 61 else "M",
            },
        },
    }
