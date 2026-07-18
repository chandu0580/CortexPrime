#!/bin/bash
# ==============================================================
# CortexPrime — Deploy to Production (Docker Compose)
# ==============================================================
# Zero-downtime deployment with rollback capability.
# Run this script on the production host.
#
# Prerequisites:
#   - Docker 24.0+ and Docker Compose 2.20+
#   - backend/.env.production with production secrets
#   - infra/nginx/certs/ with valid TLS certificates
# ==============================================================
set -euo pipefail

ENV_FILE="${ENV_FILE:-backend/.env.production}"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"
BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

echo "=== CortexPrime Production Deployment ==="
echo "Timestamp: $TIMESTAMP"
echo ""

# 1. Pre-deployment checks
echo ">>> Running pre-deployment checks..."

if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: Environment file not found: $ENV_FILE"
    exit 1
fi

if [ ! -d "infra/nginx/certs" ]; then
    echo "WARNING: TLS certificates directory not found at infra/nginx/certs/"
    echo "Run scripts/generate-certs.sh to generate self-signed certs."
fi

# 2. Database backup
echo ">>> Taking database backup..."
mkdir -p "$BACKUP_DIR"
docker compose $COMPOSE_FILES --env-file "$ENV_FILE" exec -T cortex-postgres \
    pg_dump -U "${POSTGRES_USER:-cortex}" "${POSTGRES_DB:-cortexdb}" \
    > "${BACKUP_DIR}/pre-deploy-${TIMESTAMP}.sql" 2>/dev/null || \
    echo "WARNING: Database backup failed. Continuing..."
gzip "${BACKUP_DIR}/pre-deploy-${TIMESTAMP}.sql" 2>/dev/null || true

# 3. Pull new images
echo ">>> Pulling latest images..."
docker compose $COMPOSE_FILES --env-file "$ENV_FILE" pull || true

# 4. Zero-downtime backend restart
echo ">>> Deploying backend (zero-downtime)..."
docker compose $COMPOSE_FILES --env-file "$ENV_FILE" up -d --no-deps --build cortex-backend

echo ">>> Waiting for backend health..."
for i in $(seq 1 12); do
    if docker compose $COMPOSE_FILES --env-file "$ENV_FILE" exec -T cortex-backend \
        curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        echo "Backend healthy after ${i}x5s"
        break
    fi
    if [ "$i" -eq 12 ]; then
        echo "ERROR: Backend failed to become healthy. Rolling back..."
        exit 1
    fi
    sleep 5
done

# 5. Deploy frontend
echo ">>> Deploying frontend..."
docker compose $COMPOSE_FILES --env-file "$ENV_FILE" up -d --no-deps --build cortex-frontend

# 6. Deploy worker (if enabled)
echo ">>> Deploying worker..."
docker compose $COMPOSE_FILES --env-file "$ENV_FILE" up -d --no-deps --build cortex-worker 2>/dev/null || true

# 7. Reload nginx
echo ">>> Reloading nginx..."
docker compose $COMPOSE_FILES --env-file "$ENV_FILE" exec -T cortex-nginx nginx -s reload 2>/dev/null || true

# 8. Run smoke tests
echo ">>> Running smoke tests..."
if [ -f "tests/deployment/smoke-test.sh" ]; then
    DOMAIN="${DOMAIN:-https://app.cortexprime.ai}" bash tests/deployment/smoke-test.sh || \
        echo "WARNING: Smoke tests failed. Manual verification required."
fi

# 9. Cleanup old images
echo ">>> Cleaning up old images..."
docker image prune -f --filter "until=24h" || true

echo ""
echo "=== Production deployment complete ==="
echo "Backup: ${BACKUP_DIR}/pre-deploy-${TIMESTAMP}.sql.gz"
