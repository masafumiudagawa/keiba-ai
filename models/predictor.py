"""
競馬予測モデル

LightGBM をメインモデルとして使用し、
過去のレースデータで学習→宝塚記念の着順を予測する。

学習データ: 過去のG1/重賞レース結果（特に阪神芝2200m）
目的変数: 着順（3着以内 = 1, それ以外 = 0 の二値分類）
"""

import os
import pickle
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import KFold
from sklearn.metrics import accuracy_score, log_loss, roc_auc_score
from sklearn.preprocessing import LabelEncoder

from config.settings import MODEL_DIR, PROCESSED_DIR

os.makedirs(MODEL_DIR, exist_ok=True)

# 特徴量として使用するカラム（horse_name等の非数値カラムを除外）
FEATURE_COLUMNS = [
    # 馬基本
    "age", "sex_code", "career_wins", "career_runs",
    "career_win_rate", "career_place_rate",
    # 直近フォーム
    "last_1_finish", "last_2_finish", "last_3_finish",
    "avg_finish_last5", "last_1_last3f", "avg_last3f_last5",
    "days_since_last", "prev_race_grade_code",
    # 距離・コース適性
    "win_rate_2000_2400", "place_rate_2000_2400", "runs_2000_2400",
    "win_rate_hanshin", "place_rate_hanshin", "runs_hanshin",
    "win_rate_turf", "win_rate_right",
    "g1_wins", "g1_place_count", "graded_win_rate", "best_finish_g1",
    # 騎手
    "jockey_win_rate", "jockey_place_rate",
    "jockey_g1_wins", "jockey_hanshin_win_rate",
    # レース条件
    "post_position", "gate_number", "weight_carried",
    "horse_weight", "weight_change", "track_condition_code",
    "field_size",
    # 宝塚記念傾向
    "age_win_rate_historical", "sex_win_rate_historical",
    "has_takarazuka_experience", "best_takarazuka_finish",
    # YouTube・ニュース予想（世論）
    "yt_score", "yt_honmei_count", "yt_mention_rate",
    "news_score", "news_honmei_count", "news_mention_rate",
    # オッズ
    "win_odds", "odds_popularity", "odds_trend",
    # 調教
    "training_intensity", "training_time_score",
    # 拡張データ
    "best_last3f", "avg_last3f", "running_style_code",
    "sire_turf2200_winrate", "sire_hanshin_winrate", "sire_heavy_winrate",
    "head2head_winrate", "speed_figure",
    "rest_days", "rest_performance_code",
    "trainer_g1_wins_ext", "weight_trend_code",
]


class TakarazukaPredictor:
    """宝塚記念の着順予測モデル"""

    def __init__(self):
        self.model = None
        self.feature_columns = FEATURE_COLUMNS
        self.model_path = os.path.join(MODEL_DIR, "takarazuka_lgb.pkl")

    def train(self, training_data: pd.DataFrame, target_col: str = "is_top3"):
        """学習データでモデルを訓練する

        Args:
            training_data: 特徴量 + 目的変数を含むDataFrame
            target_col: 目的変数のカラム名（デフォルト: 3着以内フラグ）
        """
        # 目的変数がなければ着順から生成
        if target_col not in training_data.columns:
            if "finish_position" in training_data.columns:
                training_data = training_data.copy()
                training_data["_finish"] = pd.to_numeric(
                    training_data["finish_position"], errors="coerce"
                )
                training_data["is_top3"] = (training_data["_finish"] <= 3).astype(int)
                target_col = "is_top3"
            else:
                raise ValueError("目的変数が見つかりません")

        # 使用する特徴量カラムを選択
        available_cols = [c for c in self.feature_columns if c in training_data.columns]
        X = training_data[available_cols].copy()
        y = training_data[target_col].copy()

        # 欠損値の処理
        X = X.fillna(-1)

        print(f"学習データ: {len(X)}行 × {len(available_cols)}特徴量")
        print(f"正例(3着以内): {y.sum()}, 負例: {len(y) - y.sum()}")

        # LightGBM パラメータ
        params = {
            "objective": "binary",
            "metric": "binary_logloss",
            "boosting_type": "gbdt",
            "num_leaves": 31,
            "learning_rate": 0.05,
            "feature_fraction": 0.8,
            "bagging_fraction": 0.8,
            "bagging_freq": 5,
            "verbose": -1,
            "n_estimators": 500,
            "early_stopping_rounds": 50,
            "is_unbalance": True,
        }

        # クロスバリデーション
        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        scores = []

        for fold, (train_idx, val_idx) in enumerate(kf.split(X)):
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]

            model = lgb.LGBMClassifier(**params)
            model.fit(
                X_train, y_train,
                eval_set=[(X_val, y_val)],
            )

            val_pred = model.predict_proba(X_val)[:, 1]
            try:
                auc = roc_auc_score(y_val, val_pred)
                scores.append(auc)
                print(f"  Fold {fold + 1}: AUC = {auc:.4f}")
            except ValueError:
                pass

        if scores:
            print(f"  平均 AUC: {np.mean(scores):.4f} ± {np.std(scores):.4f}")

        # 全データで最終モデルを学習
        self.model = lgb.LGBMClassifier(**{
            k: v for k, v in params.items() if k != "early_stopping_rounds"
        })
        self.model.fit(X, y)

        # 特徴量重要度の表示
        self._show_feature_importance(available_cols)

        # モデル保存
        self._save_model(available_cols)

        return self.model

    def predict(self, feature_matrix: pd.DataFrame, force_rule_based: bool = False) -> pd.DataFrame:
        """予測を実行して結果を返す

        LightGBMモデルとルールベースのアンサンブル予測。
        枠番・馬体重が未確定の場合はルールベースを優先する。
        """
        # 枠番が未確定ならルールベース主体
        has_gate = "gate_number" in feature_matrix.columns and (feature_matrix["gate_number"] > 0).any()

        if not force_rule_based and not has_gate:
            print("枠番未確定のためルールベース予測を使用（木曜以降はLightGBMも併用）")
            force_rule_based = True

        if not force_rule_based:
            if self.model is None:
                self._load_model()

        if force_rule_based or self.model is None:
            return self._rule_based_predict(feature_matrix)

        # LightGBMモデル予測
        available_cols = [c for c in self.feature_columns if c in feature_matrix.columns]
        X = feature_matrix[available_cols].fillna(-1)

        trained_cols = self.model.feature_name_
        if trained_cols is not None:
            for col in trained_cols:
                if col not in X.columns:
                    X[col] = -1
            X = X[trained_cols]

        probs_lgb = self.model.predict_proba(X)[:, 1]

        # ルールベース予測も取得してアンサンブル
        rule_results = self._rule_based_predict(feature_matrix)
        probs_rule = rule_results.set_index("horse_name")["win_probability"]

        # アンサンブル: LightGBM 40% + ルールベース 60%
        results = feature_matrix[["horse_name"]].copy() if "horse_name" in feature_matrix.columns \
            else pd.DataFrame(index=feature_matrix.index)

        combined = []
        for i, row in results.iterrows():
            name = row.get("horse_name", "")
            lgb_p = probs_lgb[i] if i < len(probs_lgb) else 0
            rule_p = probs_rule.get(name, 0)
            combined.append(lgb_p * 0.4 + rule_p * 0.6)

        results["win_probability"] = combined
        results["rank"] = results["win_probability"].rank(ascending=False).astype(int)
        results = results.sort_values("rank")

        return results

    def _rule_based_predict(self, feature_matrix: pd.DataFrame) -> pd.DataFrame:
        """学習データがない場合のルールベース予測

        宝塚記念の過去傾向データに基づくスコアリング:
        - 4-5歳が有利（配点大）
        - G1実績がある馬が有利
        - 直近成績が良い馬が有利
        - 阪神・中距離実績がある馬が有利
        - 騎手力
        """
        fm = feature_matrix.copy()
        fm = fm.fillna(0)

        scores = pd.Series(0.0, index=fm.index)

        # 1. 馬齢スコア（最重要: 宝塚記念は4-5歳が圧倒的に有利）
        if "age" in fm.columns:
            age_score = fm["age"].map({4: 20, 5: 25, 6: 8, 7: 3, 8: 2}).fillna(0)
            scores += age_score

        # 2. 直近成績スコア
        if "last_1_finish" in fm.columns:
            scores += (18 - fm["last_1_finish"].clip(1, 18)) * 1.5
        if "last_2_finish" in fm.columns:
            scores += (18 - fm["last_2_finish"].clip(1, 18)) * 0.8
        if "last_3_finish" in fm.columns:
            scores += (18 - fm["last_3_finish"].clip(1, 18)) * 0.5

        # 3. G1・重賞実績スコア
        if "g1_wins" in fm.columns:
            scores += fm["g1_wins"] * 15
        if "g1_place_count" in fm.columns:
            scores += fm["g1_place_count"] * 5
        if "graded_win_rate" in fm.columns:
            scores += fm["graded_win_rate"] * 20

        # 4. 距離適性スコア
        if "win_rate_2000_2400" in fm.columns:
            scores += fm["win_rate_2000_2400"] * 15
        if "place_rate_2000_2400" in fm.columns:
            scores += fm["place_rate_2000_2400"] * 10

        # 5. 阪神適性スコア
        if "win_rate_hanshin" in fm.columns:
            scores += fm["win_rate_hanshin"] * 10
        if "place_rate_hanshin" in fm.columns:
            scores += fm["place_rate_hanshin"] * 8

        # 6. 芝・右回り適性
        if "win_rate_turf" in fm.columns:
            scores += fm["win_rate_turf"] * 8
        if "win_rate_right" in fm.columns:
            scores += fm["win_rate_right"] * 5

        # 7. 通算成績
        if "career_win_rate" in fm.columns:
            scores += fm["career_win_rate"] * 15
        if "career_place_rate" in fm.columns:
            scores += fm["career_place_rate"] * 10

        # 8. 騎手力（G1実績を重視 + シーズン勝率も加味）
        #    武豊(G1:79,勝率14%) > 北村友(G1:6,勝率13%)
        #    ルメール(G1:48,勝率20%) > レーン(G1:22,勝率19%)
        if "jockey_g1_wins" in fm.columns:
            # G1勝利数をログスケールで評価（0→0, 6→8, 22→14, 48→18, 79→20）
            import numpy as _np
            g1 = fm["jockey_g1_wins"].clip(0, 100)
            scores += _np.log1p(g1) * 4.5
        if "jockey_win_rate" in fm.columns:
            scores += fm["jockey_win_rate"] * 25
        if "jockey_place_rate" in fm.columns:
            scores += fm["jockey_place_rate"] * 10

        # 9. 宝塚記念経験
        if "has_takarazuka_experience" in fm.columns:
            scores += fm["has_takarazuka_experience"] * 5

        # 10. 上がり3F（速いほど高スコア）
        if "last_1_last3f" in fm.columns:
            l3f = fm["last_1_last3f"]
            valid_l3f = l3f[l3f > 0]
            if len(valid_l3f) > 0:
                scores += (40 - l3f.clip(30, 40)) * 2  # 33秒→14点, 36秒→8点

        # 11. 前走間隔（中2-8週が理想）
        if "days_since_last" in fm.columns:
            interval = fm["days_since_last"]
            ideal = ((interval >= 14) & (interval <= 56)).astype(int)
            scores += ideal * 5

        # 12. YouTube予想家スコア
        if "yt_score" in fm.columns:
            scores += fm["yt_score"] * 2
        if "yt_honmei_count" in fm.columns:
            scores += fm["yt_honmei_count"] * 3

        # 13. ニュース・新聞予想スコア
        if "news_score" in fm.columns:
            scores += fm["news_score"] * 2
        if "news_honmei_count" in fm.columns:
            scores += fm["news_honmei_count"] * 3

        # 14. オッズ（低いほど高評価、ただし過剰評価を避けるため控えめに）
        if "win_odds" in fm.columns:
            odds = fm["win_odds"]
            valid_odds = odds[odds > 0]
            if len(valid_odds) > 0:
                # オッズの逆数（人気馬ほど高スコア）
                scores += (1.0 / odds.clip(1, 200)) * 30
        if "odds_trend" in fm.columns:
            scores += fm["odds_trend"] * 10  # オッズ低下（支持増）は加点

        # 15. 調教評価
        if "training_intensity" in fm.columns:
            scores += (fm["training_intensity"] - 3) * 5

        # ═══ 拡張特徴量 ═══

        # 16. 上がり3F（最重要: 宝塚記念で上がり最速馬は複勝率100%）
        if "best_last3f" in fm.columns:
            l3f = fm["best_last3f"]
            valid = l3f[l3f > 30]
            if len(valid) > 0:
                scores += (37 - l3f.clip(32, 37)) * 5  # 33.0→20pt, 35.0→10pt, 36.0→5pt

        # 17. スピード指数（能力の絶対値）
        if "speed_figure" in fm.columns:
            sf = fm["speed_figure"]
            valid_sf = sf[sf > 0]
            if len(valid_sf) > 0:
                scores += (sf - 90).clip(0, 30) * 1.5  # 115→37.5pt, 100→15pt

        # 18. 血統適性（種牡馬の芝2200m勝率）
        if "sire_turf2200_winrate" in fm.columns:
            scores += fm["sire_turf2200_winrate"] * 30  # 20%→6pt
        if "sire_hanshin_winrate" in fm.columns:
            scores += fm["sire_hanshin_winrate"] * 20
        if "sire_heavy_winrate" in fm.columns:
            # 馬場が重い場合に重馬場適性をボーナス
            scores += fm["sire_heavy_winrate"] * 5

        # 19. 対戦成績
        if "head2head_winrate" in fm.columns:
            scores += fm["head2head_winrate"] * 15

        # 20. 脚質×展開（宝塚記念は前有利: 逃げ/先行にボーナス）
        if "running_style_code" in fm.columns:
            style_bonus = fm["running_style_code"].map({0: 8, 1: 5, 2: 2, 3: 0}).fillna(0)
            scores += style_bonus

        # 21. 休養明け適性
        if "rest_performance_code" in fm.columns:
            scores += fm["rest_performance_code"] * 3

        # 22. 調教師G1実績
        if "trainer_g1_wins_ext" in fm.columns:
            import numpy as _np2
            scores += _np2.log1p(fm["trainer_g1_wins_ext"]) * 3

        # 23. 馬体重トレンド（安定が最良）
        if "weight_trend_code" in fm.columns:
            scores += fm["weight_trend_code"] * 2  # stable=4, increasing=2, decreasing=0

        # 正規化して確率に変換
        score_min = scores.min()
        score_range = scores.max() - score_min
        if score_range > 0:
            probs = (scores - score_min) / score_range
        else:
            probs = pd.Series(1.0 / len(scores), index=scores.index)

        # ソフトマックス的に正規化
        probs = probs / probs.sum()

        results = pd.DataFrame({"horse_name": fm.get("horse_name", fm.index)})
        results["win_probability"] = probs.values
        results["score"] = scores.values
        results["rank"] = results["win_probability"].rank(ascending=False).astype(int)
        results = results.sort_values("rank")

        return results

    def _show_feature_importance(self, feature_names: list):
        """特徴量重要度を表示"""
        if self.model is None:
            return
        importance = self.model.feature_importances_
        imp_df = pd.DataFrame({
            "feature": feature_names,
            "importance": importance,
        }).sort_values("importance", ascending=False)

        print("\n特徴量重要度 TOP15:")
        for _, row in imp_df.head(15).iterrows():
            bar = "█" * int(row["importance"] / imp_df["importance"].max() * 30)
            print(f"  {row['feature']:30s} {row['importance']:6.0f} {bar}")

    def _save_model(self, feature_names: list):
        """モデルを保存"""
        data = {
            "model": self.model,
            "feature_columns": feature_names,
        }
        with open(self.model_path, "wb") as f:
            pickle.dump(data, f)
        print(f"モデル保存: {self.model_path}")

    def _load_model(self):
        """保存済みモデルを読み込む"""
        if os.path.exists(self.model_path):
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
            self.model = data["model"]
            self.feature_columns = data.get("feature_columns", FEATURE_COLUMNS)
            print(f"モデル読み込み: {self.model_path}")
        else:
            print(f"モデルファイルが見つかりません: {self.model_path}")
