"""
特徴量エンジニアリングモジュール

収集した生データから予測モデル用の特徴量を生成する。
"""

import os
import re
import numpy as np
import pandas as pd
from config.settings import RAW_DIR, PROCESSED_DIR

os.makedirs(PROCESSED_DIR, exist_ok=True)


class FeatureEngineer:
    """馬ごとの特徴量を生成するクラス"""

    def __init__(self):
        self.horse_histories = {}  # {horse_name: DataFrame}
        self.takarazuka_history = None
        self.jockey_stats = {}
        self.youtube_predictions = None   # YouTube予想集計
        self.news_predictions = None      # ニュース予想集計
        self.odds_data = None             # オッズデータ
        self.training_data = None         # 調教データ
        self.weather_data = None          # 天気予報
        self.extended_data = None         # 拡張データ（上がり3F,脚質,血統詳細等）

    def load_data(self):
        """RAW_DIR からデータを読み込む"""
        # 馬の過去成績
        for f in os.listdir(RAW_DIR):
            if f.startswith("horse_") and f.endswith(".csv"):
                df = pd.read_csv(os.path.join(RAW_DIR, f), encoding="utf-8-sig")
                if "horse_name" in df.columns and len(df) > 0:
                    name = df["horse_name"].iloc[0]
                    self.horse_histories[name] = df

        # 手動入力の馬データ
        manual_path = os.path.join(RAW_DIR, "manual_horse_history.csv")
        if os.path.exists(manual_path):
            df = pd.read_csv(manual_path, encoding="utf-8-sig")
            for name, group in df.groupby("horse_name"):
                if name in self.horse_histories:
                    self.horse_histories[name] = pd.concat(
                        [self.horse_histories[name], group], ignore_index=True
                    )
                else:
                    self.horse_histories[name] = group

        # 宝塚記念過去結果
        tk_path = os.path.join(RAW_DIR, "takarazuka_history.csv")
        if os.path.exists(tk_path):
            self.takarazuka_history = pd.read_csv(tk_path, encoding="utf-8-sig")

        # 騎手成績
        jockey_path = os.path.join(RAW_DIR, "jockey_stats.csv")
        if os.path.exists(jockey_path):
            jdf = pd.read_csv(jockey_path, encoding="utf-8-sig")
            for _, row in jdf.iterrows():
                self.jockey_stats[row.get("jockey_name", "")] = row.to_dict()

        manual_jockey = os.path.join(RAW_DIR, "manual_jockey_stats.csv")
        if os.path.exists(manual_jockey):
            jdf = pd.read_csv(manual_jockey, encoding="utf-8-sig")
            for _, row in jdf.iterrows():
                self.jockey_stats[row.get("jockey_name", "")] = row.to_dict()

        # YouTube予想データ
        yt_path = os.path.join(RAW_DIR, "youtube_predictions.csv")
        if os.path.exists(yt_path):
            self.youtube_predictions = pd.read_csv(yt_path, encoding="utf-8-sig")

        # ニュース予想データ
        news_path = os.path.join(RAW_DIR, "news_predictions.csv")
        if os.path.exists(news_path):
            self.news_predictions = pd.read_csv(news_path, encoding="utf-8-sig")

        # オッズデータ（最新のもの）
        odds_path = os.path.join(RAW_DIR, "odds_history.csv")
        if os.path.exists(odds_path):
            self.odds_data = pd.read_csv(odds_path, encoding="utf-8-sig")

        # 調教データ
        train_path = os.path.join(RAW_DIR, "training_data.csv")
        if os.path.exists(train_path):
            self.training_data = pd.read_csv(train_path, encoding="utf-8-sig")

        # 天気予報
        weather_path = os.path.join(RAW_DIR, "weather_forecast.csv")
        if os.path.exists(weather_path):
            self.weather_data = pd.read_csv(weather_path, encoding="utf-8-sig")

        # 拡張データ（上がり3F, 脚質, 血統詳細, 対戦成績, スピード指数）
        ext_path = os.path.join(RAW_DIR, "extended_horse_data.csv")
        if os.path.exists(ext_path):
            self.extended_data = pd.read_csv(ext_path, encoding="utf-8-sig")

        loaded = []
        loaded.append(f"馬 {len(self.horse_histories)}頭")
        loaded.append(f"騎手 {len(self.jockey_stats)}名")
        if self.youtube_predictions is not None:
            loaded.append(f"YouTube予想 {len(self.youtube_predictions)}馬分")
        if self.news_predictions is not None:
            loaded.append(f"ニュース予想 {len(self.news_predictions)}馬分")
        if self.odds_data is not None:
            loaded.append(f"オッズ {len(self.odds_data)}件")
        if self.training_data is not None:
            loaded.append(f"調教 {len(self.training_data)}件")
        if self.weather_data is not None:
            loaded.append("天気予報あり")
        print(f"ロード完了: {', '.join(loaded)}")

    # ────────────────────────────────────────
    # 馬の基本特徴量
    # ────────────────────────────────────────
    def compute_horse_basic_features(self, horse_name: str, age: int, sex: str) -> dict:
        """馬の基本情報・通算成績から特徴量を生成"""
        features = {
            "age": age,
            "sex_code": self._encode_sex(sex),
            "career_wins": 0,
            "career_runs": 0,
            "career_win_rate": 0.0,
            "career_place_rate": 0.0,
        }

        history = self.horse_histories.get(horse_name)
        if history is None or history.empty:
            return features

        # 着順を数値化
        finish_col = self._find_column(history, ["finish_position", "着順"])
        if finish_col is None:
            return features

        history = history.copy()
        history["_finish"] = pd.to_numeric(history[finish_col], errors="coerce")
        valid = history.dropna(subset=["_finish"])

        if valid.empty:
            return features

        features["career_runs"] = len(valid)
        features["career_wins"] = int((valid["_finish"] == 1).sum())
        features["career_win_rate"] = features["career_wins"] / features["career_runs"]

        top3 = (valid["_finish"] <= 3).sum()
        features["career_place_rate"] = top3 / features["career_runs"]

        return features

    # ────────────────────────────────────────
    # 直近フォーム（近走成績）
    # ────────────────────────────────────────
    def compute_recent_form_features(self, horse_name: str) -> dict:
        """直近の走破成績から特徴量を生成"""
        features = {
            "last_1_finish": np.nan,
            "last_2_finish": np.nan,
            "last_3_finish": np.nan,
            "avg_finish_last5": np.nan,
            "last_1_last3f": np.nan,
            "avg_last3f_last5": np.nan,
            "last_1_margin": 0.0,
            "days_since_last": np.nan,
            "prev_race_grade_code": 0,
        }

        history = self.horse_histories.get(horse_name)
        if history is None or history.empty:
            return features

        history = history.copy()
        finish_col = self._find_column(history, ["finish_position", "着順"])
        if finish_col is None:
            return features

        history["_finish"] = pd.to_numeric(history[finish_col], errors="coerce")
        valid = history.dropna(subset=["_finish"]).head(10)  # 直近10走

        if valid.empty:
            return features

        finishes = valid["_finish"].values
        if len(finishes) >= 1:
            features["last_1_finish"] = finishes[0]
        if len(finishes) >= 2:
            features["last_2_finish"] = finishes[1]
        if len(finishes) >= 3:
            features["last_3_finish"] = finishes[2]
        if len(finishes) >= 5:
            features["avg_finish_last5"] = np.mean(finishes[:5])

        # 上がり3F
        l3f_col = self._find_column(valid, ["last_3f", "上がり3F", "上り"])
        if l3f_col and l3f_col in valid.columns:
            l3f_vals = pd.to_numeric(valid[l3f_col], errors="coerce").dropna()
            if len(l3f_vals) >= 1:
                features["last_1_last3f"] = l3f_vals.iloc[0]
            if len(l3f_vals) >= 5:
                features["avg_last3f_last5"] = l3f_vals.iloc[:5].mean()

        # 前走レースグレード
        grade_col = self._find_column(valid, ["grade", "race_name"])
        if grade_col and grade_col in valid.columns:
            prev_race = str(valid[grade_col].iloc[0])
            features["prev_race_grade_code"] = self._encode_grade(prev_race)

        # 前走からの間隔
        date_col = self._find_column(valid, ["race_date", "日付"])
        if date_col and date_col in valid.columns:
            try:
                dates = pd.to_datetime(valid[date_col], errors="coerce").dropna()
                if len(dates) >= 1:
                    last_date = dates.iloc[0]
                    race_date = pd.Timestamp("2026-06-14")
                    features["days_since_last"] = (race_date - last_date).days
            except Exception:
                pass

        return features

    # ────────────────────────────────────────
    # 距離・コース適性
    # ────────────────────────────────────────
    def compute_course_aptitude_features(self, horse_name: str) -> dict:
        """距離・コース適性の特徴量"""
        features = {
            "win_rate_2000_2400": 0.0,
            "place_rate_2000_2400": 0.0,
            "runs_2000_2400": 0,
            "win_rate_hanshin": 0.0,
            "place_rate_hanshin": 0.0,
            "runs_hanshin": 0,
            "win_rate_turf": 0.0,
            "win_rate_right": 0.0,
            "best_finish_g1": np.nan,
            "g1_wins": 0,
            "g1_place_count": 0,
            "graded_win_rate": 0.0,
        }

        history = self.horse_histories.get(horse_name)
        if history is None or history.empty:
            return features

        history = history.copy()
        finish_col = self._find_column(history, ["finish_position", "着順"])
        if finish_col is None:
            return features

        history["_finish"] = pd.to_numeric(history[finish_col], errors="coerce")
        valid = history.dropna(subset=["_finish"])

        if valid.empty:
            return features

        # 距離フィルタリング
        dist_col = self._find_column(valid, ["distance", "距離"])
        if dist_col:
            valid["_dist"] = pd.to_numeric(
                valid[dist_col].astype(str).str.replace(r"[^\d]", "", regex=True),
                errors="coerce",
            )
            mid_dist = valid[(valid["_dist"] >= 2000) & (valid["_dist"] <= 2400)]
            if len(mid_dist) > 0:
                features["runs_2000_2400"] = len(mid_dist)
                features["win_rate_2000_2400"] = (mid_dist["_finish"] == 1).mean()
                features["place_rate_2000_2400"] = (mid_dist["_finish"] <= 3).mean()

        # 阪神実績
        venue_col = self._find_column(valid, ["venue", "競馬場"])
        if venue_col:
            hanshin = valid[valid[venue_col].astype(str).str.contains("阪神")]
            if len(hanshin) > 0:
                features["runs_hanshin"] = len(hanshin)
                features["win_rate_hanshin"] = (hanshin["_finish"] == 1).mean()
                features["place_rate_hanshin"] = (hanshin["_finish"] <= 3).mean()

        # 芝実績
        surface_col = self._find_column(valid, ["surface", "馬場"])
        if surface_col:
            turf = valid[valid[surface_col].astype(str).str.contains("芝")]
            if len(turf) > 0:
                features["win_rate_turf"] = (turf["_finish"] == 1).mean()

        # 右回り実績（阪神・中山・小倉・中京・札幌・函館）
        right_venues = ["阪神", "中山", "小倉", "中京", "札幌", "函館"]
        if venue_col:
            right = valid[valid[venue_col].astype(str).apply(
                lambda x: any(v in x for v in right_venues)
            )]
            if len(right) > 0:
                features["win_rate_right"] = (right["_finish"] == 1).mean()

        # G1・重賞実績
        grade_col = self._find_column(valid, ["grade", "race_name"])
        if grade_col:
            race_names = valid[grade_col].astype(str)
            g1_mask = race_names.str.contains("G1|GⅠ|（G1）", na=False, regex=True)
            g1_races = valid[g1_mask]
            if len(g1_races) > 0:
                features["g1_wins"] = int((g1_races["_finish"] == 1).sum())
                features["g1_place_count"] = int((g1_races["_finish"] <= 3).sum())
                features["best_finish_g1"] = g1_races["_finish"].min()

            graded_mask = race_names.str.contains("G1|G2|G3|GⅠ|GⅡ|GⅢ", na=False, regex=True)
            graded = valid[graded_mask]
            if len(graded) > 0:
                features["graded_win_rate"] = (graded["_finish"] == 1).mean()

        return features

    # ────────────────────────────────────────
    # 騎手特徴量
    # ────────────────────────────────────────
    def compute_jockey_features(self, jockey_name: str) -> dict:
        """騎手の特徴量"""
        features = {
            "jockey_win_rate": 0.0,
            "jockey_place_rate": 0.0,
            "jockey_g1_wins": 0,
            "jockey_hanshin_win_rate": 0.0,
        }

        stats = self.jockey_stats.get(jockey_name)
        if stats:
            features["jockey_win_rate"] = float(stats.get("win_rate_2026", stats.get("win_rate", 0)) or 0)
            features["jockey_place_rate"] = float(stats.get("place_rate_2026", stats.get("place_rate", 0)) or 0)
            features["jockey_g1_wins"] = int(stats.get("g1_wins_career", stats.get("g1_wins", 0)) or 0)
            hanshin_runs = float(stats.get("hanshin_runs_2026", 1) or 1)
            hanshin_wins = float(stats.get("hanshin_wins_2026", 0) or 0)
            features["jockey_hanshin_win_rate"] = hanshin_wins / max(hanshin_runs, 1)

        return features

    # ────────────────────────────────────────
    # レース条件特徴量（木曜確定データ）
    # ────────────────────────────────────────
    def compute_race_condition_features(self, entry: dict) -> dict:
        """枠番・馬番・馬場状態などのレース条件特徴量"""
        features = {
            "post_position": self._safe_int(entry.get("post_position"), 0),
            "gate_number": self._safe_int(entry.get("gate_number"), 0),
            "weight_carried": self._safe_float(entry.get("weight_carried"), 0),
            "field_size": self._safe_int(entry.get("field_size"), 18),
        }

        # 馬体重
        hw = entry.get("horse_weight", "")
        if hw:
            weight_match = re.search(r"(\d+)", str(hw))
            if weight_match:
                features["horse_weight"] = int(weight_match.group(1))
            change_match = re.search(r"([+-]\d+)", str(hw))
            if change_match:
                features["weight_change"] = int(change_match.group(1))
            else:
                features["weight_change"] = 0
        else:
            features["horse_weight"] = 0
            features["weight_change"] = 0

        # 馬場状態コード
        condition = entry.get("track_condition", "良")
        features["track_condition_code"] = {
            "良": 0, "稍重": 1, "重": 2, "不良": 3
        }.get(str(condition), 0)

        return features

    # ────────────────────────────────────────
    # 宝塚記念過去傾向の統計特徴量
    # ────────────────────────────────────────
    def compute_takarazuka_trend_features(self, horse_name: str, age: int, sex: str) -> dict:
        """過去の宝塚記念傾向に基づくバイアス特徴量"""
        features = {
            "age_win_rate_historical": 0.0,     # その年齢の過去勝率
            "sex_win_rate_historical": 0.0,     # その性別の過去勝率
            "has_takarazuka_experience": 0,     # 宝塚記念出走経験
            "best_takarazuka_finish": np.nan,   # 宝塚記念最高着順
        }

        if self.takarazuka_history is None or self.takarazuka_history.empty:
            # 過去傾向データがない場合、既知の統計値を使用
            age_win_probs = {3: 0.0, 4: 0.3, 5: 0.5, 6: 0.1, 7: 0.05, 8: 0.05}
            features["age_win_rate_historical"] = age_win_probs.get(age, 0.0)
            sex_win_probs = {"牡": 0.85, "牝": 0.1, "セ": 0.05}
            features["sex_win_rate_historical"] = sex_win_probs.get(sex, 0.0)
            return features

        tk = self.takarazuka_history.copy()
        finish_col = self._find_column(tk, ["finish_position", "着順"])
        if finish_col:
            tk["_finish"] = pd.to_numeric(tk[finish_col], errors="coerce")

            # 年齢別勝率
            age_col = self._find_column(tk, ["age", "sex_age", "馬齢"])
            if age_col:
                tk["_age"] = pd.to_numeric(
                    tk[age_col].astype(str).str.extract(r"(\d+)")[0], errors="coerce"
                )
                age_group = tk[tk["_age"] == age]
                if len(age_group) > 0:
                    features["age_win_rate_historical"] = (age_group["_finish"] == 1).mean()

            # 宝塚記念出走経験
            name_col = self._find_column(tk, ["horse_name", "馬名"])
            if name_col:
                prev = tk[tk[name_col] == horse_name]
                if len(prev) > 0:
                    features["has_takarazuka_experience"] = 1
                    features["best_takarazuka_finish"] = prev["_finish"].min()

        return features

    # ────────────────────────────────────────
    # YouTube予想スコア
    # ────────────────────────────────────────
    def compute_youtube_features(self, horse_name: str) -> dict:
        """YouTube予想動画の集計データから特徴量を生成"""
        features = {
            "yt_score": 0.0,
            "yt_honmei_count": 0,
            "yt_mention_rate": 0.0,
        }
        if self.youtube_predictions is None or self.youtube_predictions.empty:
            return features

        row = self.youtube_predictions[self.youtube_predictions["horse_name"] == horse_name]
        if row.empty:
            return features

        r = row.iloc[0]
        features["yt_score"] = float(r.get("youtube_score", 0) or 0)
        features["yt_honmei_count"] = int(r.get("honmei_count", 0) or 0)
        features["yt_mention_rate"] = float(r.get("mention_rate", 0) or 0)
        return features

    # ────────────────────────────────────────
    # ニュース予想スコア
    # ────────────────────────────────────────
    def compute_news_features(self, horse_name: str) -> dict:
        """ニュース・新聞予想の集計データから特徴量を生成"""
        features = {
            "news_score": 0.0,
            "news_honmei_count": 0,
            "news_mention_rate": 0.0,
        }
        if self.news_predictions is None or self.news_predictions.empty:
            return features

        row = self.news_predictions[self.news_predictions["horse_name"] == horse_name]
        if row.empty:
            return features

        r = row.iloc[0]
        features["news_score"] = float(r.get("news_score", 0) or 0)
        features["news_honmei_count"] = int(r.get("honmei_count", 0) or 0)
        features["news_mention_rate"] = float(r.get("mention_rate", 0) or 0)
        return features

    # ────────────────────────────────────────
    # オッズ特徴量
    # ────────────────────────────────────────
    def compute_odds_features(self, horse_name: str) -> dict:
        """オッズデータから特徴量を生成"""
        features = {
            "win_odds": 0.0,
            "odds_popularity": 0,
            "odds_trend": 0.0,  # オッズの変動（下がっている=支持増）
        }
        if self.odds_data is None or self.odds_data.empty:
            return features

        horse_odds = self.odds_data[self.odds_data["horse_name"] == horse_name]
        if horse_odds.empty:
            return features

        # 最新のオッズ
        latest = horse_odds.iloc[-1]
        features["win_odds"] = float(latest.get("win_odds", 0) or 0)
        features["odds_popularity"] = int(latest.get("popularity", 0) or 0)

        # オッズの変動（複数時点ある場合）
        if len(horse_odds) >= 2:
            first_odds = float(horse_odds.iloc[0].get("win_odds", 0) or 0)
            last_odds = features["win_odds"]
            if first_odds > 0:
                features["odds_trend"] = (first_odds - last_odds) / first_odds
                # 正=オッズ低下（支持増）, 負=オッズ上昇（支持減）

        return features

    # ────────────────────────────────────────
    # 調教特徴量
    # ────────────────────────────────────────
    def compute_training_features(self, horse_name: str) -> dict:
        """調教（追い切り）データから特徴量を生成"""
        features = {
            "training_intensity": 3.0,
            "training_time_score": 0.0,
        }
        if self.training_data is None or self.training_data.empty:
            return features

        horse_train = self.training_data[self.training_data["horse_name"] == horse_name]
        if horse_train.empty:
            return features

        latest = horse_train.iloc[-1]
        features["training_intensity"] = float(latest.get("training_intensity", 3) or 3)

        # 調教タイムをスコア化
        time_str = str(latest.get("training_time", ""))
        if time_str:
            import re as _re
            match = _re.search(r"(\d+)\.(\d+)", time_str)
            if match:
                features["training_time_score"] = float(f"{match.group(1)}.{match.group(2)}")

        return features

    # ────────────────────────────────────────
    # 全特徴量の統合
    # ────────────────────────────────────────
    def build_feature_vector(self, entry: dict) -> dict:
        """1頭分の全特徴量を統合して辞書で返す"""
        horse_name = entry.get("horse_name", "")
        age = int(entry.get("age", 0) or 0)
        sex = str(entry.get("sex", ""))
        jockey_name = str(entry.get("jockey_name", ""))

        features = {"horse_name": horse_name}
        features.update(self.compute_horse_basic_features(horse_name, age, sex))
        features.update(self.compute_recent_form_features(horse_name))
        features.update(self.compute_course_aptitude_features(horse_name))
        features.update(self.compute_jockey_features(jockey_name))
        features.update(self.compute_race_condition_features(entry))
        features.update(self.compute_takarazuka_trend_features(horse_name, age, sex))
        features.update(self.compute_youtube_features(horse_name))
        features.update(self.compute_news_features(horse_name))
        features.update(self.compute_odds_features(horse_name))
        features.update(self.compute_training_features(horse_name))
        features.update(self.compute_extended_features(horse_name))

        return features

    # ────────────────────────────────────────
    # 拡張特徴量（上がり3F, 脚質, 血統, 対戦, スピード指数）
    # ────────────────────────────────────────
    def compute_extended_features(self, horse_name: str) -> dict:
        """拡張データから特徴量を生成"""
        features = {
            "best_last3f": 0.0,
            "avg_last3f": 0.0,
            "running_style_code": 0,
            "sire_turf2200_winrate": 0.0,
            "sire_hanshin_winrate": 0.0,
            "sire_heavy_winrate": 0.0,
            "head2head_winrate": 0.0,
            "speed_figure": 0.0,
            "rest_days": 0,
            "rest_performance_code": 0,
            "trainer_g1_wins_ext": 0,
            "weight_trend_code": 0,
        }
        if self.extended_data is None or self.extended_data.empty:
            return features

        row = self.extended_data[self.extended_data["horse_name"] == horse_name]
        if row.empty:
            return features

        r = row.iloc[0]
        features["best_last3f"] = float(r.get("best_last3f", 0) or 0)
        features["avg_last3f"] = float(r.get("avg_last3f", 0) or 0)
        features["running_style_code"] = {"nige": 0, "senko": 1, "sashi": 2, "oikomi": 3}.get(str(r.get("running_style", "")), 1)
        features["sire_turf2200_winrate"] = float(r.get("sire_turf2200_winrate", 0) or 0)
        features["sire_hanshin_winrate"] = float(r.get("sire_hanshin_winrate", 0) or 0)
        features["sire_heavy_winrate"] = float(r.get("sire_heavy_winrate", 0) or 0)

        h2h_total = int(r.get("head2head_total", 0) or 0)
        h2h_wins = int(r.get("head2head_wins", 0) or 0)
        features["head2head_winrate"] = h2h_wins / max(h2h_total, 1)

        features["speed_figure"] = float(r.get("speed_figure", 0) or 0)
        features["rest_days"] = int(r.get("rest_days", 0) or 0)
        features["rest_performance_code"] = {"good": 2, "ok": 1, "poor": 0}.get(str(r.get("rest_performance", "")), 1)
        features["trainer_g1_wins_ext"] = int(r.get("trainer_g1_wins", 0) or 0)
        features["weight_trend_code"] = {"stable": 2, "increasing": 1, "decreasing": 0}.get(str(r.get("weight_trend", "")), 1)

        return features

    def build_feature_matrix(self, entries: pd.DataFrame) -> pd.DataFrame:
        """出馬表（全頭分）から特徴量行列を生成"""
        rows = []
        for _, entry in entries.iterrows():
            features = self.build_feature_vector(entry.to_dict())
            rows.append(features)

        df = pd.DataFrame(rows)
        output_path = os.path.join(PROCESSED_DIR, "feature_matrix.csv")
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        print(f"特徴量行列保存: {output_path} ({len(df)}頭 × {len(df.columns)}特徴量)")
        return df

    # ────────────────────────────────────────
    # ユーティリティ
    # ────────────────────────────────────────
    @staticmethod
    def _find_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
        """候補名リストからDataFrameに存在するカラム名を返す"""
        for c in candidates:
            if c in df.columns:
                return c
        return None

    @staticmethod
    def _safe_int(val, default: int = 0) -> int:
        if val is None:
            return default
        try:
            import math
            f = float(val)
            if math.isnan(f):
                return default
            return int(f)
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _safe_float(val, default: float = 0.0) -> float:
        if val is None:
            return default
        try:
            import math
            f = float(val)
            if math.isnan(f):
                return default
            return f
        except (ValueError, TypeError):
            return default

    @staticmethod
    def _encode_sex(sex: str) -> int:
        return {"牡": 0, "牝": 1, "セ": 2}.get(sex, -1)

    @staticmethod
    def _encode_grade(race_name: str) -> int:
        if re.search(r"G1|GⅠ", race_name):
            return 4
        if re.search(r"G2|GⅡ", race_name):
            return 3
        if re.search(r"G3|GⅢ", race_name):
            return 2
        if re.search(r"OP|オープン|L|リステッド", race_name):
            return 1
        return 0
