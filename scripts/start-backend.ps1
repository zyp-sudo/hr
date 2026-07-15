$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

if ($env:SKIP_STORAGE_INIT -ne "true") {
  & (Join-Path $PSScriptRoot "init-storage.ps1")
}

foreach ($line in netstat -ano) {
  foreach ($port in @(8080, 8081)) {
    if ($line -match ":$port\s" -and $line -match "LISTENING\s+(\d+)\s*$") {
      Stop-Process -Id $Matches[1] -Force -ErrorAction SilentlyContinue
    }
  }
}

New-Item -ItemType Directory -Force -Path backend/runtime-out | Out-Null
javac -encoding UTF-8 -d backend/runtime-out backend/src/com/xh202621/*.java
$javaJob = Start-Job -Name "xh-java-backend" -ScriptBlock {
  Set-Location $using:ProjectRoot
  $env:BACKEND_PORT = "8081"
  java -cp backend/runtime-out com.xh202621.App
}
$apiJob = Start-Job -Name "xh-storage-api" -ScriptBlock {
  Set-Location $using:ProjectRoot
  $LocalEnv = Join-Path $using:ProjectRoot "scripts\local-env.ps1"
  if (Test-Path $LocalEnv) { . $LocalEnv }
  python -m uvicorn app.main:app --host 0.0.0.0 --port 8080
}

Write-Host "Public API: http://localhost:8080 (MySQL + Neo4j)" -ForegroundColor Green
Write-Host "Java API:   http://localhost:8081 (internal)" -ForegroundColor DarkGray
Write-Host "Press Ctrl+C to stop." -ForegroundColor Green
try {
  while ($true) { Start-Sleep -Seconds 1 }
} finally {
  Stop-Job $javaJob, $apiJob -ErrorAction SilentlyContinue
  Remove-Job $javaJob, $apiJob -ErrorAction SilentlyContinue
}
