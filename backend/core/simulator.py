"""
モンテカルロ レースシミュレーター

阪神芝2200m のレース展開を確率的にシミュレーションする。
各馬に脚質パラメータを設定し、200mごとのポジションを生成。
"""
import numpy as np
from dataclasses import dataclass, field


# 脚質タイプ
STYLES = {
    "nige":   {"early": 1.00, "mid": 0.97, "late": 0.94, "label": "逃げ"},
    "senko":  {"early": 0.98, "mid": 0.99, "late": 0.97, "label": "先行"},
    "sashi":  {"early": 0.94, "mid": 0.97, "late": 1.02, "label": "差し"},
    "oikomi": {"early": 0.90, "mid": 0.95, "late": 1.06, "label": "追込"},
}

CHECKPOINTS = list(range(0, 2400, 200))  # 0,200,...,2200

# 各馬のデフォルト脚質（前走データから推定）
DEFAULT_HORSE_PARAMS = {
    "クロワデュノール":   {"style": "senko",  "base_speed": 1.04, "stamina": 1.02},
    "ミュージアムマイル": {"style": "sashi",   "base_speed": 1.03, "stamina": 1.01},
    "メイショウタバル":   {"style": "nige",    "base_speed": 1.02, "stamina": 1.03},
    "レガレイラ":         {"style": "sashi",   "base_speed": 1.02, "stamina": 1.00},
    "ダノンデサイル":     {"style": "senko",   "base_speed": 1.01, "stamina": 1.02},
    "タガノデュード":     {"style": "sashi",   "base_speed": 0.99, "stamina": 1.01},
    "シンエンペラー":     {"style": "senko",   "base_speed": 1.00, "stamina": 0.99},
    "ジューンテイク":     {"style": "sashi",   "base_speed": 0.98, "stamina": 1.01},
    "マイユニバース":     {"style": "senko",   "base_speed": 0.99, "stamina": 1.00},
    "コスモキュランダ":   {"style": "senko",   "base_speed": 0.99, "stamina": 1.00},
    "ビザンチンドリーム": {"style": "oikomi",  "base_speed": 0.98, "stamina": 1.00},
    "マイネルエンペラー": {"style": "senko",   "base_speed": 0.97, "stamina": 0.99},
    "スティンガーグラス": {"style": "sashi",   "base_speed": 0.96, "stamina": 0.99},
    "シュガークン":       {"style": "senko",   "base_speed": 0.96, "stamina": 0.98},
    "ミクニインスパイア": {"style": "sashi",   "base_speed": 0.96, "stamina": 0.99},
    "シェイクユアハート": {"style": "nige",    "base_speed": 0.95, "stamina": 0.98},
    "ファミリータイム":   {"style": "sashi",   "base_speed": 0.94, "stamina": 0.97},
    "ミステリーウェイ":   {"style": "senko",   "base_speed": 0.93, "stamina": 0.96},
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
    n_horses = len(horses)
    n_checkpoints = len(CHECKPOINTS)

    # 馬場補正
    condition_factor = {"良": 1.0, "稍重": 0.99, "重": 0.97, "不良": 0.95}.get(track_condition, 1.0)

    # 各馬のパラメータ設定
    horse_params = []
    for h in horses:
        name = h.get("horse_name", "")
        params = DEFAULT_HORSE_PARAMS.get(name, {"style": "senko", "base_speed": 0.97, "stamina": 0.98})
        style = STYLES[params["style"]]
        horse_params.append({
            "name": name,
            "gate": int(h.get("gate_number", 0) or 0),
            "base_speed": params["base_speed"] * condition_factor,
            "stamina": params["stamina"],
            "style": params["style"],
            "early_mult": style["early"],
            "mid_mult": style["mid"],
            "late_mult": style["late"],
        })

    # シミュレーション実行
    all_finish_positions = np.zeros((n_simulations, n_horses), dtype=int)
    all_finish_times = np.zeros((n_simulations, n_horses))
    all_positions = np.zeros((n_simulations, n_horses, n_checkpoints))

    base_section_time = 12.0  # 200mあたり基準タイム（秒）

    for sim in range(n_simulations):
        # ペースシナリオ（ランダム）
        pace_var = np.random.normal(0, 0.3)  # ペースのブレ

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

                # ランダム要素
                noise = np.random.normal(0, 0.15)

                # 区間タイム
                section_time = base_section_time / (hp["base_speed"] * phase_mult * stamina_decay) + noise + pace_var * 0.1

                cumulative_times[hi] += max(section_time, 10.0)
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
    leader_times = np.min(rep_positions, axis=0)
    horse_results = []
    for hi in range(n_horses):
        hp = horse_params[hi]
        # 先頭からの差（秒）
        gaps = rep_positions[hi] - leader_times
        section_times = []
        for cp in range(1, n_checkpoints):
            section_times.append(round(rep_positions[hi, cp] - rep_positions[hi, cp - 1], 1))

        gate = hp["gate"] if hp["gate"] > 0 else hi + 1
        horse_results.append({
            "gate_number": gate,
            "horse_name": hp["name"],
            "color": GATE_COLORS.get((gate - 1) // 2 + 1, "#999999"),
            "style": hp["style"],
            "positions": [round(float(g), 2) for g in gaps],
            "section_times": section_times,
            "finish_time": f"{int(rep_times[hi] // 60)}:{rep_times[hi] % 60:04.1f}",
            "finish_position": int(rep_finish[hi]),
        })

    horse_results.sort(key=lambda x: x["finish_position"])

    # ペース算出
    leader_sections = []
    for cp in range(1, n_checkpoints):
        leader_sections.append(leader_times[cp] - leader_times[cp - 1])
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
