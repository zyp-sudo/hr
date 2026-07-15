# XH-202621 one-click launcher
# Starts MySQL/Neo4j/Elasticsearch + Java API (8081) + Python API (8080) + frontend (8501).
$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot
Set-Location $ProjectRoot

$LocalEnv = Join-Path $ProjectRoot "scripts\local-env.ps1"
if (Test-Path $LocalEnv) {
  . $LocalEnv
  Write-Host "==> Loaded local environment" -ForegroundColor DarkGray
}

function Test-LocalPort {
  param([Parameter(Mandatory = $true)][int]$Port)

  $client = New-Object System.Net.Sockets.TcpClient
  try {
    $pending = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
    if (-not $pending.AsyncWaitHandle.WaitOne(250)) { return $false }
    $client.EndConnect($pending)
    return $true
  } catch {
    return $false
  } finally {
    $client.Close()
  }
}

function Wait-LocalPort {
  param(
    [Parameter(Mandatory = $true)][int]$Port,
    [Parameter(Mandatory = $true)][System.Management.Automation.Job]$Job,
    [int]$Attempts = 40
  )

  for ($attempt = 0; $attempt -lt $Attempts; $attempt++) {
    if (Test-LocalPort -Port $Port) { return $true }
    if ($Job.State -in @("Completed", "Failed", "Stopped")) { return $false }
    Start-Sleep -Milliseconds 500
  }
  return $false
}

function Write-JobFailure {
  param(
    [Parameter(Mandatory = $true)][string]$Service,
    [Parameter(Mandatory = $true)][System.Management.Automation.Job]$Job
  )

  Write-Host "$Service failed (job state: $($Job.State))." -ForegroundColor Red
  $output = Receive-Job -Job $Job -Keep -ErrorAction SilentlyContinue 2>&1
  if ($output) { $output | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed } }
}

if ($env:SKIP_STORAGE_INIT -ne "true") {
  & (Join-Path $ProjectRoot "scripts\init-storage.ps1")
  if (-not $?) { throw "Storage initialization failed." }
}

Write-Host "==> Stopping old application services..." -ForegroundColor Cyan
$ports = @(8080, 8081, 8501)
foreach ($line in netstat -ano) {
  foreach ($port in $ports) {
    if ($line -match ":$port\s" -and $line -match "LISTENING\s+(\d+)\s*$") {
      $pidToKill = $Matches[1]
      if ($pidToKill -and $pidToKill -ne "0") {
        Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
        Write-Host "    Stopped PID $pidToKill (port $port)" -ForegroundColor DarkGray
      }
    }
  }
}

$BuildRoot = Join-Path ([IO.Path]::GetTempPath()) "xh-202621-java"
$RuntimeOut = Join-Path $BuildRoot ("runtime-build-" + [guid]::NewGuid().ToString("N"))
$backendJob = $null
$storageJob = $null
$frontendJob = $null

try {
  Write-Host "==> Compiling Java backend..." -ForegroundColor Cyan
  New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
  New-Item -ItemType Directory -Force -Path $RuntimeOut | Out-Null
  $javacOutput = & javac -encoding UTF-8 -d $RuntimeOut backend/src/com/xh202621/*.java 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "Java compilation failed with exit code $LASTEXITCODE.`n$($javacOutput -join [Environment]::NewLine)"
  }
  Write-Host "    Compile OK: $RuntimeOut" -ForegroundColor Green

  Write-Host "==> Starting Java API (http://localhost:8081)..." -ForegroundColor Cyan
  $backendJob = Start-Job -Name ("xh-java-backend-" + [guid]::NewGuid().ToString("N")) -ScriptBlock {
    Set-Location $using:ProjectRoot
    $env:BACKEND_PORT = "8081"
    & java -cp $using:RuntimeOut com.xh202621.App
  }
  if (-not (Wait-LocalPort -Port 8081 -Job $backendJob)) {
    Write-JobFailure -Service "Java API" -Job $backendJob
    throw "Java API did not open port 8081."
  }

  Write-Host "==> Starting Python API (http://localhost:8080)..." -ForegroundColor Cyan
  $storageJob = Start-Job -Name ("xh-storage-api-" + [guid]::NewGuid().ToString("N")) -ScriptBlock {
    Set-Location $using:ProjectRoot
    & python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
  }
  if (-not (Wait-LocalPort -Port 8080 -Job $storageJob)) {
    Write-JobFailure -Service "Python API" -Job $storageJob
    throw "Python API did not open port 8080."
  }

  $health = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/health" -TimeoutSec 10
  if ($health.status -ne "ok") {
    throw "Storage health is '$($health.status)': $($health.storage | ConvertTo-Json -Compress)"
  }

  Write-Host "==> Starting official frontend (http://localhost:8501)..." -ForegroundColor Cyan
  $frontendJob = Start-Job -Name ("xh-frontend-" + [guid]::NewGuid().ToString("N")) -ScriptBlock {
    Set-Location $using:ProjectRoot
    & python frontend/app.py
  }
  if (-not (Wait-LocalPort -Port 8501 -Job $frontendJob)) {
    Write-JobFailure -Service "Official frontend" -Job $frontendJob
    throw "Official frontend did not open port 8501."
  }

  Write-Host ""
  Write-Host "===================================" -ForegroundColor Green
  Write-Host "  System is ready" -ForegroundColor Green
  Write-Host "  Frontend: http://localhost:8501" -ForegroundColor Green
  Write-Host "  API:      http://localhost:8080" -ForegroundColor Green
  Write-Host "  Health:   http://localhost:8080/api/health" -ForegroundColor Green
  Write-Host "===================================" -ForegroundColor Green

  if ($env:XH_STARTUP_SMOKE_TEST -eq "true") {
    foreach ($uri in @(
      "http://127.0.0.1:8080/api/search/jobs?page=1&page_size=1",
      "http://127.0.0.1:8080/api/analysis/skills",
      "http://127.0.0.1:8080/api/analysis/jobs/trend",
      "http://127.0.0.1:8501/"
    )) {
      $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 30
      if ($response.StatusCode -ne 200) { throw "Smoke check failed for ${uri}: HTTP $($response.StatusCode)" }
    }
    Write-Host "Startup smoke test passed." -ForegroundColor Green
    return
  }

  Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Green
  while ($true) {
    foreach ($service in @(
      @{ Name = "Java API"; Job = $backendJob },
      @{ Name = "Python API"; Job = $storageJob },
      @{ Name = "Official frontend"; Job = $frontendJob }
    )) {
      if ($service.Job.State -in @("Completed", "Failed", "Stopped")) {
        Write-JobFailure -Service $service.Name -Job $service.Job
        throw "$($service.Name) stopped unexpectedly."
      }
    }
    Start-Sleep -Seconds 1
  }
} finally {
  Write-Host "==> Stopping application services..." -ForegroundColor Cyan
  foreach ($job in @($backendJob, $storageJob, $frontendJob)) {
    if ($null -ne $job) {
      Stop-Job -Job $job -ErrorAction SilentlyContinue
      Remove-Job -Job $job -Force -ErrorAction SilentlyContinue
    }
  }

  $resolvedBuildRoot = [IO.Path]::GetFullPath($BuildRoot).TrimEnd("\") + "\"
  $resolvedRuntimeOut = [IO.Path]::GetFullPath($RuntimeOut).TrimEnd("\") + "\"
  if ($resolvedRuntimeOut.StartsWith($resolvedBuildRoot, [StringComparison]::OrdinalIgnoreCase) -and
      ([IO.Path]::GetFileName($RuntimeOut) -like "runtime-build-*") -and
      (Test-Path -LiteralPath $RuntimeOut)) {
    Remove-Item -LiteralPath $RuntimeOut -Recurse -Force -ErrorAction SilentlyContinue
  }
  Write-Host "    Application services stopped" -ForegroundColor Green
}
