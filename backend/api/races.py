"""レース管理 API（CRUD + 汎用予測）"""
import os, sys, json, shutil
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import pandas as pd
import numpy as np

router = APIRouter()

RACES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "races")
COMMON_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data", "common")


# ── モデル ──

class RaceCreate(BaseModel):
    id: str
    name: str
    date: str
    venue: str
    distance: int
    surface: str = "芝"
    grade: str = "G1"
    course_type: str = ""
    post_time: str = ""
    trends: dict = {}


class WeightedPredictionRequest(BaseModel):
    weights: dict = {}


# ── ヘルパー ──

def _race_dir(race_id: str) -> str:
    d = os.path.join(RACES_DIR, race_id)
    if not os.path.isdir(d):
        raise HTTPException(404, f"Race not found: {race_id}")
    return d


def _load_config(race_id: str) -> dict:
    path = os.path.join(_race_dir(race_id), "config.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _load_csv(race_id: str, filename: str) -> pd.DataFrame:
    path = os.path.join(_race_dir(race_id), filename)
    if os.path.exists(path):
        return pd.read_csv(path, encoding="utf-8-sig")
    return pd.DataFrame()


# ── レース一覧 ──

@router.get("/races")
def list_races():
    races = []
    if not os.path.isdir(RACES_DIR):
        return {"races": []}
    for name in sorted(os.listdir(RACES_DIR)):
        config_path = os.path.join(RACES_DIR, name, "config.json")
        if os.path.exists(config_path):
            with open(config_path, encoding="utf-8") as f:
                cfg = json.load(f)
            races.append({
                "id": cfg.get("id", name),
                "name": cfg.get("name", name),
                "date": cfg.get("date", ""),
                "venue": cfg.get("venue", ""),
                "distance": cfg.get("distance", 0),
                "surface": cfg.get("surface", ""),
                "grade": cfg.get("grade", ""),
            })
    return {"races": races}


# ── レース追加 ──

@router.post("/races")
def create_race(req: RaceCreate):
    race_dir = os.path.join(RACES_DIR, req.id)
    os.makedirs(race_dir, exist_ok=True)

    config = req.dict()
    config_path = os.path.join(race_dir, "config.json")
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    # 空のエントリーCSV作成
    entries_path = os.path.join(race_dir, "entries.csv")
    if not os.path.exists(entries_path):
        pd.DataFrame(columns=["horse_name", "sex", "age", "weight_carried", "jockey_name", "sire"]).to_csv(
            entries_path, index=False, encoding="utf-8-sig"
        )

    return {"status": "created", "id": req.id}


# ── レース削除 ──

@router.delete("/races/{race_id}")
def delete_race(race_id: str):
    race_dir = os.path.join(RACES_DIR, race_id)
    if os.path.isdir(race_dir):
        shutil.rmtree(race_dir)
    return {"status": "deleted"}


# ── レース設定取得/更新 ──

@router.get("/races/{race_id}/config")
def get_config(race_id: str):
    return _load_config(race_id)


@router.put("/races/{race_id}/config")
def update_config(race_id: str, config: dict):
    path = os.path.join(_race_dir(race_id), "config.json")
    existing = _load_config(race_id)
    existing.update(config)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)
    return existing


# ── 特徴量生データ取得（フロントエンドでのリアルタイム再計算用）──

@router.get("/races/{race_id}/features")
def get_features(race_id: str):
    """全馬の特徴量生データを返す。フロントエンドでウェイト乗算→スコア再計算。"""
    config = _load_config(race_id)
    entries = _load_csv(race_id, "entries.csv")
    history = _load_csv(race_id, "horse_history.csv")
    extended = _load_csv(race_id, "extended_data.csv")
    jockey = pd.DataFrame()
    jockey_path = os.path.join(COMMON_DIR, "jockey_stats.csv")
    if os.path.exists(jockey_path):
        jockey = pd.read_csv(jockey_path, encoding="utf-8-sig")
    youtube = _load_csv(race_id, "youtube.csv")
    news = _load_csv(race_id, "news.csv")
    training = _load_csv(race_id, "training.csv")
    odds_df = _load_csv(race_id, "odds.csv")
    weather = _load_csv(race_id, "weather.csv")

    trends = config.get("trends", {})
    age_bias = trends.get("age_bias", {"4": 20, "5": 25, "6": 8})
    style_bias = trends.get("style_bias", {"nige": 8, "senko": 5, "sashi": 2, "oikomi": 0})

    horses = []
    if entries.empty:
        return {"features": [], "config": config}

    for _, e in entries.dropna(subset=["horse_name"]).iterrows():
        name = e.get("horse_name", "")
        age = int(e.get("age", 0) or 0)

        # 戦績
        h = history[history["horse_name"] == name] if not history.empty else pd.DataFrame()
        career_runs = len(h)
        fp = pd.to_numeric(h["finish_position"], errors="coerce").dropna() if not h.empty and "finish_position" in h.columns else pd.Series(dtype=float)
        career_wins = int((fp == 1).sum())
        g1h = h[h["grade"] == "G1"] if not h.empty and "grade" in h.columns else pd.DataFrame()
        g1fp = pd.to_numeric(g1h["finish_position"], errors="coerce").dropna() if not g1h.empty else pd.Series(dtype=float)
        g1_wins = int((g1fp == 1).sum())
        g1_place = int((g1fp <= 3).sum())
        last1 = float(fp.iloc[0]) if len(fp) > 0 else 18
        last2 = float(fp.iloc[1]) if len(fp) > 1 else 18

        # 拡張データ
        ext = extended[extended["horse_name"] == name].iloc[0].to_dict() if not extended.empty and name in extended["horse_name"].values else {}
        best3f = float(ext.get("best_last3f", 0) or 0)
        speed = float(ext.get("speed_figure", 0) or 0)
        style_code = {"nige": 0, "senko": 1, "sashi": 2, "oikomi": 3}.get(str(ext.get("running_style", "")), 1)
        style_name = str(ext.get("running_style", "senko"))

        # 騎手
        jname = str(e.get("jockey_name", ""))
        jrow = jockey[jockey["jockey_name"] == jname].iloc[0].to_dict() if not jockey.empty and jname in jockey["jockey_name"].values else {}
        j_g1 = int(jrow.get("g1_wins_career", 0) or 0)
        j_wr = float(jrow.get("win_rate_2026", 0) or 0)

        # YouTube/News
        yt_score = 0
        if not youtube.empty and name in youtube["horse_name"].values:
            yt_score = float(youtube[youtube["horse_name"] == name].iloc[0].get("youtube_score", 0) or 0)
        news_score = 0
        if not news.empty and name in news["horse_name"].values:
            news_score = float(news[news["horse_name"] == name].iloc[0].get("news_score", 0) or 0)

        # 調教
        train_val = 3.0
        if not training.empty and name in training["horse_name"].values:
            train_val = float(training[training["horse_name"] == name].iloc[0].get("training_intensity", 3) or 3)

        # 直近5走の馬柱データ
        import math
        recent_5 = []
        if not h.empty:
            for _, race in h.head(5).iterrows():
                r_date = str(race.get("race_date", ""))
                if "/" in r_date:
                    parts = r_date.split("/")
                    r_date = f"{parts[1]}/{parts[2]}" if len(parts) >= 3 else r_date
                r_finish = race.get("finish_position", "")
                try:
                    r_finish = int(float(r_finish)) if not (isinstance(r_finish, float) and math.isnan(r_finish)) else ""
                except (ValueError, TypeError):
                    r_finish = ""
                recent_5.append({
                    "date": r_date,
                    "venue": str(race.get("venue", "")),
                    "race": str(race.get("race_name", ""))[:6],
                    "dist": int(float(race.get("distance", 0) or 0)),
                    "finish": r_finish,
                    "grade": str(race.get("grade", "")),
                    "time": str(race.get("finish_time", "")),
                    "last3f": str(race.get("last_3f", "")),
                    "passing": str(ext.get("passing_pattern", "")),
                })

        # 枠番・馬番
        import math as _math
        def _si(v, d=0):
            if v is None: return d
            try:
                f = float(v)
                return d if _math.isnan(f) else int(f)
            except: return d

        gate_num = _si(e.get("gate_number"))
        post_pos = _si(e.get("post_position"))

        style_labels = {"nige": "逃げ", "senko": "先行", "sashi": "差し", "oikomi": "追込"}

        # 各カテゴリの生スコア（ウェイト1.0x時の値）
        horse = {
            "horse_name": name,
            "jockey": jname,
            "age": age,
            "sex": str(e.get("sex", "")),
            "sire": str(e.get("sire", ext.get("sire", ""))),
            "dam_sire": str(ext.get("dam_sire", "")),
            "trainer": str(ext.get("trainer", "")),
            "gate_number": gate_num,
            "post_position": post_pos,
            "weight": str(ext.get("best_weight", "")),
            "running_style_label": style_labels.get(style_name, ""),
            "career": f"{career_runs}走{career_wins}勝",
            "owner": str(ext.get("owner", "")),
            "coat_color": str(ext.get("coat_color", "")),
            "english_name": str(ext.get("english_name", "")),
            "total_prize": str(ext.get("total_prize", "")),
            "netkeiba_id": str(ext.get("netkeiba_id", "")),
            "recent_5": recent_5,
            "scores": {
                "age": float(age_bias.get(str(age), 0)),
                "recent_form": (18 - min(max(last1, 1), 18)) * 1.5 + (18 - min(max(last2, 1), 18)) * 0.8,
                "g1_record": float(np.log1p(g1_wins) * 15 + g1_place * 5),
                "distance_aptitude": 0,  # 距離適性は汎用計算が必要なため簡略化
                "jockey": float(np.log1p(j_g1) * 4.5 + j_wr * 25),
                "last_3f": float((37 - min(max(best3f, 32), 37)) * 5) if best3f > 0 else 0,
                "speed_figure": float((speed - 90) * 1.5) if speed > 0 else 0,
                "pedigree": float(ext.get("sire_turf2200_winrate", 0) or 0) * 30 + float(ext.get("sire_hanshin_winrate", 0) or 0) * 20,
                "public_opinion": yt_score * 2 + news_score * 2,
                "training": (train_val - 3) * 5,
                "running_style": float(style_bias.get(style_name, 0)),
                "head_to_head": float(ext.get("head2head_winrate", 0) or 0) * 15 if ext.get("head2head_total") else 0,
                "rest": float({"good": 6, "ok": 3, "poor": 0}.get(str(ext.get("rest_performance", "")), 3)),
                "trainer": float(np.log1p(int(ext.get("trainer_g1_wins", 0) or 0)) * 3),
                "weight_trend": float({"stable": 4, "increasing": 2, "decreasing": 0}.get(str(ext.get("weight_trend", "")), 2)),
            },
            "raw": {
                "g1_wins": g1_wins,
                "g1_place": g1_place,
                "best_last3f": best3f,
                "speed_figure": speed,
                "running_style": style_name,
                "jockey_g1": j_g1,
                "yt_score": yt_score,
                "news_score": news_score,
                "training": train_val,
                "last_1_finish": last1,
                "last_2_finish": last2,
                "win_odds": float(odds_df[odds_df["horse_name"].str.strip() == name.strip()].iloc[0].get("win_odds", 0)) if not odds_df.empty and name.strip() in odds_df["horse_name"].str.strip().values else 0,
                "popularity": int(odds_df[odds_df["horse_name"].str.strip() == name.strip()].iloc[0].get("popularity", 0)) if not odds_df.empty and name.strip() in odds_df["horse_name"].str.strip().values else 0,
            },
        }
        horses.append(horse)

    weather_info = weather.iloc[-1].to_dict() if not weather.empty else {}

    return {"features": horses, "config": config, "weather": weather_info}
