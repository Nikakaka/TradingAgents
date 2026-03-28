param(
    [string]$RepoRoot = (Split-Path -Parent $PSScriptRoot),
    [int]$HeartbeatSeconds = 30
)

$ErrorActionPreference = "Stop"

$batchScript = Join-Path $RepoRoot "run_openclaw_daily_market_watch.cmd"
$resultJson = Join-Path $RepoRoot "results\openclaw\daily_4am_market_watch.json"
$resultMarkdown = Join-Path $RepoRoot "results\openclaw\daily_4am_market_watch.md"

if (-not (Test-Path -LiteralPath $batchScript)) {
    throw "Batch script not found: $batchScript"
}

$startTime = Get-Date
Write-Output ("[market-watch] start: {0}" -f $startTime.ToString("yyyy-MM-dd HH:mm:ss"))
Write-Output ("[market-watch] command: {0}" -f $batchScript)

$process = Start-Process `
    -FilePath "cmd.exe" `
    -ArgumentList @("/c", "`"$batchScript`"") `
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

if (-not (Test-Path -LiteralPath $resultJson)) {
    throw "Expected result JSON not found: $resultJson"
}

if (-not (Test-Path -LiteralPath $resultMarkdown)) {
    throw "Expected result Markdown not found: $resultMarkdown"
}

$jsonInfo = Get-Item -LiteralPath $resultJson
$mdInfo = Get-Item -LiteralPath $resultMarkdown

Write-Output ("[market-watch] json updated: {0}" -f $jsonInfo.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))
Write-Output ("[market-watch] markdown updated: {0}" -f $mdInfo.LastWriteTime.ToString("yyyy-MM-dd HH:mm:ss"))

if ($exitCode -ne 0) {
    throw "Market watch command failed with exit code $exitCode"
}

Write-Output "[market-watch] completed successfully"
