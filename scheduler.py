"""
定期実行スケジューラ

レース当日までデータ収集を自動的に繰り返し実行する。

スケジュール:
  月〜水: 6時間ごとにニュース・YouTube予想を収集
  木曜日: 出馬表確定を検知して自動取得、以降は2時間ごとに収集
  金〜土: 2時間ごとにオッズ変動・調教データ・天気を収集
  日曜日: 30分ごとにオッズ・天気を更新、レース前に最終予測実行
"""

import os
import sys
import time
import logging
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import RAW_DIR
from scraper.netkeiba_scraper import NetkeibaScraper
from scraper.entry_scraper import EntryScraper
from scraper.youtube_scraper import YouTubeScraper
from scraper.odds_training_scraper import OddsTrainingScraper
from scraper.news_scraper import NewsScraper
from scraper.weather_scraper import WeatherScraper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "scheduler.log"),
            encoding="utf-8",
        ),
    ],
)
logger = logging.getLogger(__name__)

RACE_DATE = datetime(2026, 6, 14)  # 宝塚記念当日
RACE_TIME = datetime(2026, 6, 14, 15, 40)  # 発走15:40


class DataScheduler:
    """データ収集の定期実行スケジューラ"""

    def __init__(self, youtube_api_key: str = None):
        self.netkeiba = NetkeibaScraper()
        self.entry = EntryScraper()
        self.youtube = YouTubeScraper(api_key=youtube_api_key)
        self.odds_training = OddsTrainingScraper()
        self.news = NewsScraper()
        self.weather = WeatherScraper()
        self.run_count = 0

    def run_once(self, mode: str = "auto"):
        """1回分のデータ収集を実行

        Args:
            mode: 収集モード
                "auto"    - 日付に応じて自動判定
                "full"    - 全データ収集
                "quick"   - ニュース+天気のみ
                "entries" - 出馬表のみ
                "odds"    - オッズ+調教のみ
                "news"    - ニュース+YouTubeのみ
        """
        self.run_count += 1
        now = datetime.now()

        logger.info("=" * 70)
        logger.info(f"  データ収集 #{self.run_count}  ({now.strftime('%Y-%m-%d %H:%M')})")
        logger.info(f"  モード: {mode}")
        logger.info(f"  レースまで: {(RACE_TIME - now).days}日{(RACE_TIME - now).seconds // 3600}時間")
        logger.info("=" * 70)

        if mode == "auto":
            mode = self._determine_mode(now)
            logger.info(f"  → 自動判定モード: {mode}")

        results = {}

        try:
            if mode in ("full", "entries"):
                logger.info("\n[出馬表取得]")
                entries = self.entry.fetch_entries()
                results["entries"] = len(entries) if not entries.empty else 0

            if mode in ("full", "odds"):
                logger.info("\n[オッズ取得]")
                odds = self.odds_training.scrape_odds()
                results["odds"] = len(odds) if not odds.empty else 0

                logger.info("\n[調教データ取得]")
                training = self.odds_training.scrape_training()
                results["training"] = len(training) if not training.empty else 0

            if mode in ("full", "news"):
                logger.info("\n[ニュース予想取得]")
                news = self.news.collect_all_news()
                results["news"] = len(news) if not news.empty else 0

                logger.info("\n[YouTube予想取得]")
                yt = self.youtube.collect_predictions()
                results["youtube"] = len(yt) if not yt.empty else 0

            if mode in ("full", "quick", "odds"):
                logger.info("\n[天気予報取得]")
                weather = self.weather.fetch_weather()
                results["weather"] = 1 if weather.get("forecast") else 0

        except Exception as e:
            logger.error(f"データ収集エラー: {e}")

        logger.info(f"\n収集結果: {results}")
        return results

    def _determine_mode(self, now: datetime) -> str:
        """現在日時からデータ収集モードを自動判定"""
        days_to_race = (RACE_DATE.date() - now.date()).days

        if days_to_race > 5:
            return "news"  # 月〜火: ニュース+YouTube
        if days_to_race == 5:
            return "full"  # 水: フル収集
        if days_to_race == 4:
            return "full"  # 木: 出馬表確定日 → フル収集
        if days_to_race in (3, 2):
            return "odds"  # 金〜土: オッズ+調教
        if days_to_race == 1:
            return "full"  # 前日: フル収集
        if days_to_race == 0:
            return "odds"  # 当日: オッズ+天気中心
        return "quick"

    def run_scheduled(self):
        """レースまで定期実行を繰り返す"""
        logger.info("定期実行スケジューラ起動")
        logger.info(f"レース日時: {RACE_TIME.strftime('%Y-%m-%d %H:%M')}")

        while True:
            now = datetime.now()
            if now >= RACE_TIME:
                logger.info("レース時刻を過ぎたため終了します")
                break

            # データ収集を実行
            self.run_once(mode="auto")

            # 次回実行までの待機時間を計算
            interval = self._calculate_interval(now)
            next_run = now + timedelta(seconds=interval)

            logger.info(f"\n次回実行: {next_run.strftime('%H:%M')} "
                        f"({interval // 60}分後)")
            logger.info("-" * 70)

            time.sleep(interval)

    def _calculate_interval(self, now: datetime) -> int:
        """次回実行までの待機時間（秒）を計算"""
        days_to_race = (RACE_DATE.date() - now.date()).days

        if days_to_race > 3:
            return 6 * 3600   # 6時間
        if days_to_race in (2, 3):
            return 2 * 3600   # 2時間
        if days_to_race == 1:
            return 1 * 3600   # 1時間
        if days_to_race == 0:
            hours_to_race = (RACE_TIME - now).total_seconds() / 3600
            if hours_to_race <= 2:
                return 15 * 60   # 15分
            if hours_to_race <= 5:
                return 30 * 60   # 30分
            return 1 * 3600      # 1時間
        return 6 * 3600  # デフォルト

    def run_final_prediction(self):
        """最終予測の実行（レース直前）"""
        logger.info("=" * 70)
        logger.info("  最終データ収集 & 予測実行")
        logger.info("=" * 70)

        # 最新データをすべて取得
        self.run_once(mode="full")

        # メインスクリプトのpredict呼び出し
        from main import step_predict
        from scraper.weather_scraper import WeatherScraper

        # 天気から馬場状態を取得
        weather = self.weather.fetch_weather()
        condition = weather.get("predicted_track_condition", "良")

        logger.info(f"\n馬場状態予測: {condition}")
        step_predict(track_condition=condition)


def main():
    parser = argparse.ArgumentParser(description="宝塚記念2026 データ収集スケジューラ")
    parser.add_argument(
        "command",
        choices=["start", "once", "final"],
        help="start=定期実行, once=1回実行, final=最終予測",
    )
    parser.add_argument(
        "--mode", "-m",
        default="auto",
        choices=["auto", "full", "quick", "entries", "odds", "news"],
        help="収集モード（onceの場合）",
    )
    parser.add_argument(
        "--youtube-api-key",
        default=None,
        help="YouTube Data API v3 キー",
    )
    args = parser.parse_args()

    scheduler = DataScheduler(youtube_api_key=args.youtube_api_key)

    if args.command == "start":
        scheduler.run_scheduled()
    elif args.command == "once":
        scheduler.run_once(mode=args.mode)
    elif args.command == "final":
        scheduler.run_final_prediction()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("宝塚記念2026 データ収集スケジューラ")
        print()
        print("使い方:")
        print("  python scheduler.py start              # 定期実行（レースまで自動継続）")
        print("  python scheduler.py once               # 1回だけ全データ収集")
        print("  python scheduler.py once -m entries     # 出馬表のみ取得")
        print("  python scheduler.py once -m odds        # オッズ+調教のみ取得")
        print("  python scheduler.py once -m news        # ニュース+YouTubeのみ取得")
        print("  python scheduler.py final               # 最終データ収集+予測実行")
        print()
        print("スケジュール:")
        print("  月〜水: 6時間ごと（ニュース+YouTube）")
        print("  木曜:   出馬表確定→フル収集")
        print("  金〜土: 2時間ごと（オッズ+調教+天気）")
        print("  前日:   1時間ごと（フル収集）")
        print("  当日:   15〜30分ごと（オッズ+天気）")
    else:
        main()
