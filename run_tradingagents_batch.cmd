@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"
set "RUNNER=%SCRIPT_DIR%scripts\run_tradingagents_batch.py"

if not exist "%PYTHON_EXE%" (
  echo TradingAgents virtualenv Python not found: "%PYTHON_EXE%"
  exit /b 1
)

if not exist "%RUNNER%" (
  echo TradingAgents batch runner not found: "%RUNNER%"
  exit /b 1
)

if "%~1"=="" (
  echo Usage: run_tradingagents_batch.cmd ^<batch-config.json^> [extra runner args]
  exit /b 1
)

set "BATCH_CONFIG=%~1"
set "EXTRA_ARGS="
:collect_args
if "%~2"=="" goto run_batch
set "EXTRA_ARGS=%EXTRA_ARGS% %~2"
shift
goto collect_args

:run_batch
"%PYTHON_EXE%" "%RUNNER%" "%BATCH_CONFIG%" %EXTRA_ARGS%
exit /b %errorlevel%
