param(
    [Parameter(Mandatory = $true)]
    [string]$ResultJsonPath,
    [Parameter(Mandatory = $true)]
    [string]$Target,
    [string]$Channel = "feishu",
    [string]$Title = "每日股市分析"
)

$ErrorActionPreference = "Stop"

$displayNameOverrides = @{
    "9988.HK" = "阿里巴巴-W"
    "0700.HK" = "腾讯控股"
    "600519.SH" = "贵州茅台"
    "300750.SZ" = "宁德时代"
    "159934.SZ" = "黄金9999（代理：黄金ETF）"
}

$decisionLabelMap = @{
    "BUY" = "买入"
    "HOLD" = "持有"
    "SELL" = "卖出"
    "UNKNOWN" = "未知"
}

$statusLabelMap = @{
    "ok" = "成功"
    "error" = "失败"
}

if (-not (Test-Path -LiteralPath $ResultJsonPath)) {
    throw "Result JSON not found: $ResultJsonPath"
}

$rawJson = [System.IO.File]::ReadAllText($ResultJsonPath, [System.Text.Encoding]::UTF8)
$result = $rawJson | ConvertFrom-Json
if (-not $result) {
    throw "Unable to parse result JSON: $ResultJsonPath"
}

$lines = New-Object System.Collections.Generic.List[string]
$lines.Add($Title)
$lines.Add("")
$lines.Add(("生成时间：{0}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss")))

$counts = $result.counts
if ($counts) {
    $lines.Add(("汇总：买入 {0} | 持有 {1} | 卖出 {2} | 其他 {3} | 失败 {4}" -f $counts.buy, $counts.hold, $counts.sell, $counts.other, $counts.failed))
}

$lines.Add("")
$lines.Add("结论明细：")

foreach ($item in $result.results) {
    $ticker = [string]$item.ticker
    $displayName = $displayNameOverrides[$ticker]
    if (-not $displayName) {
        $displayName = $ticker
    }

    $decision = ([string]$item.decision).ToUpperInvariant()
    if (-not $decision) {
        $decision = "UNKNOWN"
    }
    $decisionLabel = $decisionLabelMap[$decision]
    if (-not $decisionLabel) {
        $decisionLabel = $decision
    }

    $status = [string]$item.status
    if ($status -eq "ok") {
        $decisionChange = [string]$item.decision_change
        if ($decisionChange) {
            $lines.Add(("- {0}（{1}）：{2}；变化：{3}" -f $displayName, $ticker, $decisionLabel, $decisionChange))
        } else {
            $lines.Add(("- {0}（{1}）：{2}" -f $displayName, $ticker, $decisionLabel))
        }
    } else {
        $statusLabel = $statusLabelMap[$status]
        if (-not $statusLabel) {
            $statusLabel = $status
        }
        $errorText = [string]$item.error
        if ($errorText) {
            $errorText = $errorText -replace "\s+", " "
            if ($errorText.Length -gt 120) {
                $errorText = $errorText.Substring(0, 120) + "..."
            }
            $lines.Add(("- {0}（{1}）：{2}；原因：{3}" -f $displayName, $ticker, $statusLabel, $errorText))
        } else {
            $lines.Add(("- {0}（{1}）：{2}" -f $displayName, $ticker, $statusLabel))
        }
    }
}

$lines.Add("")
$lines.Add(("结果文件：{0}" -f $ResultJsonPath))

$message = [string]::Join([Environment]::NewLine, $lines)
openclaw message send --channel $Channel --target $Target --message $message --json | Out-Null
Write-Output ("Sent report to {0}:{1}" -f $Channel, $Target)
