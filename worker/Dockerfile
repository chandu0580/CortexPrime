# ==============================================================
# CORTEXPRIME WORKER — Multi-stage Dockerfile
# Python 3.11 | Celery + Playwright | Background Task Execution
#
# Stages:
#   base         Debian slim + all system dependencies
#   deps         Python packages + Playwright browsers
#   production   Self-contained production worker image
# ==============================================================

# --------------------------------------------------------------
# BASE — System dependencies
# --------------------------------------------------------------
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /workspace

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ \
    libpq-dev \
    tesseract-ocr tesseract-ocr-eng \
    libjpeg-dev libpng-dev libffi-dev \
    portaudio19-dev libasound2-dev \
    xvfb libx11-dev libxext-dev libxi-dev xdotool \
    curl wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------------------
# DEPS — Python packages + Playwright
# --------------------------------------------------------------
FROM base AS deps

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

RUN playwright install --with-deps --no-shell chromium

# --------------------------------------------------------------
# PRODUCTION — Self-contained worker image
# --------------------------------------------------------------
FROM deps AS production

COPY backend/            ./backend/
COPY cognitive_core/     ./cognitive_core/
COPY langgraph_system/   ./langgraph_system/
COPY memory_architecture/ ./memory_architecture/
COPY memory_system/      ./memory_system/
COPY agents/             ./agents/
COPY configs/            ./configs/
COPY pyproject.toml      ./pyproject.toml
COPY worker/             ./worker/

RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find . -name "*.pyc" -delete && \
    find . -name "*.pyo" -delete

COPY worker/entrypoint.sh ./entrypoint-worker.sh
RUN chmod +x ./entrypoint-worker.sh

RUN groupadd --gid 1001 cortex && \
    useradd --uid 1001 --gid cortex --no-create-home cortex && \
    chown -R cortex:cortex /workspace

USER cortex

EXPOSE 9100

ENTRYPOINT ["./entrypoint-worker.sh"]
CMD ["celery", "-A", "worker.tasks", "worker", "--loglevel=warning", "--concurrency=4"]
