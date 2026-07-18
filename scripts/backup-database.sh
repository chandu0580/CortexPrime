#!/bin/bash
# ==============================================================
# CortexPrime — Automated Database Backup Script
# Usage: ./scripts/backup-database.sh [--s3-bucket BUCKET]
#
# Environ variables:
#   POSTGRES_HOST      (default: localhost)
#   POSTGRES_PORT      (default: 5432)
#   POSTGRES_USER      (default: cortex)
#   POSTGRES_PASSWORD  (required)
#   POSTGRES_DB        (default: cortexdb)
#   BACKUP_DIR         (default: ./backup)
#   S3_BUCKET          (optional — set to enable S3 upload)
#   AWS_ACCESS_KEY_ID  (required if S3_BUCKET set)
#   AWS_SECRET_ACCESS_KEY (required if S3_BUCKET set)
#   RETENTION_DAYS     (default: 30 — local backups older than this are removed)
# ==============================================================
set -euo pipefail

# ── Config ──────────────────────────────────────────────────────────────────
PGHOST="${POSTGRES_HOST:-localhost}"
PGPORT="${POSTGRES_PORT:-5432}"
PGUSER="${POSTGRES_USER:-cortex}"
PGPASSWORD="${POSTGRES_PASSWORD}"
PGDATABASE="${POSTGRES_DB:-cortexdb}"
BACKUP_DIR="${BACKUP_DIR:-./backup}"
S3_BUCKET="${S3_BUCKET:-}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
FILENAME="cortexprime_${PGDATABASE}_${TIMESTAMP}.dump"
BACKUP_PATH="${BACKUP_DIR}/${FILENAME}"
export PGPASSWORD

# ── Prerequisites ───────────────────────────────────────────────────────────
if [ -z "${PGPASSWORD:-}" ]; then
    echo "[backup] ERROR: POSTGRES_PASSWORD is required." >&2
    exit 1
fi

mkdir -p "${BACKUP_DIR}"

# ── Backup ───────────────────────────────────────────────────────────────────
echo "[backup] Starting database backup: ${PGDATABASE}@${PGHOST}:${PGPORT}"
echo "[backup] Output: ${BACKUP_PATH}"

pg_dump \
    -h "${PGHOST}" \
    -p "${PGPORT}" \
    -U "${PGUSER}" \
    -d "${PGDATABASE}" \
    -F c \
    -v \
    -f "${BACKUP_PATH}"

BACKUP_SIZE=$(stat -c%s "${BACKUP_PATH}" 2>/dev/null || stat -f%z "${BACKUP_PATH}" 2>/dev/null || echo "unknown")
echo "[backup] Backup complete: ${BACKUP_PATH} (${BACKUP_SIZE} bytes)"

# ── Upload to S3 ────────────────────────────────────────────────────────────
if [ -n "${S3_BUCKET}" ]; then
    if command -v aws &>/dev/null; then
        echo "[backup] Uploading to s3://${S3_BUCKET}/database/"
        aws s3 cp "${BACKUP_PATH}" "s3://${S3_BUCKET}/database/${FILENAME}"
        aws s3 cp "${BACKUP_PATH}" "s3://${S3_BUCKET}/database/latest.dump"
        echo "[backup] S3 upload complete."
    else
        echo "[backup] WARNING: AWS CLI not found, skipping S3 upload." >&2
    fi
fi

# ── Rotate local backups ────────────────────────────────────────────────────
echo "[backup] Removing backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "cortexprime_*.dump" -mtime "+${RETENTION_DAYS}" -delete
echo "[backup] Rotation complete."

echo "[backup] Database backup finished successfully."
