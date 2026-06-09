@echo off
echo ========================================
echo   KEIBA AI - 宝塚記念 2026
echo ========================================
echo.
echo Starting Backend (port 8000)...
start "KEIBA-API" cmd /c "cd /d %~dp0 && python -X utf8 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul

echo Starting Frontend (port 5173)...
start "KEIBA-WEB" cmd /c "cd /d %~dp0\frontend && npx vite --host 0.0.0.0 --port 5173"
timeout /t 3 /nobreak >nul

echo.
echo ========================================
echo   Open in browser:
echo   http://localhost:5173
echo ========================================
echo.
start http://localhost:5173
pause
