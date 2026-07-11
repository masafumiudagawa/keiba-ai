@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ========================================
echo   KEIBA AI - オッズ自動更新セットアップ
echo ========================================
echo.

if not exist logs mkdir logs

schtasks /Delete /TN "KEIBA_AI_OddsUpdate" /F >nul 2>&1

schtasks /Create /TN "KEIBA_AI_OddsUpdate" /TR "\"%~dp0update_odds.cmd\"" /SC MINUTE /MO 5 /F

if %errorlevel%==0 (
    echo.
    echo [OK] タスクスケジューラに登録しました
    echo   タスク名: KEIBA_AI_OddsUpdate
    echo   間隔:     5分ごと
    echo   ログ:     logs\odds_update.log
    echo.
) else (
    echo.
    echo [ERROR] 登録に失敗しました
    echo   管理者権限で再実行してください
)
pause
