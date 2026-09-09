# CortexPrime REST API Reference

Base URL: `http://<host>:8000`

- Authentication is via **JWT Bearer token** (`Authorization: Bearer <token>`) or **httpOnly `cortex_access` cookie**.
- Auth level `require_user` means any authenticated user; `require_admin` requires `role=admin` or `role=ADMIN`; `none` means open.
- All timestamps are ISO-8601 UTC unless noted.
- Error responses follow the pattern `{"detail": "<message>"}` with appropriate HTTP status codes.

---

## Table of Contents

1. [Auth – `/api/auth`](#1-auth--apiauth)
2. [Mission Execution – `/execute`, `/orchestrate`](#2-mission-execution)
3. [Runtime API – `/api/runtime`](#3-runtime-api--apiruntime)
4. [Mission Routes – `/api/missions`](#4-mission-routes--apimissions)
5. [Orchestrator Routes – `/api/orchestrator`](#5-orchestrator-routes--apiorchestrator)
6. [Memory Routes – `/api/memory`](#6-memory-routes--apimemory)
7. [Memory Explorer – `/api/memory/explorer`](#7-memory-explorer--apimemoryexplorer)
8. [Vector Search – `/api/vector`](#8-vector-search--apivector)
9. [Governance – `/governance`](#9-governance--governance)
10. [Governance Center – `/api/governance-center`](#10-governance-center--apigovernance-center)
11. [Executive – `/api/executive`](#11-executive--apiexecutive)
12. [Approval Center – `/api/approval-center`](#12-approval-center--apiapproval-center)
13. [Security Center – `/api/security`](#13-security-center--apisecurity)
14. [Connectors – `/api/connectors`](#14-connectors--apiconnectors)
15. [Connector Activity – `/api/connectors/activity`](#15-connector-activity--apiconnectorsactivity)
16. [Organizations – `/api/organizations`](#16-organizations--apiorganizations)
17. [Departments – `/api/departments`](#17-departments--apidepartments)
18. [Projects – `/api/projects`](#18-projects--apiprojects)
19. [Enterprise Replay – `/api/enterprise-replay`](#19-enterprise-replay--apienterprise-replay)
20. [Mission Replay – `/api/mission-replay`](#20-mission-replay--apimission-replay)
21. [Mission Library – `/api/mission-library`](#21-mission-library--apimission-library)
22. [Research – `/api/research`](#22-research--apiresearch)
23. [Computer Agent – `/computer`](#23-computer-agent--computer)
24. [Operator – `/operator`](#24-operator--operator)
25. [Workspace – `/api/workspace`](#25-workspace--apiworkspace)
26. [System Health – `/health/system`](#26-system-health--healthsystem)
27. [LLM Health – `/health/llm`](#27-llm-health--healthllm)
28. [Metrics – `/metrics`](#28-metrics--metrics)
29. [Costs – `/api/costs`](#29-costs--apicosts)
30. [Audit – `/api/audit`](#30-audit--apiaudit)
31. [Telemetry – `/api/telemetry`](#31-telemetry--apitelemetry)
32. [RabbitMQ – `/api/rabbitmq`](#32-rabbitmq--apirabbitmq)
33. [Graph (Neo4j) – `/api/graph`](#33-graph-neo4j--apigraph)
34. [Health Center – `/api/operations/health-center`](#34-health-center--apioperationshealth-center)
35. [Backup – `/api/operations/backup`](#35-backup--apioperationsbackup)
36. [Maintenance – `/api/operations/maintenance`](#36-maintenance--apioperationsmaintenance)
37. [Diagnostics – `/api/operations/diagnostics`](#37-diagnostics--apioperationsdiagnostics)
38. [Operational Reports – `/api/operations/reports`](#38-operational-reports--apioperationsreports)
39. [Root Routes – `/`, `/api/chat`](#39-root-routes)

---

## 1. Auth – `/api/auth`

### POST `/api/auth/login`

Authenticate with username + password. Returns an access token in the body and sets httpOnly `cortex_refresh` + `cortex_access` cookies.

**Auth:** none

**Request** (`LoginRequest`):
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | `str` | ✓ | 1–128 chars |
| `password` | `str` | ✓ | 1–256 chars |

**Response** (`200`, `TokenResponse`):
| Field | Type | Description |
|-------|------|-------------|
| `access_token` | `str` | JWT access token |
| `token_type` | `str` | Always `"bearer"` |
| `expires_in` | `int` | Seconds until expiry |
| `user` | `dict` | `{user_id, role, clearance}` |

**Errors:** `401` – Invalid credentials

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "secret"}'
```

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 3600,
  "user": { "user_id": "admin", "role": "OPERATOR", "clearance": "LEVEL-5" }
}
```

---

### POST `/api/auth/refresh`

Exchange a valid refresh token (httpOnly `cortex_refresh` cookie) for new tokens. Implements refresh-token rotation with revocation.

**Auth:** none (reads cookie)

**Response** (`200`, `TokenResponse`): Same as login.

```bash
curl -X POST http://localhost:8000/api/auth/refresh \
  -H "Cookie: cortex_refresh=eyJhbGci..."
```

---

### POST `/api/auth/logout`

Revoke the caller's current access + refresh tokens and clear cookies.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "status": "ok", "message": "Session terminated — tokens revoked" }
```

```bash
curl -X POST http://localhost:8000/api/auth/logout \
  -H "Authorization: Bearer eyJhbGci..."
```

---

### GET `/api/auth/me`

Return profile for the currently authenticated user.

**Auth:** `require_user`

**Response** (`200`, `UserProfile`):
| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `str` | Subject claim from JWT |
| `role` | `str` | Uppercased role |
| `clearance` | `str` | Always `"LEVEL-5"` |

```bash
curl http://localhost:8000/api/auth/me \
  -H "Authorization: Bearer eyJhbGci..."
```

```json
{ "user_id": "admin", "role": "OPERATOR", "clearance": "LEVEL-5" }
```

---

### POST `/api/auth/revoke-all`

Revoke ALL tokens for the calling user. Invalidates the current session too.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "status": "ok", "message": "All tokens revoked — please log in again", "revoked_at_epoch": 1700000000.0 }
```

---

### POST `/api/auth/admin/revoke-user/{target_user_id}`

Admin action: revoke ALL tokens for any user.

**Auth:** `require_admin`

**Response** (`200`):
```json
{ "status": "ok", "message": "All tokens revoked for user 'janedoe'", "revoked_at_epoch": 1700000000.0 }
```

**Errors:** `403` – Not admin

---

### GET `/api/auth/health`

Auth service health — no authentication required.

**Auth:** none

**Response** (`200`):
```json
{
  "status": "healthy",
  "auth": "jwt",
  "algorithm": "HS256",
  "redis_connected": true,
  "revoked_token_count": 3,
  "active_sessions": 12,
  "fail_open": false
}
```

---

## 2. Mission Execution

### POST `/execute`

Accept a mission objective and run the full pipeline in the background. Tokens stream via WebSocket.

**Auth:** `require_user`

**Request** (`ExecuteRequest`):
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `objective` | `str` | ✓ | 1–4000 chars |
| `session_id` | `str` | | Max 128 chars |
| `workspace_id` | `str` | | Max 128 chars |

**Response** (`200`, `ExecuteResponse`):
```json
{ "accepted": true, "execution_id": null, "message": "Mission accepted — streaming via WebSocket" }
```

```bash
curl -X POST http://localhost:8000/execute \
  -H "Authorization: Bearer eyJhbGci..." \
  -H "Content-Type: application/json" \
  -d '{"objective": "Research AI trends and summarize"}'
```

---

### POST `/execute/sync`

Run the mission synchronously and wait for the full result.

**Auth:** `require_user`

**Request:** Same `ExecuteRequest` as above.

**Response:** Full mission result dict.

---

### POST `/orchestrate`

Alias for `/execute` — keeps frontend compatibility.

**Auth:** `require_user`

**Request:** Same `ExecuteRequest`.

**Response** (`200`):
```json
{ "status": "accepted", "message": "Mission started — streaming via WebSocket", "result": "" }
```

---

## 3. Runtime API – `/api/runtime`

### POST `/api/runtime/execute`

Launch a full cognition pipeline execution.

**Auth:** `require_user`

**Request** (`runtime.ExecuteRequest`):
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `objective` | `str` | ✓ | | Mission objective |
| `priority` | `int` | | `5` | 1 (highest) – 10 (lowest) |
| `async_mode` | `bool` | | `false` | Fire-and-forget if true |
| `stages` | `list[str]` | | `null` | Limit to these stages |
| `session_id` | `str` | | `null` | |

**Response** (`200`):
Sync mode:
```json
{
  "execution_id": "uuid",
  "status": "completed",
  "objective": "Research AI trends",
  "completed_stages": ["plan", "research", "synthesize"],
  "failed_stages": [],
  "stage_timings": {...},
  "final_response": "...",
  "errors": [],
  "started_at": "...",
  "ended_at": "..."
}
```

Async mode:
```json
{ "accepted": true, "execution_id": "uuid", "status": "queued", "message": "Execution queued: uuid" }
```

---

### POST `/api/runtime/autonomous-loop`

Start an autonomous cognition loop with reflection-driven adaptation.

**Auth:** `require_user`

**Request** (`AutonomousLoopRequest`):
| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `goal` | `str` | ✓ | | Overarching goal |
| `max_iterations` | `int` | | `3` | 1–10 |
| `priority` | `int` | | `5` | 1–10 |

**Response** (`200`):
```json
{ "accepted": true, "loop_id": "loop-Research-AI-trends", "goal": "Research AI trends", "iterations": 5, "status": "started" }
```

---

### GET `/api/runtime/executions/{execution_id}`

Get full state of a specific execution.

**Auth:** `require_user`

**Response** (`200`): Full execution context dict.

**Errors:** `404` – Execution not found

---

### GET `/api/runtime/executions`

List executions.

**Auth:** `require_user`

| Query | Type | Default | Description |
|-------|------|---------|-------------|
| `active_only` | `bool` | `false` | Return only active executions |

**Response** (`200`):
```json
{ "executions": [...], "count": 5 }
```

---

### DELETE `/api/runtime/executions/{execution_id}`

Cancel a running execution.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "execution_id": "uuid", "cancelled": true }
```

**Errors:** `404` – Execution not found

---

### GET `/api/runtime/queue`

Snapshot of the current execution priority queue.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "queued_tasks": [...], "queue_size": 3 }
```

---

### GET `/api/runtime/agents`

All registered agents with metadata and lifecycle status.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "agents": { "orchestrator": {...}, "planner": {...} }, "total": 6, "active_agents": ["orchestrator"] }
```

---

### GET `/api/runtime/traces/{execution_id}`

Execution trace (all spans) for a specific execution.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "execution_id": "uuid", "spans": [...], "summary": {...} }
```

---

### POST `/api/runtime/decompose`

Decompose an objective into pipeline sub-tasks without executing them.

**Auth:** `require_user`

**Request** (`DecomposeRequest`):
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `objective` | `str` | ✓ | |
| `priority` | `int` | | `5` |
| `use_llm` | `bool` | | `false` |

**Response** (`200`):
```json
{ "preview_execution_id": "uuid", "objective": "...", "tasks": [...], "stage_count": 4 }
```

---

### GET `/api/runtime/infrastructure`

Live status of all infrastructure components.

**Auth:** `require_user`

**Response** (`200`):
```json
{
  "rabbitmq": { "available": true, "status": "connected" },
  "redis": { "available": true, "status": "connected" },
  "neo4j": { "available": false, "status": "disconnected" },
  "event_bus": "active",
  "websocket": "active",
  "agent_registry": 6
}
```

---

### GET `/api/runtime/cognition-graph`

Agent cognition relationship graph from Neo4j.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "agents": [...], "edges": [...] }
```

---

## 4. Mission Routes – `/api/missions`

### GET `/api/missions/active`

**Auth:** `require_user`

List active missions.

**Response** (`200`):
```json
{ "missions": [...], "status": "ok" }
```

---

### GET `/api/missions/completed`

**Auth:** `require_user`

List completed missions.

**Response** (`200`):
```json
{ "missions": [...], "status": "ok" }
```

---

## 5. Orchestrator Routes – `/api/orchestrator`

### POST `/api/orchestrator/execute`

Execute a goal through the master agent runtime.

**Auth:** `require_user`

**Request:** Arbitrary JSON payload.

---

### POST `/api/orchestrator/autonomous`

Start an autonomous reasoning loop.

**Auth:** `require_user`

**Request:** Arbitrary JSON payload.

---

### POST `/api/orchestrator/route`

Route a goal through the agent router.

**Auth:** `require_user`

---

### POST `/api/orchestrator/reflect`

Analyze a result through the reflection engine.

**Auth:** `require_user`

---

### GET `/api/orchestrator/loops/active`

List active autonomous loops.

**Auth:** `require_user`

---

### GET `/api/orchestrator/loops/history`

List loop history.

**Auth:** `require_user`

---

## 6. Memory Routes – `/api/memory`

### GET `/api/memory/status`

Return availability status of each memory subsystem.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "status": "online", "postgres": true, "redis": true, "neo4j": false, "embeddings": "healthy", "total_events_tracked": 1240 }
```

---

### POST `/api/memory/store`

Store a memory entry.

**Auth:** `require_user`

**Request** (`StoreMemoryRequest`):
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `MemoryType` | ✓ | `episodic`, `semantic`, or `reflection` |
| `agent` | `str` | ✓ | |
| `content` | `str` | ✓ | |
| `session_id` | `str` | | |
| `mission_id` | `str` | | |
| `event_type` | `str` | | Default `"memory"` |
| `concept` | `str` | | Required for semantic |
| `metadata` | `dict` | | |

**Response** (`200`):
```json
{ "memory_id": "uuid", "type": "episodic" }
```

---

### POST `/api/memory/search`

Multi-store semantic search across episodic and semantic memory.

**Auth:** `require_user`

**Request** (`SearchRequest`):
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `query` | `str` | ✓ | |
| `n_results` | `int` | | `10` |
| `session_id` | `str` | | |
| `include_episodic` | `bool` | | `true` |
| `include_semantic` | `bool` | | `true` |
| `min_relevance` | `float` | | `0.0` |

**Response** (`200`): List of matching memory dicts.

---

### GET `/api/memory/search`

GET-friendly semantic search shortcut.

**Auth:** `require_user`

| Query | Type | Required | Default |
|-------|------|----------|---------|
| `q` | `str` | ✓ | |
| `n` | `int` | | `10` |

---

### GET `/api/memory/context/{session_id}`

Assemble and return the full cognitive context for a session.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `query` | `str` | |
| `n_episodic` | `int` | `10` |
| `n_semantic` | `int` | `10` |

**Response** (`200`, `AssembledContext`):
```json
{
  "session_id": "sess-123",
  "query": "...",
  "episodic": [...],
  "semantic": [...],
  "reflections": [...],
  "active_context": {...},
  "compression_applied": false,
  "assembled_at": "2025-01-01T00:00:00"
}
```

---

### GET `/api/memory/episodic/{session_id}`

Return recent episodic events for a session.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `limit` | `int` | `50` |

---

### GET `/api/memory/semantic`

Look up semantic entries by concept or return most recent.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `concept` | `str` | |
| `limit` | `int` | `20` |

---

### POST `/api/memory/reflect`

Store a self-reflective cognitive entry.

**Auth:** `require_user`

**Request** (`ReflectRequest`):
| Field | Type | Required |
|-------|------|----------|
| `agent` | `str` | ✓ |
| `reflection` | `str` | ✓ |
| `mission_id` | `str` | |
| `score` | `float` | |
| `metadata` | `dict` | |

**Response** (`200`):
```json
{ "memory_id": "uuid" }
```

---

### GET `/api/memory/reflections/agent/{agent}`

Get reflections by agent.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `limit` | `int` | `20` |

---

### GET `/api/memory/reflections/mission/{mission_id}`

Get reflections for a mission.

**Auth:** `require_user`

---

### POST `/api/memory/session/{session_id}/init`

Initialise a new cognitive session context.

**Auth:** `require_user`

**Request Body:**
| Field | Type |
|-------|------|
| `objective` | `str` |
| `agents` | `list[str]` |

**Response** (`200`):
```json
{ "session_id": "sess-123", "status": "initialised" }
```

---

### POST `/api/memory/session/{session_id}/consolidate`

Consolidate session short-term memory into long-term semantic store.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "session_id": "sess-123", "semantic_memory_id": "uuid", "status": "consolidated" }
```

---

### GET `/api/memory/graph/lineage/{mission_id}`

Return the cognitive execution lineage for a mission.

**Auth:** `require_user`

---

### GET `/api/memory/graph/related/{memory_id}`

Return memories related via graph traversal.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `depth` | `int` | `2` |

---

## 7. Memory Explorer – `/api/memory/explorer`

### GET `/api/memory/explorer/search`

Cross-store similarity + text search.

**Auth:** `require_user`

| Query | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `q` | `str` | ✓ | | Search query |
| `limit` | `int` | | `20` | 1–100 |
| `memory_types` | `str` | | `"all"` | Comma-separated: `episodic,semantic,reflection,workspace,voice,browser,all` |
| `min_score` | `float` | | `0.0` | |
| `agent_filter` | `str` | | | |

**Response** (`200`):
```json
{ "query": "AI", "count": 5, "results": [...] }
```

---

### GET `/api/memory/explorer/timeline`

All memories ordered by date, grouped by day.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `days` | `int` | `30` |
| `limit_per_day` | `int` | `50` |

**Response** (`200`):
```json
{ "days": 30, "total": 200, "day_count": 15, "timeline": [...] }
```

---

### GET `/api/memory/explorer/graph`

Node/edge data for memory concept graph.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `limit` | `int` | `80` |

**Response** (`200`):
```json
{ "node_count": 40, "edge_count": 25, "nodes": [...], "edges": [...] }
```

---

### GET `/api/memory/explorer/stats`

Aggregate stats + heatmap data.

**Auth:** `require_user`

**Response** (`200`):
```json
{
  "total": 1200,
  "by_type": { "episodic": 800, "semantic": 300, "reflection": 100 },
  "by_agent": { "orchestrator": 400, "planner": 200 },
  "avg_similarity": null,
  "heatmap": [...],
  "date_distribution": { "2025-01-01": 15, ... }
}
```

---

## 8. Vector Search – `/api/vector`

### GET `/api/vector/health`

PostgreSQL + pgvector health status.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "status": "healthy", "pgvector": true, "latency_ms": 2.3 }
```

---

### POST `/api/vector/episodic`

Persist an episodic memory event.

**Auth:** `require_user`

**Request** (`StoreEpisodicRequest`):
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | `str` | ✓ | |
| `agent` | `str` | ✓ | |
| `event_type` | `str` | ✓ | |
| `content` | `str` | ✓ | |
| `embedding` | `list[float]` | | Pre-computed embedding |
| `metadata` | `dict` | | |

**Response** (`201`):
```json
{ "id": "uuid" }
```

---

### GET `/api/vector/episodic/{session_id}`

Return recent episodic events for a session.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `limit` | `int` | `50` |

---

### POST `/api/vector/episodic/search/vector`

Cosine similarity search over episodic memory embeddings.

**Auth:** `require_user`

**Request** (`VectorSearchRequest`):
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `embedding` | `list[float]` | ✓ | |
| `limit` | `int` | | `10` |
| `min_similarity` | `float` | | `0.0` |
| `session_id` | `str` | | |
| `agent` | `str` | | |
| `min_confidence` | `float` | | `0.0` |

---

### GET `/api/vector/episodic/search/text`

PostgreSQL full-text search over episodic memory.

**Auth:** `require_user`

| Query | Type | Required | Default |
|-------|------|----------|---------|
| `q` | `str` | ✓ | |
| `limit` | `int` | | `10` |

---

### POST `/api/vector/semantic`

Persist a semantic knowledge entry.

**Auth:** `require_user`

**Request** (`StoreSemanticRequest`):
| Field | Type | Required |
|-------|------|----------|
| `concept` | `str` | ✓ |
| `content` | `str` | ✓ |
| `embedding` | `list[float]` | |
| `source` | `str` | |
| `confidence` | `float` | (default `1.0`) |
| `metadata` | `dict` | |

**Response** (`201`):
```json
{ "id": "uuid" }
```

---

### GET `/api/vector/semantic`

Fetch semantic entries by concept name.

**Auth:** `require_user`

| Query | Type | Required | Default |
|-------|------|----------|---------|
| `concept` | `str` | ✓ | |
| `limit` | `int` | | `10` |

---

### POST `/api/vector/semantic/search/vector`

Cosine similarity search over semantic memory.

**Auth:** `require_user`

**Request:** `VectorSearchRequest`

---

### POST `/api/vector/semantic/search/hybrid`

Hybrid semantic search (vector + full-text, deduplicated).

**Auth:** `require_user`

**Request** (`HybridSearchRequest`):
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `query` | `str` | ✓ | |
| `embedding` | `list[float]` | | |
| `limit` | `int` | | `10` |
| `min_confidence` | `float` | | `0.0` |

---

### POST `/api/vector/reflection`

Persist a reflection entry.

**Auth:** `require_user`

**Request** (`StoreReflectionRequest`):
| Field | Type | Required |
|-------|------|----------|
| `agent` | `str` | ✓ |
| `reflection` | `str` | ✓ |
| `embedding` | `list[float]` | |
| `mission_id` | `str` | |
| `score` | `float` | |
| `metadata` | `dict` | |

**Response** (`201`):
```json
{ "id": "uuid" }
```

---

### GET `/api/vector/reflection/agent/{agent}`

Get reflections by agent.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `limit` | `int` | `20` |

---

### POST `/api/vector/reflection/search/vector`

Cosine similarity search over reflection embeddings.

**Auth:** `require_user`

**Request:** `VectorSearchRequest`

---

### POST `/api/vector/analytics`

Ingest a runtime analytics event.

**Auth:** `require_user`

**Request** (`RecordAnalyticsRequest`):
| Field | Type | Required |
|-------|------|----------|
| `agent` | `str` | ✓ |
| `event_type` | `str` | ✓ |
| `model` | `str` | |
| `mission_id` | `str` | |
| `session_id` | `str` | |
| `prompt_tokens` | `int` | |
| `output_tokens` | `int` | |
| `latency_ms` | `float` | |
| `cost_usd` | `float` | |
| `success` | `bool` | (default `true`) |
| `error_message` | `str` | |
| `payload` | `dict` | |

**Response** (`201`):
```json
{ "id": "uuid" }
```

---

### GET `/api/vector/analytics/agent/{agent}`

Aggregated performance stats for an agent.

**Auth:** `require_user`

---

### GET `/api/vector/analytics/hourly`

Per-agent, per-hour call volume.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `hours` | `int` | `24` |

---

### GET `/api/vector/analytics/models`

Aggregated token and cost breakdown per LLM model.

**Auth:** `require_user`

---

### GET `/api/vector/analytics/errors`

Most recent failed analytics events.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `limit` | `int` | `50` |

---

## 9. Governance – `/governance`

### POST `/governance/request-approval`

Submit a manual approval request.

**Auth:** `require_user`

**Request** (`ManualApprovalRequest`):
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `execution_id` | `str` | ✓ | |
| `agent` | `str` | | `"operator"` |
| `action` | `str` | ✓ | |
| `description` | `str` | ✓ | |
| `risk_level` | `str` | | `"high"` |
| `context` | `dict` | | |
| `session_id` | `str` | | |

**Response** (`200`):
```json
{ "accepted": true, "request_id": "uuid", "status": "pending", "message": "Approval request queued." }
```

---

### POST `/governance/approve`

Approve a pending governance request.

**Auth:** `require_admin`

**Request** (`ApproveRequest`):
| Field | Type | Required |
|-------|------|----------|
| `request_id` | `str` | ✓ |
| `approved_by` | `str` | |

**Response** (`200`):
```json
{ "success": true, "request_id": "uuid", "status": "approved", "approved_by": "admin" }
```

---

### POST `/governance/reject`

Reject a pending governance request.

**Auth:** `require_admin`

**Request** (`RejectRequest`):
| Field | Type | Required |
|-------|------|----------|
| `request_id` | `str` | ✓ |
| `rejected_by` | `str` | |
| `reason` | `str` | |

---

### GET `/governance/queue`

List all governance requests.

**Auth:** `require_user`

| Query | Type |
|-------|------|
| `status` | `str` |

**Response** (`200`):
```json
{ "requests": [...], "total": 5, "filter": "all" }
```

---

### GET `/governance/queue/pending`

List all pending approval requests.

**Auth:** `require_user`

---

### GET `/governance/audit`

Return the governance audit trail.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `page` | `int` | `1` |
| `page_size` | `int` | `50` |
| `risk_level` | `str` | |
| `outcome` | `str` | |
| `agent` | `str` | |

---

### GET `/governance/audit/summary`

Aggregated governance statistics.

**Auth:** `require_user`

---

### GET `/governance/audit/{execution_id}`

All audit entries for a specific execution.

**Auth:** `require_user`

---

### POST `/governance/emergency-stop`

Activate global emergency stop — halts all running agents.

**Auth:** `require_admin`

**Request** (`EmergencyStopRequest`):
| Field | Type | Default |
|-------|------|---------|
| `reason` | `str` | `"Operator emergency stop"` |
| `stopped_by` | `str` | `"operator"` |

---

### POST `/governance/emergency-stop/deactivate`

Lift the global emergency stop.

**Auth:** `require_admin`

---

### POST `/governance/stop-mission`

Stop a specific mission execution.

**Auth:** `require_admin`

**Request** (`StopMissionRequest`):
| Field | Type | Required |
|-------|------|----------|
| `execution_id` | `str` | ✓ |
| `reason` | `str` | |
| `stopped_by` | `str` | |

---

### POST `/governance/stop-browser`

Stop all active browser agent sessions.

**Auth:** `require_admin`

**Request:** `EmergencyStopRequest`

---

### POST `/governance/stop-computer`

Stop all active computer agent missions.

**Auth:** `require_admin`

**Request:** `EmergencyStopRequest`

---

### GET `/governance/stop-status`

Current emergency stop status.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "globally_stopped": false, "stopped_missions": [], "stopped_at": null }
```

---

### POST `/governance/safety/assess`

Assess an action for risk level without executing it.

**Auth:** `require_user`

**Request** (`SafetyAssessRequest`):
| Field | Type | Required |
|-------|------|----------|
| `action` | `str` | ✓ |
| `target` | `str` | |
| `agent` | `str` | |
| `context` | `str` | |

**Response** (`200`): Assessment dict with risk level.

---

### GET `/governance/health`

Governance system health check.

**Auth:** none

**Response** (`200`):
```json
{ "status": "online", "global_stop": false, "pending_approvals": 2, "audit_summary": {...} }
```

---

## 10. Governance Center – `/api/governance-center`

### GET `/api/governance-center/overview`

Live safety pipeline state + top-line compliance summary.

**Auth:** `require_user`

**Response** (`OverviewResponse`):
```json
{
  "pipeline": [...],
  "active_missions": 3,
  "blocked_today": 1,
  "approved_today": 12,
  "guardrail_hits": 2,
  "emergency_stop": false,
  "compliance_score": 92.5
}
```

---

### GET `/api/governance-center/risk`

Risk distribution across time windows + 30-day series.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `window` | `str` | `"30d"` |

**Response** (`RiskResponse`):
```json
{
  "today": { "label": "Today", "low": 5, "medium": 2, "high": 1, "critical": 0, "total": 8, "timestamp": "..." },
  "seven_day": {...},
  "thirty_day": {...},
  "series": [...]
}
```

---

### GET `/api/governance-center/events`

Unified event feed: tool approvals + guardrail violations + memory decisions.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `limit` | `int` | `50` |
| `event_type` | `str` | |
| `decision` | `str` | |

---

### GET `/api/governance-center/compliance`

Compliance score breakdown.

**Auth:** `require_user`

**Response** (`ComplianceResponse`):
```json
{
  "overall": 88.3,
  "grade": "B+",
  "categories": [
    { "label": "Safety Score", "score": 91.2, "trend": 0.62, "details": [...] }
  ],
  "updated_at": "..."
}
```

---

### GET `/api/governance-center/replay/{exec_id}`

Governance-filtered replay for a specific mission execution.

**Auth:** `require_user`

---

## 11. Executive – `/api/executive`

### GET `/api/executive/snapshot`

Full platform state snapshot aggregating all subsystems.

**Auth:** `require_user`

**Response** (`SnapshotResponse`):
```json
{
  "timestamp": "...",
  "system_status": "online",
  "active_missions": 2,
  "active_voice": 0,
  "active_agents": 3,
  "total_memories": 4500,
  "safety_score": 92.5,
  "llm_provider": "OpenAI",
  "current_mission": {...},
  "agents": [...],
  "subsystems": [...],
  "health_matrix": [...],
  "autonomy": [...],
  "autonomy_overall": 85.2,
  "ws_connected": true,
  "uptime_hours": 72.5
}
```

---

### GET `/api/executive/analytics`

7-day analytics series derived from audit logs + memory tables.

**Auth:** `require_user`

**Response** (`AnalyticsResponse`):
```json
{
  "series": [
    { "date": "Mon", "missions": 5, "agent_events": 20, "memory_ops": 15, "voice_sessions": 0, "governance_events": 2, "tool_calls": 8 }
  ],
  "totals": { "missions": 35, "agent_events": 140, "memory_ops": 105, ... }
}
```

---

## 12. Approval Center – `/api/approval-center`

### GET `/api/approval-center/policies`

List all approval policies.

**Auth:** `require_user`

---

### GET `/api/approval-center/policies/{policy_id}`

Get a specific approval policy.

**Auth:** `require_user`

---

### GET `/api/approval-center/workflows`

List approval workflows, optionally filtered by status.

**Auth:** `require_user`

| Query | Type |
|-------|------|
| `status` | `str` |

---

### GET `/api/approval-center/workflows/{workflow_id}`

Get detailed approval workflow state.

**Auth:** `require_user`

---

### POST `/api/approval-center/workflows`

Create a new approval workflow for a mission.

**Auth:** `require_user`

**Request Parameters:**
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `execution_id` | `str` | ✓ | |
| `mission_id` | `str` | ✓ | |
| `objective` | `str` | ✓ | |
| `risk_level` | `str` | | `"medium"` |
| `policy_id` | `str` | | |
| `target_environment` | `str` | | |
| `affected_systems` | `list[str]` | | |
| `needs_browser` | `bool` | | `false` |
| `needs_voice` | `bool` | | `false` |

**Response** (`200`):
```json
{ "status": "created", "workflow": {...}, "risk_adjusted": null }
```

---

### POST `/api/approval-center/workflows/{workflow_id}/approve`

Approve the current step of an approval workflow.

**Auth:** `require_user`

**Request Parameters:**
| Field | Type | Required |
|-------|------|----------|
| `approver` | `str` | ✓ |
| `role` | `str` | ✓ |
| `reason` | `str` | |

---

### POST `/api/approval-center/workflows/{workflow_id}/reject`

Reject the current step of an approval workflow.

**Auth:** `require_user`

---

### POST `/api/approval-center/workflows/{workflow_id}/delegate`

Delegate current approval step to another user.

**Auth:** `require_user`

---

### POST `/api/approval-center/workflows/{workflow_id}/break-glass`

Activate emergency break-glass override for a workflow.

**Auth:** `require_user`

---

### GET `/api/approval-center/delegations`

List all active approval delegations.

**Auth:** `require_user`

---

### GET `/api/approval-center/break-glass`

List all break-glass emergency override records.

**Auth:** `require_user`

---

### GET `/api/approval-center/summary`

Approval center summary statistics.

**Auth:** `require_user`

---

### GET `/api/approval-center/analytics`

Approval workflow analytics including timing and risk distribution.

**Auth:** `require_user`

---

## 13. Security Center – `/api/security`

### GET `/api/security/users`

List users.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `active_only` | `bool` | `true` |

---

### GET `/api/security/users/{user_id}`

Get user by ID.

**Auth:** `require_user`

---

### POST `/api/security/users`

Create a user.

**Auth:** `require_user`

**Request Parameters:**
| Field | Type | Required |
|-------|------|----------|
| `username` | `str` | ✓ |
| `email` | `str` | ✓ |
| `display_name` | `str` | ✓ |
| `role_ids` | `list[str]` | |
| `organization_id` | `str` | |

---

### POST `/api/security/users/{user_id}/deactivate`

Deactivate a user.

**Auth:** `require_user`

---

### GET `/api/security/roles`

List roles.

**Auth:** `require_user`

---

### GET `/api/security/roles/{role_id}`

Get role by ID.

**Auth:** `require_user`

---

### POST `/api/security/roles`

Create a role.

**Auth:** `require_user`

**Request Parameters:**
| Field | Type | Required |
|-------|------|----------|
| `name` | `str` | ✓ |
| `description` | `str` | ✓ |
| `parent_role_id` | `str` | |
| `permissions` | `list[dict]` | |

---

### POST `/api/security/users/{user_id}/roles/{role_id}`

Assign a role to a user.

**Auth:** `require_user`

---

### DELETE `/api/security/users/{user_id}/roles/{role_id}`

Remove a role from a user.

**Auth:** `require_user`

---

### GET `/api/security/groups`

List groups.

**Auth:** `require_user`

---

### POST `/api/security/groups`

Create a group.

**Auth:** `require_user`

**Request Parameters:**
| Field | Type | Required |
|-------|------|----------|
| `name` | `str` | ✓ |
| `description` | `str` | ✓ |
| `organization_id` | `str` | |
| `role_ids` | `list[str]` | |

---

### POST `/api/security/groups/{group_id}/members/{user_id}`

Add user to group.

**Auth:** `require_user`

---

### DELETE `/api/security/groups/{group_id}/members/{user_id}`

Remove user from group.

**Auth:** `require_user`

---

### GET `/api/security/organizations`

List organizations.

**Auth:** `require_user`

---

### POST `/api/security/organizations`

Create an organization.

**Auth:** `require_user`

**Request Parameters:**
| Field | Type | Required |
|-------|------|----------|
| `name` | `str` | ✓ |
| `domain` | `str` | |

---

### GET `/api/security/api-keys`

List API keys.

**Auth:** `require_user`

| Query | Type |
|-------|------|
| `user_id` | `str` |

---

### POST `/api/security/api-keys`

Create an API key.

**Auth:** `require_user`

**Request Parameters:**
| Field | Type | Required |
|-------|------|----------|
| `name` | `str` | ✓ |
| `user_id` | `str` | ✓ |
| `role_ids` | `list[str]` | |

**Response** (`200`):
```json
{ "status": "created", "api_key": {...}, "raw_key": "sk-...", "warning": "Store this key securely..." }
```

---

### POST `/api/security/api-keys/{key_id}/revoke`

Revoke an API key.

**Auth:** `require_user`

---

### POST `/api/security/api-keys/{key_id}/rotate`

Rotate an API key (returns new key).

**Auth:** `require_user`

---

### GET `/api/security/service-identities`

List service identities.

**Auth:** `require_user`

---

### POST `/api/security/service-identities`

Create a service identity.

**Auth:** `require_user`

---

### GET `/api/security/secrets`

List registered secrets.

**Auth:** `require_user`

---

### POST `/api/security/secrets`

Register a secret.

**Auth:** `require_user`

**Request Parameters:**
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `name` | `str` | ✓ | |
| `provider` | `str` | | `"env"` |
| `provider_path` | `str` | | |
| `description` | `str` | | |
| `rotation_days` | `int` | | `90` |

---

### GET `/api/security/auth-providers`

List configured auth providers.

**Auth:** `require_user`

---

### GET `/api/security/auth/oauth2/login`

Get OAuth 2.0 authorization URL.

**Auth:** `require_user`

| Query | Type |
|-------|------|
| `state` | `str` |

---

### POST `/api/security/auth/oauth2/callback`

Exchange OAuth 2.0 code for user info.

**Auth:** `require_user`

**Request Parameters:**
| Field | Type |
|-------|------|
| `code` | `str` |
| `redirect_uri` | `str` |

---

### GET `/api/security/auth/oidc/login`

Get OpenID Connect authorization URL.

**Auth:** `require_user`

---

### POST `/api/security/auth/oidc/callback`

Exchange OIDC code for user info.

**Auth:** `require_user`

---

### GET `/api/security/auth/saml/login`

Get SAML 2.0 SSO URL.

**Auth:** `require_user`

---

### POST `/api/security/auth/saml/callback`

Process SAML response.

**Auth:** `require_user`

---

### POST `/api/security/access/check`

Check if a user has permission for a resource/action.

**Auth:** `require_user`

**Request Parameters:**
| Field | Type | Required |
|-------|------|----------|
| `user_id` | `str` | ✓ |
| `resource_type` | `str` | ✓ |
| `action` | `str` | ✓ |
| `resource_id` | `str` | |

**Response** (`200`):
```json
{ "allowed": true, "user_id": "...", "resource_type": "system", "action": "read", "resource_id": null }
```

---

### GET `/api/security/access/effective-permissions/{user_id}`

Get effective permissions for a user.

**Auth:** `require_user`

---

### GET `/api/security/status`

Overall security system status.

**Auth:** `require_user`

---

## 14. Connectors – `/api/connectors`

### GET `/api/connectors`

List all connectors with their health summary.

**Auth:** `require_user`

**Response** (`200`):
```json
{
  "connectors": [
    {
      "type": "github",
      "name": "GitHub",
      "status": "connected",
      "health": { "status": "available" },
      "authentication_type": "token",
      "capabilities": ["Repositories", "Pull Requests", "Issues", "Actions"],
      "operations": [...],
      "connection_state": "connected",
      "has_credentials": true,
      "last_validation": null,
      "latency_ms": null
    }
  ],
  "total": 8
}
```

---

### GET `/api/connectors/{connector_type}`

Get detailed connector info including auth fields and permissions.

**Auth:** `require_user`

**Errors:** `404` – Connector not found

---

### POST `/api/connectors/{connector_type}/test`

Test connector credentials (no persist).

**Auth:** `require_user`

**Request** (`TestCredentialsRequest`):
| Field | Type | Required |
|-------|------|----------|
| `credentials` | `dict[str,str]` | ✓ |

**Response** (`200`):
```json
{ "success": true, "message": "Authentication successful", "latency_ms": 234 }
```

---

### POST `/api/connectors/{connector_type}/connect`

Validate, persist, and initialize a connector.

**Auth:** `require_user`

**Request** (`ConnectRequest`):
| Field | Type | Required |
|-------|------|----------|
| `credentials` | `dict[str,str]` | ✓ |

**Response** (`200`):
```json
{ "success": true, "status": "connected", "health": {...}, "message": "GitHub connected successfully", "latency_ms": 312 }
```

---

### POST `/api/connectors/{connector_type}/disconnect`

Shutdown and remove a connector.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "success": true, "message": "GitHub disconnected" }
```

---

### POST `/api/connectors/{connector_type}/refresh`

Force refresh connector health.

**Auth:** `require_user`

---

### GET `/api/connectors/{connector_type}/health`

Get detailed connector health.

**Auth:** `require_user`

**Response** (`200`):
```json
{
  "status": "healthy",
  "connector": "github",
  "name": "GitHub",
  "authenticated": true,
  "authentication_type": "token",
  "latency_ms": null,
  "version": null,
  "rate_limits": null,
  "last_sync": null,
  "available_operations": [...],
  "connection_state": "connected",
  "capabilities": [...]
}
```

---

## 15. Connector Activity – `/api/connectors/activity`

### GET `/api/connectors/activity`

List/search connector activity with filtering.

**Auth:** `require_user`

| Query | Type | Description |
|-------|------|-------------|
| `connector` | `str` | Filter by connector_name |
| `connector_type` | `str` | Filter by type |
| `operation` | `str` | Filter by operation |
| `status` | `str` | Filter by status |
| `initiated_by` | `str` | |
| `start_date` | `datetime` | ISO-8601 |
| `end_date` | `datetime` | ISO-8601 |
| `query` | `str` | Search across fields |
| `sort_by` | `str` | Default `"created_at"` |
| `sort_dir` | `str` | `"asc"` or `"desc"` |
| `page` | `int` | Default `1` |
| `page_size` | `int` | Default `50` |

---

### GET `/api/connectors/activity/{activity_id}`

Get specific connector activity entry.

**Auth:** `require_user`

---

### POST `/api/connectors/activity`

Record a connector activity entry.

**Auth:** `require_user`

**Request** (`ConnectorActivityCreate`):
| Field | Type | Required |
|-------|------|----------|
| `connector_name` | `str` | ✓ |
| `connector_type` | `str` | ✓ |
| `operation` | `str` | ✓ |
| `resource` | `str` | |
| `resource_id` | `str` | |
| `status` | `str` | |
| `initiated_by` | `str` | |
| `duration_ms` | `int` | |
| `request_id` | `uuid` | |
| `correlation_id` | `uuid` | |
| `message` | `str` | |
| `metadata` | `dict` | |

**Response** (`201`):
```json
{ "activity": {...} }
```

---

## 16. Organizations – `/api/organizations`

### GET `/api/organizations`

List/search organizations.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `query` | `str` | |
| `is_active` | `bool` | |
| `domain` | `str` | |
| `sort_by` | `str` | `"created_at"` |
| `sort_dir` | `str` | `"desc"` |
| `limit` | `int` | `50` |
| `offset` | `int` | `0` |

---

### GET `/api/organizations/{org_id}`

Get organization by ID.

**Auth:** `require_user`

---

### POST `/api/organizations`

Create organization.

**Auth:** `require_user`

**Request** (`OrganizationCreate`):
| Field | Type | Required |
|-------|------|----------|
| `name` | `str` | ✓ |
| `domain` | `str` | |
| `description` | `str` | |
| `is_active` | `bool` | (default `true`) |
| `metadata` | `dict` | |

**Response** (`201`):
```json
{ "organization": {...} }
```

---

### PUT `/api/organizations/{org_id}`

Update organization.

**Auth:** `require_user`

**Request** (`OrganizationUpdate`): All fields optional.

---

### DELETE `/api/organizations/{org_id}`

Delete organization.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "status": "deleted" }
```

---

## 17. Departments – `/api/departments`

### GET `/api/departments`

List/search departments.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `query` | `str` | |
| `is_active` | `bool` | |
| `organization_id` | `uuid` | |
| `limit` | `int` | `50` |
| `offset` | `int` | `0` |

---

### GET `/api/departments/{dept_id}`

Get department by ID.

**Auth:** `require_user`

---

### POST `/api/departments`

Create department.

**Auth:** `require_user`

**Request** (`DepartmentCreate`):
| Field | Type | Required |
|-------|------|----------|
| `name` | `str` | ✓ |
| `organization_id` | `uuid` | ✓ |
| `description` | `str` | |
| `is_active` | `bool` | |
| `metadata` | `dict` | |

---

### PUT `/api/departments/{dept_id}`

Update department.

**Auth:** `require_user`

---

### DELETE `/api/departments/{dept_id}`

Delete department.

**Auth:** `require_user`

---

## 18. Projects – `/api/projects`

### GET `/api/projects`

List/search projects.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `query` | `str` | |
| `status` | `str` | |
| `organization_id` | `uuid` | |
| `department_id` | `uuid` | |
| `owner` | `str` | |
| `sort_by` | `str` | `"created_at"` |
| `sort_dir` | `str` | `"desc"` |
| `page` | `int` | `1` |
| `page_size` | `int` | `50` |

---

### GET `/api/projects/{project_id}`

Get project by ID.

**Auth:** `require_user`

---

### POST `/api/projects`

Create project.

**Auth:** `require_user`

**Request** (`ProjectCreate`):
| Field | Type | Required |
|-------|------|----------|
| `name` | `str` | ✓ |
| `key` | `str` | ✓ |
| `organization_id` | `uuid` | ✓ |
| `department_id` | `uuid` | |
| `description` | `str` | |
| `status` | `str` | (default `"active"`) |
| `owner` | `str` | |
| `tags` | `list[str]` | |
| `metadata` | `dict` | |

---

### PUT `/api/projects/{project_id}`

Update project.

**Auth:** `require_user`

---

### DELETE `/api/projects/{project_id}`

Delete project.

**Auth:** `require_user`

---

## 19. Enterprise Replay – `/api/enterprise-replay`

### GET `/api/enterprise-replay/mission/{execution_id}`

Full mission replay with timeline, stages, duration, metrics, cost, outcome.

**Auth:** `require_user`

**Response** (`200`):
```json
{
  "execution_id": "uuid",
  "found": true,
  "status": "completed",
  "stages": [...],
  "stage_events": [...],
  "events": [...],
  "metrics": { "total_events": 45, "duration_ms": 12000, ... },
  "cost": { "total_cost": 0.05, "entries": [...] },
  "outcome": { "is_complete": true, "total_events": 45, "agents": ["planner", "research"] }
}
```

---

### GET `/api/enterprise-replay/workers/{execution_id}`

Worker replay — browser, voice, desktop actions.

**Auth:** `require_user`

---

### GET `/api/enterprise-replay/connectors/{execution_id}`

Connector replay — all external service interactions.

**Auth:** `require_user`

---

### GET `/api/enterprise-replay/decisions/{execution_id}`

Decision explorer — reasoning chain, LLM requests, validation, governance.

**Auth:** `require_user`

---

### GET `/api/enterprise-replay/memory/{execution_id}`

Memory replay — working, semantic, episodic memory changes.

**Auth:** `require_user`

---

### GET `/api/enterprise-replay/knowledge-graph/{execution_id}`

Knowledge graph replay — entity/relationship creation, graph evolution.

**Auth:** `require_user`

---

### GET `/api/enterprise-replay/costs/{execution_id}`

Cost replay — LLM tokens, model usage, worker/mission/connector costs.

**Auth:** `require_user`

---

### GET `/api/enterprise-replay/events/{execution_id}`

Event explorer — every event published through EventBus.

**Auth:** `require_user`

---

### GET `/api/enterprise-replay/timeline/{execution_id}`

Timeline explorer — chronological execution with zoom/filter support.

**Auth:** `require_user`

| Query | Type |
|-------|------|
| `zoom` | `str` |
| `agent` | `str` |
| `event_type` | `str` |

---

### GET `/api/enterprise-replay/execution-graph/{execution_id}`

Execution graph — Mission → Workers → Connectors → Memory → Knowledge Graph → Approvals → Completion.

**Auth:** `require_user`

---

### GET `/api/enterprise-replay/export/{execution_id}`

Export replay data in various formats.

**Auth:** `require_user`

| Query | Type | Default | Description |
|-------|------|---------|-------------|
| `format` | `str` | `"json"` | `json`, `markdown`, `timeline`, or `replay-package` |

---

## 20. Mission Replay – `/api/mission-replay`

### GET `/api/mission-replay/{execution_id}`

Return complete replay data (summary + all events) for a mission execution.

**Auth:** `require_user`

**Response** (`200`, `ReplayFullSchema`):
```json
{
  "summary": { "execution_id": "uuid", "found": true, "total_events": 45, "event_counts": {...}, "agents": [...], "duration_ms": 12000, "is_complete": true },
  "events": [
    {
      "event_id": "evt-1",
      "execution_id": "uuid",
      "sequence": 0,
      "event_type": "mission_started",
      "agent": "orchestrator",
      "status": "completed",
      "message": "Mission started",
      "timestamp": "...",
      "offset_ms": 0,
      "latency_ms": null,
      "phase": null,
      "confidence_score": null,
      "token_usage": null,
      "payload": {}
    }
  ]
}
```

---

### GET `/api/mission-replay/{execution_id}/timeline`

Lightweight ordered timeline with filter support.

**Auth:** `require_user`

| Query | Type |
|-------|------|
| `agent` | `str` |
| `event_type` | `str` |

---

### GET `/api/mission-replay/{execution_id}/graph`

Per-step agent-state graph for replay animation.

**Auth:** `require_user`

**Response** (`ReplayGraphSchema`):
```json
{
  "execution_id": "uuid",
  "total_steps": 10,
  "steps": [
    { "sequence": 0, "event_type": "mission_started", "agent": "orchestrator", "message": "...", "timestamp": "...", "agent_states": {"orchestrator": "running"} }
  ],
  "final_states": { "orchestrator": "completed" }
}
```

---

### GET `/api/mission-replay/`

List recent execution IDs that have replay data.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `limit` | `int` | `20` |

**Response** (`200`):
```json
{ "executions": ["uuid-1", "uuid-2"], "count": 2 }
```

---

## 21. Mission Library – `/api/mission-library`

### GET `/api/mission-library/missions`

List all available enterprise mission definitions.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "missions": [...], "total": 15 }
```

---

### GET `/api/mission-library/missions/{mission_id}`

Get detailed definition for a specific mission.

**Auth:** `require_user`

---

### POST `/api/mission-library/missions/{mission_id}/execute`

Execute an enterprise mission by ID.

**Auth:** `require_user`

**Request Parameters:**
| Field | Type |
|-------|------|
| `session_id` | `str` |
| `workspace_id` | `str` |
| `params` | `dict` |

**Response** (`200`):
```json
{
  "status": "completed",
  "mission_id": "research-summarize",
  "execution_id": "uuid",
  "result": {
    "status": "completed",
    "confidence_score": 0.95,
    "response_length": 2048,
    "stages_completed": 4,
    "worker_invocations": 2,
    "total_tokens": 1500,
    "duration_seconds": 12.5,
    "error": null
  }
}
```

---

### GET `/api/mission-library/running`

List currently executing missions.

**Auth:** `require_user`

---

## 22. Research – `/api/research`

### POST `/api/research/search`

Run a full live research pipeline: Tavily → ranking → citation → LLM synthesis.

**Auth:** `require_user`

**Request** (`ResearchRequest`):
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `query` | `str` | ✓ | |
| `mission_id` | `str` | | |
| `agent` | `str` | | `"research"` |
| `force_live` | `bool` | | `true` |
| `top_k` | `int` | | `6` |

**Response** (`200`):
```json
{
  "query": "AI trends",
  "response": "## AI Trends\n... [1] ...",
  "sources": [...],
  "citations": [...],
  "source_count": 6,
  "latency_ms": 3200,
  "success": true
}
```

---

### POST `/api/research/news`

News-focused search with recency bias.

**Auth:** `require_user`

**Request** (`NewsRequest`):
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `query` | `str` | ✓ | |
| `days` | `int` | | `7` |
| `mission_id` | `str` | | |

---

### POST `/api/research/domain`

Domain-restricted search (e.g. arxiv.org, github.com).

**Auth:** `require_user`

**Request** (`DomainRequest`):
| Field | Type | Required |
|-------|------|----------|
| `query` | `str` | ✓ |
| `include_domains` | `list[str]` | ✓ |
| `mission_id` | `str` | |

---

### GET `/api/research/history`

Return recent search history from telemetry.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `limit` | `int` | `20` |

---

## 23. Computer Agent – `/computer`

### POST `/computer/execute-workflow`

Submit a multi-step computer-use workflow.

**Auth:** `require_user`

**Request** (`WorkflowRequest`):
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `mission_name` | `str` | | Max 256 chars |
| `steps` | `list[WorkflowStep]` | ✓ | |

**WorkflowStep:**
| Field | Type | Description |
|-------|------|-------------|
| `action` | `str` | `open_website`, `google_search`, `click`, `type`, `hotkey`, `wait`, `analyze_screen` |
| `url` | `str` | |
| `query` | `str` | |
| `selector` | `str` | |
| `text` | `str` | |
| `target` | `str` | |
| `keys` | `list[str]` | |
| `seconds` | `float` | |

---

### GET `/computer/status`

Computer Agent health and active mission count.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "status": "online", "active_missions": 1, "active_mission_ids": ["uuid"] }
```

---

### GET `/computer/tasks`

Full list of active missions and recent completed tasks.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "active_tasks": [...], "completed_tasks": [...], "total_completed": 10 }
```

---

## 24. Operator – `/operator`

### GET `/operator/health`

Operator system health and capability probe.

**Auth:** none

**Response** (`200`):
```json
{
  "status": "ok",
  "capabilities": { "screen_capture": true, "ocr": true, "vision_llm": true, "computer_input": true },
  "active_missions": 0
}
```

---

### GET `/operator/monitors`

List all available monitors/displays.

**Auth:** `require_user`

---

### GET `/operator/screen/current`

Return the most recently captured snapshot without re-capturing.

**Auth:** `require_user`

**Errors:** `404` – No snapshot captured yet

---

### POST `/operator/screen/capture`

Trigger a fresh screen capture.

**Auth:** `require_user`

**Request** (`CaptureRequest`):
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `monitor` | `int` | | `0` |
| `run_ocr` | `bool` | | `true` |
| `detect_ui` | `bool` | | `true` |

---

### GET `/operator/active-missions`

Return all currently executing autonomous missions.

**Auth:** `require_user`

---

### POST `/operator/execute`

Submit a new autonomous mission. Runs synchronously.

**Auth:** `require_admin`

**Request** (`ExecuteMissionRequest`):
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `goal` | `str` | ✓ | |
| `execution_id` | `str` | | |
| `session_id` | `str` | | |
| `success_text` | `str` | | |
| `max_iterations` | `int` | | `30` |
| `use_vision` | `bool` | | `true` |

---

### GET `/operator/missions/{execution_id}`

Check if a mission is active.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "execution_id": "uuid", "status": "running", ... }
```

---

## 25. Workspace – `/api/workspace`

### POST `/api/workspace/`

Create a new workspace.

**Auth:** `require_user`

**Request** (`CreateWorkspaceRequest`):
| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | `str` | ✓ | 1–200 chars |
| `description` | `str` | | Max 1000 chars |

**Response** (`201`): Workspace object.

---

### GET `/api/workspace/`

List all workspaces.

**Auth:** `require_user`

---

### GET `/api/workspace/{ws_id}`

Get workspace by ID.

**Auth:** `require_user`

**Errors:** `404` – Not found

---

### DELETE `/api/workspace/{ws_id}`

Delete workspace.

**Auth:** `require_user`

**Response:** `204 No Content`

---

### POST `/api/workspace/{ws_id}/upload`

Upload and ingest a document into the workspace.

**Auth:** `require_user`

| Field | Type | Description |
|-------|------|-------------|
| `file` | `UploadFile` | Multipart file upload |

Allowed extensions: `pdf, docx, txt, md, pptx, png, jpg, jpeg, gif, webp, bmp, tiff`. Max file size: 50 MB.

**Response** (`201`):
```json
{ "id": "uuid", "filename": "doc.pdf", "total_chunks": 12, "total_pages": 5, "message": "Ingested 12 chunks from 5 pages", ... }
```

---

### GET `/api/workspace/{ws_id}/documents`

List documents in a workspace.

**Auth:** `require_user`

---

### DELETE `/api/workspace/{ws_id}/documents/{doc_id}`

Delete a document.

**Auth:** `require_user`

**Response:** `204 No Content`

---

### GET `/api/workspace/{ws_id}/documents/{doc_id}/chunks`

View document chunks.

**Auth:** `require_user`

---

### POST `/api/workspace/{ws_id}/search`

Semantic search over workspace documents.

**Auth:** `require_user`

**Request** (`SearchRequest`):
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `query` | `str` | ✓ | |
| `n_chunks` | `int` | | `8` |

---

### POST `/api/workspace/{ws_id}/chat`

RAG chat against workspace documents.

**Auth:** `require_user`

**Request** (`WorkspaceChatRequest`):
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `query` | `str` | ✓ | |
| `session_id` | `str` | | |
| `n_chunks` | `int` | | `6` |
| `model` | `str` | | |

**Response** (`200`):
```json
{
  "answer": "Based on the document...",
  "citations": [{"citation_id": "[AB12]", "filename": "doc.pdf", "page_number": 3, ...}],
  "chunks_used": 4,
  "model_used": "gpt-4"
}
```

---

## 26. System Health – `/health/system`

### GET `/health/system`

Aggregated system health — fans out to all subsystems concurrently.

**Auth:** none

**Response** (`200`):
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "build_hash": null,
  "uptime_sec": 12345.6,
  "started_at": "2025-01-01T00:00:00",
  "environment": "development",
  "components": {
    "auth": { "status": "healthy", "latency_ms": 2.1, "detail": {...} },
    "database": { "status": "healthy", "latency_ms": 3.2, "detail": {...} },
    "llm": { "status": "healthy", "latency_ms": 150.0, "detail": {...} },
    "redis": { "status": "healthy", "latency_ms": 0.5, "detail": {} },
    "postgres": { "status": "healthy", "latency_ms": 1.2, "detail": {...} },
    "request_tracing": { "status": "healthy", "latency_ms": 0.1, "detail": {...} },
    "exception_handler": { "status": "healthy", ... },
    "sentry": { "status": "healthy", ... }
  }
}
```

---

## 27. LLM Health – `/health/llm`

### GET `/health/llm`

Per-provider status, latency, availability.

**Auth:** none

**Response** (`200`):
```json
{
  "status": "ok",
  "global_error_rate": 0.0,
  "global_fallback_count": 0,
  "providers": {
    "azure": { "availability": "available", "call_count": 100, "avg_latency_ms": 450, ... },
    "openai": { "availability": "available", ... },
    "claude": { "availability": "not_configured", ... },
    "gemini": { "availability": "not_configured", ... },
    "ollama": { "availability": "not_configured", ... }
  }
}
```

---

### GET `/health/llm/telemetry`

Full telemetry snapshot including recent requests.

**Auth:** `require_user`

---

### POST `/health/llm/reset`

Reset telemetry counters and circuit-breaker state.

**Auth:** `require_admin`

**Request** (`ResetRequest`):
| Field | Type | Description |
|-------|------|-------------|
| `provider` | `str` | One of: `azure`, `openai`, `claude`, `gemini`, `ollama`, or `null` for all |

**Response** (`200`):
```json
{ "reset": "all", "status": "ok" }
```

---

## 28. Metrics – `/metrics`

### GET `/metrics`

Prometheus scrape endpoint.

**Auth:** none

**Response** (`200`): `text/plain; version=0.0.4`

```text
# HELP cortex_http_requests_total Total HTTP requests
# TYPE cortex_http_requests_total counter
cortex_http_requests_total{method="GET",path="/api/auth/health",status="200"} 42
...
```

---

## 29. Costs – `/api/costs`

### GET `/api/costs/summary`

Executive cost summary — today, this month, top missions, trends.

**Auth:** `require_user`

---

### GET `/api/costs/daily`

Daily cost totals for the last N days.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `days` | `int` | `30` |

---

### GET `/api/costs/providers`

Provider cost breakdown for the last N days.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `days` | `int` | `30` |

---

### GET `/api/costs/mission/{mission_id}`

Total cost and provider breakdown for a specific mission.

**Auth:** `require_user`

---

### GET `/api/costs/user/{user_id}`

Cost breakdown for a specific user.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `days` | `int` | `30` |

---

## 30. Audit – `/api/audit`

### GET `/api/audit`

List/search enterprise audit entries.

**Auth:** `require_user`

| Query | Type | Description |
|-------|------|-------------|
| `category` | `str` | Filter by agent/category |
| `actor` | `str` | Filter by user_id/actor |
| `status` | `str` | Filter by outcome (`allowed`, `blocked`, `approved`, `rejected`, `pending`, `started`, `completed`, `failed`, `stopped`) |
| `severity` | `str` | Filter by risk_level (`low`, `medium`, `high`, `critical`) |
| `resource_type` | `str` | |
| `resource_id` | `str` | Exact execution_id |
| `start_date` | `datetime` | ISO-8601 |
| `end_date` | `datetime` | ISO-8601 |
| `query` | `str` | Search across action, reason, agent, user_id, execution_id |
| `sort_by` | `str` | Default `"created_at"` |
| `sort_dir` | `str` | `"asc"` or `"desc"` |
| `page` | `int` | Default `1` |
| `page_size` | `int` | Default `50` |

**Response** (`200`):
```json
{ "entries": [...], "total": 100, "page": 1, "page_size": 50 }
```

---

### GET `/api/audit/{entry_id}`

Get a specific audit entry.

**Auth:** `require_user`

---

## 31. Telemetry – `/api/telemetry`

### GET `/api/telemetry/runtime`

Current runtime state: active executions, agent states, history.

**Auth:** `require_user`

**Response** (`200`):
```json
{
  "timestamp": "...",
  "active_executions": 2,
  "active_agents": 3,
  "total_completed": 45,
  "total_failed": 2,
  "agents": { "orchestrator": "running", "planner": "idle" },
  "recent_executions": [...],
  "queue_depth": 2
}
```

---

### GET `/api/telemetry/health`

Lightweight health endpoint.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "status": "operational", "timestamp": "..." }
```

---

## 32. RabbitMQ – `/api/rabbitmq`

### GET `/api/rabbitmq/health`

RabbitMQ connection status.

**Auth:** `require_user`

**Response** (`200`):
```json
{ "status": "connected", "available": true, "trace_stats": {...} }
```

---

### GET `/api/rabbitmq/trace/recent`

Most recent N message trace entries.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `limit` | `int` | `100` |

---

### GET `/api/rabbitmq/trace/stats`

Aggregate publish/consume statistics.

**Auth:** `require_user`

---

### GET `/api/rabbitmq/trace/{exec_id}`

Trace entries for a specific execution.

**Auth:** `require_user`

---

### GET `/api/rabbitmq/dlq`

Non-destructively peek at dead-letter queue messages.

**Auth:** `require_user`

| Query | Type | Default |
|-------|------|---------|
| `limit` | `int` | `50` |

---

### POST `/api/rabbitmq/dlq/replay/{message_id}`

Republish a dead-letter message back to the orchestration exchange.

**Auth:** `require_admin`

---

### DELETE `/api/rabbitmq/dlq`

Purge all messages from the dead-letter queue.

**Auth:** `require_admin`

---

## 33. Graph (Neo4j) – `/api/graph`

### GET `/api/graph/health`

Neo4j connection status and basic graph stats.

**Auth:** none

---

### GET `/api/graph/agents`

List all Agent nodes.

**Auth:** none

---

### GET `/api/graph/agents/{name}`

Get an Agent node by name.

**Auth:** none

---

### POST `/api/graph/agents`

Create or update an Agent node.

**Auth:** none

**Request** (`UpsertAgentRequest`):
| Field | Type | Required |
|-------|------|----------|
| `name` | `str` | ✓ |
| `agent_type` | `str` | ✓ |
| `capabilities` | `list[str]` | |
| `metadata` | `dict` | |

---

### POST `/api/graph/agents/dependency`

Record a DEPENDS_ON edge between two agents.

**Auth:** none

**Request** (`AgentDependencyRequest`):
| Field | Type | Required |
|-------|------|----------|
| `from_agent` | `str` | ✓ |
| `to_agent` | `str` | ✓ |
| `reason` | `str` | |

---

### GET `/api/graph/agents/{name}/context`

Full cognitive context for an agent.

**Auth:** none

---

### GET `/api/graph/agents/{name}/dependencies`

Transitive dependency chain for an agent.

**Auth:** none

| Query | Type | Default |
|-------|------|---------|
| `depth` | `int` | `3` |

---

### GET `/api/graph/agents/{name}/centrality`

Influence context (upstream/downstream) for an agent.

**Auth:** none

---

### GET `/api/graph/agents/graph/full`

Full agent collaboration graph.

**Auth:** none

---

### GET `/api/graph/agents/graph/centrality`

Agents ranked by graph centrality.

**Auth:** none

| Query | Type | Default |
|-------|------|---------|
| `limit` | `int` | `20` |

---

### POST `/api/graph/memories`

Create or update a Memory node.

**Auth:** none

**Request** (`UpsertMemoryRequest`):
| Field | Type | Required |
|-------|------|----------|
| `memory_id` | `str` | ✓ |
| `memory_type` | `str` | ✓ |
| `content` | `str` | ✓ |
| `agent` | `str` | |
| `execution_id` | `str` | |
| `mission_id` | `str` | |
| `metadata` | `dict` | |

---

### GET `/api/graph/memories/{memory_id}`

Get a Memory node.

**Auth:** none

---

### GET `/api/graph/memories/{memory_id}/related`

Memories related to a given memory.

**Auth:** none

| Query | Type | Default |
|-------|------|---------|
| `depth` | `int` | `2` |
| `limit` | `int` | `20` |

---

### GET `/api/graph/memories/{memory_id}/context`

Expand memory into multi-hop context.

**Auth:** none

| Query | Type | Default |
|-------|------|---------|
| `depth` | `int` | `2` |

---

### POST `/api/graph/memories/link`

Create a relationship between two Memory nodes.

**Auth:** none

**Request** (`LinkMemoriesRequest`):
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `source_id` | `str` | ✓ | |
| `target_id` | `str` | ✓ | |
| `rel_type` | `str` | | `"RELATED_TO"` |
| `weight` | `float` | | `1.0` |

---

### GET `/api/graph/memories/search/fts`

Full-text search over memory content.

**Auth:** none

| Query | Type | Required |
|-------|------|----------|
| `q` | `str` | ✓ |
| `limit` | `int` | (default `10`) |

---

### GET `/api/graph/executions/{execution_id}/lineage`

Execution lineage tree.

**Auth:** none

| Query | Type | Default |
|-------|------|---------|
| `depth` | `int` | `5` |

---

### GET `/api/graph/executions/{execution_id}/impact`

Full downstream impact of an execution.

**Auth:** none

| Query | Type | Default |
|-------|------|---------|
| `depth` | `int` | `3` |

---

### GET `/api/graph/executions/{execution_id}/replay`

Complete ordered lineage for replay.

**Auth:** none

---

### GET `/api/graph/executions/recent`

Recent executions.

**Auth:** none

| Query | Type | Default |
|-------|------|---------|
| `limit` | `int` | `20` |
| `status` | `str` | |

---

### GET `/api/graph/missions/{mission_id}`

Execution summary for a mission.

**Auth:** none

---

### POST `/api/graph/cognition/events`

Record a CognitionEvent node.

**Auth:** none

**Request** (`CognitionEventRequest`):
| Field | Type | Required |
|-------|------|----------|
| `event_id` | `str` | ✓ |
| `event_type` | `str` | ✓ |
| `agent` | `str` | ✓ |
| `execution_id` | `str` | |
| `payload_summary` | `str` | |

---

### GET `/api/graph/cognition/events/{event_id}/pipeline`

Downstream cognition pipeline from an event.

**Auth:** none

| Query | Type | Default |
|-------|------|---------|
| `depth` | `int` | `10` |

---

### POST `/api/graph/cognition/reflections`

Record a Reflection node.

**Auth:** none

**Request** (`ReflectionRequest`):
| Field | Type | Required |
|-------|------|----------|
| `reflection_id` | `str` | ✓ |
| `agent` | `str` | ✓ |
| `summary` | `str` | ✓ |
| `execution_id` | `str` | |
| `memory_ids` | `list[str]` | |

---

### GET `/api/graph/cognition/patterns`

Agent collaboration patterns.

**Auth:** none

---

### GET `/api/graph/world-models`

List all WorldModel nodes.

**Auth:** none

---

### POST `/api/graph/world-models`

Create or update a WorldModel node.

**Auth:** none

**Request** (`UpsertWorldModelRequest`):
| Field | Type | Required |
|-------|------|----------|
| `model_id` | `str` | ✓ |
| `name` | `str` | ✓ |
| `domain` | `str` | ✓ |
| `description` | `str` | |

---

### GET `/api/graph/world-models/{model_id}/subgraph`

Full concept graph for a WorldModel.

**Auth:** none

---

### POST `/api/graph/concepts`

Create or update a Concept node.

**Auth:** none

**Request** (`UpsertConceptRequest`):
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `name` | `str` | ✓ | |
| `domain` | `str` | | `"general"` |
| `description` | `str` | | |
| `confidence` | `float` | | `1.0` |

---

### POST `/api/graph/concepts/relate`

Create a semantic relationship between two concepts.

**Auth:** none

**Request** (`RelateConceptsRequest`):
| Field | Type | Required | Default |
|-------|------|----------|---------|
| `concept_a` | `str` | ✓ | |
| `concept_b` | `str` | ✓ | |
| `rel_type` | `str` | | `"RELATED_TO"` |
| `weight` | `float` | | `1.0` |
| `description` | `str` | | |

---

### GET `/api/graph/concepts/{name}/neighborhood`

Semantic neighborhood of a concept.

**Auth:** none

| Query | Type | Default |
|-------|------|---------|
| `depth` | `int` | `2` |
| `limit` | `int` | `30` |

---

### GET `/api/graph/concepts/search`

Full-text search over concepts.

**Auth:** none

| Query | Type | Required |
|-------|------|----------|
| `q` | `str` | ✓ |
| `limit` | `int` | (default `10`) |

---

### GET `/api/graph/context/{agent_name}`

Full cognitive context for an agent (cross-domain).

**Auth:** none

| Query | Type |
|-------|------|
| `execution_id` | `str` |
| `memory_depth` | `int` |

---

### GET `/api/graph/path/agents`

Shortest path(s) between two agents.

**Auth:** none

| Query | Type | Required | Default |
|-------|------|----------|---------|
| `from_agent` | `str` | ✓ | |
| `to_agent` | `str` | ✓ | |
| `max_depth` | `int` | | `6` |

---

## 34. Health Center – `/api/operations/health-center`

> **Retired in Phase 10.29 (ADR-119).** The Health Center (enterprise operations) API/model surface was removed from the repository. Discovery (Phases 10.23, 10.27, 10.28) found no production consumer, no frontend client, no operator workflow and no table on any database; the routes had been mounted at `/api/api/…` since their introduction and answered `UndefinedTableError` on every migration-built database. The historical description is preserved in git history and in `docs/PHASE_10_27_GA_SURFACE_DECISION_DISCOVERY.md`.

## 35. Backup – `/api/operations/backup`

> **Retired in Phase 10.29 (ADR-119).** The enterprise Backup & Restore API/model surface was removed from the repository. Discovery (Phases 10.23, 10.27, 10.28) found no production consumer, no frontend client, no operator workflow and no table on any database; the routes had been mounted at `/api/api/…` since their introduction and answered `UndefinedTableError` on every migration-built database. The historical description is preserved in git history and in `docs/PHASE_10_27_GA_SURFACE_DECISION_DISCOVERY.md`.

GA database backup and disaster recovery are unaffected: `scripts/backup-database.sh` and the Helm `backup-cronjob.yaml` (`pg_dump`, retention, S3 rotation) never used this API — see the Administrator Guide §11 and the Disaster Recovery Runbook §2.

## 36. Maintenance – `/api/operations/maintenance`

> **Retired in Phase 10.29 (ADR-119).** The Maintenance Mode API/model surface was removed from the repository. Discovery (Phases 10.23, 10.27, 10.28) found no production consumer, no frontend client, no operator workflow and no table on any database; the routes had been mounted at `/api/api/…` since their introduction and answered `UndefinedTableError` on every migration-built database. The historical description is preserved in git history and in `docs/PHASE_10_27_GA_SURFACE_DECISION_DISCOVERY.md`.

`should_block_new_mission()` was never called by the mission runtime; maintenance state never affected mission admission (Phase 10.28 census).

## 37. Diagnostics – `/api/operations/diagnostics`

### GET `/api/operations/diagnostics`

Generate and return a full diagnostics report as JSON.

**Auth:** `require_user`

---

### GET `/api/operations/diagnostics/download`

Download diagnostics as a JSON file attachment.

**Auth:** `require_user`

---

## 38. Operational Reports – `/api/operations/reports`

> **Retired in Phase 10.29 (ADR-119).** The Operational Reports API/model surface was removed from the repository. Discovery (Phases 10.23, 10.27, 10.28) found no production consumer, no frontend client, no operator workflow and no table on any database; the routes had been mounted at `/api/api/…` since their introduction and answered `UndefinedTableError` on every migration-built database. The historical description is preserved in git history and in `docs/PHASE_10_27_GA_SURFACE_DECISION_DISCOVERY.md`.

## 39. Root Routes

### GET `/`

System info and agent registry listing.

**Auth:** none

**Response** (`200`):
```json
{
  "system": "CortexPrime",
  "status": "running",
  "architecture": "multi-agent-cognitive-runtime",
  "registered_agents": ["orchestrator", "planner", "research", "critic", "optimizer", "memory"],
  "realtime_streaming": true,
  "runtime_state": "active",
  "version": "1.0.0"
}
```

---

### POST `/api/chat`

Simple LLM chat endpoint.

**Auth:** none

**Request** (`SimpleChatRequest`):
| Field | Type | Required |
|-------|------|----------|
| `message` | `str` | ✓ |

**Response** (`200`):
```json
{ "response": "Hello! How can I help you today?" }
```

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What is CortexPrime?"}'
```

---

## Common Error Codes

| Code | Description |
|------|-------------|
| `400` | Bad request — invalid input |
| `401` | Unauthenticated — missing or invalid token |
| `403` | Forbidden — insufficient role |
| `404` | Resource not found |
| `409` | Conflict — duplicate resource |
| `413` | Payload too large |
| `422` | Unprocessable entity — validation error |
| `429` | Rate limit exceeded |
| `500` | Internal server error |
| `501` | Not implemented — feature not configured |
| `503` | Service temporarily unavailable |

### Error Response Format

All API errors follow a consistent schema:

```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "A descriptive error message.",
    "details": {
      "field": "email",
      "reason": "Must be a valid email address"
    },
    "request_id": "req_abc123"
  }
}
```

---

## WebSocket API

### Connection URL

```
wss://api.cortexprime.example.com/ws?token=<access_token>
```

- **Protocol:** WSS (WebSocket over TLS)
- **Authentication:** Pass your JWT access token as a query parameter
- **Reconnection:** Client should implement exponential backoff reconnection

### Authentication

```javascript
const ws = new WebSocket('wss://api.cortexprime.example.com/ws?token=eyJhbGciOiJIUzI1NiIs...');
```

### Event Types

| Event Type | Direction | Description |
|------------|-----------|-------------|
| `mission.started` | Server→Client | A mission has started execution |
| `mission.progress` | Server→Client | Mission progress update |
| `mission.completed` | Server→Client | Mission completed successfully |
| `mission.failed` | Server→Client | Mission encountered a fatal error |
| `agent.status_change` | Server→Client | Agent status changed (online/offline/error) |
| `agent.log` | Server→Client | Live log line from an agent |
| `decision.made` | Server→Client | A decision was made during execution |
| `memory.updated` | Server→Client | Memory entry was created or updated |
| `notification.alert` | Server→Client | System alert notification |
| `governance.approval_needed` | Server→Client | New approval request pending |

### Subscription Format

Client sends a subscription message to filter which events to receive:

```json
{
  "type": "subscribe",
  "channels": [
    "mission:exec_xyz789",
    "agent:agent_001",
    "notifications:high"
  ]
}
```

To unsubscribe:

```json
{
  "type": "unsubscribe",
  "channels": [
    "mission:exec_xyz789"
  ]
}
```

### Payload Schemas

**mission.progress:**

```json
{
  "type": "mission.progress",
  "timestamp": "2026-07-04T12:00:30Z",
  "data": {
    "execution_id": "exec_xyz789",
    "progress_percent": 45,
    "current_objective": "obj_001",
    "status": "running",
    "elapsed_seconds": 30,
    "estimated_remaining_seconds": 35
  }
}
```

**agent.log:**

```json
{
  "type": "agent.log",
  "timestamp": "2026-07-04T12:00:35Z",
  "data": {
    "agent_id": "agent_001",
    "level": "info",
    "message": "Processing batch 3 of 10",
    "metadata": {
      "batch_id": 3,
      "records": 500
    }
  }
}
```

**decision.made:**

```json
{
  "type": "decision.made",
  "timestamp": "2026-07-04T12:02:00Z",
  "data": {
    "execution_id": "exec_xyz789",
    "decision_id": "dec_001",
    "agent": "analyst-agent-v2",
    "decision_type": "visualization_selection",
    "input_summary": "Timeseries data with 3 dimensions, 1500 records",
    "chosen": "line_chart",
    "confidence": 0.87,
    "alternatives_considered": 2
  }
}
```

**notification.alert:**

```json
{
  "type": "notification.alert",
  "timestamp": "2026-07-04T12:05:00Z",
  "data": {
    "notification_id": "notif_001",
    "severity": "high",
    "title": "Approval Required",
    "message": "Mission 'Data Analysis Pipeline' requires approval for external data export",
    "action_url": "/governance/approval/apr_001"
  }
}
```

### Example WebSocket Client (JavaScript)

```javascript
const ws = new WebSocket('wss://api.cortexprime.example.com/ws?token=YOUR_TOKEN');

ws.onopen = () => {
  console.log('Connected to CortexPrime WebSocket');

  // Subscribe to mission updates and agent logs
  ws.send(JSON.stringify({
    type: 'subscribe',
    channels: ['mission:exec_xyz789', 'agent:agent_001', 'decision:*']
  }));
};

ws.onmessage = (event) => {
  const payload = JSON.parse(event.data);
  console.log('Event:', payload.type, payload.data);
};

ws.onclose = () => {
  console.log('Disconnected from CortexPrime WebSocket');
};

ws.onerror = (error) => {
  console.error('WebSocket error:', error);
};
```

### Example WebSocket Client (Python with websockets library)

```python
import asyncio
import json
import websockets

async def listen():
    uri = "wss://api.cortexprime.example.com/ws?token=YOUR_TOKEN"
    async with websockets.connect(uri) as ws:
        # Subscribe to events
        await ws.send(json.dumps({
            "type": "subscribe",
            "channels": ["mission:exec_xyz789", "notification:*"]
        }))

        # Listen for messages
        async for message in ws:
            payload = json.loads(message)
            print(f"Event: {payload['type']}", payload['data'])

asyncio.run(listen())
```
