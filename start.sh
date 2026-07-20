#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ "${SKIP_STORAGE_INIT:-false}" != "true" ]]; then
  docker compose up -d mysql neo4j elasticsearch milvus-etcd milvus-minio milvus
  echo "Waiting for MySQL, Neo4j, Elasticsearch and Milvus..."
  for _ in $(seq 1 60); do
    mysql_health=$(docker inspect --format '{{.State.Health.Status}}' xh-job-mysql 2>/dev/null || true)
    neo4j_health=$(docker inspect --format '{{.State.Health.Status}}' xh-job-neo4j 2>/dev/null || true)
    es_health=$(docker inspect --format '{{.State.Health.Status}}' xh-job-elasticsearch 2>/dev/null || true)
    milvus_health=$(docker inspect --format '{{.State.Health.Status}}' xh-milvus 2>/dev/null || true)
    [[ "$mysql_health" == "healthy" && "$neo4j_health" == "healthy" && "$es_health" == "healthy" && "$milvus_health" == "healthy" ]] && break
    sleep 2
  done
  python scripts/bootstrap_storage.py --sync
  python scripts/sync_mysql_to_es.py --auto
fi

mkdir -p backend/runtime-out
javac -encoding UTF-8 -d backend/runtime-out backend/src/com/xh202621/*.java
BACKEND_PORT=8081 java -cp backend/runtime-out com.xh202621.App &
JAVA_PID=$!
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 &
API_PID=$!

if [[ ! -d talentmatch-frontend/node_modules ]]; then
  (cd talentmatch-frontend && npm ci)
fi
(cd talentmatch-frontend && PORT=3000 npm run dev) &
FRONTEND_PID=$!

cleanup() {
  kill "$JAVA_PID" "$API_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Frontend:   http://localhost:3000"
echo "Public API: http://localhost:8080 (MySQL + Elasticsearch + Neo4j + Milvus)"
echo "Java API:   http://localhost:8081"
echo "Neo4j UI:   http://localhost:7474"
wait
