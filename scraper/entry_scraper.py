"""
出馬表（枠番・馬番・騎手・斤量）自動取得モジュール

木曜日に確定する出馬表データをnetkeiba / JRA公式から自動スクレイピングする。
手動入力不要で thursday_entries.csv を生成する。

URL構造:
  netkeiba: https://race.netkeiba.com/race/shutuba.html?race_id=YYYYPPNNDDRR
  JRA公式:  https://www.jra.go.jp/keiba/g1/takara/syutsuba.html
"""

import os
import re
import time
import logging

import requests
from bs4 import BeautifulSoup
import pandas as pd

from config.settings import RAW_DIR, TAKARAZUKA_2026

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


class EntryScraper:
    """確定出馬表を自動取得するスクレイパー"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        os.makedirs(RAW_DIR, exist_ok=True)

    # ────────────────────────────────────────
    # netkeiba 出馬表取得
    # ────────────────────────────────────────
    def fetch_from_netkeiba(self, race_id: str = None) -> pd.DataFrame | None:
        """netkeibaの出馬表ページから確定データを取得

        Args:
            race_id: レースID（例: 202609030811）
                     未指定時は2026年宝塚記念のIDを自動推定

        Returns:
            出馬表DataFrame or None
        """
        if race_id is None:
            race_id = self._estimate_race_id()
            logger.info(f"レースID自動推定: {race_id}")

        url = f"https://race.netkeiba.com/race/shutuba.html?race_id={race_id}"
        logger.info(f"netkeiba出馬表取得: {url}")

        try:
            time.sleep(1.5)
            resp = self.session.get(url, timeout=30)
            resp.encoding = "UTF-8"

            if resp.status_code != 200:
                logger.warning(f"HTTP {resp.status_code}: {url}")
                return None

            soup = BeautifulSoup(resp.text, "lxml")
            return self._parse_netkeiba_shutuba(soup)

        except Exception as e:
            logger.error(f"netkeiba出馬表取得エラー: {e}")
            return None

    def _parse_netkeiba_shutuba(self, soup: BeautifulSoup) -> pd.DataFrame | None:
        """netkeibaの出馬表HTMLを解析"""
        # 出馬表テーブルを探す
        table = soup.select_one("table.ShutubaTable, table.RaceTable01, table.Shutuba_Table")
        if not table:
            # 代替セレクタ
            table = soup.select_one("table[class*='shutuba'], table[class*='Shutuba']")
        if not table:
            logger.warning("出馬表テーブルが見つかりません（まだ公開されていない可能性）")
            return None

        rows = table.select("tr.HorseList, tr[class*='HorseList']")
        if not rows:
            rows = table.select("tbody tr")

        entries = []
        for row in rows:
            cols = row.select("td")
            if len(cols) < 8:
                continue

            # 馬ID取得
            horse_link = row.select_one("a[href*='/horse/']")
            horse_id = ""
            if horse_link:
                match = re.search(r"/horse/(\w+)", horse_link.get("href", ""))
                if match:
                    horse_id = match.group(1)

            # 騎手ID取得
            jockey_link = row.select_one("a[href*='/jockey/']")
            jockey_id = ""
            jockey_name = ""
            if jockey_link:
                jockey_name = jockey_link.get_text(strip=True)
                match = re.search(r"/jockey/(\w+)", jockey_link.get("href", ""))
                if match:
                    jockey_id = match.group(1)

            # 調教師取得
            trainer_link = row.select_one("a[href*='/trainer/']")
            trainer_name = trainer_link.get_text(strip=True) if trainer_link else ""

            entry = {
                "post_position": self._get_text(cols, 0),     # 枠番
                "gate_number": self._get_text(cols, 1),       # 馬番
                "horse_name": self._extract_horse_name(cols, 3),
                "horse_id": horse_id,
                "sex_age": self._get_text(cols, 4),
                "weight_carried": self._get_text(cols, 5),    # 斤量
                "jockey_name": jockey_name or self._get_text(cols, 6),
                "jockey_id": jockey_id,
                "trainer_name": trainer_name or self._get_text(cols, 7),
                "horse_weight": "",  # 当日まで未確定
            }

            # 性別・馬齢を分離
            sex_age = entry["sex_age"]
            match = re.match(r"([牡牝セ])(\d+)", sex_age)
            if match:
                entry["sex"] = match.group(1)
                entry["age"] = int(match.group(2))
            else:
                entry["sex"] = ""
                entry["age"] = 0

            entries.append(entry)

        if entries:
            df = pd.DataFrame(entries)
            logger.info(f"netkeiba出馬表: {len(df)}頭取得")
            return df

        return None

    # ────────────────────────────────────────
    # JRA 公式出馬表取得
    # ────────────────────────────────────────
    def fetch_from_jra(self) -> pd.DataFrame | None:
        """JRA公式サイトの宝塚記念出馬表を取得"""
        url = "https://www.jra.go.jp/keiba/g1/takara/syutsuba.html"
        logger.info(f"JRA出馬表取得: {url}")

        try:
            time.sleep(1.5)
            resp = self.session.get(url, timeout=30)
            resp.encoding = "UTF-8"

            if resp.status_code != 200:
                logger.warning(f"HTTP {resp.status_code}: {url}")
                return None

            soup = BeautifulSoup(resp.text, "lxml")
            return self._parse_jra_shutuba(soup)

        except Exception as e:
            logger.error(f"JRA出馬表取得エラー: {e}")
            return None

    def _parse_jra_shutuba(self, soup: BeautifulSoup) -> pd.DataFrame | None:
        """JRA公式の出馬表HTMLを解析"""
        table = soup.select_one("table.basic, table[class*='syutsuba']")
        if not table:
            tables = soup.select("table")
            # 出馬表らしいテーブルを探す
            for t in tables:
                headers = t.get_text()
                if "枠番" in headers and "馬番" in headers:
                    table = t
                    break

        if not table:
            logger.warning("JRA出馬表テーブルが見つかりません")
            return None

        rows = table.select("tbody tr, tr")
        entries = []

        for row in rows:
            cols = row.select("td")
            if len(cols) < 6:
                continue

            # 枠番が数字であることを確認（ヘッダー行スキップ）
            post_text = cols[0].get_text(strip=True)
            if not post_text.isdigit():
                continue

            entry = {
                "post_position": post_text,
                "gate_number": self._get_text(cols, 1),
                "horse_name": self._get_text(cols, 3),
                "sex_age": self._get_text(cols, 4),
                "weight_carried": self._get_text(cols, 5),
                "jockey_name": self._get_text(cols, 6) if len(cols) > 6 else "",
                "trainer_name": self._get_text(cols, 7) if len(cols) > 7 else "",
                "horse_weight": "",
            }

            sex_age = entry["sex_age"]
            match = re.match(r"([牡牝セ])(\d+)", sex_age)
            if match:
                entry["sex"] = match.group(1)
                entry["age"] = int(match.group(2))
            else:
                entry["sex"] = ""
                entry["age"] = 0

            entries.append(entry)

        if entries:
            df = pd.DataFrame(entries)
            logger.info(f"JRA出馬表: {len(df)}頭取得")
            return df

        return None

    # ────────────────────────────────────────
    # 統合取得（netkeiba → JRA のフォールバック）
    # ────────────────────────────────────────
    def fetch_entries(self, race_id: str = None) -> pd.DataFrame:
        """出馬表を取得する（netkeiba優先、失敗時JRA公式にフォールバック）

        Returns:
            確定出馬表DataFrame
        """
        logger.info("=" * 60)
        logger.info("確定出馬表の自動取得を開始")
        logger.info("=" * 60)

        # まずnetkeibaから取得を試みる
        df = self.fetch_from_netkeiba(race_id)

        # netkeibaで取得できなければJRA公式を試す
        if df is None or df.empty:
            logger.info("netkeiba取得失敗 → JRA公式サイトから取得を試みます")
            df = self.fetch_from_jra()

        if df is None or df.empty:
            logger.warning(
                "出馬表の自動取得に失敗しました。\n"
                "考えられる原因:\n"
                "  1. まだ出馬表が公開されていない（木曜日以降に公開）\n"
                "  2. サイト構造の変更によるスクレイピング失敗\n"
                "手動入力してください: data/raw/thursday_entries.csv"
            )
            return pd.DataFrame()

        # field_sizeを追加
        df["field_size"] = len(df)

        # CSV保存
        output_path = os.path.join(RAW_DIR, "thursday_entries.csv")
        df.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info(f"出馬表保存: {output_path} ({len(df)}頭)")

        # 取得結果を表示
        self._display_entries(df)

        return df

    def _display_entries(self, df: pd.DataFrame):
        """取得した出馬表を表示"""
        print("\n" + "=" * 70)
        print("  宝塚記念 2026 - 確定出馬表")
        print("=" * 70)
        print(f"{'枠':>3} {'馬番':>4} {'馬名':<16} {'性齢':<5} {'斤量':>4} {'騎手':<10}")
        print("-" * 70)

        for _, row in df.iterrows():
            post = row.get("post_position", "")
            gate = row.get("gate_number", "")
            name = row.get("horse_name", "")
            sex = row.get("sex", "")
            age = row.get("age", "")
            weight = row.get("weight_carried", "")
            jockey = row.get("jockey_name", "")

            sex_age = f"{sex}{age}" if sex and age else row.get("sex_age", "")
            print(f"{post:>3} {gate:>4}  {name:<16} {sex_age:<5} {weight:>4} {jockey:<10}")

        print("=" * 70)

    # ────────────────────────────────────────
    # ユーティリティ
    # ────────────────────────────────────────
    def _estimate_race_id(self) -> str:
        """2026年宝塚記念のレースIDを推定

        レースID形式: YYYYPPNNDDRR
          YYYY: 西暦
          PP:   競馬場コード (09=阪神)
          NN:   開催回数
          DD:   開催日数
          RR:   レース番号 (11=メインレース)
        """
        # 宝塚記念は阪神3回開催の8日目11R が一般的
        return "202609030811"

    @staticmethod
    def _get_text(cols: list, idx: int) -> str:
        if idx < len(cols):
            return cols[idx].get_text(strip=True)
        return ""

    @staticmethod
    def _extract_horse_name(cols: list, idx: int) -> str:
        """馬名を抽出（リンクテキストからも取得）"""
        if idx >= len(cols):
            return ""
        cell = cols[idx]
        link = cell.select_one("a")
        if link:
            return link.get_text(strip=True)
        return cell.get_text(strip=True)


if __name__ == "__main__":
    scraper = EntryScraper()
    entries = scraper.fetch_entries()
    if entries.empty:
        print("\n出馬表未公開。木曜日以降に再実行してください。")
        print("または手動入力: python main.py templates")
