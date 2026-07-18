#!/bin/bash
# ==============================================================
# CortexPrime — Deploy to Staging (Docker Compose)
# ==============================================================
set -euo pipefail

ENV_FILE="${ENV_FILE:-backend/.env.staging}"
COMPOSE_FILES="-f docker-compose.yml -f docker-compose.staging.yml"

echo "=== CortexPrime Staging Deployment ==="
echo ""

# 1. Validate environment file
if [ ! -f "$ENV_FILE" ]; then
    echo "ERROR: Environment file not found: $ENV_FILE"
    echo "Create it from backend/.env.example and set staging values."
    exit 1
fi

# 2. Pull latest images
echo ">>> Pulling latest images..."
docker compose $COMPOSE_FILES --env-file "$ENV_FILE" pull || true

# 3. Start services
echo ">>> Starting services..."
docker compose $COMPOSE_FILES --env-file "$ENV_FILE" up -d --build

# 4. Wait for healthy
echo ">>> Waiting for services to be healthy..."
sleep 15

# 5. Run smoke tests
echo ">>> Running smoke tests..."
bash tests/deployment/smoke-test.sh || {
    echo "WARNING: Smoke tests failed. Check docker logs for details."
}

# 6. Show status
echo ">>> Service status:"
docker compose $COMPOSE_FILES --env-file "$ENV_FILE" ps

echo ""
echo "=== Deployment complete ==="
