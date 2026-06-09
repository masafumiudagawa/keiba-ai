"""
オッズ・調教データ・前走情報スクレイパー

netkeiba/JRAから以下を収集する:
1. 前日・当日オッズの変動
2. 調教タイム（追い切りデータ）
3. パドック・馬体重（当日）
4. 前走詳細データ
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


class OddsTrainingScraper:
    """オッズ・調教データスクレイパー"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        os.makedirs(RAW_DIR, exist_ok=True)

    # ────────────────────────────────────────
    # 1. オッズデータ取得
    # ────────────────────────────────────────
    def scrape_odds(self, race_id: str = "202609030811") -> pd.DataFrame:
        """単勝・複勝オッズを取得

        前日オッズ → 当日朝 → 直前 と変動を記録
        """
        logger.info("オッズデータの取得開始...")

        # netkeiba オッズページ
        url = f"https://race.netkeiba.com/odds/index.html?race_id={race_id}&type=b1"
        odds_data = self._fetch_odds_page(url)

        if not odds_data:
            # JRA公式のオッズも試す
            jra_url = "https://www.jra.go.jp/keiba/g1/takara/odds.html"
            odds_data = self._fetch_jra_odds(jra_url)

        if odds_data:
            df = pd.DataFrame(odds_data)
            df["fetched_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

            # 既存データに追記（オッズ変動の記録）
            output_path = os.path.join(RAW_DIR, "odds_history.csv")
            if os.path.exists(output_path):
                existing = pd.read_csv(output_path, encoding="utf-8-sig")
                df = pd.concat([existing, df], ignore_index=True)

            df.to_csv(output_path, index=False, encoding="utf-8-sig")
            logger.info(f"オッズデータ保存: {output_path} ({len(odds_data)}頭)")

            self._display_odds(odds_data)
            return df

        logger.warning("オッズデータの取得に失敗（まだ発売前の可能性）")
        return pd.DataFrame()

    def _fetch_odds_page(self, url: str) -> list[dict]:
        """netkeibaのオッズページを解析"""
        try:
            time.sleep(1.5)
            resp = self.session.get(url, timeout=30)
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "lxml")

            # 単勝オッズテーブル
            table = soup.select_one("table.RaceOdds_HorseList, table[class*='Odds']")
            if not table:
                return []

            rows = table.select("tr")
            odds_list = []

            for row in rows:
                cols = row.select("td")
                if len(cols) < 4:
                    continue

                horse_link = row.select_one("a[href*='/horse/']")
                horse_name = horse_link.get_text(strip=True) if horse_link else self._get_text(cols, 2)

                odds_list.append({
                    "gate_number": self._get_text(cols, 0),
                    "horse_name": horse_name,
                    "win_odds": self._parse_float(self._get_text(cols, -2)),
                    "popularity": self._get_text(cols, -1),
                })

            return odds_list
        except Exception as e:
            logger.error(f"オッズページ解析エラー: {e}")
            return []

    def _fetch_jra_odds(self, url: str) -> list[dict]:
        """JRA公式のオッズページを解析"""
        try:
            time.sleep(1.5)
            resp = self.session.get(url, timeout=30)
            if resp.status_code != 200:
                return []

            soup = BeautifulSoup(resp.text, "lxml")
            tables = soup.select("table")

            for table in tables:
                text = table.get_text()
                if "単勝" in text or "オッズ" in text:
                    rows = table.select("tr")
                    odds_list = []
                    for row in rows:
                        cols = row.select("td")
                        if len(cols) >= 3:
                            first = cols[0].get_text(strip=True)
                            if first.isdigit():
                                odds_list.append({
                                    "gate_number": first,
                                    "horse_name": cols[1].get_text(strip=True),
                                    "win_odds": self._parse_float(cols[2].get_text(strip=True)),
                                })
                    if odds_list:
                        return odds_list
            return []
        except Exception as e:
            logger.error(f"JRAオッズ解析エラー: {e}")
            return []

    # ────────────────────────────────────────
    # 2. 調教（追い切り）データ取得
    # ────────────────────────────────────────
    def scrape_training(self, race_id: str = "202609030811") -> pd.DataFrame:
        """追い切り（調教）タイムデータを取得"""
        logger.info("調教データの取得開始...")

        url = f"https://race.netkeiba.com/race/oikiri.html?race_id={race_id}"
        try:
            time.sleep(1.5)
            resp = self.session.get(url, timeout=30)
            if resp.status_code != 200:
                logger.warning(f"調教ページ取得失敗: HTTP {resp.status_code}")
                return pd.DataFrame()

            soup = BeautifulSoup(resp.text, "lxml")
            table = soup.select_one("table[class*='OikiriTable'], table[class*='Training']")
            if not table:
                # 代替テーブル検索
                tables = soup.select("table")
                for t in tables:
                    if "調教" in t.get_text() or "追切" in t.get_text():
                        table = t
                        break

            if not table:
                logger.warning("調教データテーブルが見つかりません")
                return pd.DataFrame()

            rows = table.select("tr")
            training_data = []

            for row in rows:
                cols = row.select("td")
                if len(cols) < 5:
                    continue

                horse_link = row.select_one("a[href*='/horse/']")
                horse_name = horse_link.get_text(strip=True) if horse_link else ""
                if not horse_name:
                    continue

                record = {
                    "horse_name": horse_name,
                    "training_date": self._get_text(cols, 0),
                    "training_course": self._get_text(cols, 1),  # 栗東CW, 美浦南W 等
                    "training_condition": self._get_text(cols, 2),  # 良/稍 等
                    "training_time": self._get_text(cols, 3),  # 全体タイム
                    "last_3f_time": self._get_text(cols, 4) if len(cols) > 4 else "",
                    "last_1f_time": self._get_text(cols, 5) if len(cols) > 5 else "",
                    "training_eval": self._get_text(cols, -1),  # 評価
                }

                # 追い切りの強度を数値化
                eval_text = record["training_eval"]
                record["training_intensity"] = self._eval_training(eval_text)

                training_data.append(record)

            if training_data:
                df = pd.DataFrame(training_data)
                output_path = os.path.join(RAW_DIR, "training_data.csv")
                df.to_csv(output_path, index=False, encoding="utf-8-sig")
                logger.info(f"調教データ保存: {output_path} ({len(df)}件)")

                self._display_training(df)
                return df

        except Exception as e:
            logger.error(f"調教データ取得エラー: {e}")

        return pd.DataFrame()

    def _eval_training(self, text: str) -> float:
        """調教評価をスコア化"""
        if re.search(r"抜群|絶好|S|◎", text):
            return 5.0
        if re.search(r"好調|良好|A|○", text):
            return 4.0
        if re.search(r"普通|平凡|B|△", text):
            return 3.0
        if re.search(r"不安|心配|C|▲", text):
            return 2.0
        if re.search(r"不良|×", text):
            return 1.0
        return 3.0  # デフォルト

    # ────────────────────────────────────────
    # 3. 前走レースの詳細データ取得
    # ────────────────────────────────────────
    def scrape_prev_race_details(self, race_id: str) -> pd.DataFrame:
        """前走のラップタイム・ペースデータを取得"""
        logger.info(f"前走レース詳細取得: {race_id}")

        url = f"https://db.netkeiba.com/race/{race_id}/"
        try:
            time.sleep(1.5)
            resp = self.session.get(url, timeout=30)
            resp.encoding = "EUC-JP"
            if resp.status_code != 200:
                return pd.DataFrame()

            soup = BeautifulSoup(resp.text, "lxml")

            # ラップタイム
            lap_data = {}
            lap_section = soup.select_one(".race_lap_cell, .lap_block")
            if lap_section:
                lap_text = lap_section.get_text()
                laps = re.findall(r"(\d+\.?\d*)", lap_text)
                if laps:
                    lap_data["lap_times"] = "-".join(laps)
                    float_laps = [float(l) for l in laps]
                    half = len(float_laps) // 2
                    lap_data["first_half_pace"] = sum(float_laps[:half])
                    lap_data["second_half_pace"] = sum(float_laps[half:])
                    lap_data["pace_type"] = (
                        "H" if lap_data["first_half_pace"] < lap_data["second_half_pace"]
                        else "S" if lap_data["first_half_pace"] > lap_data["second_half_pace"] + 1
                        else "M"
                    )

            if lap_data:
                return pd.DataFrame([lap_data])

        except Exception as e:
            logger.error(f"前走詳細取得エラー: {e}")

        return pd.DataFrame()

    # ────────────────────────────────────────
    # 表示ヘルパー
    # ────────────────────────────────────────
    def _display_odds(self, odds_data: list[dict]):
        print("\n  単勝オッズ:")
        sorted_odds = sorted(odds_data, key=lambda x: x.get("win_odds", 999))
        for i, od in enumerate(sorted_odds[:10], 1):
            print(f"    {i:2d}番人気  {od['horse_name']:15s}  {od.get('win_odds', '---'):>6}倍")

    def _display_training(self, df: pd.DataFrame):
        print("\n  調教データ:")
        for _, row in df.iterrows():
            print(f"    {row['horse_name']:15s}  "
                  f"{row.get('training_course', ''):8s}  "
                  f"{row.get('training_time', ''):8s}  "
                  f"評価: {row.get('training_intensity', 3):.0f}")

    @staticmethod
    def _get_text(cols: list, idx: int) -> str:
        if idx < len(cols):
            return cols[idx].get_text(strip=True)
        return ""

    @staticmethod
    def _parse_float(text: str) -> float:
        try:
            return float(re.sub(r"[^\d.]", "", text))
        except (ValueError, TypeError):
            return 0.0


if __name__ == "__main__":
    scraper = OddsTrainingScraper()
    scraper.scrape_odds()
    scraper.scrape_training()
