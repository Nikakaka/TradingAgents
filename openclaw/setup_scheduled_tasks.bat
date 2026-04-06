@echo off
chcp 65001 >nul 2>&1
REM ============================================================
REM OpenClaw Scheduled Tasks Setup Script for Windows
REM ============================================================
REM
REM 此脚本设置 Windows 任务计划，在交易日自动运行持仓分析
REM 早盘: 11:30 快速分析 (depth=1)
REM 收盘: 16:30 深度分析 (depth=3)
REM
REM 配置文件: openclaw/config/scheduled_tasks.json
REM 任务运行器: openclaw/run_task.py
REM

setlocal enabledelayedexpansion

REM 获取脚本所在目录
set SCRIPT_DIR=%~dp0
set PROJECT_DIR=%SCRIPT_DIR%..
set PYTHON_EXE=python

REM 检查 Python 是否可用
%PYTHON_EXE% --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please ensure Python is in PATH.
    exit /b 1
)

echo ============================================================
echo OpenClaw 定时任务设置
echo ============================================================
echo.
echo 项目目录: %PROJECT_DIR%
echo.

REM 检查配置文件
set CONFIG_FILE=%PROJECT_DIR%\openclaw\config\scheduled_tasks.json
if not exist "%CONFIG_FILE%" (
    echo [WARN] 配置文件不存在: %CONFIG_FILE%
    echo [INFO] 使用默认配置
)

REM 检查飞书配置
set FEISHU_CONFIG=%PROJECT_DIR%\config\feishu.json
if exist "%FEISHU_CONFIG%" (
    echo [OK] 找到飞书配置文件: %FEISHU_CONFIG%
) else (
    echo [INFO] 未找到飞书配置文件: %FEISHU_CONFIG%
    echo [INFO] 请设置环境变量 FEISHU_WEBHOOK_URL 或创建 config/feishu.json
    echo.
)

REM 检查持仓文件
set POSITIONS_FILE=%PROJECT_DIR%\positions.txt
if exist "%POSITIONS_FILE%" (
    echo [OK] 找到持仓文件: %POSITIONS_FILE%
) else (
    echo [WARN] 未找到持仓文件: %POSITIONS_FILE%
    echo [INFO] 请先运行 python scripts/quick_import.py 导入持仓
    echo.
)

echo.
echo 创建 Windows 任务计划...
echo.

REM 任务1: 早盘快速分析 (11:30)
set TASK_NAME_MORNING=OpenClaw_MorningAnalysis
set TASK_CMD_MORNING=%PYTHON_EXE% "%PROJECT_DIR%\openclaw\run_task.py" --task morning

REM 删除已存在的任务
schtasks /query /tn "%TASK_NAME_MORNING%" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] 删除已存在的任务: %TASK_NAME_MORNING%
    schtasks /delete /tn "%TASK_NAME_MORNING%" /f >nul 2>&1
)

REM 创建新任务 (工作日 11:30)
schtasks /create ^
    /tn "%TASK_NAME_MORNING%" ^
    /tr "\"%PYTHON_EXE%\" \"%PROJECT_DIR%\openclaw\run_task.py\" --task morning" ^
    /sc weekly /d MON,TUE,WED,THU,FRI ^
    /st 11:30 ^
    /f ^
    /rl HIGHEST

if errorlevel 1 (
    echo [ERROR] 创建早盘任务失败
) else (
    echo [OK] 早盘任务创建成功: %TASK_NAME_MORNING%
    echo     运行时间: 工作日 11:30
    echo     研究深度: 1 (快速分析)
)

echo.

REM 任务2: 收盘深度分析 (16:30)
set TASK_NAME_EVENING=OpenClaw_EveningAnalysis
set TASK_CMD_EVENING=%PYTHON_EXE% "%PROJECT_DIR%\openclaw\run_task.py" --task evening

REM 删除已存在的任务
schtasks /query /tn "%TASK_NAME_EVENING%" >nul 2>&1
if not errorlevel 1 (
    echo [INFO] 删除已存在的任务: %TASK_NAME_EVENING%
    schtasks /delete /tn "%TASK_NAME_EVENING%" /f >nul 2>&1
)

REM 创建新任务 (工作日 16:30)
schtasks /create ^
    /tn "%TASK_NAME_EVENING%" ^
    /tr "\"%PYTHON_EXE%\" \"%PROJECT_DIR%\openclaw\run_task.py\" --task evening" ^
    /sc weekly /d MON,TUE,WED,THU,FRI ^
    /st 16:30 ^
    /f ^
    /rl HIGHEST

if errorlevel 1 (
    echo [ERROR] 创建收盘任务失败
) else (
    echo [OK] 收盘任务创建成功: %TASK_NAME_EVENING%
    echo     运行时间: 工作日 16:30
    echo     研究深度: 3 (深度分析)
)

echo.
echo ============================================================
echo 设置完成
echo ============================================================
echo.
echo 已创建任务:
echo   1. %TASK_NAME_MORNING% - 工作日 11:30 (快速分析)
echo   2. %TASK_NAME_EVENING% - 工作日 16:30 (深度分析)
echo.
echo 管理任务:
echo   查看任务: schtasks /query /tn "OpenClaw_MorningAnalysis"
echo   立即运行: schtasks /run /tn "OpenClaw_MorningAnalysis"
echo   删除任务: schtasks /delete /tn "OpenClaw_MorningAnalysis" /f
echo.
echo 手动运行测试:
echo   早盘分析: python openclaw/run_task.py --task morning
echo   收盘分析: python openclaw/run_task.py --task evening
echo   自定义深度: python openclaw/run_task.py --depth 2
echo   查看配置: python openclaw/run_task.py --list
echo.
echo 飞书通知配置:
echo   方式1: 设置环境变量 FEISHU_WEBHOOK_URL
echo   方式2: 创建文件 %PROJECT_DIR%\config\feishu.json
echo          内容: {"webhook_url": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"}
echo.

pause
