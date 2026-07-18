# XH-202621 TalentMatch — Competition Deployment

## Quick Start

```bash
# 1. Configure environment (optional — defaults work out-of-the-box)
cp deploy/.env.example deploy/.env

# 2. Start everything with one command
docker compose -f deploy/docker-compose.competition.yml up -d

# 3. Wait for all services to become healthy (≈60–90 s on first run)
docker compose -f deploy/docker-compose.competition.yml ps

# 4. Access the application
#    Web UI   → http://localhost:3000
#    API Docs → http://localhost:8080/docs
#    Admin    → http://localhost:8080/admin
```

## Architecture

```
                 ┌──────────────────┐
                 │   Web Frontend   │  port 3000
                 │  Express + Vite  │
                 └────────┬─────────┘
                          │ proxy
          ┌───────────────┼───────────────┐
          ▼                               ▼
┌──────────────────┐            ┌──────────────────┐
│   FastAPI (8080) │            │   Java (8081)    │
│  Search·Storage  │◄──────────►│  KG·Analytics    │
└──┬───┬───┬───┬───┘            └──────────────────┘
   │   │   │   │                      │
   ▼   ▼   ▼   ▼                      ▼
┌────┐┌────┐┌────┐┌──────┐    ┌──────────────┐
│MySQL││Neo4j││ ES ││Milvus│    │  CSV data/   │
│:3307││:7687││:9200││:19530│   │  (read-only) │
└────┘└────┘└────┘└──────┘    └──────────────┘
```

## Services

| Service | Port | Container Name | Health Endpoint |
|---|---|---|---|
| Web Frontend | 3000 | `xh-comp-web-frontend` | `/api/health` |
| FastAPI | 8080 | `xh-comp-storage-api` | `/api/health` |
| Java Backend | 8081 | `xh-comp-java-backend` | `/api/health` |
| MySQL 8.4 | 3307 | `xh-comp-mysql` | mysqladmin ping |
| Neo4j 5.26 | 7474/7687 | `xh-comp-neo4j` | cypher-shell |
| Elasticsearch 8.13 | 9200 | `xh-comp-elasticsearch` | `/_cluster/health` |
| Milvus 2.6 | 19530 | `xh-comp-milvus` | `/healthz` |

## Build Images

Images are built automatically on first `docker compose up`. To rebuild:

```bash
docker compose -f deploy/docker-compose.competition.yml build --no-cache
```

Individual services:

```bash
docker compose -f deploy/docker-compose.competition.yml build python
docker compose -f deploy/docker-compose.competition.yml build java
docker compose -f deploy/docker-compose.competition.yml build web
```

## Verify Deployment

```bash
# Windows (PowerShell)
.\scripts\verify-competition-deployment.ps1

# Linux / macOS
bash scripts/verify-competition-deployment.sh
```

## Data Safety

- **Named volumes** (`comp_*_data`) persist across restarts and `docker compose down`.
- **`docker compose down -v` is intentionally avoided** — volumes survive teardown.
- The `data/` directory is mounted **read-only** into the Java container.
- No real passwords, API keys, or secrets are baked into images.

## Environment Variables

Copy `deploy/.env.example` to `deploy/.env` and customize:

| Variable | Default | Notes |
|---|---|---|
| `MYSQL_ROOT_PASSWORD` | `password` | Change for production |
| `NEO4J_PASSWORD` | `password123` | Change for production |
| `GEMINI_API_KEY` | *(empty)* | Fill to enable AI features |
| `AI_PROVIDER` | `google` | `google`, `deepseek`, `openai` |

## Troubleshooting

```bash
# Check service status
docker compose -f deploy/docker-compose.competition.yml ps

# View logs for a specific service
docker compose -f deploy/docker-compose.competition.yml logs python
docker compose -f deploy/docker-compose.competition.yml logs web

# Restart a single service
docker compose -f deploy/docker-compose.competition.yml restart python

# Tear down (volumes preserved)
docker compose -f deploy/docker-compose.competition.yml down

# ⚠️  WARNING — IRREVERSIBLE  ⚠️
# `down -v` permanently deletes ALL named volumes (MySQL, Neo4j, ES, Milvus data).
# This operation CANNOT be undone. Do NOT run this on any environment with real data.
# Only use for clean-room resets or disposable test environments.
#
# Tear down AND wipe all data (DESTRUCTIVE)
# docker compose -f deploy/docker-compose.competition.yml down -v
```
