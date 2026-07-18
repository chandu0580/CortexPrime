#!/bin/bash
# ==============================================================
# CortexPrime — Bootstrap Environment
# ==============================================================
# Run this once when setting up a new environment.
# Generates secrets, TLS certs, and initial config.
# ==============================================================
set -euo pipefail

ENVIRONMENT="${1:-development}"
ENV_FILE="backend/.env.${ENVIRONMENT}"

echo "=== CortexPrime Environment Bootstrap ==="
echo "Environment: $ENVIRONMENT"
echo ""

# 1. Generate random secrets
echo ">>> Generating secrets..."
JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
JWT_REFRESH=$(python3 -c "import secrets; print(secrets.token_urlsafe(48))")
POSTGRES_PASS=$(python3 -c "import secrets; print(secrets.token_hex(24))")
REDIS_PASS=$(python3 -c "import secrets; print(secrets.token_hex(24))")
RABBIT_PASS=$(python3 -c "import secrets; print(secrets.token_hex(24))")
NEO4J_PASS=$(python3 -c "import secrets; print(secrets.token_hex(24))")

# 2. Create env file from example
if [ ! -f "backend/.env.example" ]; then
    echo "ERROR: backend/.env.example not found"
    exit 1
fi

cp backend/.env.example "$ENV_FILE"

# 3. Populate with generated secrets
if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=${JWT_SECRET}/" "$ENV_FILE"
    sed -i '' "s/JWT_REFRESH_SECRET=.*/JWT_REFRESH_SECRET=${JWT_REFRESH}/" "$ENV_FILE"
    sed -i '' "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${POSTGRES_PASS}/" "$ENV_FILE"
    sed -i '' "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=${REDIS_PASS}/" "$ENV_FILE"
    sed -i '' "s/RABBITMQ_PASSWORD=.*/RABBITMQ_PASSWORD=${RABBIT_PASS}/" "$ENV_FILE"
    sed -i '' "s/NEO4J_PASSWORD=.*/NEO4J_PASSWORD=${NEO4J_PASS}/" "$ENV_FILE"
else
    sed -i "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=${JWT_SECRET}/" "$ENV_FILE"
    sed -i "s/JWT_REFRESH_SECRET=.*/JWT_REFRESH_SECRET=${JWT_REFRESH}/" "$ENV_FILE"
    sed -i "s/POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${POSTGRES_PASS}/" "$ENV_FILE"
    sed -i "s/REDIS_PASSWORD=.*/REDIS_PASSWORD=${REDIS_PASS}/" "$ENV_FILE"
    sed -i "s/RABBITMQ_PASSWORD=.*/RABBITMQ_PASSWORD=${RABBIT_PASS}/" "$ENV_FILE"
    sed -i "s/NEO4J_PASSWORD=.*/NEO4J_PASSWORD=${NEO4J_PASS}/" "$ENV_FILE"
fi

echo "Secrets written to $ENV_FILE"
echo ""

# 4. Generate self-signed TLS certs
if [ "$ENVIRONMENT" = "development" ] || [ "$ENVIRONMENT" = "staging" ]; then
    echo ">>> Generating self-signed TLS certificates..."
    if [ -f "scripts/generate-certs.sh" ]; then
        bash scripts/generate-certs.sh
    else
        echo "WARNING: scripts/generate-certs.sh not found. Skipping TLS cert generation."
    fi
fi

# 5. Create required directories
echo ">>> Creating required directories..."
mkdir -p backups generated_voice generated_screens

# 6. Set file permissions
echo ">>> Setting file permissions..."
chmod 600 "$ENV_FILE"

echo ""
echo "=== Bootstrap complete ==="
echo "Environment:  $ENVIRONMENT"
echo "Config file:  $ENV_FILE"
echo ""
echo "Next steps:"
echo "  1. Edit $ENV_FILE to add your API keys (OPENAI_API_KEY, etc.)"
echo "  2. Run: docker compose -f docker-compose.yml up -d"
echo "  3. Verify: curl http://localhost:8000/health"
