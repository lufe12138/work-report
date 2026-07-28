@echo off
REM 周报定时任务入口（Windows 计划任务调用本脚本）
REM 逻辑：先判断是否「放假前最后一个工作日」，是则拉取 GitLab 并用 LLM 生成周报

setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] 未找到虚拟环境 .venv，请先执行: python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  exit /b 1
)

REM 日志目录
if not exist "logs" mkdir logs

for /f %%i in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd"') do set TODAY=%%i
set LOG_FILE=logs\scheduled-%TODAY%.log

echo ===== %date% %time% 开始 =====>> "%LOG_FILE%"
".venv\Scripts\python.exe" -X utf8 main.py --if-last-workday >> "%LOG_FILE%" 2>&1
set EXIT_CODE=%ERRORLEVEL%
echo ===== %date% %time% 结束 exit=%EXIT_CODE% =====>> "%LOG_FILE%"
exit /b %EXIT_CODE%
