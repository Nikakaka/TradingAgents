param(
    [int]$HeartbeatSeconds = 30
)

$ErrorActionPreference = "Stop"

$RepoRoot = $PSScriptRoot
$BatchConfig = Join-Path $RepoRoot "openclaw\tasks\daily_4am_market_watch.json"
$ResultJson = Join-Path $RepoRoot "results\openclaw\daily_4am_market_watch.json"
$ResultMarkdown = Join-Path $RepoRoot "results\openclaw\daily_4am_market_watch.md"
$BatchScript = Join-Path $RepoRoot "run_tradingagents_batch.cmd"
$SendScript = Join-Path $RepoRoot "scripts\send_openclaw_report.ps1"
$ReportTarget = "ou_1fe34e053d3467d44463b76f316872e2"

Write-Output "[daily-watch] Starting at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

if (-not (Test-Path -LiteralPath $BatchScript)) {
    throw "TradingAgents batch command not found: $BatchScript"
}

# Run the batch analysis
Write-Output "[daily-watch] Running batch analysis..."
$process = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList @("/c", "`"$BatchScript`" `"$BatchConfig`" --result-json `"$ResultJson`" --result-markdown `"$ResultMarkdown`"") `
    -WorkingDirectory $RepoRoot `
    -PassThru `
    -NoNewWindow

Write-Output "[daily-watch] Batch process started (PID: $($process.Id))"

# Monitor the process with heartbeats
$startTime = Get-Date
while (-not $process.HasExited) {
    Start-Sleep -Seconds $HeartbeatSeconds
    $process.Refresh()
    if (-not $process.HasExited) {
        $elapsed = [int]((Get-Date) - $startTime).TotalSeconds
        Write-Output "[daily-watch] Still running... ${elapsed}s elapsed"
    }
}

$exitCode = $process.ExitCode
Write-Output "[daily-watch] Batch process finished with exit code: $exitCode"

if ($exitCode -eq 0) {
    # Verify output files exist
    if (-not (Test-Path -LiteralPath $ResultJson)) {
        throw "Expected result JSON not found: $ResultJson"
    }

    if (-not (Test-Path -LiteralPath $ResultMarkdown)) {
        throw "Expected result Markdown not found: $ResultMarkdown"
    }

    Write-Output "[daily-watch] Output files verified"
}

# Send Feishu notification regardless of batch exit code (unless script errors)
Write-Output "[daily-watch] Sending Feishu notification..."

if (-not (Test-Path -LiteralPath $SendScript)) {
    throw "Report send script not found: $SendScript"
}

& $SendScript -ResultJsonPath $ResultJson -Target $ReportTarget -Title "每日股市分析"
$notifyExitCode = $LASTEXITCODE

if ($notifyExitCode -ne 0) {
    Write-Warning "[daily-watch] Feishu notification failed with exit code: $notifyExitCode"
} else {
    Write-Output "[daily-watch] Feishu notification sent successfully"
}

Write-Output "[daily-watch] Completed at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"

# Exit with batch exit code to preserve status
exit $exitCode
