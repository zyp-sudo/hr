$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

function Assert-NativeSuccess([string]$Step) {
  if ($LASTEXITCODE -ne 0) {
    throw "$Step failed with exit code $LASTEXITCODE."
  }
}

Write-Host "==> Starting MySQL, Neo4j and Elasticsearch..." -ForegroundColor Cyan
docker compose up -d mysql neo4j elasticsearch
Assert-NativeSuccess "docker compose up"

Write-Host "==> Waiting for databases..." -ForegroundColor Cyan
$MySQLContainer = if ($env:MYSQL_CONTAINER_NAME) { $env:MYSQL_CONTAINER_NAME } else { "xh-job-mysql" }
$Neo4jContainer = if ($env:NEO4J_CONTAINER_NAME) { $env:NEO4J_CONTAINER_NAME } else { "xh-job-neo4j" }
$ESContainer = if ($env:ES_CONTAINER_NAME) { $env:ES_CONTAINER_NAME } else { "xh-job-elasticsearch" }
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
  $states = docker inspect --format '{{.State.Health.Status}}' $MySQLContainer $Neo4jContainer $ESContainer 2>$null
  Assert-NativeSuccess "docker inspect database health"
  if ($states.Count -eq 3 -and ($states | Where-Object { $_ -ne "healthy" }).Count -eq 0) {
    $ready = $true
    break
  }
  Start-Sleep -Seconds 2
}
if (-not $ready) {
  throw "MySQL/Neo4j/Elasticsearch did not become healthy in time. Run 'docker compose ps' for details."
}

Write-Host "==> Incrementally synchronizing MySQL and Neo4j snapshots..." -ForegroundColor Cyan
python scripts/bootstrap_storage.py --sync
Assert-NativeSuccess "MySQL/Neo4j snapshot synchronization"
Write-Host "==> Synchronizing MySQL job_postings to Elasticsearch..." -ForegroundColor Cyan
python scripts/sync_mysql_to_es.py --auto
Assert-NativeSuccess "Elasticsearch synchronization"
Write-Host "    Storage initialization complete." -ForegroundColor Green
