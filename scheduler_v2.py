"""
汎用データ更新スケジューラ v2

全レースのデータを定期的に更新する。
  - 天気予報: Open-Meteo API（キー不要）
  - オッズ: netkeiba（地方/中央対応）
  - YouTube/ニュース: WebSearch（手動トリガー）

使い方:
  python scheduler_v2.py update          # 全レースのデータを1回更新
  python scheduler_v2.py update-odds     # オッズのみ更新
  python scheduler_v2.py update-weather  # 天気のみ更新
  python scheduler_v2.py loop            # 30分ごとに自動更新（Ctrl+Cで停止）
"""

import os, sys, json, time, logging
from datetime import datetime

import requests
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

RACES_DIR = os.path.join(os.path.dirname(__file__), "data", "races")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

# 競馬場の緯度経度
VENUE_COORDS = {
    "阪神": (34.8042, 135.3594),
    "東京": (35.6644, 139.4815),
    "中山": (35.7275, 139.9550),
    "京都": (34.9267, 135.7100),
    "中京": (35.1700, 137.0400),
    "小倉": (33.8800, 130.8400),
    "札幌": (43.0500, 141.4000),
    "函館": (41.8100, 140.7300),
    "新潟": (37.8700, 139.0200),
    "福島": (37.7500, 140.4600),
    "大井": (35.5878, 139.7413),
    "船橋": (35.6950, 139.9830),
    "園田": (34.7570, 135.4250),
    "水沢": (39.0800, 141.1500),
}


def get_all_races() -> list[dict]:
    """全レースのconfigを取得"""
    races = []
    if not os.path.isdir(RACES_DIR):
        return races
    for name in os.listdir(RACES_DIR):
        cfg_path = os.path.join(RACES_DIR, name, "config.json")
        if os.path.exists(cfg_path):
            with open(cfg_path, encoding="utf-8") as f:
                races.append(json.load(f))
    return races


def update_weather(race: dict):
    """天気予報を更新"""
    venue = race.get("venue", "")
    race_date = race.get("date", "")
    race_id = race.get("id", "")
    coords = VENUE_COORDS.get(venue)
    if not coords or not race_date:
        log.warning(f"  天気更新スキップ: {venue} の座標なし")
        return

    try:
        r = requests.get("https://api.open-meteo.com/v1/forecast", params={
            "latitude": coords[0], "longitude": coords[1],
            "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,windspeed_10m_max",
            "timezone": "Asia/Tokyo",
            "start_date": race_date, "end_date": race_date,
        }, timeout=15)
        d = r.json().get("daily", {})

        code = d.get("weathercode", [0])[0]
        weather_map = {0: "快晴", 1: "晴れ", 2: "くもり", 3: "曇り", 51: "小雨", 53: "雨", 61: "小雨", 63: "雨", 65: "大雨", 80: "にわか雨", 95: "雷雨"}
        precip = d.get("precipitation_sum", [0])[0] or 0
        prob = d.get("precipitation_probability_max", [0])[0] or 0

        if precip >= 20 or prob >= 80: condition = "不良"
        elif precip >= 5 or prob >= 60: condition = "重"
        elif precip >= 1 or prob >= 40: condition = "稍重"
        else: condition = "良"

        weather = {
            "location": venue, "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "race_date": race_date,
            "forecast": weather_map.get(code, f"code:{code}"),
            "temperature_high": d.get("temperature_2m_max", [None])[0],
            "temperature_low": d.get("temperature_2m_min", [None])[0],
            "precipitation_mm": precip,
            "precipitation_probability": prob,
            "wind_speed": d.get("windspeed_10m_max", [None])[0],
            "predicted_track_condition": condition,
        }
        pd.DataFrame([weather]).to_csv(
            os.path.join(RACES_DIR, race_id, "weather.csv"),
            index=False, encoding="utf-8-sig",
        )
        log.info(f"  天気更新: {venue} → {weather['forecast']} 馬場:{condition}")
    except Exception as e:
        log.error(f"  天気更新エラー: {e}")


def update_odds_nar(race: dict):
    """地方競馬のオッズをnetkeibaから取得"""
    race_id = race.get("id", "")
    # netkeibaのレースIDを推定（地方競馬）
    race_date = race.get("date", "").replace("-", "")
    venue_code = {"大井": "44", "船橋": "43", "園田": "51", "水沢": "35"}.get(race.get("venue", ""), "")
    if not venue_code:
        log.info(f"  オッズ更新スキップ: {race.get('venue')} は地方競馬コード未対応")
        return

    netkeiba_race_id = f"{race_date[:4]}{venue_code}{race_date[4:]}11"
    url = f"https://nar.netkeiba.com/odds/index.html?race_id={netkeiba_race_id}&type=b1"

    try:
        from bs4 import BeautifulSoup
        time.sleep(1.5)
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code != 200:
            log.warning(f"  オッズ取得失敗: HTTP {resp.status_code}")
            return

        soup = BeautifulSoup(resp.text, "lxml")
        rows = soup.select("tr.OddsTableBody, tr[class*='HorseList']")
        if not rows:
            log.warning("  オッズテーブルが見つかりません")
            return

        odds_list = []
        for row in rows:
            cols = row.select("td")
            if len(cols) < 4:
                continue
            horse_link = row.select_one("a[href*='/horse/']")
            horse_name = horse_link.get_text(strip=True) if horse_link else ""
            if not horse_name:
                continue
            try:
                odds_val = float(cols[-2].get_text(strip=True).replace(",", ""))
                pop = int(cols[-1].get_text(strip=True))
            except (ValueError, IndexError):
                continue
            odds_list.append({
                "horse_name": horse_name,
                "win_odds": odds_val,
                "popularity": pop,
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })

        if odds_list:
            df = pd.DataFrame(odds_list)
            df.to_csv(os.path.join(RACES_DIR, race_id, "odds.csv"), index=False, encoding="utf-8-sig")
            log.info(f"  オッズ更新: {len(odds_list)}馬")
        else:
            log.info("  オッズデータなし（発売前？）")

    except Exception as e:
        log.error(f"  オッズ更新エラー: {e}")


def update_all():
    """全レースのデータを更新"""
    races = get_all_races()
    log.info(f"=== データ更新開始: {len(races)}レース ===")

    for race in races:
        race_date_str = race.get("date", "")
        if race_date_str:
            try:
                race_date = datetime.strptime(race_date_str, "%Y-%m-%d")
                if race_date.date() < datetime.now().date():
                    log.info(f"[{race['name']}] 過去のレースのためスキップ")
                    continue
            except ValueError:
                pass

        log.info(f"\n[{race.get('name', '')}] ({race.get('venue', '')} {race.get('date', '')})")
        update_weather(race)
        update_odds_nar(race)

    log.info("\n=== データ更新完了 ===")


def loop(interval_min: int = 30):
    """定期実行ループ"""
    log.info(f"定期更新ループ開始（{interval_min}分間隔）")
    while True:
        update_all()
        log.info(f"次回更新: {interval_min}分後")
        time.sleep(interval_min * 60)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "update"
    if cmd == "update":
        update_all()
    elif cmd == "update-weather":
        for r in get_all_races():
            update_weather(r)
    elif cmd == "update-odds":
        for r in get_all_races():
            update_odds_nar(r)
    elif cmd == "loop":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        loop(interval)
    else:
        print(__doc__)
