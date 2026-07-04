# CortexPrime

A full-stack autonomous multi-agent AI operating system with a cinematic real-time UI, cognitive orchestration, computer-use capabilities, voice interaction, and a persistent memory architecture.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Running the Application](#running-the-application)
- [Frontend Pages](#frontend-pages)
- [Backend API](#backend-api)
- [Environment Variables](#environment-variables)
- [Key Features](#key-features)

---

## Overview

CortexPrime is an autonomous AI runtime that coordinates multiple specialized agents (Planner, Researcher, Critic, Optimizer, Orchestrator) to complete complex missions. It exposes a real-time WebSocket event bus, a REST API, and a Next.js frontend that visualises cognitive state, agent activity, memory, and live streaming responses.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend (Next.js)                     │
│  /, /runtime, /cognition, /memory, /operator, /voice          │
│  Zustand stores · WebSocket live events · REST API client     │
└─────────────────────────┬────────────────────────────────────┘
                           │  HTTP :8000  /  WS :8000/ws
┌─────────────────────────▼────────────────────────────────────┐
│                    Backend (FastAPI + uvicorn)                 │
│  Agent Registry · Event Bus · Runtime State · LLM Router      │
│  Agents: Planner · Researcher · Critic · Optimizer            │
│  Memory: Episodic · Semantic · Short-term · Vector (Chroma)   │
│  Tools: Browser (Playwright) · Computer-use · Vision · Voice  │
└──────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

### Backend
| Package | Purpose |
|---|---|
| FastAPI + uvicorn | REST API + WebSocket server |
| OpenAI / Anthropic / Google Gemini / Ollama | LLM providers |
| ChromaDB | Vector memory |
| Playwright | Browser automation |
| pyautogui + mss | Desktop computer-use |
| edge-tts + SpeechRecognition | Voice I/O |
| pymupdf | PDF / OCR processing |

### Frontend
| Package | Purpose |
|---|---|
| Next.js 16 + React 19 | App framework |
| TypeScript | Type safety |
| TailwindCSS v4 | Styling |
| Zustand v5 | State management |
| ReactFlow v11 | Agent graph visualisation |
| Framer Motion | Animations |
| Recharts | Runtime metrics charts |
| Axios | HTTP client |
| react-markdown | Markdown rendering |

---

## Project Structure

```
cortexprime/
├── backend/                  # FastAPI application
│   ├── main.py               # App entrypoint (uvicorn target)
│   ├── api/                  # Route definitions
│   ├── agents/               # Agent implementations
│   ├── core/                 # Logging, errors, exception handlers
│   ├── middleware/           # Request ID correlation middleware
│   ├── events/               # Event bus + event models
│   ├── llm/                  # LLM provider routing
│   ├── memory/               # Memory subsystems
│   ├── orchestrator/         # Mission orchestration
│   ├── runtime/              # Agent registry + runtime state
│   ├── tools/                # API, repair, autonomy tools
│   ├── voice/                # TTS + STT
│   ├── vision/               # Screenshot + OCR
│   ├── websocket/            # WebSocket router
│   ├── .env                  # Environment variables (not committed)
│   └── .env.example          # Template — copy to .env
│
├── frontend/                 # Next.js application
│   ├── app/                  # App router pages
│   ├── components/           # UI components
│   ├── hooks/                # Custom React hooks
│   ├── services/             # API + WebSocket clients
│   ├── store/                # Zustand stores
│   ├── types/                # TypeScript types
│   ├── utils/                # Utility functions
│   └── styles/               # Global CSS + animations
│
├── agents/                   # Standalone agent configs
├── cognitive_core/           # Cognition + world model
├── langgraph_system/         # LangGraph runtime graphs
├── memory_architecture/      # Memory subsystem modules
├── scripts/                  # Bootstrap + deployment scripts
├── tests/                    # Integration + unit tests (pytest)
├── docs/                     # DEPLOYMENT.md, PRODUCTION_CHECKLIST.md
├── .github/workflows/        # CI/CD — test, security, release
├── requirements.txt          # Python runtime dependencies
├── requirements-dev.txt      # Dev/test tooling (pytest-cov, ruff, mypy)
└── docker-compose.yml        # Container orchestration
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 20+
- A virtual environment tool (`venv`)

### 1. Clone and set up the Python environment

```powershell
git clone <repo-url>
cd cortexprime

python -m venv venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt
```

### 2. Configure environment variables

Create `backend/.env` (already present) and set at minimum:

```env
OPENAI_API_KEY=sk-...
```

Optional provider keys:

```env
ANTHROPIC_API_KEY=...
GOOGLE_API_KEY=...
```

### 3. Install frontend dependencies

```powershell
cd frontend
npm install
```

---

## Running the Application

### Start the backend

> **Important:** always run this command from the **project root** (`C:\projects\cortexprime`), not from inside the `backend/` folder. The module path `backend.main` requires the root to be on Python's path.

```powershell
# From C:\projects\cortexprime  (project root)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1

.\venv\Scripts\uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

Backend available at: **http://localhost:8000**  
API docs (Swagger UI): **http://localhost:8000/docs**  
WebSocket endpoint: **ws://localhost:8000/ws**

### Start the frontend

```powershell
cd frontend
npm run dev
```

Frontend available at: **http://localhost:3000**

### Using Docker Compose (production)

Use the production override for deployment-like local runs:

#### First run (or after Dockerfile / dependency / source changes)

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file backend/.env up -d --build
```

#### Normal daily start (no rebuild)

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file backend/.env up -d
```

#### Check service health

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file backend/.env ps
```

#### Stop the stack

```powershell
docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file backend/.env down
```

All 9 services should become healthy: nginx (TLS :443), frontend (:3000 internal), backend (:8000 internal), postgres, redis, rabbitmq, neo4j, prometheus (:9090), grafana (:3001).

> Opening Docker Desktop alone does not start this stack if containers are stopped. Run `docker compose ... up -d` to start it.

---

## Frontend Pages

| Route | Description |
|---|---|
| `/` | Landing page V4 — mouse-reactive, interactive capability cards |
| `/command` | Command centre — chat, mission timeline, runtime status |
| `/runtime` | Live agent activity, metrics, events, health |
| `/cognition` | Cognition pulse, Agent Graph V2, execution flow |
| `/memory` | Episodic viewer, semantic memory, reflection log |
| `/operator` | Browser runtime, desktop telemetry, computer-use stream |
| `/voice` | Voice orb, waveform, real-time transcript, wake-word |
| `/governance-center` | Human approval queue, safety controls |
| `/memory-explorer` | Memory Explorer — cross-store search, timeline, graph, heatmap |
| `/replay` | Mission Replay — step-by-step execution playback |
| `/analytics` | Performance analytics and telemetry |
| `/costs` | Executive cost intelligence dashboard |
| `/system-status` | Deployment diagnostics and component health |
| `/showcase` | Recruiter / investor presentation mode — keyboard nav, auto-advance |

---

## Backend API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/missions/active` | List active missions |
| `GET` | `/api/missions/completed` | List completed missions |
| `POST` | `/api/orchestrator/autonomous` | Launch autonomous mission |
| `GET` | `/api/orchestrator/loops/active` | Active orchestration loops |
| `GET` | `/health` | Backend health check |
| `GET` | `/health/system` | Aggregated system health (all 12 subsystems) |
| `GET` | `/metrics` | Prometheus metrics scrape endpoint |
| `GET` | `/api/costs/summary` | Executive cost summary (today / month / trends) |
| `GET` | `/api/costs/daily` | Daily cost totals |
| `GET` | `/api/costs/providers` | Provider breakdown |
| `GET` | `/api/memory/explorer/search` | Cross-store vector + text memory search |
| `GET` | `/api/memory/explorer/timeline` | Memories grouped by date |
| `GET` | `/api/memory/explorer/graph` | Memory concept graph (nodes + edges) |
| `GET` | `/api/memory/explorer/stats` | Aggregate stats + heatmap |
| `GET` | `/api/mission-replay/{id}` | Full mission replay data |
| `WS`  | `/ws` | Real-time cognitive event stream |

Full interactive docs: **http://localhost:8000/docs**

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in values. Never commit the real `.env` file.

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes* | OpenAI API key (`*` or Azure equivalent) |
| `AZURE_OPENAI_API_KEY` | Yes* | Azure OpenAI key (alternative to direct OpenAI) |
| `AZURE_OPENAI_ENDPOINT` | Yes* | Azure OpenAI endpoint URL |
| `ANTHROPIC_API_KEY` | No | Anthropic Claude key |
| `GOOGLE_API_KEY` | No | Google Gemini key |
| `TAVILY_API_KEY` | No | Tavily search API key (web research) |
| `POSTGRES_URL` | Yes | PostgreSQL connection string |
| `REDIS_URL` | Yes | Redis connection string |
| `DATABASE_URL` | Yes | Same as `POSTGRES_URL` (used by Alembic) |
| `JWT_SECRET_KEY` | Yes | ≥32-char random secret for access tokens |
| `JWT_REFRESH_SECRET` | Yes | ≥32-char random secret for refresh tokens |
| `SENTRY_DSN` | No | Sentry backend error tracking DSN |
| `NEXT_PUBLIC_SENTRY_DSN` | No | Sentry frontend DSN |
| `ENVIRONMENT` | No | `development` \| `staging` \| `production` |
| `STRUCTURED_LOGGING` | No | `true` = JSON logs (recommended in production) |
| `RATE_LIMIT_ENABLED` | No | `true` to enable Redis-backed rate limiting |
| `WS_AUTH_REQUIRED` | No | `true` to require JWT on WebSocket connections |
| `NEXT_PUBLIC_API_URL` | No | Backend URL (default: `http://localhost:8000`) |
| `NEXT_PUBLIC_WS_URL` | No | WebSocket URL (default: `ws://localhost:8000/ws`) |

> **Production note:** Swagger UI (`/docs`) and ReDoc (`/redoc`) are disabled when `ENVIRONMENT=production`. API documentation is only accessible in development.

---

## Observability

All HTTP responses include an `X-Request-ID` header for distributed tracing. Structured JSON logs are emitted to stdout when `STRUCTURED_LOGGING=true`. The `/health/system` endpoint reports the status of 12 subsystems including `request_tracing`, `exception_handler`, and `sentry`.

Error responses always use the standard envelope:
```json
{"success": false, "error": {"code": "NOT_FOUND", "message": "...", "request_id": "..."}}
```

---

## CI/CD & Deployment

Three GitHub Actions workflows run on every push:

| Workflow | Trigger | What it does |
|---|---|---|
| `test.yml` | push/PR to `main`/`develop` | pytest (45% cov threshold) + Next.js build + Docker smoke test |
| `security.yml` | push + weekly | pip-audit, npm audit, Trivy container scan, Semgrep OWASP |
| `release.yml` | tag `v*.*.*` | Multi-arch Docker push to GHCR + GitHub Release creation |

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the full deployment runbook and [docs/PRODUCTION_CHECKLIST.md](docs/PRODUCTION_CHECKLIST.md) for the pre-release checklist.

---

## Key Features

- **Multi-agent orchestration** — Planner, Researcher, Critic, and Optimizer agents collaborate under a central orchestrator to complete complex missions
- **Real-time cognitive event stream** — WebSocket-driven live feed of every agent thought, action, and decision
- **Persistent memory** — Episodic, semantic, short-term, and vector (Chroma) memory with reflection and consolidation
- **Computer use** — Autonomous browser control via Playwright and desktop automation via pyautogui
- **Voice interface** — Wake-word detection, speech-to-text input, and TTS responses
- **Vision** — Screenshot capture and OCR for visual context
- **Multi-LLM routing** — Dynamically routes tasks to OpenAI, Anthropic, Google Gemini, or local Ollama models
- **Cinematic UI** — Dark glassmorphism design with animated neural grid, streaming responses, and real-time charts
