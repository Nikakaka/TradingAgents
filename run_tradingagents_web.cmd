@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "RUNNER=%SCRIPT_DIR%scripts\run_tradingagents_web.ps1"

if not exist "%POWERSHELL_EXE%" (
  echo PowerShell not found: "%POWERSHELL_EXE%"
  exit /b 1
)

if not exist "%RUNNER%" (
  echo TradingAgents web runner not found: "%RUNNER%"
  exit /b 1
)

"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%RUNNER%"
exit /b %errorlevel%
