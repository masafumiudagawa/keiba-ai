@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo [%date% %time%] データ更新開始 >> logs\odds_update.log
python -X utf8 scheduler_v2.py update >> logs\odds_update.log 2>&1
echo [%date% %time%] データ更新完了 >> logs\odds_update.log
echo. >> logs\odds_update.log
