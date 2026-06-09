@echo off
chcp 65001 >nul
cd /d "%~dp0"
start "API" cmd /k "python -X utf8 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul
start "WEB" cmd /k "cd frontend && npx vite --host 0.0.0.0 --port 5173"
timeout /t 3 /nobreak >nul
start http://localhost:5173
