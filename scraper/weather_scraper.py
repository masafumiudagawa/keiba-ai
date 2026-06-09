"""
天気予報データ収集モジュール

レース当日の天気予報を取得して馬場状態を予測する。
阪神競馬場（宝塚市）の天気予報を収集。
"""

import os
import re
import time
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import pandas as pd

from config.settings import RAW_DIR

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


class WeatherScraper:
    """天気予報データ収集"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        os.makedirs(RAW_DIR, exist_ok=True)

    def fetch_weather(self) -> dict:
        """阪神競馬場周辺（宝塚市）の天気予報を取得"""
        logger.info("天気予報データの取得開始...")

        weather = {
            "location": "宝塚市（阪神競馬場）",
            "fetched_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "race_date": "2026-06-14",
            "forecast": "",
            "temperature_high": None,
            "temperature_low": None,
            "precipitation_probability": None,
            "wind_speed": None,
            "wind_direction": "",
            "predicted_track_condition": "良",
        }

        # Open-Meteo API（無料・APIキー不要）
        weather = self._fetch_open_meteo(weather)

        # 馬場状態の予測
        weather["predicted_track_condition"] = self._predict_track_condition(weather)

        # 保存
        output_path = os.path.join(RAW_DIR, "weather_forecast.csv")
        df = pd.DataFrame([weather])

        # 既存データに追記（天気変化の記録）
        if os.path.exists(output_path):
            existing = pd.read_csv(output_path, encoding="utf-8-sig")
            df = pd.concat([existing, df], ignore_index=True)

        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info(f"天気予報保存: {output_path}")

        self._display_weather(weather)
        return weather

    def _fetch_open_meteo(self, weather: dict) -> dict:
        """Open-Meteo APIで天気予報を取得（無料・キー不要）"""
        # 阪神競馬場の座標（宝塚市）
        lat = 34.8042
        lon = 135.3594

        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lat,
            "longitude": lon,
            "daily": "weathercode,temperature_2m_max,temperature_2m_min,precipitation_sum,precipitation_probability_max,windspeed_10m_max,winddirection_10m_dominant",
            "timezone": "Asia/Tokyo",
            "start_date": "2026-06-14",
            "end_date": "2026-06-14",
        }

        try:
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                daily = data.get("daily", {})

                if daily.get("temperature_2m_max"):
                    weather["temperature_high"] = daily["temperature_2m_max"][0]
                if daily.get("temperature_2m_min"):
                    weather["temperature_low"] = daily["temperature_2m_min"][0]
                if daily.get("precipitation_sum"):
                    weather["precipitation_mm"] = daily["precipitation_sum"][0]
                if daily.get("precipitation_probability_max"):
                    weather["precipitation_probability"] = daily["precipitation_probability_max"][0]
                if daily.get("windspeed_10m_max"):
                    weather["wind_speed"] = daily["windspeed_10m_max"][0]

                # 天気コードから天気を判定
                code = daily.get("weathercode", [0])[0]
                weather["forecast"] = self._weather_code_to_text(code)

                logger.info("Open-Meteo API: 天気予報取得成功")
            else:
                logger.warning(f"Open-Meteo API: HTTP {resp.status_code}")
        except Exception as e:
            logger.error(f"Open-Meteo API エラー: {e}")

        return weather

    def _predict_track_condition(self, weather: dict) -> str:
        """天気から馬場状態を予測"""
        precip = weather.get("precipitation_mm", 0) or 0
        precip_prob = weather.get("precipitation_probability", 0) or 0

        if precip >= 20 or precip_prob >= 80:
            return "重"
        if precip >= 5 or precip_prob >= 60:
            return "稍重"
        if precip >= 1 or precip_prob >= 40:
            return "稍重"  # 微妙な場合は稍重寄り
        return "良"

    @staticmethod
    def _weather_code_to_text(code: int) -> str:
        """WMO天気コードをテキストに変換"""
        weather_map = {
            0: "快晴", 1: "晴れ", 2: "くもり", 3: "曇り",
            45: "霧", 48: "霧",
            51: "小雨", 53: "雨", 55: "強い雨",
            56: "凍雨", 57: "凍雨",
            61: "小雨", 63: "雨", 65: "大雨",
            71: "小雪", 73: "雪", 75: "大雪",
            80: "にわか雨", 81: "にわか雨", 82: "豪雨",
            95: "雷雨",
        }
        return weather_map.get(code, f"不明(code:{code})")

    def _display_weather(self, weather: dict):
        print("\n" + "=" * 60)
        print("  レース当日 天気予報")
        print("=" * 60)
        print(f"  日付: {weather['race_date']}（日）")
        print(f"  場所: {weather['location']}")
        print(f"  天気: {weather.get('forecast', '未取得')}")
        print(f"  気温: {weather.get('temperature_low', '?')}℃ 〜 {weather.get('temperature_high', '?')}℃")
        print(f"  降水確率: {weather.get('precipitation_probability', '?')}%")
        print(f"  降水量: {weather.get('precipitation_mm', '?')}mm")
        print(f"  風速: {weather.get('wind_speed', '?')}km/h")
        print(f"  → 予測馬場状態: {weather['predicted_track_condition']}")
        print("=" * 60)


if __name__ == "__main__":
    scraper = WeatherScraper()
    scraper.fetch_weather()
