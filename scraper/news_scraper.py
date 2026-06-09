"""
スポーツ紙・ニュースサイトからの予想データ収集

以下のソースから専門家予想を収集する:
- 日刊スポーツ (nikkansports.com)
- スポーツ報知 (hochi.news)
- サンスポ (sanspo.com)
- デイリースポーツ (daily.co.jp)
- netkeiba コラム・予想
- Yahoo!競馬
"""

import os
import re
import time
import logging
from datetime import datetime
from collections import Counter

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

HORSE_NAMES = [
    "クロワデュノール", "コスモキュランダ", "シェイクユアハート",
    "シュガークン", "シンエンペラー", "ジューンテイク",
    "スティンガーグラス", "タガノデュード", "ダノンデサイル",
    "ビザンチンドリーム", "ファミリータイム", "マイネルエンペラー",
    "マイユニバース", "ミクニインスパイア", "ミステリーウェイ",
    "ミュージアムマイル", "メイショウタバル", "レガレイラ",
]


class NewsScraper:
    """スポーツ紙・ニュースサイトの予想データ収集"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        os.makedirs(RAW_DIR, exist_ok=True)

    def collect_all_news(self) -> pd.DataFrame:
        """全ニュースソースから予想データを収集"""
        logger.info("=" * 60)
        logger.info("スポーツ紙・ニュース予想の収集開始")
        logger.info("=" * 60)

        all_articles = []

        sources = [
            ("日刊スポーツ", self._scrape_nikkansports),
            ("スポーツ報知", self._scrape_hochi),
            ("サンスポ", self._scrape_sanspo),
            ("netkeiba", self._scrape_netkeiba_columns),
            ("Yahoo!競馬", self._scrape_yahoo_keiba),
        ]

        for name, scraper_func in sources:
            logger.info(f"  {name} から収集中...")
            try:
                articles = scraper_func()
                for article in articles:
                    article["source"] = name
                all_articles.extend(articles)
                logger.info(f"  {name}: {len(articles)}記事取得")
            except Exception as e:
                logger.warning(f"  {name}: 取得失敗 - {e}")
            time.sleep(2)

        if not all_articles:
            logger.warning("ニュース記事が取得できませんでした")
            return pd.DataFrame()

        # 馬名の出現を分析
        mention_summary = self._analyze_mentions(all_articles)

        # 保存
        articles_df = pd.DataFrame(all_articles)
        articles_path = os.path.join(RAW_DIR, "news_articles.csv")
        articles_df.to_csv(articles_path, index=False, encoding="utf-8-sig")

        summary_path = os.path.join(RAW_DIR, "news_predictions.csv")
        mention_summary.to_csv(summary_path, index=False, encoding="utf-8-sig")
        logger.info(f"ニュース予想保存: {summary_path}")

        return mention_summary

    def _scrape_nikkansports(self) -> list[dict]:
        """日刊スポーツの宝塚記念記事を収集"""
        articles = []
        url = "https://www.nikkansports.com/keiba/news/"
        articles.extend(self._search_google_news("宝塚記念 2026 site:nikkansports.com"))
        return articles

    def _scrape_hochi(self) -> list[dict]:
        """スポーツ報知の宝塚記念記事を収集"""
        return self._search_google_news("宝塚記念 2026 予想 site:hochi.news")

    def _scrape_sanspo(self) -> list[dict]:
        """サンスポの宝塚記念記事を収集"""
        return self._search_google_news("宝塚記念 2026 予想 site:sanspo.com")

    def _scrape_netkeiba_columns(self) -> list[dict]:
        """netkeibaのコラム・予想記事を収集"""
        articles = []

        # netkeiba 宝塚記念特集ページ
        urls = [
            "https://race.netkeiba.com/race/newspaper.html?race_id=202609030811",
            "https://news.netkeiba.com/?pid=column_search&word=%E5%AE%9D%E5%A1%9A%E8%A8%98%E5%BF%B5",
        ]

        for url in urls:
            try:
                time.sleep(1.5)
                resp = self.session.get(url, timeout=30)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "lxml")

                # 新聞予想の印を解析
                marks_table = soup.select_one("table[class*='Newspaper'], table[class*='Mark']")
                if marks_table:
                    articles.extend(self._parse_newspaper_marks(marks_table))
                    continue

                # コラム記事を解析
                article_links = soup.select("a[href*='column'], a[href*='news']")
                for link in article_links[:10]:
                    href = link.get("href", "")
                    title = link.get_text(strip=True)
                    if "宝塚" in title or "記念" in title:
                        content = self._fetch_article_content(href)
                        articles.append({
                            "title": title,
                            "url": href,
                            "content": content,
                        })
            except Exception as e:
                logger.debug(f"netkeiba記事取得エラー: {e}")

        return articles

    def _parse_newspaper_marks(self, table) -> list[dict]:
        """新聞の◎○▲△印を解析"""
        articles = []
        rows = table.select("tr")

        for row in rows:
            cols = row.select("td")
            if len(cols) < 3:
                continue

            horse_link = row.select_one("a[href*='/horse/']")
            if not horse_link:
                continue

            horse_name = horse_link.get_text(strip=True)

            # 各紙の印を集計
            marks_text = row.get_text()
            honmei_count = marks_text.count("◎")
            taikou_count = marks_text.count("○")
            tanana_count = marks_text.count("▲")
            renka_count = marks_text.count("△")

            articles.append({
                "title": f"新聞予想印: {horse_name}",
                "content": f"◎{honmei_count} ○{taikou_count} ▲{tanana_count} △{renka_count}",
                "marks": {
                    "honmei": honmei_count,
                    "taikou": taikou_count,
                    "tanana": tanana_count,
                    "renka": renka_count,
                },
                "horse_name": horse_name,
            })

        return articles

    def _scrape_yahoo_keiba(self) -> list[dict]:
        """Yahoo!競馬の予想データを収集"""
        return self._search_google_news("宝塚記念 2026 予想 site:keiba.yahoo.co.jp")

    def _search_google_news(self, query: str) -> list[dict]:
        """Google検索で競馬ニュース記事を取得"""
        articles = []
        try:
            url = "https://www.google.com/search"
            params = {"q": query, "num": 15, "tbm": "nws"}
            time.sleep(2)
            resp = self.session.get(url, params=params, timeout=30)

            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")

                # 検索結果を解析
                for result in soup.select("div.SoaBEf, div[class*='result']"):
                    title_el = result.select_one("div.MBeuO, h3, a")
                    link_el = result.select_one("a[href]")

                    title = title_el.get_text(strip=True) if title_el else ""
                    href = link_el.get("href", "") if link_el else ""
                    snippet_el = result.select_one("div.GI74Re, div[class*='snippet']")
                    snippet = snippet_el.get_text(strip=True) if snippet_el else ""

                    if title:
                        articles.append({
                            "title": title,
                            "url": href,
                            "content": f"{title} {snippet}",
                        })

                # フォールバック: 一般的なリンク抽出
                if not articles:
                    for link in soup.select("a[href]"):
                        href = link.get("href", "")
                        title = link.get_text(strip=True)
                        if any(keyword in title for keyword in ["宝塚", "記念", "予想"]):
                            articles.append({
                                "title": title,
                                "url": href,
                                "content": title,
                            })

        except Exception as e:
            logger.debug(f"Google News検索エラー: {e}")

        return articles[:10]  # 上位10件

    def _fetch_article_content(self, url: str) -> str:
        """記事本文を取得"""
        try:
            if not url.startswith("http"):
                return ""
            time.sleep(1.5)
            resp = self.session.get(url, timeout=30)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "lxml")
                # 本文抽出（記事系のセレクタ）
                article = soup.select_one(
                    "article, .article-body, .articleBody, "
                    ".entry-content, .post-content, main"
                )
                if article:
                    return article.get_text(strip=True)[:3000]
            return ""
        except Exception:
            return ""

    def _analyze_mentions(self, articles: list[dict]) -> pd.DataFrame:
        """記事中の馬名出現を分析・集計"""
        mention_data = {name: {
            "mention_count": 0,
            "honmei_count": 0,
            "taikou_count": 0,
            "articles_mentioned": 0,
            "news_score": 0.0,
        } for name in HORSE_NAMES}

        for article in articles:
            content = f"{article.get('title', '')} {article.get('content', '')}"
            mentioned_horses = set()

            for horse in HORSE_NAMES:
                count = content.count(horse)
                if count > 0:
                    mention_data[horse]["mention_count"] += count
                    mentioned_horses.add(horse)

                    # 印の解析
                    if article.get("marks"):
                        marks = article["marks"]
                        if article.get("horse_name") == horse:
                            mention_data[horse]["honmei_count"] += marks.get("honmei", 0)
                            mention_data[horse]["taikou_count"] += marks.get("taikou", 0)

                    # コンテキストから本命判定
                    idx = content.find(horse)
                    if idx >= 0:
                        ctx = content[max(0, idx - 20):idx + len(horse) + 20]
                        if re.search(r"◎|本命", ctx):
                            mention_data[horse]["honmei_count"] += 1
                        elif re.search(r"○|対抗", ctx):
                            mention_data[horse]["taikou_count"] += 1

            for h in mentioned_horses:
                mention_data[h]["articles_mentioned"] += 1

        # スコア算出
        total_articles = len(articles) if articles else 1
        results = []
        for horse, data in mention_data.items():
            data["horse_name"] = horse
            data["mention_rate"] = data["articles_mentioned"] / total_articles
            data["news_score"] = (
                data["honmei_count"] * 5 +
                data["taikou_count"] * 3 +
                data["mention_count"] * 0.5
            )
            results.append(data)

        df = pd.DataFrame(results).sort_values("news_score", ascending=False)

        # 結果表示
        print("\n" + "=" * 60)
        print("  ニュース・新聞予想 集計")
        print("=" * 60)
        print(f"  分析記事数: {len(articles)}件\n")
        for _, row in df.head(10).iterrows():
            if row["mention_count"] > 0:
                print(f"  {row['horse_name']:15s}  "
                      f"◎{int(row['honmei_count'])} ○{int(row['taikou_count'])}  "
                      f"言及{int(row['mention_count'])}回  "
                      f"スコア: {row['news_score']:.1f}")

        return df


if __name__ == "__main__":
    scraper = NewsScraper()
    scraper.collect_all_news()
