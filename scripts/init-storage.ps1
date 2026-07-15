$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

Write-Host "==> Starting MySQL, Neo4j and Elasticsearch..." -ForegroundColor Cyan
docker compose up -d mysql neo4j elasticsearch

Write-Host "==> Waiting for databases..." -ForegroundColor Cyan
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
  $states = docker inspect --format '{{.State.Health.Status}}' xh-job-mysql xh-job-neo4j xh-job-elasticsearch 2>$null
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
Write-Host "==> Synchronizing MySQL job_postings to Elasticsearch..." -ForegroundColor Cyan
python scripts/sync_mysql_to_es.py --auto
Write-Host "    Storage initialization complete." -ForegroundColor Green
