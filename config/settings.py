"""プロジェクト設定"""
import os

# ベースディレクトリ
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
RAW_DIR = os.path.join(DATA_DIR, "raw")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
MODEL_DIR = os.path.join(BASE_DIR, "models", "saved")

# スクレイピング設定
SCRAPE_INTERVAL = 1.5  # リクエスト間隔（秒）- サーバー負荷軽減
NETKEIBA_BASE_URL = "https://db.netkeiba.com"
NETKEIBA_RACE_URL = "https://race.netkeiba.com"

# 2026年宝塚記念の基本情報
TAKARAZUKA_2026 = {
    "race_name": "宝塚記念",
    "date": "2026-06-14",
    "venue": "阪神",
    "distance": 2200,
    "surface": "芝",
    "grade": "G1",
    "course_type": "右・内",
    "venue_code": "09",  # 阪神
}

# 収集対象年数
HISTORY_YEARS = 10  # 過去レース傾向分析用
HORSE_HISTORY_RACES = 20  # 各馬の直近レース数

# 競馬場コード (netkeiba)
VENUE_CODES = {
    "01": "札幌", "02": "函館", "03": "福島", "04": "新潟",
    "05": "東京", "06": "中山", "07": "中京", "08": "京都",
    "09": "阪神", "10": "小倉",
}

# 2026年宝塚記念 特別登録馬（18頭）
REGISTERED_HORSES_2026 = [
    {"name": "クロワデュノール", "age": 4, "sex": "牡"},
    {"name": "コスモキュランダ", "age": 5, "sex": "牡"},
    {"name": "シェイクユアハート", "age": 6, "sex": "牡"},
    {"name": "シュガークン", "age": 5, "sex": "牡"},
    {"name": "シンエンペラー", "age": 5, "sex": "牡"},
    {"name": "ジューンテイク", "age": 5, "sex": "牡"},
    {"name": "スティンガーグラス", "age": 5, "sex": "牡"},
    {"name": "タガノデュード", "age": 5, "sex": "牡"},
    {"name": "ダノンデサイル", "age": 5, "sex": "牡"},
    {"name": "ビザンチンドリーム", "age": 5, "sex": "牡"},
    {"name": "ファミリータイム", "age": 5, "sex": "牡"},
    {"name": "マイネルエンペラー", "age": 6, "sex": "牡"},
    {"name": "マイユニバース", "age": 4, "sex": "牡"},
    {"name": "ミクニインスパイア", "age": 4, "sex": "牡"},
    {"name": "ミステリーウェイ", "age": 8, "sex": "セ"},
    {"name": "ミュージアムマイル", "age": 4, "sex": "牡"},
    {"name": "メイショウタバル", "age": 5, "sex": "牡"},
    {"name": "レガレイラ", "age": 5, "sex": "牝"},
]

# 特徴量カテゴリ
FEATURE_CATEGORIES = {
    "horse_basic": [
        "age",              # 馬齢
        "sex",              # 性別
        "weight",           # 馬体重
        "weight_change",    # 馬体重増減
        "career_wins",      # 通算勝利数
        "career_win_rate",  # 通算勝率
        "career_place_rate",# 通算複勝率
    ],
    "recent_form": [
        "last_1_finish",    # 前走着順
        "last_2_finish",    # 2走前着順
        "last_3_finish",    # 3走前着順
        "avg_finish_last5", # 直近5走平均着順
        "last_1_margin",    # 前走着差
        "last_1_time",      # 前走タイム
        "days_since_last",  # 前走からの間隔（日数）
    ],
    "distance_aptitude": [
        "win_rate_2000_2400",   # 2000-2400m勝率
        "place_rate_2000_2400", # 2000-2400m複勝率
        "avg_finish_2000_2400", # 2000-2400m平均着順
        "best_time_2200",       # 2200mベストタイム
    ],
    "course_aptitude": [
        "win_rate_hanshin",     # 阪神勝率
        "place_rate_hanshin",   # 阪神複勝率
        "win_rate_turf",        # 芝勝率
        "win_rate_right",       # 右回り勝率
    ],
    "class_performance": [
        "g1_wins",              # G1勝利数
        "g1_place_count",       # G1複勝回数
        "graded_win_rate",      # 重賞勝率
        "prev_race_grade",      # 前走格
        "prev_race_finish",     # 前走着順
    ],
    "jockey": [
        "jockey_win_rate",          # 騎手勝率
        "jockey_place_rate",        # 騎手複勝率
        "jockey_g1_wins",           # 騎手G1勝利数
        "jockey_hanshin_win_rate",  # 騎手阪神勝率
        "jockey_horse_combo_runs",  # 騎手×馬コンビ出走数
        "jockey_horse_combo_wins",  # 騎手×馬コンビ勝利数
    ],
    "trainer": [
        "trainer_win_rate",         # 調教師勝率
        "trainer_g1_wins",          # 調教師G1勝利数
    ],
    "race_conditions": [
        "post_position",    # 枠番
        "gate_number",      # 馬番
        "track_condition",  # 馬場状態（良/稍重/重/不良）
        "weather",          # 天候
        "field_size",       # 出走頭数
    ],
    "pedigree": [
        "sire_turf_win_rate",       # 父の芝勝率
        "sire_distance_win_rate",   # 父の該当距離勝率
        "sire_hanshin_win_rate",    # 父の阪神勝率
    ],
}
