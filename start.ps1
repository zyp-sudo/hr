# XH-202621 one-click launcher
# Starts MySQL/Neo4j/Elasticsearch + Java API (8081) + Python API (8080)
# + the redesigned TalentMatch React frontend/full-stack gateway (3000).
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
    if ($Job.State -in @("Completed", "Failed", "Stopped")) { return $false }
    if (Test-LocalPort -Port $Port) {
      Start-Sleep -Milliseconds 250
      return $Job.State -notin @("Completed", "Failed", "Stopped")
    }
    Start-Sleep -Milliseconds 500
  }
  return $false
}

function Get-ListeningProcessIds {
  param([Parameter(Mandatory = $true)][int]$Port)

  $processIds = foreach ($line in netstat -ano) {
    if ($line -match "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$") {
      [int]$Matches[1]
    }
  }
  return @($processIds | Where-Object { $_ -gt 0 } | Select-Object -Unique)
}

function Stop-LocalPort {
  param([Parameter(Mandatory = $true)][int]$Port)

  foreach ($processId in (Get-ListeningProcessIds -Port $Port)) {
    try {
      Stop-Process -Id $processId -Force -ErrorAction Stop
      Write-Host "    Stopped PID $processId (port $Port)" -ForegroundColor DarkGray
    } catch {
      Write-Host "    Could not stop PID $processId on port $Port`: $($_.Exception.Message)" -ForegroundColor Yellow
    }
  }

  for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if (-not (Test-LocalPort -Port $Port)) { return }
    Start-Sleep -Milliseconds 200
  }

  $remaining = Get-ListeningProcessIds -Port $Port
  $ownerText = if ($remaining.Count) { $remaining -join ", " } else { "unknown process" }
  throw "Port $Port is still occupied by $ownerText. Close the old service or run this launcher as Administrator, then try again."
}

function Test-HttpService {
  param(
    [Parameter(Mandatory = $true)][string]$Uri,
    [string]$ExpectedStatus
  )

  try {
    $response = Invoke-RestMethod -Uri $Uri -TimeoutSec 3
    if ($ExpectedStatus) { return $response.status -eq $ExpectedStatus }
    return $true
  } catch {
    return $false
  }
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
$ReuseStorageApi = Test-HttpService -Uri "http://127.0.0.1:8080/api/health" -ExpectedStatus "ok"
$ReuseJavaApi = Test-HttpService -Uri "http://127.0.0.1:8081/api/real-jobs?limit=1"
$ReuseFrontend = Test-HttpService -Uri "http://127.0.0.1:3000/api/health" -ExpectedStatus "ok"

if ($ReuseStorageApi) {
  Write-Host "    Reusing healthy Python API on port 8080" -ForegroundColor Green
} else {
  Stop-LocalPort -Port 8080
}
if ($ReuseJavaApi) {
  Write-Host "    Reusing healthy Java API on port 8081" -ForegroundColor Green
} else {
  Stop-LocalPort -Port 8081
}
if ($ReuseFrontend) {
  Write-Host "    Reusing healthy TalentMatch frontend on port 3000" -ForegroundColor Green
} else {
  Stop-LocalPort -Port 3000
}

$PythonExe = (Get-Command python -ErrorAction Stop).Source
Write-Host "    Python: $PythonExe" -ForegroundColor DarkGray

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

  if (-not $ReuseJavaApi) {
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
  }

  if (-not $ReuseStorageApi) {
    Write-Host "==> Starting Python API (http://localhost:8080)..." -ForegroundColor Cyan
    $storageJob = Start-Job -Name ("xh-storage-api-" + [guid]::NewGuid().ToString("N")) -ScriptBlock {
      Set-Location $using:ProjectRoot
      $env:PYTHONUTF8 = "1"
      $env:PYTHONUNBUFFERED = "1"
      & $using:PythonExe -m uvicorn app.main:app --host 0.0.0.0 --port 8080
    }
    if (-not (Wait-LocalPort -Port 8080 -Job $storageJob)) {
      Write-JobFailure -Service "Python API" -Job $storageJob
      throw "Python API did not open port 8080."
    }
  }

  $health = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/health" -TimeoutSec 10
  if ($health.status -ne "ok") {
    throw "Storage health is '$($health.status)': $($health.storage | ConvertTo-Json -Compress)"
  }

  $TalentMatchDir = Join-Path $ProjectRoot "talentmatch"
  if (-not (Test-Path (Join-Path $TalentMatchDir "package.json"))) {
    throw "Redesigned frontend was not found: $TalentMatchDir"
  }
  if (-not (Test-Path (Join-Path $TalentMatchDir "node_modules"))) {
    Write-Host "==> Installing redesigned frontend dependencies..." -ForegroundColor Cyan
    Push-Location $TalentMatchDir
    try {
      if (Test-Path "package-lock.json") {
        & npm.cmd ci
      } else {
        & npm.cmd install
      }
      if ($LASTEXITCODE -ne 0) { throw "npm dependency installation failed with exit code $LASTEXITCODE." }
    } finally {
      Pop-Location
    }
  }

  if (-not $ReuseFrontend) {
    Write-Host "==> Starting redesigned frontend (http://localhost:3000)..." -ForegroundColor Cyan
    $frontendJob = Start-Job -Name ("xh-frontend-" + [guid]::NewGuid().ToString("N")) -ScriptBlock {
      Set-Location $using:TalentMatchDir
      $env:PORT = "3000"
      & npm.cmd run dev
    }
    if (-not (Wait-LocalPort -Port 3000 -Job $frontendJob)) {
      Write-JobFailure -Service "Redesigned frontend" -Job $frontendJob
      throw "Redesigned frontend did not open port 3000."
    }
  }

  Write-Host ""
  Write-Host "===================================" -ForegroundColor Green
  Write-Host "  System is ready" -ForegroundColor Green
  Write-Host "===================================" -ForegroundColor Green
  Write-Host ""
  Write-Host "  前端界面 (UI):" -ForegroundColor Magenta
  Write-Host "    http://localhost:3000" -ForegroundColor White
  Write-Host ""
  Write-Host "  后端 API (数据接口):" -ForegroundColor Magenta
  Write-Host "    主页 / 跳转:       http://localhost:8080" -ForegroundColor White
  Write-Host "    Swagger 文档:      http://localhost:8080/docs" -ForegroundColor White
  Write-Host "    健康检查:           http://localhost:8080/api/health" -ForegroundColor White
  Write-Host ""
  Write-Host "  Java 分析服务:       http://localhost:8081" -ForegroundColor DarkGray
  Write-Host "===================================" -ForegroundColor Green

  if ($env:XH_STARTUP_SMOKE_TEST -eq "true") {
    foreach ($uri in @(
      "http://127.0.0.1:8080/api/search/jobs?page=1&page_size=1",
      "http://127.0.0.1:8080/api/analysis/skills",
      "http://127.0.0.1:8080/api/analysis/jobs/trend",
      "http://127.0.0.1:3000/",
      "http://127.0.0.1:3000/api/health"
    )) {
      $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 30
      if ($response.StatusCode -ne 200) { throw "Smoke check failed for ${uri}: HTTP $($response.StatusCode)" }
    }
    Write-Host "Startup smoke test passed." -ForegroundColor Green
    return
  }

  Write-Host "Press Ctrl+C to stop all services." -ForegroundColor Green
  while ($true) {
    $managedServices = @(
      @{ Name = "Java API"; Job = $backendJob },
      @{ Name = "Python API"; Job = $storageJob },
      @{ Name = "Redesigned frontend"; Job = $frontendJob }
    ) | Where-Object { $null -ne $_.Job }
    foreach ($service in $managedServices) {
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
