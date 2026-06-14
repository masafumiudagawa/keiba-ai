@echo off
chcp 65001 >nul
cd /d "C:\Users\wwmudagawa\Documents\馬\keiba_ai"
if not exist logs mkdir logs
echo [%date% %time%] データ更新開始 >> logs\odds_update.log
python scheduler_v2.py update >> logs\odds_update.log 2>&1
echo [%date% %time%] データ更新完了 >> logs\odds_update.log
echo. >> logs\odds_update.log
