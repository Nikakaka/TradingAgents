$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $PSScriptRoot
$PythonExe = Join-Path $ScriptDir ".venv\Scripts\python.exe"
$HostName = "127.0.0.1"
$Port = 8000
$Url = "http://${HostName}:${Port}"

if (-not (Test-Path $PythonExe)) {
    Write-Error "TradingAgents virtualenv Python not found: $PythonExe"
}

Write-Host "Checking for existing process on port $Port..."
for ($attempt = 0; $attempt -lt 5; $attempt++) {
    $existing = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique

    if (-not $existing) {
        break
    }

    foreach ($procId in $existing) {
        if ($procId) {
            Write-Host "Stopping existing process $procId on port $Port..."
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }

    Start-Sleep -Milliseconds 800
}

$stillListening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique

if ($stillListening) {
    throw "Failed to release port $Port. Process(es) still listening: $($stillListening -join ', ')"
}

Write-Host "Starting TradingAgents Web UI on $Url"
$process = Start-Process -FilePath $PythonExe `
    -ArgumentList @("-m", "cli.main", "web", "--host", $HostName, "--port", "$Port") `
    -WorkingDirectory $ScriptDir `
    -PassThru

$portReady = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 1
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object -First 1 -ExpandProperty OwningProcess
    if ($listener) {
        $portReady = $true
        break
    }
}

if (-not $portReady) {
    if ($process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }
    throw "TradingAgents Web UI did not start listening on port $Port in time."
}

$timestamp = [DateTimeOffset]::Now.ToUnixTimeSeconds()
Start-Process "$Url/?t=$timestamp"

$listenerProc = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
    Select-Object -First 1 -ExpandProperty OwningProcess

Write-Host "Web UI launched. If the browser did not open, visit $Url"
if ($listenerProc) {
    try {
        $procInfo = Get-Process -Id $listenerProc -ErrorAction Stop
        Write-Host "Listening PID: $($procInfo.Id) ($($procInfo.ProcessName))"
    } catch {
    }
}
