# CortexPrime Enterprise Documentation

Version 1.0.0-rc.1

---

## Documentation Index

| # | Document | Description |
|---|----------|-------------|
| 1 | [System Architecture](architecture.md) | Overall architecture, component diagrams, data flow, deployment topology |
| 2 | [API Reference](api.md) | Complete REST API documentation with request/response schemas |
| 3 | [Connector Reference](connectors.md) | Enterprise connector configuration, operations, and behavior |
| 4 | [Workflow Reference](workflow.md) | Workflow definitions, approval gates, retry policies, mission skills |
| 5 | [Deployment Guide](DEPLOYMENT.md) | Environment setup, Docker, infrastructure, production startup |
| 6 | [Administrator Guide](ADMINISTRATOR_GUIDE.md) | Day-2 operations: health, maintenance, backup, diagnostics, reports |
| 7 | [End User Guide](USER_GUIDE.md) | Common tasks: connectors, missions, workflows, replay, analytics |
| 8 | [Developer Guide](developer_guide.md) | Adding connectors, workflows, skills, testing, performance |
| 9 | [Security Guide](SECURITY_GUIDE.md) | Authentication, authorization, MFA, SSO, secrets, audit |
| 10 | [Troubleshooting Guide](TROUBLESHOOTING_GUIDE.md) | Common issues, diagnostic commands, log collection |
| 11 | [Production Checklist](PRODUCTION_CHECKLIST.md) | Pre-deployment validation checklist |
| 12 | [Operations Runbook](OPERATIONS_RUNBOOK.md) | Day-to-day operational procedures |
| 13 | [Disaster Recovery](DISASTER_RECOVERY_RUNBOOK.md) | Backup strategies, restore procedures, DR scenarios |
| 14 | [Release Readiness](RELEASE_READINESS.md) | Pre-release validation assessment and risk analysis |

---

## Quick Links

- **Source:** `backend/` — Python FastAPI (3.13)
- **Frontend:** `frontend/` — Next.js 16 (TypeScript)
- **Tests:** `tests/` — pytest with asyncio support
- **Benchmarks:** `tests/benchmarks/` — performance and load tests
- **Infrastructure:** PostgreSQL + pgvector, Redis, RabbitMQ, Neo4j, ChromaDB
- **Monitoring:** Prometheus + Grafana, Sentry, structured JSON logging

## Environment Overview

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENV` | `development` | Runtime environment (production hides API docs) |
| `BACKEND_PORT` | `8000` | FastAPI listen port |
| `LOG_LEVEL` | `INFO` | Logging level |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins |

See [Deployment Guide](DEPLOYMENT.md) for full environment variable reference.
