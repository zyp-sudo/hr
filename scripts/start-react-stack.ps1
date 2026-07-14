$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendDir = Join-Path $ProjectRoot "frontend-react"

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
  Write-Host "frontend-react/node_modules not found. Run npm install in frontend-react first." -ForegroundColor Yellow
  exit 1
}

Write-Host "==> Compiling Java backend..." -ForegroundColor Cyan
Set-Location $ProjectRoot
javac -encoding UTF-8 -d backend/out backend/src/com/xh202621/*.java

Write-Host "==> Starting Java backend on http://localhost:8080" -ForegroundColor Cyan
$backend = Start-Job -Name "xh-java-backend" -ScriptBlock {
  Set-Location $using:ProjectRoot
  java -cp backend/out com.xh202621.App
}

Write-Host "==> Starting React frontend on http://localhost:5173" -ForegroundColor Cyan
$frontend = Start-Job -Name "xh-react-frontend" -ScriptBlock {
  Set-Location $using:FrontendDir
  npm.cmd run dev
}

Write-Host ""
Write-Host "React frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "Java backend:    http://localhost:8080" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop jobs." -ForegroundColor Green

try {
  while ($true) { Start-Sleep -Seconds 1 }
} finally {
  Stop-Job $backend, $frontend -ErrorAction SilentlyContinue
  Remove-Job $backend, $frontend -ErrorAction SilentlyContinue
}
