"""
YouTube 競馬予想動画からのデータ収集モジュール

YouTube Data API v3 またはWebスクレイピングで
宝塚記念の予想動画を収集し、以下を抽出する:
- 各予想家の本命・対抗・穴馬
- コメント欄の支持率
- 動画の再生数・評価（信頼度の指標）

APIキーがない場合はWeb検索+ページ解析で代替する。
"""

import os
import re
import json
import time
import logging
from datetime import datetime, timedelta
from collections import Counter

import requests
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

# 2026宝塚記念の登録馬名（マッチング用）
HORSE_NAMES = [
    "クロワデュノール", "コスモキュランダ", "シェイクユアハート",
    "シュガークン", "シンエンペラー", "ジューンテイク",
    "スティンガーグラス", "タガノデュード", "ダノンデサイル",
    "ビザンチンドリーム", "ファミリータイム", "マイネルエンペラー",
    "マイユニバース", "ミクニインスパイア", "ミステリーウェイ",
    "ミュージアムマイル", "メイショウタバル", "レガレイラ",
]


class YouTubeScraper:
    """YouTube競馬予想動画からデータを収集"""

    def __init__(self, api_key: str = None):
        """
        Args:
            api_key: YouTube Data API v3 キー（任意）
                     環境変数 YOUTUBE_API_KEY からも取得可能
        """
        self.api_key = api_key or os.environ.get("YOUTUBE_API_KEY")
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        os.makedirs(RAW_DIR, exist_ok=True)

    def collect_predictions(self) -> pd.DataFrame:
        """宝塚記念の予想動画を収集して分析"""
        logger.info("=" * 60)
        logger.info("YouTube 宝塚記念予想動画の収集開始")
        logger.info("=" * 60)

        videos = []

        if self.api_key:
            videos = self._search_with_api()
        else:
            logger.info("YouTube API キー未設定。Web検索ベースで収集します。")
            logger.info("精度向上のため YOUTUBE_API_KEY 環境変数の設定を推奨します。")
            videos = self._search_without_api()

        if not videos:
            logger.warning("予想動画が見つかりませんでした")
            return pd.DataFrame()

        # 各動画から馬名の出現を分析
        all_mentions = []
        for video in videos:
            mentions = self._extract_horse_mentions(video)
            all_mentions.extend(mentions)

        # 集計
        result = self._aggregate_mentions(all_mentions, videos)

        # 保存
        output_path = os.path.join(RAW_DIR, "youtube_predictions.csv")
        result.to_csv(output_path, index=False, encoding="utf-8-sig")
        logger.info(f"YouTube予想データ保存: {output_path}")

        # 動画一覧も保存
        videos_df = pd.DataFrame(videos)
        videos_path = os.path.join(RAW_DIR, "youtube_videos.csv")
        videos_df.to_csv(videos_path, index=False, encoding="utf-8-sig")

        return result

    # ────────────────────────────────────────
    # YouTube Data API v3 による検索
    # ────────────────────────────────────────
    def _search_with_api(self) -> list[dict]:
        """YouTube Data API で予想動画を検索"""
        search_queries = [
            "宝塚記念 2026 予想",
            "宝塚記念 2026 本命",
            "宝塚記念 2026 全頭診断",
            "宝塚記念 2026 穴馬",
        ]

        all_videos = []
        seen_ids = set()

        for query in search_queries:
            url = "https://www.googleapis.com/youtube/v3/search"
            params = {
                "part": "snippet",
                "q": query,
                "type": "video",
                "maxResults": 15,
                "order": "relevance",
                "publishedAfter": "2026-06-01T00:00:00Z",
                "key": self.api_key,
            }

            try:
                resp = self.session.get(url, params=params, timeout=30)
                if resp.status_code != 200:
                    logger.warning(f"YouTube API エラー: {resp.status_code}")
                    continue

                data = resp.json()
                for item in data.get("items", []):
                    vid = item["id"].get("videoId", "")
                    if vid and vid not in seen_ids:
                        seen_ids.add(vid)
                        snippet = item["snippet"]
                        video = {
                            "video_id": vid,
                            "title": snippet.get("title", ""),
                            "description": snippet.get("description", ""),
                            "channel": snippet.get("channelTitle", ""),
                            "published_at": snippet.get("publishedAt", ""),
                            "url": f"https://www.youtube.com/watch?v={vid}",
                        }
                        all_videos.append(video)

                time.sleep(0.5)
            except Exception as e:
                logger.error(f"YouTube API 検索エラー: {e}")

        # 動画の統計情報を取得
        for video in all_videos:
            stats = self._get_video_stats(video["video_id"])
            video.update(stats)

        logger.info(f"YouTube API: {len(all_videos)}件の動画を取得")
        return all_videos

    def _get_video_stats(self, video_id: str) -> dict:
        """動画の再生数・いいね数を取得"""
        stats = {"view_count": 0, "like_count": 0, "comment_count": 0}
        if not self.api_key:
            return stats

        url = "https://www.googleapis.com/youtube/v3/videos"
        params = {
            "part": "statistics",
            "id": video_id,
            "key": self.api_key,
        }
        try:
            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                if items:
                    s = items[0].get("statistics", {})
                    stats["view_count"] = int(s.get("viewCount", 0))
                    stats["like_count"] = int(s.get("likeCount", 0))
                    stats["comment_count"] = int(s.get("commentCount", 0))
        except Exception:
            pass
        return stats

    # ────────────────────────────────────────
    # APIキーなしの場合のWeb検索ベース収集
    # ────────────────────────────────────────
    def _search_without_api(self) -> list[dict]:
        """Web検索で YouTube 動画情報を収集（APIキー不要）"""
        search_queries = [
            "宝塚記念 2026 予想 site:youtube.com",
            "宝塚記念 2026 本命 穴馬 site:youtube.com",
            "宝塚記念 2026 全頭診断 site:youtube.com",
        ]

        all_videos = []
        seen_urls = set()

        for query in search_queries:
            try:
                # Google検索でYouTube動画を探す
                google_url = "https://www.google.com/search"
                params = {"q": query, "num": 20}
                time.sleep(2)
                resp = self.session.get(google_url, params=params, timeout=30)

                if resp.status_code == 200:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "lxml")

                    # YouTube URLを抽出
                    for link in soup.select("a[href]"):
                        href = link.get("href", "")
                        # Google検索結果のリンクからYouTube URLを抽出
                        yt_match = re.search(
                            r"(https?://(?:www\.)?youtube\.com/watch\?v=[\w-]+)", href
                        )
                        if yt_match:
                            yt_url = yt_match.group(1)
                            if yt_url not in seen_urls:
                                seen_urls.add(yt_url)
                                vid_match = re.search(r"v=([\w-]+)", yt_url)
                                video = {
                                    "video_id": vid_match.group(1) if vid_match else "",
                                    "title": link.get_text(strip=True),
                                    "description": "",
                                    "channel": "",
                                    "url": yt_url,
                                    "view_count": 0,
                                    "like_count": 0,
                                }
                                all_videos.append(video)
            except Exception as e:
                logger.error(f"Web検索エラー: {e}")

        # 各動画ページから詳細情報を取得
        for video in all_videos[:20]:  # 上位20件に制限
            details = self._fetch_video_page(video["url"])
            video.update(details)
            time.sleep(1.5)

        logger.info(f"Web検索ベース: {len(all_videos)}件の動画を取得")
        return all_videos

    def _fetch_video_page(self, url: str) -> dict:
        """YouTube動画ページから情報を抽出"""
        details = {"description": "", "channel": ""}
        try:
            resp = self.session.get(url, timeout=30)
            if resp.status_code == 200:
                text = resp.text
                # タイトル
                title_match = re.search(r'"title":"([^"]+)"', text)
                if title_match:
                    details["title"] = title_match.group(1)
                # チャンネル名
                channel_match = re.search(r'"ownerChannelName":"([^"]+)"', text)
                if channel_match:
                    details["channel"] = channel_match.group(1)
                # 説明文
                desc_match = re.search(r'"shortDescription":"([^"]*)"', text)
                if desc_match:
                    details["description"] = desc_match.group(1).replace("\\n", "\n")
                # 再生回数
                views_match = re.search(r'"viewCount":"(\d+)"', text)
                if views_match:
                    details["view_count"] = int(views_match.group(1))
        except Exception as e:
            logger.debug(f"動画ページ取得エラー: {e}")
        return details

    # ────────────────────────────────────────
    # 馬名抽出・分析
    # ────────────────────────────────────────
    def _extract_horse_mentions(self, video: dict) -> list[dict]:
        """動画のタイトル・説明から馬名の出現を抽出"""
        mentions = []
        text = f"{video.get('title', '')} {video.get('description', '')}"
        view_count = video.get("view_count", 0)

        for horse in HORSE_NAMES:
            count = text.count(horse)
            if count > 0:
                # 本命・対抗・穴馬の判定
                role = self._detect_role(text, horse)
                mentions.append({
                    "horse_name": horse,
                    "video_id": video.get("video_id", ""),
                    "channel": video.get("channel", ""),
                    "mention_count": count,
                    "role": role,
                    "view_count": view_count,
                })
        return mentions

    def _detect_role(self, text: str, horse_name: str) -> str:
        """テキスト中で馬名がどの役割で言及されているかを判定"""
        # 馬名の周辺テキストを取得
        idx = text.find(horse_name)
        if idx == -1:
            return "mention"

        context = text[max(0, idx - 30):idx + len(horse_name) + 30]

        if re.search(r"◎|本命|一番手|最有力|鉄板", context):
            return "honmei"  # 本命
        if re.search(r"○|対抗|二番手", context):
            return "taikou"  # 対抗
        if re.search(r"▲|単穴|三番手", context):
            return "tanana"  # 単穴
        if re.search(r"△|連下|押さえ", context):
            return "renka"   # 連下
        if re.search(r"★|穴馬|大穴|激走|波乱", context):
            return "anaba"   # 穴馬
        return "mention"     # 単純な言及

    def _aggregate_mentions(self, mentions: list[dict], videos: list[dict]) -> pd.DataFrame:
        """全動画の言及を集計してスコア化"""
        if not mentions:
            return pd.DataFrame()

        df = pd.DataFrame(mentions)
        total_videos = len(videos)

        # 馬名ごとに集計
        results = []
        for horse in HORSE_NAMES:
            horse_df = df[df["horse_name"] == horse]
            if horse_df.empty:
                results.append({
                    "horse_name": horse,
                    "mention_videos": 0,
                    "mention_rate": 0.0,
                    "honmei_count": 0,
                    "taikou_count": 0,
                    "anaba_count": 0,
                    "youtube_score": 0.0,
                    "total_views_weighted": 0,
                })
                continue

            mention_videos = horse_df["video_id"].nunique()
            honmei = len(horse_df[horse_df["role"] == "honmei"])
            taikou = len(horse_df[horse_df["role"] == "taikou"])
            tanana = len(horse_df[horse_df["role"] == "tanana"])
            anaba = len(horse_df[horse_df["role"] == "anaba"])

            # 再生数加重スコア（再生数が多い予想家の意見に重み）
            views_weighted = (horse_df["view_count"] * horse_df["mention_count"]).sum()

            # YouTubeスコア（本命=5, 対抗=3, 単穴=2, 穴馬=1.5, 言及=1）
            role_weights = {"honmei": 5, "taikou": 3, "tanana": 2, "anaba": 1.5, "renka": 1, "mention": 0.5}
            score = sum(role_weights.get(r, 0.5) for r in horse_df["role"])

            results.append({
                "horse_name": horse,
                "mention_videos": mention_videos,
                "mention_rate": mention_videos / max(total_videos, 1),
                "honmei_count": honmei,
                "taikou_count": taikou,
                "tanana_count": tanana,
                "anaba_count": anaba,
                "youtube_score": score,
                "total_views_weighted": views_weighted,
            })

        result_df = pd.DataFrame(results).sort_values("youtube_score", ascending=False)

        # 結果表示
        print("\n" + "=" * 60)
        print("  YouTube 予想家 支持率ランキング")
        print("=" * 60)
        print(f"  分析動画数: {total_videos}本\n")
        for _, row in result_df.head(10).iterrows():
            print(f"  {row['horse_name']:15s}  "
                  f"◎{int(row['honmei_count'])} ○{int(row['taikou_count'])} "
                  f"穴{int(row['anaba_count'])}  "
                  f"スコア: {row['youtube_score']:.1f}  "
                  f"言及率: {row['mention_rate']:.0%}")

        return result_df


if __name__ == "__main__":
    scraper = YouTubeScraper()
    scraper.collect_predictions()
