# XH-202621 one-click launcher
# Start MySQL/Neo4j + storage API(8080) + Java analytics(8081) + frontend(8501)
$ErrorActionPreference = "Stop"

$LocalEnv = Join-Path $PSScriptRoot "scripts\local-env.ps1"
if (Test-Path $LocalEnv) {
  . $LocalEnv
  Write-Host "==> Loaded local environment" -ForegroundColor Gray
}

# 1. Initialize real storage (first run imports data; later runs skip existing data)
if ($env:SKIP_STORAGE_INIT -ne "true") {
  & (Join-Path $PSScriptRoot "scripts\init-storage.ps1")
}

# 2. Stop old application processes
Write-Host "==> Stopping old services..." -ForegroundColor Cyan
$ports = @(8080, 8081, 8501)
foreach ($line in netstat -ano) {
  foreach ($port in $ports) {
    if ($line -match ":$port\s" -and $line -match "LISTENING\s+(\d+)\s*$") {
      $pidToKill = $Matches[1]
      if ($pidToKill -and $pidToKill -ne "0") {
        Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
        Write-Host "    Stopped PID $pidToKill (port $port)" -ForegroundColor Gray
      }
    }
  }
}

# 3. Compile Java analytics backend
Write-Host "==> Compiling Java backend..." -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path backend/runtime-out | Out-Null
$javacOutput = javac -encoding UTF-8 -d backend/runtime-out backend/src/com/xh202621/*.java 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "Compile failed: $javacOutput" -ForegroundColor Red
  exit 1
}
Write-Host "    Compile OK" -ForegroundColor Green

# 4. Start Java analytics backend (internal)
Write-Host "==> Starting Java analytics service (http://localhost:8081)..." -ForegroundColor Cyan
$backendJob = Start-Job -Name "xh-backend" -ScriptBlock {
  Set-Location $using:PWD
  $LocalEnv = Join-Path $using:PWD "scripts\local-env.ps1"
  if (Test-Path $LocalEnv) {
    . $LocalEnv
  }
  $env:BACKEND_PORT = "8081"
  java -cp backend/runtime-out com.xh202621.App 2>&1 | Write-Host -ForegroundColor DarkGray
}
Write-Host "    Backend job ID: $($backendJob.Id)" -ForegroundColor Green

# 5. Start MySQL/Neo4j runtime API (public)
Write-Host "==> Starting storage API (http://localhost:8080)..." -ForegroundColor Cyan
$storageJob = Start-Job -Name "xh-storage-api" -ScriptBlock {
  Set-Location $using:PWD
  $LocalEnv = Join-Path $using:PWD "scripts\local-env.ps1"
  if (Test-Path $LocalEnv) { . $LocalEnv }
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 2>&1 | Write-Host -ForegroundColor DarkGray
}
Write-Host "    Storage API job ID: $($storageJob.Id)" -ForegroundColor Green

# 6. Wait for public API
Write-Host "==> Waiting for MySQL/Neo4j API..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
  try {
    $null = Invoke-WebRequest -Uri "http://localhost:8080/api/health" -TimeoutSec 1 -UseBasicParsing
    $ready = $true
    break
  } catch {
    Start-Sleep -Milliseconds 500
  }
}
if ($ready) {
  Write-Host "    Backend is ready" -ForegroundColor Green
} else {
  Write-Host "    WARNING: Backend may not be ready" -ForegroundColor Yellow
}

# 7. Start frontend
Write-Host "==> Starting frontend (http://localhost:8501)..." -ForegroundColor Cyan
$frontendJob = Start-Job -Name "xh-frontend" -ScriptBlock {
  Set-Location $using:PWD
  python frontend/app.py 2>&1 | Write-Host -ForegroundColor DarkGray
}
Write-Host "    Frontend job ID: $($frontendJob.Id)" -ForegroundColor Green

Start-Sleep -Seconds 1

Write-Host ""
Write-Host "===================================" -ForegroundColor Green
Write-Host "  System is running!" -ForegroundColor Green
Write-Host "  Frontend: http://localhost:8501" -ForegroundColor Green
Write-Host "  Backend:  http://localhost:8080" -ForegroundColor Green
Write-Host "  Press Ctrl+C to stop all..." -ForegroundColor Green
Write-Host "===================================" -ForegroundColor Green
Write-Host ""

# 8. Wait for Ctrl+C, then cleanup
try {
  while ($true) { Start-Sleep -Seconds 1 }
} finally {
  Write-Host ""
  Write-Host "==> Stopping services..." -ForegroundColor Cyan
  Stop-Job -Name "xh-backend" -ErrorAction SilentlyContinue
  Stop-Job -Name "xh-storage-api" -ErrorAction SilentlyContinue
  Stop-Job -Name "xh-frontend" -ErrorAction SilentlyContinue
  Remove-Job -Name "xh-backend" -ErrorAction SilentlyContinue
  Remove-Job -Name "xh-storage-api" -ErrorAction SilentlyContinue
  Remove-Job -Name "xh-frontend" -ErrorAction SilentlyContinue

  foreach ($line in netstat -ano) {
    foreach ($port in $ports) {
      if ($line -match ":$port\s" -and $line -match "LISTENING\s+(\d+)\s*$") {
        $pidToKill = $Matches[1]
        if ($pidToKill -and $pidToKill -ne "0") {
          Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
        }
      }
    }
  }
  Write-Host "    All services stopped" -ForegroundColor Green
}
