$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $ProjectRoot

$LocalEnv = Join-Path $PSScriptRoot "local-env.ps1"
if (Test-Path $LocalEnv) {
  . $LocalEnv
  Write-Host "Loaded scripts/local-env.ps1" -ForegroundColor DarkGray
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

  Write-Host "$Service failed to become ready (job state: $($Job.State))." -ForegroundColor Red
  $output = Receive-Job -Job $Job -Keep -ErrorAction SilentlyContinue 2>&1
  if ($output) { $output | ForEach-Object { Write-Host "    $_" -ForegroundColor DarkRed } }
}

if ($env:SKIP_STORAGE_INIT -ne "true") {
  & (Join-Path $PSScriptRoot "init-storage.ps1")
  if (-not $?) { throw "Storage initialization failed." }
}

foreach ($line in netstat -ano) {
  foreach ($port in @(8080, 8081)) {
    if ($line -match ":$port\s" -and $line -match "LISTENING\s+(\d+)\s*$") {
      Stop-Process -Id $Matches[1] -Force -ErrorAction SilentlyContinue
    }
  }
}

$BuildRoot = Join-Path ([IO.Path]::GetTempPath()) "xh-202621-java"
$RuntimeOut = Join-Path $BuildRoot ("runtime-build-" + [guid]::NewGuid().ToString("N"))
$javaJob = $null
$apiJob = $null

try {
  New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
  New-Item -ItemType Directory -Force -Path $RuntimeOut | Out-Null
  $javacOutput = & javac -encoding UTF-8 -d $RuntimeOut backend/src/com/xh202621/*.java 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw "Java compilation failed with exit code $LASTEXITCODE.`n$($javacOutput -join [Environment]::NewLine)"
  }
  Write-Host "Java compile OK: $RuntimeOut" -ForegroundColor Green

  $javaJob = Start-Job -Name ("xh-java-backend-" + [guid]::NewGuid().ToString("N")) -ScriptBlock {
    Set-Location $using:ProjectRoot
    $env:BACKEND_PORT = "8081"
    & java -cp $using:RuntimeOut com.xh202621.App
  }
  if (-not (Wait-LocalPort -Port 8081 -Job $javaJob)) {
    Write-JobFailure -Service "Java API" -Job $javaJob
    throw "Java API did not open port 8081."
  }

  $apiJob = Start-Job -Name ("xh-storage-api-" + [guid]::NewGuid().ToString("N")) -ScriptBlock {
    Set-Location $using:ProjectRoot
    & python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
  }
  if (-not (Wait-LocalPort -Port 8080 -Job $apiJob)) {
    Write-JobFailure -Service "Python API" -Job $apiJob
    throw "Python API did not open port 8080."
  }

  try {
    $health = Invoke-RestMethod -Uri "http://127.0.0.1:8080/api/health" -TimeoutSec 10
  } catch {
    Write-JobFailure -Service "Python API health check" -Job $apiJob
    throw
  }
  if ($health.status -ne "ok") {
    throw "Storage health is '$($health.status)': $($health.storage | ConvertTo-Json -Compress)"
  }

  Write-Host "Public API: http://localhost:8080 (MySQL + Elasticsearch + Neo4j)" -ForegroundColor Green
  Write-Host "Java API:   http://localhost:8081 (internal)" -ForegroundColor DarkGray

  if ($env:XH_STARTUP_SMOKE_TEST -eq "true") {
    foreach ($uri in @(
      "http://127.0.0.1:8080/api/search/jobs?page=1&page_size=1",
      "http://127.0.0.1:8080/api/analysis/skills",
      "http://127.0.0.1:8080/api/analysis/jobs/trend"
    )) {
      $response = Invoke-WebRequest -Uri $uri -UseBasicParsing -TimeoutSec 30
      if ($response.StatusCode -ne 200) { throw "Smoke check failed for ${uri}: HTTP $($response.StatusCode)" }
    }
    Write-Host "Startup smoke test passed." -ForegroundColor Green
    return
  }

  Write-Host "Press Ctrl+C to stop." -ForegroundColor Green
  while ($true) {
    foreach ($service in @(
      @{ Name = "Java API"; Job = $javaJob },
      @{ Name = "Python API"; Job = $apiJob }
    )) {
      if ($service.Job.State -in @("Completed", "Failed", "Stopped")) {
        Write-JobFailure -Service $service.Name -Job $service.Job
        throw "$($service.Name) stopped unexpectedly."
      }
    }
    Start-Sleep -Seconds 1
  }
} finally {
  foreach ($job in @($javaJob, $apiJob)) {
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
}
