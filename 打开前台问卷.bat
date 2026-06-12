@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if "%SURVEY_HOST%"=="" set SURVEY_HOST=127.0.0.1
if "%SURVEY_PORT%"=="" set SURVEY_PORT=8000
if "%SURVEY_DB_PATH%"=="" set SURVEY_DB_PATH=survey_data.db
if "%SURVEY_PROJECT_ROOT%"=="" set SURVEY_PROJECT_ROOT=.
if "%SURVEY_BASE_URL%"=="" set SURVEY_BASE_URL=http://%SURVEY_HOST%:%SURVEY_PORT%

powershell -NoProfile -ExecutionPolicy Bypass -Command "try { Invoke-WebRequest -UseBasicParsing -Uri '%SURVEY_BASE_URL%/' -TimeoutSec 2 | Out-Null; exit 0 } catch { exit 1 }"
if errorlevel 1 (
  start "问卷服务" cmd /k "cd /d ""%~dp0"" && set SURVEY_HOST=%SURVEY_HOST% && set SURVEY_PORT=%SURVEY_PORT% && set SURVEY_DB_PATH=%SURVEY_DB_PATH% && set SURVEY_PROJECT_ROOT=%SURVEY_PROJECT_ROOT% && set SURVEY_BASE_URL=%SURVEY_BASE_URL% && python survey_server.py --host %SURVEY_HOST% --port %SURVEY_PORT% --db ""%SURVEY_DB_PATH%"" --root ""%SURVEY_PROJECT_ROOT%"""
  timeout /t 3 >nul
)

start "" "%SURVEY_BASE_URL%/survey"

endlocal
