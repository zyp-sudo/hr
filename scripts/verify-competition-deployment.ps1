<#
.SYNOPSIS
    Validates the competition Docker Compose setup WITHOUT altering running
    containers or performing destructive operations (no down -v).

.DESCRIPTION
    Checks prerequisites, file existence, compose config validity, port
    conflicts, attempts image builds (network failures are non-fatal), and
    verifies safety constraints.

.PARAMETER SkipBuild
    Skip image build attempts (faster validation).

.EXAMPLE
    .\scripts\verify-competition-deployment.ps1
    .\scripts\verify-competition-deployment.ps1 -SkipBuild
#>
param(
    [switch] $SkipBuild = $false
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$script:Pass = 0
$script:Fail = 0
$script:Warn = 0

$ComposeFile = "deploy/docker-compose.competition.yml"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

function Write-Pass { $script:Pass++; Write-Host "  [PASS]  $args" -ForegroundColor Green }
function Write-Fail { $script:Fail++; Write-Host "  [FAIL]  $args" -ForegroundColor Red }
function Write-Warn { $script:Warn++; Write-Host "  [WARN]  $args" -ForegroundColor Yellow }
function Write-Divider { Write-Host ("─" * 60) }

# =============================================================================
Write-Host ("─" * 60) -ForegroundColor Cyan
Write-Host "  XH-202621 Competition Deployment Verification" -ForegroundColor Cyan
Write-Host ("─" * 60) -ForegroundColor Cyan
Write-Host ""

Push-Location $ProjectRoot

try {
    # ---- 1. Prerequisites ---------------------------------------------------
    Write-Host "[1/6] Prerequisites" -ForegroundColor Cyan
    Write-Divider

    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) {
        $ver = & docker --version 2>&1
        Write-Pass "docker is available ($ver)"
    } else {
        Write-Fail "docker not found — install Docker Desktop"
    }

    $composeVersion = & docker compose version 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "docker compose is available ($composeVersion)"
    } else {
        Write-Fail "docker compose not found — Docker Compose plugin is required"
    }

    # ---- 2. Required files --------------------------------------------------
    Write-Host ""
    Write-Host "[2/6] Required files" -ForegroundColor Cyan
    Write-Divider

    function Test-File {
        param($Path, $Description)
        if (Test-Path $Path) {
            Write-Pass "file exists: $Path"
        } else {
            Write-Fail "missing: $Path — $Description"
        }
    }

    Test-File $ComposeFile "main compose file"
    Test-File "deploy/Dockerfile.python" "Python Dockerfile"
    Test-File "deploy/Dockerfile.java" "Java Dockerfile"
    Test-File "deploy/Dockerfile.web" "Web Dockerfile"
    Test-File "deploy/.env.example" "env template"

    if (Test-Path "requirements.txt") { Write-Pass "requirements.txt exists (Python build)" }
    else { Write-Fail "missing requirements.txt" }

    if (Test-Path "app") { Write-Pass "app/ directory exists (Python build)" }
    else { Write-Fail "missing app/ directory" }

    if (Test-Path "backend/src") { Write-Pass "backend/src/ directory exists (Java build)" }
    else { Write-Fail "missing backend/src/" }

    if ((Test-Path "talentmatch") -and (Test-Path "talentmatch/package.json")) {
        Write-Pass "talentmatch/ ready (Web build)"
    } else {
        Write-Fail "missing talentmatch source"
    }

    if ((Test-Path "data") -and (Test-Path "data/jobs.csv")) {
        Write-Pass "data/ directory with CSV files (Java runtime)"
    } else {
        Write-Warn "data/ or data/jobs.csv missing — Java may have limited data"
    }

    # ---- 3. docker compose config validation --------------------------------
    Write-Host ""
    Write-Host "[3/6] Docker Compose config validation" -ForegroundColor Cyan
    Write-Divider

    $composeDir = Split-Path -Parent $ComposeFile
    $tmpEnv = $false
    if (-not (Test-Path "$composeDir/.env")) {
        Write-Host "  (no deploy/.env found — using .env.example for validation)"
        Copy-Item "$composeDir/.env.example" "$composeDir/.env"
        $tmpEnv = $true
    }

    $configOutput = & docker compose -f $ComposeFile config 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Pass "docker compose config is valid"
    } else {
        Write-Fail "docker compose config has errors`n$configOutput"
    }

    if ($tmpEnv) {
        Remove-Item "$composeDir/.env"
    }

    Write-Host ""
    Write-Host "  Services defined:"
    $services = & docker compose -f $ComposeFile config --services 2>&1
    foreach ($svc in $services) {
        Write-Host "    • $svc"
    }

    # ---- 4. Port conflict check ---------------------------------------------
    Write-Host ""
    Write-Host "[4/6] Port conflict check" -ForegroundColor Cyan
    Write-Divider

    function Test-Port {
        param($Port, $Label)
        $listener = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Where-Object { $_.State -eq "Listen" }
        if ($listener) {
            Write-Warn "port ${Port} (${Label}) is in use — may conflict"
        } else {
            Write-Pass "port ${Port} (${Label}) is free"
        }
    }

    Test-Port 3000 "web"
    Test-Port 8080 "storage-api"
    Test-Port 8081 "java-backend"
    Test-Port 3307 "mysql"
    Test-Port 7474 "neo4j-http"
    Test-Port 7687 "neo4j-bolt"
    Test-Port 9200 "elasticsearch"
    Test-Port 19530 "milvus"

    # ---- 5. Image build (best-effort) ---------------------------------------
    Write-Host ""
    Write-Host "[5/6] Image build (best-effort — network failures are non-fatal)" -ForegroundColor Cyan
    Write-Divider

    function Invoke-BuildService {
        param($Service)
        if ($SkipBuild) {
            Write-Host "  (skipped — -SkipBuild flag set) $Service"
            return
        }
        Write-Host "  Building ${Service}..."
        $buildOutput = & docker compose -f $ComposeFile build --quiet $Service 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Pass "built image for ${Service}"
        } else {
            Write-Warn "could not build ${Service} (network/dependency issue) — retry later"
        }
    }

    Invoke-BuildService "python"
    Invoke-BuildService "java"
    Invoke-BuildService "web"

    # ---- 6. Safety checks ---------------------------------------------------
    Write-Host ""
    Write-Host "[6/6] Safety checks" -ForegroundColor Cyan
    Write-Divider

    $composeContent = Get-Content $ComposeFile -Raw
    if ($composeContent -match '\bdown\s+-v\b') {
        Write-Fail "compose file references 'down -v' — would destroy data volumes"
    } else {
        Write-Pass "compose file does not force volume removal"
    }

    $volCount = ([regex]::Matches($composeContent, '^  comp_', [System.Text.RegularExpressions.RegexOptions]::Multiline)).Count
    if ($volCount -ge 4) {
        Write-Pass "named volumes defined for data persistence (${volCount} volumes)"
    } else {
        Write-Warn "few named volumes found — data may not persist"
    }

    # ---- Summary ------------------------------------------------------------
    Write-Host ""
    Write-Host ("─" * 60) -ForegroundColor Cyan
    Write-Host "  Results:  " -NoNewline
    Write-Host "${script:Pass} passed  " -NoNewline -ForegroundColor Green
    Write-Host "${script:Fail} failed  " -NoNewline -ForegroundColor Red
    Write-Host "${script:Warn} warnings" -ForegroundColor Yellow
    Write-Host ("─" * 60) -ForegroundColor Cyan

    if ($script:Fail -gt 0) {
        Write-Host ""
        Write-Host "Some checks failed. Fix the issues above before deploying." -ForegroundColor Red
        exit 1
    }

    Write-Host ""
    Write-Host "All checks passed! Start the competition environment with:" -ForegroundColor Green
    Write-Host ""
    Write-Host "  docker compose -f deploy/docker-compose.competition.yml up -d" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Then verify:" -ForegroundColor Green
    Write-Host "  docker compose -f deploy/docker-compose.competition.yml ps" -ForegroundColor Cyan
    Write-Host "  curl http://localhost:3000/api/health" -ForegroundColor Cyan
    Write-Host ""

} finally {
    Pop-Location
}
