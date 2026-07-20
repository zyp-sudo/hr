$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendDir = Join-Path $ProjectRoot "_archived-frontends/frontend-react"

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
  Write-Host "_archived-frontends/frontend-react/node_modules not found. Run npm install in _archived-frontends/frontend-react first." -ForegroundColor Yellow
  exit 1
}

if ($env:SKIP_STORAGE_INIT -ne "true") {
  & (Join-Path $PSScriptRoot "init-storage.ps1")
}

foreach ($line in netstat -ano) {
  foreach ($port in @(8080, 8081, 5173)) {
    if ($line -match ":$port\s" -and $line -match "LISTENING\s+(\d+)\s*$") {
      Stop-Process -Id $Matches[1] -Force -ErrorAction SilentlyContinue
    }
  }
}

Write-Host "==> Compiling Java backend..." -ForegroundColor Cyan
Set-Location $ProjectRoot
New-Item -ItemType Directory -Force -Path backend/runtime-out | Out-Null
javac -encoding UTF-8 -d backend/runtime-out backend/src/com/xh202621/*.java

Write-Host "==> Starting Java analytics service on http://localhost:8081" -ForegroundColor Cyan
$backend = Start-Job -Name "xh-java-backend" -ScriptBlock {
  Set-Location $using:ProjectRoot
  $env:BACKEND_PORT = "8081"
  java -cp backend/runtime-out com.xh202621.App
}

Write-Host "==> Starting MySQL/Neo4j API on http://localhost:8080" -ForegroundColor Cyan
$storage = Start-Job -Name "xh-storage-api" -ScriptBlock {
  Set-Location $using:ProjectRoot
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
}

Write-Host "==> Starting React frontend on http://localhost:5173" -ForegroundColor Cyan
$frontend = Start-Job -Name "xh-react-frontend" -ScriptBlock {
  Set-Location $using:FrontendDir
  npm.cmd run dev
}

Write-Host ""
Write-Host "React frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "Storage API:     http://localhost:8080" -ForegroundColor Green
Write-Host "Java analytics:  http://localhost:8081" -ForegroundColor DarkGray
Write-Host "Press Ctrl+C to stop jobs." -ForegroundColor Green

try {
  while ($true) { Start-Sleep -Seconds 1 }
} finally {
  Stop-Job $backend, $storage, $frontend -ErrorAction SilentlyContinue
  Remove-Job $backend, $storage, $frontend -ErrorAction SilentlyContinue
}
