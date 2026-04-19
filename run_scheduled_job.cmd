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
REM Optimizations for depth=3:
REM - Increased recursion limit to 600
REM - Memory cleanup between stocks
REM - 6-hour timeout for batch analysis
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
    set "TIMEOUT=9000"
) else if "%TASK_TYPE%"=="evening" (
    set "DEPTH=3"
    set "TASK_FILE=openclaw\tasks\positions_evening.json"
    set "TASK_NAME=Evening Deep Analysis"
    set "TIMEOUT=21600"
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
echo Timeout: %TIMEOUT% seconds
echo ============================================================
echo.

REM Step 1: Update task file (read latest positions from G:\Finance\持仓)
echo [STEP 1] Updating task file from latest positions...
"%PYTHON_EXE%" "%SCRIPT_DIR%scripts\generate_position_tasks.py" --positions-dir "%POSITIONS_DIR%" --depth %DEPTH% --output "%SCRIPT_DIR%%TASK_FILE%"
if errorlevel 1 (
    echo [ERROR] Failed to generate task file
    exit /b 1
)
echo.

REM Step 2: Run batch analysis
REM Note: Do NOT use --stop-on-error so that individual stock failures don't stop the batch
echo [STEP 2] Running batch analysis...
set "TIMESTAMP=%DATE:~0,4%%DATE:~5,2%%DATE:~8,2%_%TIME:~0,2%%TIME:~3,2%%TIME:~6,2%"
set "TIMESTAMP=%TIMESTAMP: =0%"
set "RESULT_JSON=%SCRIPT_DIR%results\openclaw\batch_%TIMESTAMP%.json"
set "RESULT_MD=%SCRIPT_DIR%results\openclaw\report_%TIMESTAMP%.md"

"%PYTHON_EXE%" "%SCRIPT_DIR%scripts\run_tradingagents_batch.py" "%SCRIPT_DIR%%TASK_FILE%" --result-json "%RESULT_JSON%" --result-markdown "%RESULT_MD%"
set "BATCH_EXIT_CODE=%errorlevel%"
echo.

REM Step 3: Send Feishu notification
echo [STEP 3] Sending notification...
"%PYTHON_EXE%" "%SCRIPT_DIR%scripts\send_feishu_notification.py" --task "%TASK_TYPE%" --result "%RESULT_JSON%" 2>nul
if errorlevel 1 (
    echo [WARN] Failed to send notification (non-fatal)
)
echo.

echo ============================================================
echo Completed with exit code: %BATCH_EXIT_CODE%
echo Result: %RESULT_JSON%
echo Report: %RESULT_MD%
echo ============================================================

REM Always exit 0 to indicate the job ran (even if some stocks failed)
REM The batch result JSON contains detailed per-stock status
exit /b 0
