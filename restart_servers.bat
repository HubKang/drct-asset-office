@echo off
setlocal

cd /d "%~dp0"

echo [1/5] Stopping existing backend/frontend dev processes...
taskkill /F /FI "WINDOWTITLE eq DrCT Backend*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DrCT Frontend*" /T >nul 2>&1

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] .venv\Scripts\python.exe not found.
  echo Create venv first: py -m venv .venv
  exit /b 1
)

echo [2/5] Installing backend dependencies in .venv...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install backend dependencies.
  exit /b 1
)

echo [3/5] Starting backend server (.venv + .env)...
start "DrCT Backend" cmd /k "cd /d "%~dp0" && call .venv\Scripts\activate.bat && python scripts\init_db.py && python -m uvicorn backend.app.main:app --reload --env-file .env"
if errorlevel 1 (
  echo [ERROR] Failed to start backend command window.
  exit /b 1
)

echo [4/5] Starting frontend server...
if not exist "frontend\node_modules" (
  echo [INFO] frontend\node_modules not found. Installing frontend dependencies...
  cd /d "%~dp0frontend"
  npm install
  if errorlevel 1 (
    echo [ERROR] Failed to install frontend dependencies.
    exit /b 1
  )
  cd /d "%~dp0"
)
start "DrCT Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"
if errorlevel 1 (
  echo [ERROR] Failed to start frontend command window.
  exit /b 1
)

echo [5/5] Done.
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:5173

endlocal
