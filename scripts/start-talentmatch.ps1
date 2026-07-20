$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$FrontendDir = Join-Path $ProjectRoot "talentmatch-frontend"

if (-not (Test-Path (Join-Path $FrontendDir "package.json"))) {
  throw "TalentMatch project not found: $FrontendDir"
}

Set-Location $FrontendDir

if (-not (Test-Path "node_modules")) {
  Write-Host "==> Installing dependencies..." -ForegroundColor Cyan
  & npm.cmd install
  if ($LASTEXITCODE -ne 0) { throw "npm install failed with exit code $LASTEXITCODE." }
}

$pids = foreach ($line in netstat -ano) {
  if ($line -match "^\s*TCP\s+\S+:3000\s+\S+\s+LISTENING\s+(\d+)\s*$") {
    [int]$Matches[1]
  }
}
foreach ($pidToKill in ($pids | Where-Object { $_ -gt 0 } | Select-Object -Unique)) {
  Stop-Process -Id $pidToKill -Force -ErrorAction SilentlyContinue
  Write-Host "Stopped old process $pidToKill on port 3000." -ForegroundColor DarkGray
}

$env:PORT = "3000"
$env:STORAGE_API_URL = "http://127.0.0.1:8080"
$env:JAVA_API_URL = "http://127.0.0.1:8081"
Write-Host "==> Starting redesigned TalentMatch page" -ForegroundColor Cyan
Write-Host "    http://localhost:3000" -ForegroundColor Green
Write-Host "    Press Ctrl+C to stop." -ForegroundColor DarkGray
& npm.cmd run dev
