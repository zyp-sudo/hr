$ErrorActionPreference = "Continue"

$ProjectRoot = "E:\202676"
$DelaySeconds = 300
$PythonCommand = "python"
$ScriptPath = Join-Path $ProjectRoot "scripts\crawl_jobs_100k.py"
$LogDir = Join-Path $ProjectRoot "logs"

if (-not (Test-Path -LiteralPath $ProjectRoot)) {
    Write-Host "Project root not found: $ProjectRoot" -ForegroundColor Red
    exit 1
}

if (-not (Test-Path -LiteralPath $ScriptPath)) {
    Write-Host "Crawler script not found: $ScriptPath" -ForegroundColor Red
    exit 1
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

if (-not $env:CHINA_JOB_TARGET) { $env:CHINA_JOB_TARGET = "100000" }
if (-not $env:CHINA_JOB_SOURCES) { $env:CHINA_JOB_SOURCES = "china,foreign,imports" }
if (-not $env:CHINA_JOB_BALANCED) { $env:CHINA_JOB_BALANCED = "1" }
if (-not $env:ENABLE_GREENHOUSE) { $env:ENABLE_GREENHOUSE = "1" }
if (-not $env:ENABLE_LEVER) { $env:ENABLE_LEVER = "1" }
if (-not $env:ENABLE_REMOTEOK) { $env:ENABLE_REMOTEOK = "1" }
if (-not $env:ENABLE_ARBEITNOW) { $env:ENABLE_ARBEITNOW = "1" }
if (-not $env:ENABLE_TENCENT) { $env:ENABLE_TENCENT = "1" }
if (-not $env:ENABLE_IMPORTS) { $env:ENABLE_IMPORTS = "1" }
if (-not $env:TENCENT_JOB_MAX) { $env:TENCENT_JOB_MAX = "100000" }
if (-not $env:TENCENT_JOB_WORKERS) { $env:TENCENT_JOB_WORKERS = "32" }
if (-not $env:ARBEITNOW_MAX_PAGES) { $env:ARBEITNOW_MAX_PAGES = "2000" }

while ($true) {
    $startedAt = Get-Date
    $stamp = $startedAt.ToString("yyyyMMdd-HHmmss")
    $logPath = Join-Path $LogDir "crawl-loop-$stamp.log"

    Write-Host "[$($startedAt.ToString('yyyy-MM-dd HH:mm:ss'))] Starting crawl. Log: $logPath" -ForegroundColor Cyan
    Push-Location $ProjectRoot
    try {
        & $PythonCommand $ScriptPath *>&1 | Tee-Object -FilePath $logPath
        $exitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }

    $endedAt = Get-Date
    Write-Host "[$($endedAt.ToString('yyyy-MM-dd HH:mm:ss'))] Crawl finished with exit code $exitCode." -ForegroundColor Yellow
    Write-Host "Waiting $DelaySeconds seconds before next run. Press Ctrl+C to stop." -ForegroundColor DarkGray
    Start-Sleep -Seconds $DelaySeconds
}
