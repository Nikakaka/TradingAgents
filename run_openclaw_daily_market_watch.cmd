@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "BATCH_CONFIG=%SCRIPT_DIR%openclaw\tasks\daily_4am_market_watch.json"
set "RESULT_JSON=%SCRIPT_DIR%results\openclaw\daily_4am_market_watch.json"
set "RESULT_MD=%SCRIPT_DIR%results\openclaw\daily_4am_market_watch.md"
set "RUNNER=%SCRIPT_DIR%run_tradingagents_batch.cmd"
set "SEND_SCRIPT=%SCRIPT_DIR%scripts\send_openclaw_report.ps1"
set "REPORT_TARGET=ou_1fe34e053d3467d44463b76f316872e2"

if not exist "%RUNNER%" (
  echo TradingAgents batch command not found: "%RUNNER%"
  exit /b 1
)

call "%RUNNER%" "%BATCH_CONFIG%" --result-json "%RESULT_JSON%" --result-markdown "%RESULT_MD%"
if errorlevel 1 exit /b %errorlevel%

if not exist "%SEND_SCRIPT%" (
  echo Report send script not found: "%SEND_SCRIPT%"
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%SEND_SCRIPT%" -ResultJsonPath "%RESULT_JSON%" -Target "%REPORT_TARGET%" -Title "每日股市分析"
exit /b %errorlevel%
