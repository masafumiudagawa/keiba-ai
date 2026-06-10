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


NAR_VENUE_CODE = {"大井": "44", "船橋": "43", "園田": "51", "水沢": "35"}
JRA_VENUE_CODE = {
    "札幌": "01", "函館": "02", "福島": "03", "新潟": "04", "東京": "05",
    "中山": "06", "中京": "07", "京都": "08", "阪神": "09", "小倉": "10",
}


def update_odds(race: dict):
    """中央/地方を自動判別してオッズを取得"""
    venue = race.get("venue", "")
    if venue in NAR_VENUE_CODE:
        update_odds_nar(race)
    elif venue in JRA_VENUE_CODE:
        update_odds_jra(race)
    else:
        log.info(f"  オッズ更新スキップ: {venue} は未対応")


def update_odds_jra(race: dict):
    """中央競馬のオッズをnetkeiba APIから取得"""
    race_id = race.get("id", "")
    venue = race.get("venue", "")
    netkeiba_race_id = race.get("netkeiba_race_id", "")

    if not netkeiba_race_id:
        # netkeiba_race_idが未設定 → 自動探索
        netkeiba_race_id = _find_jra_race_id(race)
        if not netkeiba_race_id:
            log.info(f"  JRAオッズ: netkeiba_race_idが見つかりません")
            return
        # 見つかったIDをconfigに保存
        _save_netkeiba_race_id(race_id, netkeiba_race_id)

    try:
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0"}

        # 1. 出馬表から馬番→馬名マッピングを取得
        time.sleep(1.0)
        shutuba_url = f"https://race.netkeiba.com/race/shutuba.html?race_id={netkeiba_race_id}"
        resp = requests.get(shutuba_url, headers=headers, timeout=15)
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")

        num_to_name = {}
        order_names = []  # 枠順未確定時のフォールバック用
        for row in soup.select("tr.HorseList"):
            tds = row.select("td")
            if len(tds) < 4:
                continue
            umaban = tds[1].get_text(strip=True)
            horse_info = tds[3]
            name_tag = horse_info.select_one("a") or horse_info
            horse_name = name_tag.get_text(strip=True)
            if horse_name:
                order_names.append(horse_name)
                if umaban.isdigit():
                    num_to_name[umaban] = horse_name

        # 枠順未確定の場合、表示順で1-indexed
        if not num_to_name and order_names:
            for i, name in enumerate(order_names, 1):
                num_to_name[str(i)] = name

        if not num_to_name:
            log.warning("  出馬表の解析に失敗")
            return

        # 2. JRAオッズAPIからデータ取得
        time.sleep(1.0)
        odds_url = "https://race.netkeiba.com/api/api_get_jra_odds.html"
        resp = requests.get(odds_url, params={
            "race_id": netkeiba_race_id, "type": "1", "compress": "0",
        }, headers=headers, timeout=15)
        data = resp.json()

        odds_raw = data.get("data")
        if not odds_raw or not isinstance(odds_raw, dict):
            log.info(f"  JRAオッズ: データなし (status={data.get('status')}, 発売前？)")
            return

        odds_data = odds_raw.get("odds", {}).get("1", {})
        if not odds_data:
            log.info("  JRAオッズ: 単勝データなし")
            return

        odds_list = []
        for umaban, values in odds_data.items():
            # values = [オッズ, ?, 人気]
            horse_name = num_to_name.get(umaban.lstrip("0"), "")
            if not horse_name:
                horse_name = num_to_name.get(umaban, f"馬番{umaban}")
            try:
                win_odds = float(values[0])
                popularity = int(values[2])
            except (ValueError, IndexError):
                continue
            odds_list.append({
                "gate_number": int(umaban),
                "horse_name": horse_name,
                "win_odds": win_odds,
                "popularity": popularity,
                "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })

        if odds_list:
            df = pd.DataFrame(odds_list).sort_values("gate_number")
            df.to_csv(os.path.join(RACES_DIR, race_id, "odds.csv"), index=False, encoding="utf-8-sig")
            log.info(f"  JRAオッズ更新: {len(odds_list)}馬")
        else:
            log.info("  JRAオッズデータなし")

    except Exception as e:
        log.error(f"  JRAオッズ更新エラー: {e}")


def _find_jra_race_id(race: dict) -> str:
    """netkeibaからレースIDを自動探索（トップページ + レース一覧の両方を試行）"""
    race_date = race.get("date", "").replace("-", "")
    venue = race.get("venue", "")
    venue_code = JRA_VENUE_CODE.get(venue, "")

    if not race_date or not venue_code:
        return ""

    import re
    headers = {"User-Agent": "Mozilla/5.0"}
    pattern = rf"({race_date[:4]}{venue_code}\d{{6}})"

    try:
        # 1. トップページから探す（未来のレースも含まれる）
        resp = requests.get("https://race.netkeiba.com/top/", headers=headers, timeout=15)
        matches = re.findall(pattern, resp.text)
        if matches:
            candidates = sorted(set(matches))
            return candidates[-1]

        # 2. レース一覧ページから探す
        time.sleep(0.5)
        resp = requests.get(f"https://db.netkeiba.com/race/list/{race_date}/",
                            headers=headers, timeout=15)
        resp.encoding = resp.apparent_encoding
        matches = re.findall(rf"race/{pattern}", resp.text)
        if matches:
            candidates = sorted(set(matches))
            return candidates[-1]

        return ""

    except Exception as e:
        log.error(f"  レースID探索エラー: {e}")
        return ""


def _save_netkeiba_race_id(race_id: str, netkeiba_race_id: str):
    """config.jsonにnetkeiba_race_idを保存"""
    config_path = os.path.join(RACES_DIR, race_id, "config.json")
    if os.path.exists(config_path):
        with open(config_path, encoding="utf-8") as f:
            config = json.load(f)
        config["netkeiba_race_id"] = netkeiba_race_id
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        log.info(f"  netkeiba_race_id保存: {netkeiba_race_id}")


def update_odds_nar(race: dict):
    """地方競馬のオッズをnetkeibaから取得"""
    race_id = race.get("id", "")
    race_date = race.get("date", "").replace("-", "")
    venue_code = NAR_VENUE_CODE.get(race.get("venue", ""), "")
    if not venue_code:
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

        soup = BeautifulSoup(resp.text, "html.parser")
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


def update_horse_ids(race: dict):
    """netkeiba_idが未設定の馬のIDをnetkeibaから取得してextended_data.csvを更新"""
    race_id = race.get("id", "")
    venue = race.get("venue", "")
    ext_path = os.path.join(RACES_DIR, race_id, "extended_data.csv")

    if not os.path.exists(ext_path):
        return

    ext = pd.read_csv(ext_path, encoding="utf-8-sig")
    if "netkeiba_id" not in ext.columns:
        ext["netkeiba_id"] = ""

    ext["netkeiba_id"] = ext["netkeiba_id"].astype(str)
    # 未設定の馬があるか確認
    missing = ext["netkeiba_id"].isin(["", "nan", "None", "nan"])
    if not missing.any():
        return

    try:
        import re
        from bs4 import BeautifulSoup
        headers = {"User-Agent": "Mozilla/5.0"}

        # NARの場合: 出馬表から取得
        if venue in NAR_VENUE_CODE:
            race_date = race.get("date", "").replace("-", "")
            nar_code = NAR_VENUE_CODE[venue]
            nar_race_id = f"{race_date[:4]}{nar_code}{race_date[4:]}11"
            url = f"https://nar.netkeiba.com/race/shutuba.html?race_id={nar_race_id}"
        elif venue in JRA_VENUE_CODE:
            nk_race_id = race.get("netkeiba_race_id", "")
            if not nk_race_id:
                return
            url = f"https://race.netkeiba.com/race/shutuba.html?race_id={nk_race_id}"
        else:
            return

        time.sleep(1.0)
        resp = requests.get(url, headers=headers, timeout=15)
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "html.parser")

        name_to_id = {}
        for row in soup.select("tr.HorseList"):
            for a in row.select("a"):
                href = a.get("href", "")
                m = re.search(r"/horse/(\d+)", href)
                if m:
                    name = a.get_text(strip=True)
                    if name:
                        name_to_id[name] = m.group(1)

        if not name_to_id:
            return

        updated = 0
        for idx, row in ext.iterrows():
            hname = row["horse_name"]
            if missing.iloc[idx] and hname in name_to_id:
                ext.at[idx, "netkeiba_id"] = name_to_id[hname]
                updated += 1

        if updated > 0:
            ext.to_csv(ext_path, index=False, encoding="utf-8-sig")
            log.info(f"  netkeiba_id更新: {updated}馬")

    except Exception as e:
        log.error(f"  netkeiba_id取得エラー: {e}")


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
        update_horse_ids(race)
        update_weather(race)
        update_odds(race)

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
            update_odds(r)
    elif cmd == "loop":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        loop(interval)
    else:
        print(__doc__)
