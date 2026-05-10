@echo off
setlocal

cd /d "%~dp0"

echo [1/5] Stopping existing backend/frontend dev processes...
for %%P in (uvicorn.exe node.exe python.exe) do (
  taskkill /F /IM %%P >nul 2>&1
)

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv\Scripts\python.exe not found.
  echo Create venv first: py -m venv .venv
  exit /b 1
)

echo [2/5] Installing backend dependencies in .venv...
".venv\Scripts\python.exe" -m pip install -r requirements.txt >nul 2>&1

echo [3/5] Starting backend server (.venv + .env)...
start "DrCT Backend" cmd /k "cd /d "%~dp0" && call .venv\Scripts\activate.bat && python scripts\init_db.py && python -m uvicorn backend.app.main:app --reload --env-file .env"

echo [4/5] Starting frontend server...
start "DrCT Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo [5/5] Done.
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:5173

endlocal
