"""
netkeiba.com からのデータスクレイピングモジュール

収集対象データ:
1. 過去の宝塚記念結果（過去10年分）
2. 阪神芝2200mの過去レース結果
3. 各登録馬の過去成績
4. 騎手成績
5. 種牡馬成績
"""

import os
import re
import time
import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup
import pandas as pd
from tqdm import tqdm

from config.settings import (
    SCRAPE_INTERVAL, NETKEIBA_BASE_URL, RAW_DIR,
    HISTORY_YEARS, HORSE_HISTORY_RACES,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# リクエストヘッダー
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


class NetkeibaScraper:
    """netkeiba.comからデータを収集するスクレイパー"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        os.makedirs(RAW_DIR, exist_ok=True)

    def _fetch(self, url: str) -> BeautifulSoup | None:
        """URLからHTMLを取得してBeautifulSoupオブジェクトを返す"""
        try:
            time.sleep(SCRAPE_INTERVAL)
            resp = self.session.get(url, timeout=30)
            resp.encoding = "EUC-JP"
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "lxml")
            logger.warning(f"HTTP {resp.status_code}: {url}")
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
        return None

    # ────────────────────────────────────────
    # 1. 過去の宝塚記念結果を取得
    # ────────────────────────────────────────
    def scrape_takarazuka_history(self, years: int = HISTORY_YEARS) -> pd.DataFrame:
        """過去の宝塚記念結果を取得する

        netkeiba のレース検索結果ページからレースIDを取得し、
        各レースの結果を取得する。
        """
        logger.info(f"宝塚記念の過去{years}年分のデータを収集開始...")

        # 宝塚記念のレース一覧を取得
        current_year = datetime.now().year
        race_ids = []

        # netkeiba のレース検索で宝塚記念を検索
        search_url = (
            f"{NETKEIBA_BASE_URL}/?pid=race_list&word=%E5%AE%9D%E5%A1%9A%E8%A8%98%E5%BF%B5"
            f"&start_year={current_year - years}&end_year={current_year - 1}"
            f"&grade%5B%5D=1"  # G1
        )
        soup = self._fetch(search_url)
        if soup:
            links = soup.select("a[href*='/race/']")
            for link in links:
                href = link.get("href", "")
                match = re.search(r"/race/(\d{12})/", href)
                if match:
                    race_ids.append(match.group(1))

        # 手動で過去の宝塚記念レースIDを追加（バックアップ）
        # 阪神(09) 宝塚記念のレースID形式: YYYYJJDDRRNN
        known_ids = [
            "202509030811",  # 2025年
            "202409030811",  # 2024年
            "202309030811",  # 2023年
            "202209030811",  # 2022年
            "202109030811",  # 2021年
            "202009030811",  # 2020年
            "201909030811",  # 2019年
            "201809030811",  # 2018年
            "201709030811",  # 2017年
            "201609030811",  # 2016年
        ]
        for rid in known_ids:
            if rid not in race_ids:
                race_ids.append(rid)

        all_results = []
        for race_id in tqdm(race_ids, desc="宝塚記念結果取得"):
            result = self.scrape_race_result(race_id)
            if result is not None and not result.empty:
                result["race_id"] = race_id
                result["race_year"] = int(race_id[:4])
                all_results.append(result)

        if all_results:
            df = pd.concat(all_results, ignore_index=True)
            output_path = os.path.join(RAW_DIR, "takarazuka_history.csv")
            df.to_csv(output_path, index=False, encoding="utf-8-sig")
            logger.info(f"宝塚記念過去データ保存: {output_path} ({len(df)}行)")
            return df
        return pd.DataFrame()

    # ────────────────────────────────────────
    # 2. 個別レース結果の取得
    # ────────────────────────────────────────
    def scrape_race_result(self, race_id: str) -> pd.DataFrame | None:
        """指定レースIDの結果を取得"""
        url = f"{NETKEIBA_BASE_URL}/race/{race_id}/"
        soup = self._fetch(url)
        if not soup:
            return None

        # レース情報の解析
        race_info = self._parse_race_info(soup)

        # 結果テーブルの解析
        result_table = soup.select_one("table.race_table_01")
        if not result_table:
            logger.warning(f"結果テーブルが見つかりません: {race_id}")
            return None

        rows = result_table.select("tr")[1:]  # ヘッダー行をスキップ
        results = []

        for row in rows:
            cols = row.select("td")
            if len(cols) < 13:
                continue

            # 馬IDの取得
            horse_link = cols[3].select_one("a")
            horse_id = ""
            if horse_link:
                match = re.search(r"/horse/(\w+)/", horse_link.get("href", ""))
                if match:
                    horse_id = match.group(1)

            # 騎手IDの取得
            jockey_link = cols[6].select_one("a")
            jockey_id = ""
            if jockey_link:
                match = re.search(r"/jockey/(\w+)/", jockey_link.get("href", ""))
                if match:
                    jockey_id = match.group(1)

            # 調教師IDの取得
            trainer_link = cols[12].select_one("a") if len(cols) > 12 else None
            trainer_id = ""
            if trainer_link:
                match = re.search(r"/trainer/(\w+)/", trainer_link.get("href", ""))
                if match:
                    trainer_id = match.group(1)

            record = {
                "finish_position": self._clean_text(cols[0]),
                "post_position": self._clean_text(cols[1]),  # 枠番
                "gate_number": self._clean_text(cols[2]),     # 馬番
                "horse_name": self._clean_text(cols[3]),
                "horse_id": horse_id,
                "sex_age": self._clean_text(cols[4]),
                "weight_carried": self._clean_text(cols[5]),  # 斤量
                "jockey_name": self._clean_text(cols[6]),
                "jockey_id": jockey_id,
                "finish_time": self._clean_text(cols[7]),
                "margin": self._clean_text(cols[8]),          # 着差
                "passing_order": self._clean_text(cols[10]) if len(cols) > 10 else "",
                "last_3f": self._clean_text(cols[11]) if len(cols) > 11 else "",  # 上がり3F
                "trainer_name": self._clean_text(cols[12]) if len(cols) > 12 else "",
                "trainer_id": trainer_id,
                "horse_weight": self._clean_text(cols[14]) if len(cols) > 14 else "",  # 馬体重
                "odds": self._clean_text(cols[9]) if len(cols) > 9 else "",
                "popularity": self._clean_text(cols[13]) if len(cols) > 13 else "",
            }
            record.update(race_info)
            results.append(record)

        return pd.DataFrame(results) if results else None

    def _parse_race_info(self, soup: BeautifulSoup) -> dict:
        """レースの基本情報を解析"""
        info = {
            "race_name": "",
            "distance": 0,
            "surface": "",
            "track_condition": "",
            "weather": "",
            "venue": "",
            "race_date": "",
            "grade": "",
        }

        # レース名
        race_name_tag = soup.select_one("h1.racedata_title, .data_intro h1")
        if race_name_tag:
            info["race_name"] = self._clean_text(race_name_tag)

        # 距離・馬場状態など
        race_data = soup.select_one("diary_snap_cut span, .racedata p span")
        if race_data:
            text = race_data.get_text()
            # 芝/ダート + 距離
            match = re.search(r"(芝|ダ)(\d+)m", text)
            if match:
                info["surface"] = "芝" if match.group(1) == "芝" else "ダート"
                info["distance"] = int(match.group(2))
            # 馬場状態
            match = re.search(r"馬場:(良|稍重|重|不良)", text)
            if match:
                info["track_condition"] = match.group(1)
            # 天候
            match = re.search(r"天候:(晴|曇|雨|小雨|雪)", text)
            if match:
                info["weather"] = match.group(1)

        return info

    # ────────────────────────────────────────
    # 3. 馬の過去成績を取得
    # ────────────────────────────────────────
    def scrape_horse_history(self, horse_id: str, max_races: int = HORSE_HISTORY_RACES) -> pd.DataFrame | None:
        """指定馬の過去成績を取得"""
        url = f"{NETKEIBA_BASE_URL}/horse/{horse_id}/"
        soup = self._fetch(url)
        if not soup:
            return None

        # 馬名の取得
        horse_name = ""
        name_tag = soup.select_one(".horse_title h1")
        if name_tag:
            horse_name = self._clean_text(name_tag)

        # 血統情報の取得
        pedigree = self._parse_pedigree(soup)

        # 過去成績テーブル
        perf_table = soup.select_one("table.db_h_race_results")
        if not perf_table:
            logger.warning(f"成績テーブルが見つかりません: {horse_id}")
            return None

        rows = perf_table.select("tbody tr")
        records = []

        for i, row in enumerate(rows[:max_races]):
            cols = row.select("td")
            if len(cols) < 20:
                continue

            # レースIDの取得
            race_link = cols[4].select_one("a")
            race_id = ""
            if race_link:
                match = re.search(r"/race/(\d+)/", race_link.get("href", ""))
                if match:
                    race_id = match.group(1)

            record = {
                "horse_id": horse_id,
                "horse_name": horse_name,
                "race_date": self._clean_text(cols[0]),
                "venue": self._clean_text(cols[1]),
                "weather": self._clean_text(cols[2]),
                "race_number": self._clean_text(cols[3]),
                "race_name": self._clean_text(cols[4]),
                "field_size": self._clean_text(cols[6]),
                "post_position": self._clean_text(cols[7]),
                "gate_number": self._clean_text(cols[8]),
                "odds": self._clean_text(cols[9]),
                "popularity": self._clean_text(cols[10]),
                "finish_position": self._clean_text(cols[11]),
                "jockey_name": self._clean_text(cols[12]),
                "weight_carried": self._clean_text(cols[13]),
                "distance": self._clean_text(cols[14]) if len(cols) > 14 else "",
                "surface": self._clean_text(cols[15]) if len(cols) > 15 else "",
                "track_condition": self._clean_text(cols[16]) if len(cols) > 16 else "",
                "finish_time": self._clean_text(cols[17]) if len(cols) > 17 else "",
                "margin": self._clean_text(cols[18]) if len(cols) > 18 else "",
                "last_3f": self._clean_text(cols[22]) if len(cols) > 22 else "",
                "horse_weight": self._clean_text(cols[23]) if len(cols) > 23 else "",
                "race_id": race_id,
            }
            record.update(pedigree)
            records.append(record)

        if records:
            df = pd.DataFrame(records)
            output_path = os.path.join(RAW_DIR, f"horse_{horse_id}.csv")
            df.to_csv(output_path, index=False, encoding="utf-8-sig")
            logger.info(f"馬データ保存: {horse_name} ({len(df)}レース)")
            return df
        return None

    def _parse_pedigree(self, soup: BeautifulSoup) -> dict:
        """血統情報を解析"""
        pedigree = {"sire": "", "dam": "", "dam_sire": ""}
        pedigree_table = soup.select_one("table.blood_table")
        if pedigree_table:
            links = pedigree_table.select("a")
            if len(links) >= 1:
                pedigree["sire"] = self._clean_text(links[0])
            if len(links) >= 3:
                pedigree["dam"] = self._clean_text(links[2])
            if len(links) >= 4:
                pedigree["dam_sire"] = self._clean_text(links[3])
        return pedigree

    # ────────────────────────────────────────
    # 4. 騎手成績の取得
    # ────────────────────────────────────────
    def scrape_jockey_stats(self, jockey_id: str) -> dict | None:
        """騎手の年間成績を取得"""
        url = f"{NETKEIBA_BASE_URL}/jockey/{jockey_id}/"
        soup = self._fetch(url)
        if not soup:
            return None

        jockey_name = ""
        name_tag = soup.select_one("h1.rider_title, .Name h1")
        if name_tag:
            jockey_name = self._clean_text(name_tag)

        stats = {
            "jockey_id": jockey_id,
            "jockey_name": jockey_name,
            "total_wins": 0,
            "total_runs": 0,
            "win_rate": 0.0,
            "place_rate": 0.0,
            "g1_wins": 0,
        }

        # 成績テーブルの解析
        tables = soup.select("table.nk_tb_common")
        for table in tables:
            rows = table.select("tr")
            for row in rows:
                cols = row.select("td")
                if len(cols) >= 4:
                    try:
                        stats["total_runs"] = int(self._clean_text(cols[1]).replace(",", ""))
                        stats["total_wins"] = int(self._clean_text(cols[2]).replace(",", ""))
                        if stats["total_runs"] > 0:
                            stats["win_rate"] = stats["total_wins"] / stats["total_runs"]
                    except (ValueError, IndexError):
                        pass
                    break

        return stats

    # ────────────────────────────────────────
    # 5. 阪神芝2200mの過去レースを収集
    # ────────────────────────────────────────
    def scrape_hanshin_2200_races(self, years: int = 5) -> pd.DataFrame:
        """阪神芝2200mの過去レース結果を収集（コース適性分析用）"""
        logger.info(f"阪神芝2200mの過去{years}年分のレースを収集開始...")

        current_year = datetime.now().year
        race_ids = []

        for year in range(current_year - years, current_year):
            # 阪神芝2200mのレース検索
            search_url = (
                f"{NETKEIBA_BASE_URL}/?pid=race_list"
                f"&start_year={year}&end_year={year}"
                f"&jyo%5B%5D=09"  # 阪神
                f"&kyori_min=2200&kyori_max=2200"
                f"&track%5B%5D=1"  # 芝
            )
            soup = self._fetch(search_url)
            if soup:
                links = soup.select("a[href*='/race/']")
                for link in links:
                    href = link.get("href", "")
                    match = re.search(r"/race/(\d{12})/", href)
                    if match:
                        race_ids.append(match.group(1))

        all_results = []
        for race_id in tqdm(race_ids, desc="阪神2200m結果取得"):
            result = self.scrape_race_result(race_id)
            if result is not None and not result.empty:
                result["race_id"] = race_id
                all_results.append(result)

        if all_results:
            df = pd.concat(all_results, ignore_index=True)
            output_path = os.path.join(RAW_DIR, "hanshin_2200_history.csv")
            df.to_csv(output_path, index=False, encoding="utf-8-sig")
            logger.info(f"阪神2200mデータ保存: {output_path} ({len(df)}行)")
            return df
        return pd.DataFrame()

    # ────────────────────────────────────────
    # 6. 馬IDの検索
    # ────────────────────────────────────────
    def search_horse_id(self, horse_name: str) -> str | None:
        """馬名からnetkeiba上のIDを検索"""
        import urllib.parse
        encoded_name = urllib.parse.quote(horse_name)
        url = f"{NETKEIBA_BASE_URL}/?pid=horse_search&word={encoded_name}"
        soup = self._fetch(url)
        if soup:
            horse_link = soup.select_one("a[href*='/horse/']")
            if horse_link:
                match = re.search(r"/horse/(\w+)/", horse_link.get("href", ""))
                if match:
                    return match.group(1)
        return None

    # ────────────────────────────────────────
    # メイン収集フロー
    # ────────────────────────────────────────
    def collect_all_data(self, registered_horses: list[dict]) -> dict:
        """全データを一括収集する

        Args:
            registered_horses: 登録馬リスト [{"name": "...", "age": N, "sex": "..."}, ...]

        Returns:
            dict: 収集結果のサマリー
        """
        summary = {"takarazuka_history": 0, "horse_histories": 0, "hanshin_2200": 0}

        # 1. 宝塚記念の過去結果
        logger.info("=" * 60)
        logger.info("STEP 1: 宝塚記念過去データの収集")
        logger.info("=" * 60)
        tk_df = self.scrape_takarazuka_history()
        summary["takarazuka_history"] = len(tk_df) if not tk_df.empty else 0

        # 2. 各登録馬の過去成績
        logger.info("=" * 60)
        logger.info("STEP 2: 登録馬の過去成績の収集")
        logger.info("=" * 60)
        horse_count = 0
        for horse in tqdm(registered_horses, desc="登録馬データ取得"):
            horse_id = self.search_horse_id(horse["name"])
            if horse_id:
                horse["horse_id"] = horse_id
                df = self.scrape_horse_history(horse_id)
                if df is not None:
                    horse_count += 1
            else:
                logger.warning(f"馬ID未発見: {horse['name']}")
        summary["horse_histories"] = horse_count

        # 3. 阪神芝2200mのレース結果
        logger.info("=" * 60)
        logger.info("STEP 3: 阪神芝2200m過去レースの収集")
        logger.info("=" * 60)
        hanshin_df = self.scrape_hanshin_2200_races()
        summary["hanshin_2200"] = len(hanshin_df) if not hanshin_df.empty else 0

        # 登録馬リスト（IDつき）を保存
        horses_df = pd.DataFrame(registered_horses)
        horses_df.to_csv(os.path.join(RAW_DIR, "registered_horses.csv"),
                         index=False, encoding="utf-8-sig")

        logger.info("=" * 60)
        logger.info(f"収集完了サマリー: {summary}")
        logger.info("=" * 60)
        return summary

    @staticmethod
    def _clean_text(element) -> str:
        """要素のテキストをクリーンアップ"""
        if element is None:
            return ""
        return element.get_text(strip=True) if hasattr(element, "get_text") else str(element).strip()


if __name__ == "__main__":
    from config.settings import REGISTERED_HORSES_2026
    scraper = NetkeibaScraper()
    scraper.collect_all_data(REGISTERED_HORSES_2026)
