#!/bin/bash
# ==============================================================
# CortexPrime — Production Rollback
# ==============================================================
# Reverts to the previous Docker image tags.
# ==============================================================
set -euo pipefail

ENV_FILE="${ENV_FILE:-backend/.env.production}"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.prod.yml"

echo "=== CortexPrime Rollback ==="
echo ""

# 1. List recent images
echo ">>> Recent backend images:"
docker images ghcr.io/cortexprime/cortexprime-backend --format "table {{.Tag}}\t{{.CreatedAt}}\t{{.Size}}" | head -10
echo ""

# 2. Confirm rollback
read -p "Enter the image tag to roll back to: " TAG
if [ -z "$TAG" ]; then
    echo "ERROR: No tag specified."
    exit 1
fi

# 3. Update compose to use the specified tag
echo ">>> Rolling back backend to tag: $TAG"
export IMAGE_TAG="$TAG"

# 4. Database rollback prompt
read -p "Roll back database? This may cause data loss. (y/N): " DB_ROLLBACK
if [ "$DB_ROLLBACK" = "y" ] || [ "$DB_ROLLBACK" = "Y" ]; then
    echo ">>> Stopping backend..."
    docker compose $COMPOSE_FILES --env-file "$ENV_FILE" stop cortex-backend

    BACKUP_DIR="./backups"
    echo ">>> Available backups:"
    ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null | head -10 || echo "No backups found."
    read -p "Enter backup filename to restore (or leave blank to skip): " BACKUP_FILE
    if [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_DIR/$BACKUP_FILE" ]; then
        echo ">>> Restoring database from $BACKUP_FILE..."
        gunzip -c "$BACKUP_DIR/$BACKUP_FILE" | \
            docker compose $COMPOSE_FILES --env-file "$ENV_FILE" exec -T cortex-postgres \
            psql -U "${POSTGRES_USER:-cortex}" "${POSTGRES_DB:-cortexdb}"
    fi
fi

# 5. Restart with old image
echo ">>> Restarting services..."
docker compose $COMPOSE_FILES --env-file "$ENV_FILE" up -d --force-recreate

# 6. Verify
echo ">>> Verifying health..."
sleep 15
docker compose $COMPOSE_FILES --env-file "$ENV_FILE" exec -T cortex-backend \
    curl -sf http://localhost:8000/health && echo "Backend healthy" || echo "Backend unhealthy"

echo ""
echo "=== Rollback complete ==="
