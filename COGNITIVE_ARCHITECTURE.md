# CortexPrime — Cognitive Architecture

## Overview

CortexPrime is a multi-agent cognitive runtime that orchestrates autonomous AI agents across a bounded-context, event-driven architecture. The system comprises four runtime layers (Identity, Knowledge, Mission, Execution) and two cross-cutting planes (Governance, Observability).

## Runtime Layers

### Identity Runtime
Manages authentication, authorization, SSO, and multi-tenancy. Provides JWT-based token issuance with refresh rotation and revocation via Redis-backed blacklist. Supports OAuth 2.0 providers and role-based access control (RBAC) with permission scoping.

### Knowledge Runtime
Persistent semantic, episodic, and procedural memory stores. Uses PostgreSQL (pgvector) for vector embeddings, Redis for transient/working memory, and Neo4j for knowledge graph relationships. Supports multi-modal memory retrieval with ranking and re-ranking.

### Mission Runtime
State-machine-driven mission lifecycle (queued → running → completed/failed). Dual-layer replay store (in-memory + PostgreSQL) enables full mission traceability. Mission planner decomposes goals into sub-tasks using recursive planning with LLM guidance.

### Execution Runtime
Sandboxed execution of agent tasks. Supports shell commands (restricted allowlist), HTTP requests, and Python scripting (sandboxed with restricted builtins). Results feed back into mission state via event bus.

## Cross-Cutting Planes

### Governance
Safety guardrails (input/output validation, PII detection), audit logging (cryptographically chained), approval workflows, rate limiting, emergency stop, and compliance reporting.

### Observability
Prometheus metrics (HTTP, LLM, missions, agents, voice, memory), structured JSON logging with request ID correlation, OpenTelemetry tracing (HTTP exporter), and pre-built Grafana dashboards.

## Event-Driven Communication

The EventBus provides publish/subscribe with:
- In-memory event history (capped at 10,000 events)
- WebSocket streaming (session-aware routing)
- Mission replay store (dual-layer persistence)
- Prometheus metric instrumentation

## Deployment Topology

- **Backend**: FastAPI (async Python 3.11) — horizontal scaling with sticky sessions
- **Worker**: Celery — background task processing
- **Frontend**: Next.js 16 (App Router) — server-side rendering
- **Infrastructure**: PostgreSQL (pgvector), Redis, RabbitMQ, Neo4j, MinIO, OpenSearch
- **Orchestration**: Kubernetes (Helm) or Docker Compose
