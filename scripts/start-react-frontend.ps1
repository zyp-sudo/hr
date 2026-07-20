$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendDir = Join-Path $ProjectRoot "_archived-frontends/frontend-react"

Set-Location $FrontendDir

if (-not (Test-Path "node_modules")) {
  Write-Host "node_modules not found. Run npm install in _archived-frontends/frontend-react first." -ForegroundColor Yellow
  exit 1
}

npm.cmd run dev
