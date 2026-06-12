@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if "%SURVEY_HOST%"=="" set SURVEY_HOST=127.0.0.1
if "%SURVEY_PORT%"=="" set SURVEY_PORT=8000
if "%SURVEY_DB_PATH%"=="" set SURVEY_DB_PATH=survey_data.db
if "%SURVEY_PROJECT_ROOT%"=="" set SURVEY_PROJECT_ROOT=.
if "%SURVEY_BASE_URL%"=="" set SURVEY_BASE_URL=http://%SURVEY_HOST%:%SURVEY_PORT%

if not exist survey_server.py (
  echo 未找到 survey_server.py
  pause
  exit /b 1
)

echo 正在启动研究问卷系统...
echo 前台问卷: %SURVEY_BASE_URL%/survey
echo 管理后台: %SURVEY_BASE_URL%/admin/login
echo.
python survey_server.py --host %SURVEY_HOST% --port %SURVEY_PORT% --db "%SURVEY_DB_PATH%" --root "%SURVEY_PROJECT_ROOT%"

endlocal
