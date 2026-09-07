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
# Schema ownership: ALEMBIC (ADR-109, Phase 10.17).
#
# What used to be here, and why it is gone
# ----------------------------------------
# This block used to CREATE the alembic_version table and INSERT '0008' into it
# whenever it was empty, so that a database "restored from a pre-Alembic backup"
# would not re-run every migration. Its comment described a restored database;
# its CONDITION only tested whether the version table was empty -- which is also
# true of a brand-new, completely empty one.
#
# '0008' is not a revision id either. The real one is
# 0008_add_connector_status. Alembic resolves partial ids by unique prefix, so
# instead of erroring it matched, believed 0001-0008 had already run, started at
# 0009 and failed there -- leaving the database with one table and no
# application schema. Verified by execution in Phase 10.18.
#
# There is no safe way to tell "restored" from "fresh" by looking at an empty
# version table, because an empty version table carries no information. So this
# no longer guesses. Every state now resolves through Alembic's own semantics:
#
#   empty database                  -> migrations run from 0001
#   empty alembic_version           -> identical to absent; runs from 0001
#   valid revision recorded         -> upgrade continues from it
#   invalid revision recorded       -> Alembic refuses, naming the revision
#   tables present, no version row  -> 0001 fails loudly on the first CREATE
#
# The last two fail closed with an explicit diagnostic, which is the correct
# outcome: the database is in a state nobody can resolve without being told.
#
# Recovery, when it is genuinely needed, is an OPERATOR decision and is stated
# explicitly rather than inferred:
#
#   ALEMBIC_STAMP_REVISION=<revision>   # e.g. 0008_add_connector_status
#
# Alembic validates the revision itself and refuses an unknown one, so a typo
# cannot silently strand the database at a revision that does not exist.
# ---------------------------------------------------------------------------
if [ -n "${ALEMBIC_STAMP_REVISION:-}" ]; then
    echo "[entrypoint] ALEMBIC_STAMP_REVISION=${ALEMBIC_STAMP_REVISION} set by the operator."
    echo "[entrypoint] Stamping without running migrations. This asserts the schema"
    echo "[entrypoint] already matches that revision; nothing here verifies that."
    alembic -c "$ALEMBIC_INI" stamp "$ALEMBIC_STAMP_REVISION"
    echo "[entrypoint] Stamp complete."
fi

# Acquire a PostgreSQL advisory lock to prevent concurrent migrations in
# multi-replica deployments. Only one replica will proceed; the others wait.
echo "[entrypoint] Acquiring advisory lock for migration…"
psql "$DATABASE_URL" -c "SELECT pg_advisory_lock(2024071801);" 2>/dev/null || true

MIGRATION_LOCK_HELD=true
cleanup() {
    if [ "${MIGRATION_LOCK_HELD}" = "true" ]; then
        echo "[entrypoint] Releasing advisory lock…"
        psql "$DATABASE_URL" -c "SELECT pg_advisory_unlock(2024071801);" 2>/dev/null || true
    fi
}
trap cleanup EXIT

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

# Release advisory lock explicitly before starting the app
MIGRATION_LOCK_HELD=false
psql "$DATABASE_URL" -c "SELECT pg_advisory_unlock(2024071801);" 2>/dev/null || true
trap - EXIT

echo "[entrypoint] -------------------------------------------------------"
echo "[entrypoint] Starting application: $*"
echo "[entrypoint] -------------------------------------------------------"


