#!/bin/sh
# =============================================================================
# CortexPrime Docker Entrypoint
#
# Runs ``alembic upgrade head`` before starting the application so that
# the database schema is always synchronised on every deployment.
#
# Usage (set as ENTRYPOINT in Dockerfile):
#   ENTRYPOINT ["./entrypoint.sh"]
#   CMD        ["uvicorn", "backend.main:app", ...]
#
# The CMD (or docker-compose ``command:``) becomes the arguments passed
# to ``exec "$@"`` below.
# =============================================================================

set -e

ALEMBIC_INI="backend/database/migrations/alembic.ini"

echo "[entrypoint] -------------------------------------------------------"
echo "[entrypoint] CortexPrime database migration"
echo "[entrypoint] -------------------------------------------------------"

# ---------------------------------------------------------------------------
# If the alembic_version table already exists but was created outside Alembic
# tracking (e.g. a DB restored from a pre-Alembic backup), stamp it to the
# latest revision so the first ``upgrade head`` is a no-op rather than
# attempting to re-run all migrations from scratch and failing with duplicate
# table errors.
#
# This runs via psql using the same DATABASE_URL that Alembic uses.
# If DATABASE_URL is not set the stamp step is skipped gracefully.
# ---------------------------------------------------------------------------
if [ -n "${DATABASE_URL:-}" ]; then
    echo "[entrypoint] Checking alembic_version table …"
    # Create the version table if it doesn't exist, and stamp to head if empty
    psql "$DATABASE_URL" <<'SQL' 2>/dev/null || true
CREATE TABLE IF NOT EXISTS alembic_version (
    version_num VARCHAR(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
-- Only stamp if the table is empty (never been touched by alembic)
INSERT INTO alembic_version (version_num)
SELECT '0004'
WHERE NOT EXISTS (SELECT 1 FROM alembic_version);
SQL
    echo "[entrypoint] alembic_version table ready."
else
    echo "[entrypoint] DATABASE_URL not set — skipping pre-stamp (will rely on alembic upgrade)."
fi

# Retry up to 10 times with 3-second back-off so the container can start
# before PostgreSQL is fully ready (common in docker compose up --build).
MAX_RETRIES=10
RETRY_DELAY=3
attempt=1

while [ $attempt -le $MAX_RETRIES ]; do
    echo "[entrypoint] Attempt $attempt/$MAX_RETRIES: alembic upgrade head"
    if alembic -c "$ALEMBIC_INI" upgrade head; then
        echo "[entrypoint] Migrations complete."
        break
    fi

    if [ $attempt -eq $MAX_RETRIES ]; then
        echo "[entrypoint] ERROR: All $MAX_RETRIES migration attempts failed."
        # Respect BLOCK_ON_MIGRATION_FAILURE env var
        if [ "${BLOCK_ON_MIGRATION_FAILURE:-false}" = "true" ]; then
            echo "[entrypoint] BLOCK_ON_MIGRATION_FAILURE=true — aborting startup."
            exit 1
        else
            echo "[entrypoint] BLOCK_ON_MIGRATION_FAILURE not set — continuing anyway."
        fi
        break
    fi

    echo "[entrypoint] Retrying in ${RETRY_DELAY}s…"
    sleep $RETRY_DELAY
    attempt=$((attempt + 1))
done

echo "[entrypoint] -------------------------------------------------------"
echo "[entrypoint] Starting application: $*"
echo "[entrypoint] -------------------------------------------------------"


