# XH-202621 one-click launcher
# Compile backend + start backend(8080) + start frontend(8501)
$ErrorActionPreference = "Stop"

$LocalEnv = Join-Path $PSScriptRoot "scripts\local-env.ps1"
if (Test-Path $LocalEnv) {
  . $LocalEnv
  Write-Host "==> Loaded local environment" -ForegroundColor Gray
}

# 1. Stop old processes
Write-Host "==> Stopping old services..." -ForegroundColor Cyan
$ports = @(8080, 8501)
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

# 2. Compile backend
Write-Host "==> Compiling Java backend..." -ForegroundColor Cyan
$javacOutput = javac -encoding UTF-8 -d backend/out backend/src/com/xh202621/*.java 2>&1
if ($LASTEXITCODE -ne 0) {
  Write-Host "Compile failed: $javacOutput" -ForegroundColor Red
  exit 1
}
Write-Host "    Compile OK" -ForegroundColor Green

# 3. Start backend
Write-Host "==> Starting backend (http://localhost:8080)..." -ForegroundColor Cyan
$backendJob = Start-Job -Name "xh-backend" -ScriptBlock {
  Set-Location $using:PWD
  $LocalEnv = Join-Path $using:PWD "scripts\local-env.ps1"
  if (Test-Path $LocalEnv) {
    . $LocalEnv
  }
  java -cp backend/out com.xh202621.App 2>&1 | Write-Host -ForegroundColor DarkGray
}
Write-Host "    Backend job ID: $($backendJob.Id)" -ForegroundColor Green

# 4. Wait for backend
Write-Host "==> Waiting for backend..." -ForegroundColor Cyan
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

# 5. Start frontend
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

# 6. Wait for Ctrl+C, then cleanup
try {
  while ($true) { Start-Sleep -Seconds 1 }
} finally {
  Write-Host ""
  Write-Host "==> Stopping services..." -ForegroundColor Cyan
  Stop-Job -Name "xh-backend" -ErrorAction SilentlyContinue
  Stop-Job -Name "xh-frontend" -ErrorAction SilentlyContinue
  Remove-Job -Name "xh-backend" -ErrorAction SilentlyContinue
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
