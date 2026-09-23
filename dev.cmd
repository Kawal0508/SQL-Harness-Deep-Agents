@echo off
rem Windows equivalent of the Makefile, for shells without make.
rem
rem   dev install   virtualenv, Python deps, npm deps
rem   dev db        build Database\Synthea\health.db from the Synthea CSVs
rem   dev build     compile the frontend bundle into Frontend\dist
rem   dev up        build, then run both services
rem   dev down      stop whatever is listening on 8000 or 8001
rem   dev check     read-only self-check, needs no API key

setlocal
set PY=.venv\Scripts\python.exe

if /i "%~1"=="install" goto install
if /i "%~1"=="db" goto db
if /i "%~1"=="build" goto build
if /i "%~1"=="up" goto up
if /i "%~1"=="down" goto down
if /i "%~1"=="check" goto check
goto help

:help
echo   dev install   virtualenv, Python deps, npm deps
echo   dev db        build Database\Synthea\health.db from the Synthea CSVs
echo   dev build     compile the frontend bundle into Frontend\dist
echo   dev up        build, then run both services
echo   dev down      stop whatever is listening on 8000 or 8001
echo   dev check     read-only self-check, needs no API key
exit /b 0

:install
python -m venv .venv
if errorlevel 1 exit /b 1
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 exit /b 1
npm --prefix Frontend install
exit /b %errorlevel%

:db
"%PY%" Database\Synthea\load.py
exit /b %errorlevel%

:build
npm --prefix Frontend run build
exit /b %errorlevel%

:check
"%PY%" Backend\tools.py
exit /b %errorlevel%

:up
call npm --prefix Frontend run build
if errorlevel 1 exit /b 1
if not exist "Database\Synthea\health.db" (
  echo No Database\Synthea\health.db. Run: dev db
  exit /b 1
)
echo agent  http://localhost:8000
echo admin  http://localhost:8001
rem Admin gets its own window so this one can host the agent service. Closing
rem that window, or `dev down`, stops it; Ctrl-C here stops only the agent.
start "sql-harness-admin" "%PY%" -m uvicorn admin:app --app-dir Backend --port 8001
"%PY%" -m uvicorn api:app --app-dir Backend --port 8000
exit /b %errorlevel%

:down
rem Kill the listening worker itself. Stopping a uvicorn --reload parent leaves
rem its worker holding the port, which then refuses the next bind.
powershell -NoProfile -Command "Get-NetTCPConnection -LocalPort 8000,8001 -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique | ForEach-Object { Stop-Process -Id $_ -Force -ErrorAction SilentlyContinue }"
echo stopped
exit /b 0
