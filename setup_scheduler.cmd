@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   KEIBA AI - オッズ自動更新セットアップ
echo ========================================
echo.

:: ログディレクトリ作成
if not exist logs mkdir logs

:: 既存タスクがあれば削除
schtasks /Delete /TN "KEIBA_AI_OddsUpdate" /F >nul 2>&1

:: タスクスケジューラに登録（30分間隔）
schtasks /Create /TN "KEIBA_AI_OddsUpdate" /TR "\"%~dp0update_odds.cmd\"" /SC MINUTE /MO 30 /ST 09:00 /ET 17:00 /F

if %errorlevel%==0 (
    echo.
    echo [OK] タスクスケジューラに登録しました
    echo   タスク名: KEIBA_AI_OddsUpdate
    echo   間隔:     30分ごと
    echo   時間帯:   09:00 - 17:00
    echo   ログ:     logs\odds_update.log
    echo.
    echo 手動で確認/変更する場合:
    echo   taskschd.msc を開いてください
) else (
    echo.
    echo [ERROR] 登録に失敗しました
    echo   管理者権限で再実行してください
)
echo.
pause
