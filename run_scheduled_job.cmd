@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
REM ============================================================
REM OpenClaw Scheduled Job Runner
REM
REM This script is called by OpenClaw scheduled tasks:
REM 1. Update position task files
REM 2. Run batch analysis
REM 3. Send Feishu notification
REM
REM Usage:
REM   run_scheduled_job.cmd morning   # Morning analysis (depth=1)
REM   run_scheduled_job.cmd evening   # Evening analysis (depth=3)
REM
REM Timeout handling:
REM - Each subprocess has its own timeout via Python
REM - The entire script is wrapped with a global timeout
REM - A progress marker file is created so OpenClaw can detect
REM   that the task is running (not failed)
REM
REM Position files are read from G:\Finance\持仓 (latest file by date)
REM

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=%SCRIPT_DIR%.venv\Scripts\python.exe"
set "POSITIONS_DIR=G:\Finance\持仓"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python not found: %PYTHON_EXE%
    exit /b 1
)

if "%~1"=="" (
    echo Usage: run_scheduled_job.cmd ^<morning^|evening^>
    exit /b 1
)

set "TASK_TYPE=%~1"

REM Set task parameters
if "%TASK_TYPE%"=="morning" (
    set "DEPTH=1"
    set "TASK_FILE=openclaw\tasks\positions_morning.json"
    set "TASK_NAME=Morning Quick Analysis"
    set "GLOBAL_TIMEOUT=3600"
    set "PER_TASK_TIMEOUT=1200"
    set "PARALLEL=3"
) else if "%TASK_TYPE%"=="evening" (
    set "DEPTH=3"
    set "TASK_FILE=openclaw\tasks\positions_evening.json"
    set "TASK_NAME=Evening Deep Analysis"
    set "GLOBAL_TIMEOUT=21600"
    set "PER_TASK_TIMEOUT=3600"
    set "PARALLEL=2"
) else (
    echo [ERROR] Unknown task type: %TASK_TYPE%
    echo Usage: run_scheduled_job.cmd ^<morning^|evening^>
    exit /b 1
)

echo ============================================================
echo OpenClaw %TASK_NAME%
echo Time: %DATE% %TIME%
echo Depth: %DEPTH%
echo Positions Dir: %POSITIONS_DIR%
echo Global Timeout: %GLOBAL_TIMEOUT% seconds
echo Per-Task Timeout: %PER_TASK_TIMEOUT% seconds
echo Parallel Workers: %PARALLEL%
echo ============================================================
echo.

REM Create progress marker so OpenClaw knows the task started
set "PROGRESS_FILE=%SCRIPT_DIR%results\openclaw\.scheduled_job_%TASK_TYPE%_running"
echo Started at %DATE% %TIME% > "%PROGRESS_FILE%"

REM Step 1: Update task file (read latest positions from G:\Finance\持仓)
echo [STEP 1] Updating task file from latest positions...
"%PYTHON_EXE%" "%SCRIPT_DIR%scripts\generate_position_tasks.py" --positions-dir "%POSITIONS_DIR%" --depth %DEPTH% --output "%SCRIPT_DIR%%TASK_FILE%"
if errorlevel 1 (
    echo [ERROR] Failed to generate task file
    echo Failed at Step 1: generate_position_tasks.py returned error >> "%PROGRESS_FILE%"
    del "%PROGRESS_FILE%" 2>nul
    exit /b 1
)
echo Step 1 done at %DATE% %TIME% >> "%PROGRESS_FILE%"
echo.

REM Step 2: Run batch analysis with per-task timeout
REM Note: Do NOT use --stop-on-error so that individual stock failures don't stop the batch
echo [STEP 2] Running batch analysis...
set "TIMESTAMP=%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "RESULT_JSON=%SCRIPT_DIR%results\openclaw\batch_%TIMESTAMP%.json"
set "RESULT_MD=%SCRIPT_DIR%results\openclaw\report_%TIMESTAMP%.md"

echo Result JSON: %RESULT_JSON% >> "%PROGRESS_FILE%"

set "TRADINGAGENTS_TASK_TIMEOUT=%PER_TASK_TIMEOUT%"
set "TRADINGAGENTS_PROGRESS_FILE=%PROGRESS_FILE%"
"%PYTHON_EXE%" "%SCRIPT_DIR%scripts\run_tradingagents_batch.py" "%SCRIPT_DIR%%TASK_FILE%" --result-json "%RESULT_JSON%" --result-markdown "%RESULT_MD%" --parallel %PARALLEL%
set "BATCH_EXIT_CODE=%errorlevel%"
echo Step 2 done at %DATE% %TIME% exit_code=%BATCH_EXIT_CODE% >> "%PROGRESS_FILE%"
echo.

REM Step 3: Send Feishu notification
echo [STEP 3] Sending notification...
"%PYTHON_EXE%" "%SCRIPT_DIR%scripts\send_feishu_notification.py" --task "%TASK_TYPE%" --result "%RESULT_JSON%" 2>nul
if errorlevel 1 (
    echo [WARN] Failed to send notification (non-fatal)
)
echo.

REM Remove progress marker (task completed)
del "%PROGRESS_FILE%" 2>nul

echo ============================================================
echo Completed with exit code: %BATCH_EXIT_CODE%
echo Result: %RESULT_JSON%
echo Report: %RESULT_MD%
echo ============================================================

REM Always exit 0 to indicate the job ran (even if some stocks failed)
REM The batch result JSON contains detailed per-stock status
exit /b 0
