"""
手動データ入力・CSV読み込みモジュール

スクレイピングが困難な場合やデータ補完のため、
CSVファイルから手動でデータを読み込むためのモジュール。
木曜日に確定する出馬表データもここから入力する。
"""

import os
import pandas as pd
from config.settings import RAW_DIR, PROCESSED_DIR, REGISTERED_HORSES_2026


def generate_csv_templates():
    """手動入力用のCSVテンプレートを生成する"""
    os.makedirs(RAW_DIR, exist_ok=True)

    # ────────────────────────────────────────
    # 1. 馬の過去成績テンプレート
    # ────────────────────────────────────────
    horse_history_cols = [
        "horse_name",       # 馬名
        "race_date",        # レース日 (YYYY/MM/DD)
        "venue",            # 競馬場
        "race_name",        # レース名
        "grade",            # グレード (G1/G2/G3/OP/条件)
        "distance",         # 距離 (m)
        "surface",          # 芝/ダート
        "track_condition",  # 馬場状態 (良/稍重/重/不良)
        "weather",          # 天候
        "field_size",       # 出走頭数
        "post_position",    # 枠番
        "gate_number",      # 馬番
        "finish_position",  # 着順
        "finish_time",      # タイム (M:SS.s)
        "margin",           # 着差
        "last_3f",          # 上がり3F
        "passing_order",    # 通過順位 (1-2-3-4)
        "weight_carried",   # 斤量
        "jockey_name",      # 騎手名
        "horse_weight",     # 馬体重 (kg)
        "weight_change",    # 体重増減 (+/-kg)
        "odds",             # 単勝オッズ
        "popularity",       # 人気
        "sire",             # 父
        "dam_sire",         # 母父
        "trainer_name",     # 調教師名
    ]

    template = pd.DataFrame(columns=horse_history_cols)
    path = os.path.join(RAW_DIR, "template_horse_history.csv")
    template.to_csv(path, index=False, encoding="utf-8-sig")

    # ────────────────────────────────────────
    # 2. 宝塚記念過去結果テンプレート
    # ────────────────────────────────────────
    takarazuka_cols = [
        "year",             # 開催年
        "finish_position",  # 着順
        "post_position",    # 枠番
        "gate_number",      # 馬番
        "horse_name",       # 馬名
        "sex",              # 性別
        "age",              # 馬齢
        "weight_carried",   # 斤量
        "jockey_name",      # 騎手名
        "finish_time",      # タイム
        "margin",           # 着差
        "passing_order",    # 通過順位
        "last_3f",          # 上がり3F
        "horse_weight",     # 馬体重
        "weight_change",    # 体重増減
        "odds",             # 単勝オッズ
        "popularity",       # 人気
        "track_condition",  # 馬場状態
        "weather",          # 天候
        "sire",             # 父
        "prev_race",        # 前走レース名
        "prev_finish",      # 前走着順
        "trainer_name",     # 調教師名
    ]

    template = pd.DataFrame(columns=takarazuka_cols)
    path = os.path.join(RAW_DIR, "template_takarazuka_history.csv")
    template.to_csv(path, index=False, encoding="utf-8-sig")

    # ────────────────────────────────────────
    # 3. 木曜日確定データ（出馬表）テンプレート
    # ────────────────────────────────────────
    entry_cols = [
        "gate_number",      # 馬番
        "post_position",    # 枠番
        "horse_name",       # 馬名
        "sex",              # 性別
        "age",              # 馬齢
        "weight_carried",   # 斤量
        "jockey_name",      # 騎手名
        "trainer_name",     # 調教師名
        "horse_weight",     # 馬体重 (前走)
        "sire",             # 父
        "dam_sire",         # 母父
        "prev_race",        # 前走レース名
        "prev_finish",      # 前走着順
        "prev_distance",    # 前走距離
        "days_since_last",  # 前走からの間隔（日数）
    ]

    # 登録馬名を事前に入れたテンプレート
    entries = []
    for horse in REGISTERED_HORSES_2026:
        entries.append({
            "horse_name": horse["name"],
            "sex": horse["sex"],
            "age": horse["age"],
        })
    template = pd.DataFrame(entries, columns=entry_cols)
    path = os.path.join(RAW_DIR, "thursday_entries.csv")
    template.to_csv(path, index=False, encoding="utf-8-sig")

    # ────────────────────────────────────────
    # 4. 騎手成績テンプレート
    # ────────────────────────────────────────
    jockey_cols = [
        "jockey_name",          # 騎手名
        "total_wins_2026",      # 2026年勝利数
        "total_runs_2026",      # 2026年騎乗数
        "win_rate_2026",        # 2026年勝率
        "place_rate_2026",      # 2026年複勝率
        "g1_wins_career",       # 通算G1勝利数
        "hanshin_wins_2026",    # 阪神勝利数
        "hanshin_runs_2026",    # 阪神騎乗数
        "turf_2200_wins",       # 芝2200m勝利数
        "turf_2200_runs",       # 芝2200m騎乗数
    ]

    template = pd.DataFrame(columns=jockey_cols)
    path = os.path.join(RAW_DIR, "template_jockey_stats.csv")
    template.to_csv(path, index=False, encoding="utf-8-sig")

    print("CSVテンプレートを生成しました:")
    print(f"  - {RAW_DIR}/template_horse_history.csv    (馬の過去成績)")
    print(f"  - {RAW_DIR}/template_takarazuka_history.csv (宝塚記念過去結果)")
    print(f"  - {RAW_DIR}/thursday_entries.csv           (木曜確定出馬表)")
    print(f"  - {RAW_DIR}/template_jockey_stats.csv     (騎手成績)")


def load_thursday_entries(filepath: str = None) -> pd.DataFrame:
    """木曜日に確定した出馬表データを読み込む"""
    if filepath is None:
        filepath = os.path.join(RAW_DIR, "thursday_entries.csv")

    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"出馬表ファイルが見つかりません: {filepath}\n"
            f"先に generate_csv_templates() でテンプレートを生成してください。"
        )

    df = pd.read_csv(filepath, encoding="utf-8-sig")
    print(f"出馬表読み込み: {len(df)}頭")
    return df


def load_horse_history(horse_name: str = None) -> pd.DataFrame:
    """馬の過去成績データを読み込む（スクレイピング結果 or 手動CSV）"""
    all_data = []

    # スクレイピングで取得した個別ファイル
    for f in os.listdir(RAW_DIR):
        if f.startswith("horse_") and f.endswith(".csv"):
            df = pd.read_csv(os.path.join(RAW_DIR, f), encoding="utf-8-sig")
            all_data.append(df)

    # 手動入力ファイル
    manual_path = os.path.join(RAW_DIR, "manual_horse_history.csv")
    if os.path.exists(manual_path):
        df = pd.read_csv(manual_path, encoding="utf-8-sig")
        all_data.append(df)

    if not all_data:
        return pd.DataFrame()

    combined = pd.concat(all_data, ignore_index=True)

    if horse_name:
        combined = combined[combined["horse_name"] == horse_name]

    return combined


if __name__ == "__main__":
    generate_csv_templates()
