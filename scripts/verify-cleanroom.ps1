$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

$suffix = [guid]::NewGuid().ToString("N").Substring(0, 12)
$project = "xh-job-clean-$suffix"
function Get-FreeTcpPort {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  $listener.Start()
  try { return ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port }
  finally { $listener.Stop() }
}
$env:MYSQL_CONTAINER_NAME = "$project-mysql"
$env:NEO4J_CONTAINER_NAME = "$project-neo4j"
$env:ES_CONTAINER_NAME = "$project-es"
$env:MYSQL_PORT = [string](Get-FreeTcpPort)
$env:NEO4J_HTTP_PORT = [string](Get-FreeTcpPort)
$env:NEO4J_BOLT_PORT = [string](Get-FreeTcpPort)
$env:ES_PORT = [string](Get-FreeTcpPort)
$env:MYSQL_URL = "mysql+pymysql://root:password@localhost:$($env:MYSQL_PORT)/job_kg?charset=utf8mb4"
$env:NEO4J_URI = "bolt://localhost:$($env:NEO4J_BOLT_PORT)"
$env:NEO4J_USERNAME = "neo4j"
$env:NEO4J_PASSWORD = "password123"
$env:ES_HOST = "http://localhost:$($env:ES_PORT)"
$stateRoot = Join-Path $env:TEMP $project

try {
  docker compose -p $project up -d --wait mysql neo4j elasticsearch
  if ($LASTEXITCODE -ne 0) { throw "Clean-room containers failed to become healthy." }
  python scripts/bootstrap_storage.py --sync --state-file (Join-Path $stateRoot "storage.json")
  if ($LASTEXITCODE -ne 0) { throw "Clean-room MySQL/Neo4j bootstrap failed." }
  python scripts/sync_mysql_to_es.py --auto --state-file (Join-Path $stateRoot "elasticsearch.json")
  if ($LASTEXITCODE -ne 0) { throw "Clean-room Elasticsearch bootstrap failed." }
  python scripts/verify_storage_counts.py
  if ($LASTEXITCODE -ne 0) { throw "Clean-room storage-count verification failed." }
  Write-Host "Clean-room initialization passed for project $project." -ForegroundColor Green
}
finally {
  docker compose -p $project down -v --remove-orphans
  $resolvedTemp = [IO.Path]::GetFullPath($env:TEMP).TrimEnd("\") + "\"
  $resolvedState = [IO.Path]::GetFullPath($stateRoot).TrimEnd("\") + "\"
  if ($resolvedState.StartsWith($resolvedTemp, [StringComparison]::OrdinalIgnoreCase) -and
      ([IO.Path]::GetFileName($stateRoot) -like "xh-job-clean-*") -and
      (Test-Path -LiteralPath $stateRoot)) {
    Remove-Item -LiteralPath $stateRoot -Recurse -Force -ErrorAction SilentlyContinue
  }
}
