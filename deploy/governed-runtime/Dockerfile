# CortexPrime governed runtime -- the image a production deployment runs.
#
# Phase 11.1-K. One process: the product API (backend.api.product.server) with
# CORTEX_RUN_GOVERNED_PLANE=1, which composes the governed runtime, commissions
# connectors, and runs the signal, investigation and remediation loops and
# connector health. The migration job runs Alembic from the same image.
#
# Build (from the repository root):
#   docker build -f deploy/governed-runtime/Dockerfile -t cortexprime/governed-runtime:1.0.0 .
# The Dockerfile-specific ignore file next to this one admits only backend/ and
# this directory, so neither the V1 frontend nor a virtualenv reaches the build.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY deploy/governed-runtime/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY backend /app/backend

# A fixed, non-root identity; the process writes nothing to its own filesystem.
RUN useradd --uid 65532 --no-create-home --shell /usr/sbin/nologin cortex
USER 65532:65532

EXPOSE 8110 9102
ENV CORTEX_RUN_GOVERNED_PLANE=1 \
    CORTEX_METRICS_PORT=9102
CMD ["python", "-m", "uvicorn", "backend.api.product.server:app", "--host", "0.0.0.0", "--port", "8110", "--no-access-log"]
