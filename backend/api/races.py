"""レース管理 API（CRUD + 汎用予測）"""
import os, sys, json, shutil, re, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
import pandas as pd
import numpy as np
import requests as http_requests

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

        # 通算勝率
        career_win_rate = career_wins / max(career_runs, 1)

        # コース経験: 今回と同じ競馬場での過去走
        race_venue = config.get("venue", "")
        venue_exp = 0.0
        if not h.empty and "venue" in h.columns and race_venue:
            venue_runs = h[h["venue"] == race_venue]
            if len(venue_runs) > 0:
                v_fp = pd.to_numeric(venue_runs["finish_position"], errors="coerce").dropna()
                if len(v_fp) > 0:
                    v_wr = float((v_fp <= 3).sum()) / len(v_fp)
                    venue_exp = v_wr * 10 + min(len(v_fp), 5) * 1.5

        # 拡張データ
        ext = extended[extended["horse_name"] == name].iloc[0].to_dict() if not extended.empty and name in extended["horse_name"].values else {}
        best3f = float(ext.get("best_last3f", 0) or 0)
        speed = float(ext.get("speed_figure", 0) or 0)
        style_code = {"nige": 0, "senko": 1, "sashi": 2, "oikomi": 3}.get(str(ext.get("running_style", "")), 1)
        style_name = str(ext.get("running_style", "senko"))

        # 距離適性: 今回の距離±400m以内の過去走で好走率を計算
        race_dist = config.get("distance", 2000)
        race_surface = config.get("surface", "芝")
        dist_apt = 0.0
        if not h.empty and "distance" in h.columns:
            dist_col = pd.to_numeric(h["distance"], errors="coerce")
            surf_match = h["surface"] == race_surface if "surface" in h.columns else pd.Series(True, index=h.index)
            near = h[(dist_col >= race_dist - 400) & (dist_col <= race_dist + 400) & surf_match]
            if len(near) > 0:
                near_fp = pd.to_numeric(near["finish_position"], errors="coerce").dropna()
                if len(near_fp) > 0:
                    win_rate = float((near_fp <= 3).sum()) / len(near_fp)
                    avg_finish = float(near_fp.mean())
                    # スコア: 好走率(0-1) * 20 + (10 - 平均着順) * 1.5 + 経験値ボーナス
                    dist_apt = win_rate * 20 + max(10 - avg_finish, 0) * 1.5 + min(len(near_fp), 5) * 1.0

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
                    "passing": str(race.get("passing_pattern", "")),
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

        # 対戦成績の事前計算
        h2h_total = int(ext.get("head2head_total", 0) or 0)
        h2h_wins = int(ext.get("head2head_wins", 0) or 0)
        h2h_wr = h2h_wins / max(h2h_total, 1)

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
            "netkeiba_id": str(ext.get("netkeiba_id", "")).replace(".0", "").strip(),
            "recent_5": recent_5,
            "scores": {
                # ── Tier1: 最重要（max 25-32） ──
                # 1. 前走着順: 直近成績が最も予測に寄与（ML研究で一貫して上位）
                "last_finish": (18 - min(max(last1, 1), 18)) * 1.5,                      # max 25.5
                # 2. スピード指数: 能力の絶対値（芝での精度低下を考慮し係数抑制）
                "speed_figure": float((speed - 90) * 1.2) if speed > 0 else 0,            # max 30
                # 3. 上がり3F: 中距離G1で決定的。最速馬の複勝率が極めて高い
                "last_3f": float((37 - min(max(best3f, 32), 37)) * 5) if best3f > 0 else 0,  # max 25
                # 4. G1勝利: 最高峰での実績。対数で差を圧縮
                "g1_wins": min(float(np.log1p(g1_wins) * 15), 25),                        # max 25
                # 5. 距離適性: 距離±400m・同馬場の好走率+平均着順+経験値（G1馬はすでに適性ありなので係数抑制）
                "distance_aptitude": round(dist_apt * 0.7, 1),                            # max 28

                # ── Tier2: 重要（max 12-20） ──
                # 6. 馬齢: config.jsonで設定（レースごとに異なる）
                "age": float(age_bias.get(str(age), 0)),                                  # max 25(config依存)
                # 7. 騎手G1実績: ML分析で常に上位因子
                "jockey_g1": float(np.log1p(j_g1) * 4.5),                                 # max 20
                # 8. G1複勝: 安定感の指標。G1勝利(max25)を超えない設計
                "g1_places": min(float(g1_place * 3), 18),                                 # max 18
                # 9. 通算勝率: 安定した予測因子
                "career_win_rate": round(career_win_rate * 15, 1),                         # max 15
                # 10. 騎手シーズン勝率: 現在の好調さを反映
                "jockey_win_rate": min(float(j_wr * 50), 15),                              # max 15
                # 11. 調教: 追い切り速い馬は遅い馬の3-10倍の勝率
                "training": (train_val - 3) * 6.5,                                         # max 13
                # 12. 2走前着順: 安定感の指標（前走より減衰）
                "second_last_finish": (18 - min(max(last2, 1), 18)) * 0.7,                 # max 11.9

                # ── Tier3: 中程度（max 5-12） ──
                # 13. 対戦成績: 直接対決の相性（サンプル少のため抑制）
                "head_to_head": min(h2h_wr * 12, 12) if h2h_total > 0 else 0,             # max 12
                # 14. 厩舎力: トレーナーは予測に有意（学術研究）
                "trainer_score": float(np.log1p(int(ext.get("trainer_g1_wins", 0) or 0)) * 4.2),  # max 11
                # 15. コース経験: 同競馬場の好走率+出走経験
                "venue_experience": min(round(venue_exp * 0.8, 1), 10),                    # max 10
                # 16. 脚質: 展開依存。config.jsonで設定
                "running_style": float(style_bias.get(style_name, 0)) * 1.2,               # max 9.6
                # 17. 休養: 近年の休養明け好走率向上を反映
                "rest": float({"good": 9, "ok": 5, "poor": 1}.get(str(ext.get("rest_performance", "")), 5)),  # max 9
                # 18. 血統（距離適性）: 未知の距離適性予測に有用
                "pedigree_distance": min(float(ext.get("sire_turf2200_winrate", 0) or 0) * 25, 8),   # max 8
                # 19. 体重推移: ±2kg安定が最高勝率
                "weight_trend": float({"stable": 7, "increasing": 4, "decreasing": 2}.get(str(ext.get("weight_trend", "")), 4)),  # max 7

                # ── Tier4: 補助（max 5-8） ──
                # 20. ニュース世論: プロ記者の知見。キャップは設けつつ差別化を確保
                "news": min(news_score * 0.6, 12),                                         # max 12
                # 21. YouTube世論: 市場の集合知として参考。ニュースよりやや抑制
                "youtube": min(yt_score * 0.5, 12),                                        # max 12
                # 22. 血統（競馬場適性）: コース特性は父から遺伝
                "pedigree_venue": min(float(ext.get("sire_hanshin_winrate", 0) or 0) * 20, 6),  # max 6
                # 23. 血統（重馬場適性）: 重馬場時に差別化要因
                "pedigree_heavy": min(float(ext.get("sire_heavy_winrate", 0) or 0) * 15, 5),    # max 5
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


# ── 馬画像 API ──

_photo_cache: dict[str, list[str]] = {}

@router.get("/horses/{netkeiba_id}/photos")
def get_horse_photos(netkeiba_id: str):
    """netkeibaから馬の写真ID一覧を取得（キャッシュ付き）"""
    if not netkeiba_id or not netkeiba_id.isdigit():
        return {"photos": []}

    if netkeiba_id in _photo_cache:
        return {"photos": _photo_cache[netkeiba_id]}

    try:
        time.sleep(0.5)
        resp = http_requests.get(
            f"https://db.netkeiba.com/horse/{netkeiba_id}/",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if resp.status_code != 200:
            return {"photos": []}

        photo_ids = re.findall(
            r'show_photo\.php\?horse_id=' + netkeiba_id + r'&no=(\d+)&tn=yes',
            resp.text,
        )
        # 重複除去して最大8枚
        seen = set()
        unique = []
        for pid in photo_ids:
            if pid not in seen:
                seen.add(pid)
                unique.append(pid)
        unique = unique[:8]

        _photo_cache[netkeiba_id] = unique
        return {"photos": unique}
    except Exception:
        return {"photos": []}


@router.get("/horses/{netkeiba_id}/photo/{photo_id}")
def proxy_horse_photo(netkeiba_id: str, photo_id: str):
    """netkeibaの馬画像をプロキシして返す"""
    if not netkeiba_id.isdigit() or not photo_id.isdigit():
        raise HTTPException(400, "Invalid ID")

    try:
        resp = http_requests.get(
            f"https://db.netkeiba.com/show_photo.php?horse_id={netkeiba_id}&no={photo_id}&tn=no&tmp=no",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        if resp.status_code != 200 or not resp.content:
            raise HTTPException(404, "Photo not found")

        return Response(
            content=resp.content,
            media_type=resp.headers.get("Content-Type", "image/jpeg"),
            headers={"Cache-Control": "public, max-age=86400"},
        )
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, "Failed to fetch photo")
