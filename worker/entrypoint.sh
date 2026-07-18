#!/bin/bash
# ==============================================================
# CortexPrime Worker — Entrypoint
# Starts metrics server then Celery worker.
# Migrations are handled by the backend exclusively.
# ==============================================================
set -e

echo "[worker] Starting CortexPrime Worker..."

# Start Prometheus metrics server in background
python -c "from worker.metrics_server import start_metrics_server; start_metrics_server()" &
echo "[worker] Metrics server started on port ${WORKER_METRICS_PORT:-9100}."

echo "[worker] Worker ready. Starting task consumer..."
exec "$@"
