param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [int]$HeartbeatSeconds = 30
)

$ErrorActionPreference = "Stop"

$batchScript = Join-Path $RepoRoot "run_tradingagents_batch.cmd"
$resultJson = Join-Path $RepoRoot "results\openclaw\daily_4am_market_watch.json"
$resultMarkdown = Join-Path $RepoRoot "results\openclaw\daily_4am_market_watch.md"
$batchConfig = Join-Path $RepoRoot "openclaw\tasks\daily_4am_market_watch.json"
$sendScript = Join-Path $RepoRoot "scripts\send_openclaw_report.ps1"
$reportTarget = "ou_1fe34e053d3467d44463b76f316872e2"

if (-not (Test-Path -LiteralPath $batchScript)) {
    throw "Batch script not found: $batchScript"
}

$startTime = Get-Date
Write-Output ("[market-watch] start: {0}" -f $startTime.ToString("yyyy-MM-dd HH:mm:ss"))
Write-Output ("[market-watch] command: {0}" -f $batchScript)

# Run the batch analysis
$process = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList @("/c", "`"$batchScript`" `"$batchConfig`" --result-json `"$resultJson`" --result-markdown `"$resultMarkdown`"") `
    -WorkingDirectory $RepoRoot `
    -PassThru

Write-Output ("[market-watch] pid: {0}" -f $process.Id)

while (-not $process.HasExited) {
    Start-Sleep -Seconds $HeartbeatSeconds
    $process.Refresh()
    if (-not $process.HasExited) {
        $elapsed = [int]((Get-Date) - $startTime).TotalSeconds
        Write-Output ("[market-watch] still running... {0}s elapsed" -f $elapsed)
    }
}

$exitCode = $process.ExitCode
$finishedAt = Get-Date
Write-Output ("[market-watch] finished: {0}" -f $finishedAt.ToString("yyyy-MM-dd HH:mm:ss"))
Write-Output ("[market-watch] exit code: {0}" -f $exitCode)

# Check if output files exist
$jsonUpdated = $false
$mdUpdated = $false

if (Test-Path -LiteralPath $resultJson) {
    $jsonUpdated = $true
    $jsonInfo = Get-Item -LiteralPath $resultJson
    Write-Output ("[market-watch] json updated: {0}" -f $jsonInfo.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))
} else {
    Write-Output ("[market-watch] json file not found: {0}" -f $resultJson)
}

if (Test-Path -LiteralPath $resultMarkdown) {
    $mdUpdated = $true
    $mdInfo = Get-Item -LiteralPath $resultMarkdown
    Write-Output ("[market-watch] markdown updated: {0}" -f $mdInfo.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))
} else {
    Write-Output ("[market-watch] markdown file not found: {0}" -f $resultMarkdown)
}

# Send Feishu notification
Write-Output ("[market-watch] sending notification...")

if (Test-Path -LiteralPath $sendScript) {
    & $sendScript -ResultJsonPath $resultJson -Target $reportTarget -Title "每日股市分析"
    $notifyExitCode = $LASTEXITCODE
    if ($notifyExitCode -ne 0) {
        Write-Warning ("[market-watch] notification failed with exit code: {0}" -f $notifyExitCode)
    } else {
        Write-Output "[market-watch] notification sent successfully"
    }
} else {
    Write-Warning ("[market-watch] notification script not found: {0}" -f $sendScript)
}

# Final status
if ($exitCode -ne 0) {
    Write-Output ("[market-watch] completed with errors (exit code: {0})" -f $exitCode)
    exit $exitCode
}

Write-Output "[market-watch] completed successfully"
exit 0
