@echo off
setlocal
set REPO_ROOT=%~dp0..
set PYTHON_CMD=python
if exist "%REPO_ROOT%\.venv\Scripts\python.exe" set PYTHON_CMD=%REPO_ROOT%\.venv\Scripts\python.exe
start "backend" powershell -NoExit -Command "Set-Location '%REPO_ROOT%'; $env:PYTHONPYCACHEPREFIX='%REPO_ROOT%\.pycache'; & '%PYTHON_CMD%' -m uvicorn --app-dir '%REPO_ROOT%' backend.app.main:app --reload --host 127.0.0.1 --port 8002"
cd /d "%REPO_ROOT%"
set VITE_API_BASE_URL=http://127.0.0.1:8002
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5190 --strictPort --configLoader native
