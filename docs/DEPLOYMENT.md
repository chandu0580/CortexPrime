# CortexPrime — Deployment Runbook

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Local Development Deployment](#3-local-development-deployment)
4. [Staging Deployment](#4-staging-deployment)
5. [Production Deployment](#5-production-deployment)
6. [Rollback Procedure](#6-rollback-procedure)
7. [Disaster Recovery](#7-disaster-recovery)
8. [Health Verification](#8-health-verification)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Architecture Overview

```
Internet
    │ 443 (TLS)
    ▼
┌─────────────────┐
│  nginx (proxy)  │  Rate limiting, TLS termination, security headers
└────────┬────────┘
         │
    ┌────┴──────────────┐
    │                   │
    ▼                   ▼
┌─────────┐       ┌──────────┐
│ backend │       │ frontend │   (Next.js SSR)
│ :8000   │       │ :3000    │
└────┬────┘       └──────────┘
     │
     ├── PostgreSQL  :5432  (pgvector, persistent data)
     ├── Redis        :6379  (sessions, pub/sub, rate limiting)
     ├── RabbitMQ     :5672  (mission event bus)
     ├── Neo4j        :7687  (cognition graph)
     ├── Prometheus   :9090  (metrics scrape)
     └── Grafana      :3001  (dashboards)
```

**Container count:** 9 services  
**Networking:** `cortex-app` (frontend ↔ nginx), `cortex-data` (backend ↔ databases)  
**TLS:** nginx terminates; certificates in `infra/nginx/certs/`

---

## 2. Prerequisites

| Tool | Minimum Version | Verify |
|---|---|---|
| Docker | 24.0 | `docker --version` |
| Docker Compose | 2.20 | `docker compose version` |
| Python | 3.11 | `python --version` |
| Node.js | 20 | `node --version` |
| Git | 2.40 | `git --version` |

**Minimum host resources (production):**
- CPU: 4 cores
- RAM: 8 GB
- Disk: 40 GB SSD

---

## 3. Local Development Deployment

### 3.1 First-time setup

```bash
# Clone and enter
git clone <repo-url> cortexprime
cd cortexprime

# Generate self-signed TLS certs (nginx requires them)
bash scripts/generate-certs.sh
# Output: infra/nginx/certs/cert.pem + key.pem

# Copy and populate environment
cp backend/.env.example backend/.env
# Edit backend/.env with at minimum:
#   OPENAI_API_KEY=sk-...
#   JWT_SECRET_KEY=<32+ char random string>
#   JWT_REFRESH_SECRET=<32+ char random string>
```

### 3.2 Start all services

```bash
docker compose -f docker-compose.yml up -d --build
```

Verify all 9 containers healthy:
```bash
docker compose ps
```

### 3.3 Access

| Service | URL |
|---|---|
| Frontend | https://localhost (accept self-signed cert) |
| API docs | http://localhost:8000/docs |
| Grafana | http://localhost:3001 (admin/admin) |
| Prometheus | http://localhost:9090 |

### 3.4 Stop

```bash
docker compose down
# To also remove volumes (wipes all data):
docker compose down -v
```

---

## 4. Staging Deployment

Staging uses the same image stack as production but with relaxed secrets and no TLS enforcement.

### 4.1 Environment setup

```bash
# On the staging host
git clone <repo-url> /opt/cortexprime
cd /opt/cortexprime

# Populate environment (staging-specific values)
cp backend/.env.example backend/.env
vim backend/.env
# Set ENVIRONMENT=staging, real LLM keys, staging DB passwords
```

### 4.2 TLS certificates

```bash
# Option A: Let's Encrypt (requires domain + port 80 accessible)
certbot certonly --standalone -d staging.yourdomain.com
cp /etc/letsencrypt/live/staging.yourdomain.com/fullchain.pem infra/nginx/certs/cert.pem
cp /etc/letsencrypt/live/staging.yourdomain.com/privkey.pem infra/nginx/certs/key.pem

# Option B: Self-signed (internal staging)
bash scripts/generate-certs.sh
```

### 4.3 Deploy

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file backend/.env \
  up -d --build
```

### 4.4 Stamp database migrations

After first deploy or when DB is empty:
```bash
docker exec cortex-postgres psql -U cortex -d cortexdb \
  -c "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY);"
docker exec cortex-postgres psql -U cortex -d cortexdb \
  -c "DELETE FROM alembic_version; INSERT INTO alembic_version VALUES ('0004');"
```

### 4.5 Verify staging

```bash
curl -sk https://staging.yourdomain.com/health/system | python3 -m json.tool
```

---

## 5. Production Deployment

### 5.1 Pre-deployment checklist

Run through [docs/PRODUCTION_CHECKLIST.md](PRODUCTION_CHECKLIST.md) before every production deploy.

### 5.2 Pull latest images (GHCR)

```bash
# On production host
docker pull ghcr.io/<org>/cortexprime-backend:v1.0.0
docker pull ghcr.io/<org>/cortexprime-frontend:v1.0.0
```

Or build from source:
```bash
git fetch --tags
git checkout v1.0.0
```

### 5.3 Zero-downtime deploy sequence

```bash
# 1. Take a database backup BEFORE any deploy
docker exec cortex-postgres \
  pg_dump -U cortex cortexdb \
  > backups/cortexdb-$(date +%Y%m%d-%H%M%S).sql

# 2. Pull new images
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file backend/.env pull

# 3. Restart backend (frontend can stay up during backend restart)
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file backend/.env up -d --no-deps cortex-backend

# 4. Wait for backend health
sleep 15
docker exec cortex-backend curl -sf http://localhost:8000/health

# 5. Restart frontend
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file backend/.env up -d --no-deps cortex-frontend

# 6. Reload nginx (no downtime)
docker exec cortex-nginx nginx -s reload

# 7. Verify full health
curl -sk https://yourdomain.com/health/system | python3 -m json.tool
```

### 5.4 Environment variables (production required)

| Variable | Description |
|---|---|
| `OPENAI_API_KEY` | Primary LLM provider key |
| `JWT_SECRET_KEY` | ≥32 chars, cryptographically random |
| `JWT_REFRESH_SECRET` | ≥32 chars, different from JWT_SECRET_KEY |
| `POSTGRES_PASSWORD` | Strong DB password |
| `SENTRY_DSN` | Error tracking (set `NEXT_PUBLIC_SENTRY_DSN` too) |
| `ENVIRONMENT` | Must be `production` |
| `CORS_ORIGINS` | Exact frontend URL, e.g. `https://yourdomain.com` |
| `WS_AUTH_REQUIRED` | Must be `true` in production |

### 5.5 Generate secure secrets

```bash
# JWT secrets
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# Database password
python3 -c "import secrets; print(secrets.token_hex(24))"
```

---

## 6. Rollback Procedure

### 6.1 Application rollback (previous Docker image)

```bash
# Identify previous image tag
docker images ghcr.io/<org>/cortexprime-backend | head -5

# Roll back backend to previous version
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file backend/.env \
  up -d --no-deps --force-recreate \
  cortex-backend
# Edit docker-compose.prod.yml to pin the old image tag first

# Verify health
docker exec cortex-backend curl -sf http://localhost:8000/health
```

### 6.2 Database rollback

> ⚠️ Only attempt a DB rollback if the application rollback alone does not resolve the issue. DB rollbacks can cause data loss.

```bash
# Stop backend to prevent new writes
docker compose stop cortex-backend

# Restore from backup
docker exec -i cortex-postgres \
  psql -U cortex -d cortexdb \
  < backups/cortexdb-<timestamp>.sql

# Restart backend with old image
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file backend/.env up -d cortex-backend
```

### 6.3 Alembic migration rollback

```bash
# Downgrade one step
docker exec cortex-backend sh -c \
  "cd /workspace && alembic -c backend/database/migrations/alembic.ini downgrade -1"

# Downgrade to specific revision
docker exec cortex-backend sh -c \
  "cd /workspace && alembic -c backend/database/migrations/alembic.ini downgrade 0003"
```

### 6.4 Full stack rollback

```bash
# 1. Bring down current stack
docker compose -f docker-compose.yml -f docker-compose.prod.yml down

# 2. Restore DB backup
docker compose up -d cortex-postgres
sleep 10
docker exec -i cortex-postgres psql -U cortex -d cortexdb \
  < backups/cortexdb-<timestamp>.sql

# 3. Deploy previous tag
git checkout v<previous-version>
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file backend/.env up -d --build

# 4. Verify
curl -sk https://yourdomain.com/health/system
```

---

## 7. Disaster Recovery

### 7.1 Scenarios and responses

| Scenario | RTO | RPO | Response |
|---|---|---|---|
| Single container crash | <1 min | 0 | Docker restart policy handles automatically |
| Backend OOM | 2 min | 0 | Docker restart + scale check |
| Database corruption | 30 min | Last backup | Restore from backup (§6.2) |
| Complete host failure | 60 min | Last backup | Re-provision host, restore data |
| Secrets compromise | Immediate | N/A | Rotate secrets, redeploy |

### 7.2 Backup strategy

**Database (PostgreSQL)**

```bash
# Automated daily backup — add to crontab
0 2 * * * docker exec cortex-postgres pg_dump -U cortex cortexdb \
  | gzip > /backups/cortexdb-$(date +\%Y\%m\%d).sql.gz

# Retention: keep 30 days
find /backups -name "cortexdb-*.sql.gz" -mtime +30 -delete
```

**Redis** (sessions + runtime state — can be rebuilt, but backup if needed)

```bash
docker exec cortex-redis redis-cli BGSAVE
docker cp cortex-redis:/data/dump.rdb backups/redis-$(date +%Y%m%d).rdb
```

**Volumes backup**

```bash
# Backup all named volumes
for vol in cortex-postgres-data cortex-neo4j-data cortex-chroma-data; do
  docker run --rm \
    -v ${vol}:/source:ro \
    -v $(pwd)/backups:/backup \
    alpine tar czf /backup/${vol}-$(date +%Y%m%d).tar.gz -C /source .
done
```

### 7.3 Recovery from complete failure

```bash
# On new host:
# 1. Install Docker + clone repo
apt-get install -y docker.io docker-compose-plugin
git clone <repo-url> /opt/cortexprime && cd /opt/cortexprime

# 2. Restore secrets from vault / secret manager
cp /path/to/secrets/backend.env backend/.env

# 3. Start database first
docker compose up -d cortex-postgres cortex-redis
sleep 15

# 4. Restore database backup
docker exec -i cortex-postgres psql -U cortex -d cortexdb \
  < /path/to/backups/cortexdb-latest.sql

# 5. Start all services
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file backend/.env up -d

# 6. Verify
curl -sk https://yourdomain.com/health/system | python3 -m json.tool
```

### 7.4 Secrets rotation

```bash
# 1. Generate new secrets
NEW_JWT=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
NEW_JWT_REFRESH=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")

# 2. Update backend/.env
sed -i "s/^JWT_SECRET_KEY=.*/JWT_SECRET_KEY=${NEW_JWT}/" backend/.env
sed -i "s/^JWT_REFRESH_SECRET=.*/JWT_REFRESH_SECRET=${NEW_JWT_REFRESH}/" backend/.env

# 3. Redeploy backend (all existing tokens will be invalidated — users re-login)
docker compose -f docker-compose.yml -f docker-compose.prod.yml \
  --env-file backend/.env up -d --no-deps --force-recreate cortex-backend

# 4. Notify users (all sessions will be invalidated)
```

---

## 8. Health Verification

### Quick health check

```bash
# Overall system status
curl -sk https://yourdomain.com/health/system | python3 -m json.tool

# Backend direct
docker exec cortex-backend curl -sf http://localhost:8000/health

# Prometheus metrics
curl -sk https://yourdomain.com/metrics | grep "^cortex_" | head -10

# Database
docker exec cortex-postgres pg_isready -U cortex

# Redis
docker exec cortex-redis redis-cli ping
```

### Expected healthy response

```json
{
  "status": "healthy",
  "components": {
    "database":          { "status": "healthy" },
    "redis":             { "status": "healthy" },
    "rabbitmq":          { "status": "healthy" },
    "neo4j":             { "status": "healthy" },
    "embeddings":        { "status": "healthy" },
    "request_tracing":   { "status": "healthy" },
    "exception_handler": { "status": "healthy" },
    "sentry":            { "status": "healthy" }
  }
}
```

---

## 9. Troubleshooting

### Backend won't start — migration loop

**Symptom:** `DuplicateTableError: relation "missions" already exists`  
**Cause:** `alembic_version` table missing — DB created outside Alembic tracking  
**Fix:**
```bash
docker exec cortex-postgres psql -U cortex -d cortexdb \
  -c "CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL PRIMARY KEY);"
docker exec cortex-postgres psql -U cortex -d cortexdb \
  -c "DELETE FROM alembic_version; INSERT INTO alembic_version VALUES ('0004');"
docker compose restart cortex-backend
```

### 502 Bad Gateway from nginx

**Cause:** Backend not ready yet (usually just started)  
**Fix:** Wait 15s after `docker compose up`, then test again.
```bash
docker exec cortex-backend curl -sf http://localhost:8000/health
```

### RabbitMQ disconnected in health

**Cause:** RabbitMQ container not ready when backend started  
**Fix:**
```bash
docker compose restart cortex-backend
```
Backend reconnects automatically on next request.

### Embedding dimension mismatch

**Symptom:** `CRITICAL: EMBEDDING DIMENSION MISMATCH at startup`  
**Cause:** OpenAI key missing or wrong embedding model in `.env`  
**Fix:** Set `OPENAI_API_KEY` and verify `MODEL_EMBEDDING_PRIMARY` in `.env`, then restart backend.

### Frontend build failure (GHCR)

```bash
# Pull pre-built image instead of building locally
docker pull ghcr.io/<org>/cortexprime-frontend:latest
# Tag and update compose to use this image
```

### Sentry not receiving events

1. Verify `SENTRY_DSN` and `NEXT_PUBLIC_SENTRY_DSN` are set in `backend/.env`
2. Check `/health/system` → `sentry.detail.dsn_configured` should be `true`
3. Verify outbound HTTPS to `*.sentry.io` is not blocked by firewall
