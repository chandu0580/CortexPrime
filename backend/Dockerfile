# ==============================================================
# CORTEXPRIME BACKEND — Multi-stage Dockerfile
# Python 3.11 | FastAPI | Uvicorn | Playwright
#
# Stages:
#   base         Debian slim + all system dependencies
#   deps         Python packages + Playwright browsers
#   development  Dev target (source mounted via volume)
#   production   Self-contained production image
# ==============================================================

# --------------------------------------------------------------
# BASE — System dependencies
# --------------------------------------------------------------
FROM python:3.11-slim AS base

# Prevents .pyc files and enables stdout/stderr flushing
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /workspace

# Install system dependencies required by CortexPrime subsystems
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build toolchain
    build-essential \
    gcc \
    g++ \
    # PostgreSQL client libraries (asyncpg / psycopg2)
    libpq-dev \
    # OCR (pytesseract)
    tesseract-ocr \
    tesseract-ocr-eng \
    # Image processing
    libjpeg-dev \
    libpng-dev \
    libffi-dev \
    # PortAudio for voice I/O (pyaudio)
    portaudio19-dev \
    libasound2-dev \
    # Virtual display for computer-use (pyautogui)
    xvfb \
    libx11-dev \
    libxext-dev \
    libxi-dev \
    xdotool \
    # Health-check & tooling
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# --------------------------------------------------------------
# DEPS — Python packages
# --------------------------------------------------------------
FROM base AS deps

COPY requirements.txt .

# Install all Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Install Playwright + Chromium for browser-automation subsystem.
# Skip the separate headless-shell artifact to avoid an additional CDN fetch.
RUN playwright install --with-deps --no-shell chromium

# --------------------------------------------------------------
# DEVELOPMENT — Hot-reload, source code mounted via volume
# --------------------------------------------------------------
FROM deps AS development

# Source code is mounted by docker-compose: .:/workspace:cached
# entrypoint.sh is available via the volume mount at /workspace/backend/entrypoint.sh

EXPOSE 8000

# Run migrations then start uvicorn.
# The entrypoint script is provided by the volume-mounted source tree.
ENTRYPOINT ["sh", "/workspace/backend/entrypoint.sh"]
CMD ["uvicorn", "backend.main:app", \
     "--reload", \
     "--host", "0.0.0.0", \
     "--port", "8000"]

# --------------------------------------------------------------
# PRODUCTION — Self-contained image
# --------------------------------------------------------------
FROM deps AS production

# Copy only the application source (no dev artifacts)
COPY backend/            ./backend/
COPY cognitive_core/     ./cognitive_core/
COPY langgraph_system/   ./langgraph_system/
COPY memory_architecture/ ./memory_architecture/
COPY memory_system/      ./memory_system/
COPY agents/             ./agents/
COPY configs/            ./configs/
COPY pyproject.toml      ./pyproject.toml

# Clean up bytecode
RUN find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true && \
    find . -name "*.pyc" -delete && \
    find . -name "*.pyo" -delete

# Copy and chmod entrypoint script
COPY backend/entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Non-root user for security
RUN groupadd --gid 1001 cortex && \
    useradd --uid 1001 --gid cortex --no-create-home cortex && \
    chown -R cortex:cortex /workspace

USER cortex

EXPOSE 8000

# Run migrations then start uvicorn (4 workers; tune with WEB_CONCURRENCY)
ENTRYPOINT ["./entrypoint.sh"]
CMD ["uvicorn", "backend.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "4", \
     "--log-level", "warning"]
