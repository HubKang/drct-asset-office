@echo off
setlocal

cd /d "%~dp0"
set "ROOT=%~dp0"
set "VENV_PY=%ROOT%.venv\Scripts\python.exe"
set "VENV_ACTIVATE=%ROOT%.venv\Scripts\activate.bat"

echo [1/5] Stopping existing backend/frontend dev processes...
taskkill /F /FI "WINDOWTITLE eq DrCT Backend*" /T >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq DrCT Frontend*" /T >nul 2>&1

if not exist "%VENV_PY%" (
  echo [ERROR] .venv\Scripts\python.exe not found.
  echo Create venv first: py -m venv .venv
  exit /b 1
)

echo [INFO] Using Python:
"%VENV_PY%" -c "import sys; print(sys.executable)"

echo [2/5] Installing backend dependencies in .venv...
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [ERROR] Failed to install backend dependencies.
  exit /b 1
)

echo [3/5] Starting backend server (.venv + .env)...
start "DrCT Backend" cmd /k "cd /d "%ROOT%" && call "%VENV_ACTIVATE%" && "%VENV_PY%" scripts\init_db.py && "%VENV_PY%" -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --env-file .env"
if errorlevel 1 (
  echo [ERROR] Failed to start backend command window.
  exit /b 1
)

echo [4/5] Starting frontend server...
if not exist "frontend\node_modules" (
  echo [INFO] frontend\node_modules not found. Installing frontend dependencies...
  cd /d "%ROOT%frontend"
  npm install
  if errorlevel 1 (
    echo [ERROR] Failed to install frontend dependencies.
    exit /b 1
  )
  cd /d "%ROOT%"
)

start "DrCT Frontend" cmd /k "cd /d "%ROOT%frontend" && npm run dev"
if errorlevel 1 (
  echo [ERROR] Failed to start frontend command window.
  exit /b 1
)

echo [5/5] Done.
echo Backend:  http://127.0.0.1:8000
echo Frontend: http://127.0.0.1:5173

endlocal