#!/usr/bin/env bash
# =============================================================================
# verify-competition-deployment.sh
#
# Validates the competition Docker Compose setup WITHOUT altering running
# containers or performing destructive operations (no down -v).
#
# Usage: bash scripts/verify-competition-deployment.sh
# =============================================================================
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

PASS=0
FAIL=0
WARN=0

COMPOSE_FILE="deploy/docker-compose.competition.yml"
PROJECT_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

say() { printf "%b\n" "$*"; }
pass() { PASS=$((PASS + 1)); say "  ${GREEN}✓ PASS${NC}  $1"; }
fail() { FAIL=$((FAIL + 1)); say "  ${RED}✗ FAIL${NC}  $1 — $2"; }
warn() { WARN=$((WARN + 1)); say "  ${YELLOW}⚠ WARN${NC}  $1 — $2"; }

divider() {
    printf '%*s\n' 60 '' | tr ' ' '─'
}

# ---------------------------------------------------------------------------
say "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
say "${CYAN}  XH-202621 Competition Deployment Verification${NC}"
say "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
say ""

# ---- 1. Prerequisites -------------------------------------------------------
say "${CYAN}[1/6] Prerequisites${NC}"
divider

if command -v docker &>/dev/null; then
    pass "docker is available ($(docker --version))"
else
    fail "docker not found" "install Docker Desktop or Docker Engine"
fi

if docker compose version &>/dev/null; then
    pass "docker compose is available ($(docker compose version))"
else
    fail "docker compose not found" "Docker Compose plugin is required"
fi

# ---- 2. Required files ------------------------------------------------------
say ""
say "${CYAN}[2/6] Required files${NC}"
divider

cd "$PROJECT_ROOT"

check_file() {
    if [ -f "$1" ]; then
        pass "file exists: $1"
    else
        fail "missing file: $1" "create $1 before deploying"
    fi
}

check_file "$COMPOSE_FILE"
check_file "deploy/Dockerfile.python"
check_file "deploy/Dockerfile.java"
check_file "deploy/Dockerfile.web"
check_file "deploy/.env.example"

# Check source directories needed for builds
if [ -f "requirements.txt" ]; then
    pass "requirements.txt exists (Python build)"
else
    fail "missing requirements.txt" "Python Dockerfile needs this"
fi

if [ -d "app" ]; then
    pass "app/ directory exists (Python build)"
else
    fail "missing app/ directory" "Python Dockerfile needs this"
fi

if [ -d "backend/src" ]; then
    pass "backend/src/ directory exists (Java build)"
else
    fail "missing backend/src/" "Java Dockerfile needs this"
fi

if [ -d "talentmatch" ] && [ -f "talentmatch/package.json" ]; then
    pass "talentmatch/ ready (Web build)"
else
    fail "missing talentmatch source" "Web Dockerfile needs this"
fi

if [ -d "data" ] && [ -f "data/jobs.csv" ]; then
    pass "data/ directory with CSV files (Java runtime)"
else
    warn "data/ or data/jobs.csv missing" "Java container may start with limited data"
fi

# ---- 3. docker compose config validation ------------------------------------
say ""
say "${CYAN}[3/6] Docker Compose config validation${NC}"
divider

# Copy .env.example to temporary .env for validation if no .env exists
COMPOSE_DIR="$(dirname "$COMPOSE_FILE")"
TMP_ENV=0
if [ ! -f "$COMPOSE_DIR/.env" ]; then
    say "  (no deploy/.env found — using .env.example for validation)"
    cp "$COMPOSE_DIR/.env.example" "$COMPOSE_DIR/.env"
    TMP_ENV=1
fi

if docker compose -f "$COMPOSE_FILE" config --quiet 2>&1; then
    pass "docker compose config is valid"
else
    CONFIG_OUT=$(docker compose -f "$COMPOSE_FILE" config 2>&1) || true
    fail "docker compose config has errors" "$CONFIG_OUT"
fi

# Clean up temp .env
if [ "$TMP_ENV" -eq 1 ]; then
    rm -f "$COMPOSE_DIR/.env"
fi

# Show service summary
say ""
say "  Services defined:"
docker compose -f "$COMPOSE_FILE" config --services 2>/dev/null | while read -r svc; do
    say "    • $svc"
done

# ---- 4. Port conflict check -------------------------------------------------
say ""
say "${CYAN}[4/6] Port conflict check${NC}"
divider

check_port() {
    local port="$1" label="$2"
    if command -v ss &>/dev/null; then
        if ss -tlnp 2>/dev/null | grep -q ":${port} "; then
            warn "port ${port} (${label}) appears in use" "may conflict at startup"
        else
            pass "port ${port} (${label}) is free"
        fi
    elif command -v netstat &>/dev/null; then
        if netstat -tlnp 2>/dev/null | grep -q ":${port} "; then
            warn "port ${port} (${label}) appears in use" "may conflict at startup"
        else
            pass "port ${port} (${label}) appears free"
        fi
    else
        say "  (skipped — ss/netstat not available)"
    fi
}

check_port 3000 "web"
check_port 8080 "storage-api"
check_port 8081 "java-backend"
check_port 3307 "mysql"
check_port 7474 "neo4j-http"
check_port 7687 "neo4j-bolt"
check_port 9200 "elasticsearch"
check_port 19530 "milvus"

# ---- 5. Image build (best-effort) -------------------------------------------
say ""
say "${CYAN}[5/6] Image build (best-effort — network failures are non-fatal)${NC}"
divider

build_service() {
    local svc="$1"
    say "  Building ${svc}..."
    if docker compose -f "$COMPOSE_FILE" build --quiet "$svc" 2>&1; then
        pass "built image for ${svc}"
        return 0
    else
        warn "could not build ${svc} (network or dependency issue)" "retry later"
        return 1
    fi
}

build_service python
build_service java
build_service web

# ---- 6. No destructive operations check -------------------------------------
say ""
say "${CYAN}[6/6] Safety checks${NC}"
divider

# Verify the compose file does NOT force volume removal
if grep -qE '\bdown\s+-v\b' "$COMPOSE_FILE" 2>/dev/null; then
    fail "compose file references 'down -v'" "this would destroy data volumes"
else
    pass "compose file does not force volume removal"
fi

# Check that named volumes are defined
VOL_COUNT=$(grep -c '^  comp_' "$COMPOSE_FILE" 2>/dev/null || echo "0")
if [ "$VOL_COUNT" -ge 4 ]; then
    pass "named volumes defined for data persistence (${VOL_COUNT} volumes)"
else
    warn "few named volumes found" "data may not persist across restarts"
fi

# Environmental warning for Windows users
if [[ "$(uname -s)" == MINGW* ]] || [[ "$(uname -s)" == MSYS* ]] || [[ "$(uname -s)" == CYGWIN* ]]; then
    warn "Git Bash detected on Windows" "consider running verify-competition-deployment.ps1 in PowerShell for native checks"
fi

# ---- Summary ----------------------------------------------------------------
say ""
say "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
say "  Results:  ${GREEN}${PASS} passed${NC}  ${RED}${FAIL} failed${NC}  ${YELLOW}${WARN} warnings${NC}"
say "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

if [ "$FAIL" -gt 0 ]; then
    say ""
    say "${RED}Some checks failed. Fix the issues above before deploying.${NC}"
    exit 1
fi

say ""
say "${GREEN}All checks passed! Start the competition environment with:${NC}"
say ""
say "  ${CYAN}docker compose -f deploy/docker-compose.competition.yml up -d${NC}"
say ""
say "Then verify:"
say "  ${CYAN}docker compose -f deploy/docker-compose.competition.yml ps${NC}"
say ""
