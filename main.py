"""
宝塚記念2026 予測AIツール - メインスクリプト

使い方:
  python main.py collect     # 過去レースデータをnetkeibaから収集
  python main.py entries     # 出馬表（枠番・騎手・斤量）を自動取得
  python main.py youtube     # YouTube予想動画を収集・分析
  python main.py news        # スポーツ紙・ニュース予想を収集
  python main.py odds        # オッズ・調教データを取得
  python main.py weather     # レース当日の天気予報を取得
  python main.py fetch-all   # 上記すべてを一括実行
  python main.py train       # モデル学習
  python main.py predict     # 予測実行
  python main.py schedule    # 定期実行スケジューラ起動
  python main.py templates   # 手動入力用CSVテンプレート生成
"""

import sys
import os
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import numpy as np

from config.settings import (
    REGISTERED_HORSES_2026, RAW_DIR, PROCESSED_DIR,
    TAKARAZUKA_2026,
)


def step_collect():
    """過去レースデータをnetkeibaから収集"""
    from scraper.netkeiba_scraper import NetkeibaScraper
    print("=" * 70)
    print("  過去レースデータ収集（netkeiba）")
    print("=" * 70)
    print("  対象: 宝塚記念過去10年 / 各登録馬の過去20走 / 阪神芝2200m")
    print("  サーバー負荷軽減のため1.5秒間隔でリクエストします。\n")

    scraper = NetkeibaScraper()
    summary = scraper.collect_all_data(REGISTERED_HORSES_2026)
    print(f"\n収集完了: {summary}")


def step_entries():
    """出馬表（枠番・馬番・騎手・斤量）を自動取得"""
    from scraper.entry_scraper import EntryScraper
    print("=" * 70)
    print("  確定出馬表の自動取得")
    print("=" * 70)

    scraper = EntryScraper()
    entries = scraper.fetch_entries()
    if entries.empty:
        print("\n出馬表未公開。木曜日（6/11）以降に再実行してください。")


def step_youtube(api_key: str = None):
    """YouTube予想動画を収集・分析"""
    from scraper.youtube_scraper import YouTubeScraper
    print("=" * 70)
    print("  YouTube 予想動画の収集・分析")
    print("=" * 70)

    scraper = YouTubeScraper(api_key=api_key)
    result = scraper.collect_predictions()
    if result.empty:
        print("予想動画が見つかりませんでした。")


def step_news():
    """スポーツ紙・ニュース予想を収集"""
    from scraper.news_scraper import NewsScraper
    print("=" * 70)
    print("  スポーツ紙・ニュース予想の収集")
    print("=" * 70)

    scraper = NewsScraper()
    result = scraper.collect_all_news()
    if result.empty:
        print("ニュース記事が見つかりませんでした。")


def step_odds():
    """オッズ・調教データを取得"""
    from scraper.odds_training_scraper import OddsTrainingScraper
    print("=" * 70)
    print("  オッズ・調教データの取得")
    print("=" * 70)

    scraper = OddsTrainingScraper()
    print("\n[単勝オッズ]")
    scraper.scrape_odds()
    print("\n[調教データ]")
    scraper.scrape_training()


def step_weather():
    """レース当日の天気予報を取得"""
    from scraper.weather_scraper import WeatherScraper
    scraper = WeatherScraper()
    weather = scraper.fetch_weather()
    return weather


def step_fetch_all(api_key: str = None):
    """全データソースから一括収集"""
    print("=" * 70)
    print("  全データソース一括収集")
    print("=" * 70)
    print("  1. 過去レースデータ（netkeiba）")
    print("  2. 確定出馬表")
    print("  3. YouTube予想動画")
    print("  4. スポーツ紙・ニュース予想")
    print("  5. オッズ・調教データ")
    print("  6. 天気予報")
    print("=" * 70)

    step_collect()
    step_entries()
    step_youtube(api_key=api_key)
    step_news()
    step_odds()
    step_weather()

    print("\n" + "=" * 70)
    print("  全データ収集完了！")
    print("=" * 70)
    _show_data_status()


def step_templates():
    """手動入力用CSVテンプレート生成"""
    from scraper.manual_data_loader import generate_csv_templates
    print("=" * 70)
    print("  CSV入力テンプレートの生成")
    print("=" * 70)
    generate_csv_templates()


def step_train():
    """過去データからモデルを学習"""
    from features.feature_engineering import FeatureEngineer
    from models.predictor import TakarazukaPredictor

    print("=" * 70)
    print("  モデル学習")
    print("=" * 70)

    fe = FeatureEngineer()
    fe.load_data()

    training_path = os.path.join(RAW_DIR, "takarazuka_history.csv")
    if os.path.exists(training_path):
        tk_history = pd.read_csv(training_path, encoding="utf-8-sig")
        print(f"学習データ: 宝塚記念過去 {len(tk_history)}行")

        rows = []
        for _, entry in tk_history.iterrows():
            features = fe.build_feature_vector(entry.to_dict())
            features["finish_position"] = entry.get("finish_position", np.nan)
            rows.append(features)

        training_df = pd.DataFrame(rows)
        print(f"特徴量行列: {training_df.shape}")

        predictor = TakarazukaPredictor()
        predictor.train(training_df)
    else:
        print(f"学習データなし: {training_path}")
        print("ルールベース予測はデータなしでも動作します。")
        print("先に: python main.py collect")


def step_predict(track_condition: str = "auto"):
    """宝塚記念2026の予測を実行"""
    from features.feature_engineering import FeatureEngineer
    from models.predictor import TakarazukaPredictor

    # 天気から馬場状態を自動判定
    if track_condition == "auto":
        weather_path = os.path.join(RAW_DIR, "weather_forecast.csv")
        if os.path.exists(weather_path):
            wdf = pd.read_csv(weather_path, encoding="utf-8-sig")
            if not wdf.empty:
                track_condition = wdf.iloc[-1].get("predicted_track_condition", "良")
                print(f"天気予報から馬場状態を自動判定: {track_condition}")
            else:
                track_condition = "良"
        else:
            track_condition = "良"

    print("=" * 70)
    print("  宝塚記念 2026 - AI 予測")
    print(f"  阪神 芝2200m  2026年6月14日(日)  馬場: {track_condition}")
    print("=" * 70)

    # 出馬表データ読み込み
    entries_path = os.path.join(RAW_DIR, "thursday_entries.csv")
    if os.path.exists(entries_path):
        entries = pd.read_csv(entries_path, encoding="utf-8-sig")
        entries = entries.dropna(subset=["horse_name"])
        has_entries = "post_position" in entries.columns and entries["post_position"].notna().any()
        if has_entries:
            print(f"\n確定出馬表: {len(entries)}頭")
        else:
            print(f"\n登録馬データ: {len(entries)}頭（枠番未確定）")
    else:
        print("\n登録馬データで暫定予測を行います。")
        entries = pd.DataFrame(REGISTERED_HORSES_2026)

    entries["track_condition"] = track_condition
    entries["field_size"] = len(entries)

    # 特徴量生成
    fe = FeatureEngineer()
    fe.load_data()
    feature_matrix = fe.build_feature_matrix(entries)

    # 予測
    predictor = TakarazukaPredictor()
    results = predictor.predict(feature_matrix)

    # データソースの状況表示
    _show_data_status()

    # 結果表示
    print("\n" + "=" * 70)
    print("  予 測 結 果")
    print("=" * 70)

    for _, row in results.iterrows():
        rank = int(row["rank"])
        name = row["horse_name"]
        prob = row["win_probability"] * 100

        entry_info = entries[entries["horse_name"] == name]
        extra = ""
        if not entry_info.empty:
            ei = entry_info.iloc[0]
            post = ei.get("post_position", "")
            gate = ei.get("gate_number", "")
            jockey = ei.get("jockey_name", "")
            if post and not pd.isna(post):
                extra += f" [{int(post)}枠{int(gate)}番]"
            if jockey and not pd.isna(jockey):
                extra += f" {jockey}"

        medal = {1: "**", 2: "* ", 3: "* "}.get(rank, "  ")
        print(f"  {medal} {rank:2d}位  {name:15s}{extra}  確率: {prob:5.1f}%")

    # 推奨買い目
    _show_betting_suggestions(results)

    # 結果保存
    output_path = os.path.join(PROCESSED_DIR, "prediction_result.csv")
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    results.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"\n予測結果保存: {output_path}")

    return results


def step_schedule(mode: str = "auto", api_key: str = None):
    """定期実行スケジューラ"""
    from scheduler import DataScheduler
    scheduler = DataScheduler(youtube_api_key=api_key)
    if mode == "start":
        scheduler.run_scheduled()
    else:
        scheduler.run_once(mode=mode)


def _show_data_status():
    """収集済みデータの状況を表示"""
    print("\n" + "-" * 70)
    print("  収集データ状況:")
    data_files = {
        "takarazuka_history.csv":   "宝塚記念過去データ",
        "thursday_entries.csv":     "確定出馬表",
        "youtube_predictions.csv":  "YouTube予想",
        "news_predictions.csv":     "ニュース予想",
        "odds_history.csv":         "オッズデータ",
        "training_data.csv":        "調教データ",
        "weather_forecast.csv":     "天気予報",
    }
    for filename, label in data_files.items():
        path = os.path.join(RAW_DIR, filename)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"    [OK] {label:20s} ({size:,} bytes)")
        else:
            print(f"    [--] {label:20s} 未収集")
    print("-" * 70)


def _show_betting_suggestions(results: pd.DataFrame):
    """推奨買い目を表示"""
    print("\n" + "-" * 70)
    print("  推奨買い目（参考）")
    print("-" * 70)
    top = results.head(5)["horse_name"].tolist()

    if len(top) >= 1:
        print(f"\n  ◎ 本命: {top[0]}")
    if len(top) >= 2:
        print(f"  ○ 対抗: {top[1]}")
    if len(top) >= 3:
        print(f"  ▲ 単穴: {top[2]}")
    if len(top) >= 4:
        print(f"  △ 連下: {', '.join(top[3:5])}")

    if len(top) >= 1:
        print(f"\n  単勝: {top[0]}")
    if len(top) >= 2:
        print(f"  馬連: {top[0]} - {top[1]}")
    if len(top) >= 3:
        print(f"  三連複: {' - '.join(top[:3])}")
        print(f"  ワイド: {top[0]}-{top[1]}, {top[0]}-{top[2]}, {top[1]}-{top[2]}")
    if len(top) >= 5:
        from itertools import combinations
        combos = list(combinations(top[:5], 3))
        print(f"  三連複BOX（5頭）: {len(combos)}点")


def main():
    parser = argparse.ArgumentParser(
        description="宝塚記念2026 予測AIツール",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=[
            "collect", "entries", "youtube", "news", "odds",
            "weather", "fetch-all", "train", "predict",
            "schedule", "templates", "status",
        ],
        help="実行コマンド",
    )
    parser.add_argument("--condition", "-c", default="auto",
                        help="馬場状態 (良/稍重/重/不良/auto)")
    parser.add_argument("--youtube-api-key", default=None,
                        help="YouTube Data API v3 キー")
    parser.add_argument("--schedule-mode", "-m", default="auto",
                        choices=["auto", "full", "quick", "entries", "odds", "news", "start"],
                        help="スケジューラモード")
    args = parser.parse_args()

    cmd = args.command

    if cmd == "collect":
        step_collect()
    elif cmd == "entries":
        step_entries()
    elif cmd == "youtube":
        step_youtube(api_key=args.youtube_api_key)
    elif cmd == "news":
        step_news()
    elif cmd == "odds":
        step_odds()
    elif cmd == "weather":
        step_weather()
    elif cmd == "fetch-all":
        step_fetch_all(api_key=args.youtube_api_key)
    elif cmd == "train":
        step_train()
    elif cmd == "predict":
        step_predict(track_condition=args.condition)
    elif cmd == "schedule":
        step_schedule(mode=args.schedule_mode, api_key=args.youtube_api_key)
    elif cmd == "templates":
        step_templates()
    elif cmd == "status":
        _show_data_status()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("推奨実行順序:")
        print("  1. pip install -r requirements.txt")
        print("  2. python main.py collect       # 過去データ収集（初回のみ）")
        print("  3. python main.py youtube        # YouTube予想収集")
        print("  4. python main.py news           # ニュース予想収集")
        print("  5. python main.py entries        # 出馬表取得（木曜以降）")
        print("  6. python main.py odds           # オッズ+調教（木曜以降）")
        print("  7. python main.py weather        # 天気予報")
        print("  8. python main.py train          # モデル学習")
        print("  9. python main.py predict        # 予測実行")
        print()
        print("または定期実行:")
        print("  python main.py schedule -m start # レースまで自動データ収集")
        print()
        print("データ状況確認:")
        print("  python main.py status")
    else:
        main()
