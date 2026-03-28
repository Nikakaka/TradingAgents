@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"
set "RUNNER=%SCRIPT_DIR%scripts\run_tradingagents.py"

if not exist "%PYTHON_EXE%" (
  echo TradingAgents virtualenv Python not found: "%PYTHON_EXE%"
  exit /b 1
)

if not exist "%RUNNER%" (
  echo TradingAgents runner not found: "%RUNNER%"
  exit /b 1
)

"%PYTHON_EXE%" "%RUNNER%" %*
exit /b %errorlevel%
