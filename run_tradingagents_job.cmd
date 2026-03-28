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

if "%~1"=="" (
  echo Usage: run_tradingagents_job.cmd ^<task-config.json^> [extra runner args]
  exit /b 1
)

set "TASK_CONFIG=%~1"
set "EXTRA_ARGS="
:collect_args
if "%~2"=="" goto run_job
set "EXTRA_ARGS=%EXTRA_ARGS% %~2"
shift
goto collect_args

:run_job
"%PYTHON_EXE%" "%RUNNER%" --config-file "%TASK_CONFIG%" %EXTRA_ARGS%
exit /b %errorlevel%
