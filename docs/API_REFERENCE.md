# CortexPrime v1.0.0 GA — API Reference

> **Version:** 1.0.0 GA  
> **Last Updated:** July 2026  
> **Base URL:** `https://api.cortexprime.example.com`  
> **Content-Type:** `application/json`

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Runtime API](#2-runtime-api)
3. [Memory API](#3-memory-api)
4. [Knowledge Graph API](#4-knowledge-graph-api)
5. [Mission Replay API](#5-mission-replay-api)
6. [Enterprise Replay API](#6-enterprise-replay-api)
7. [Governance API](#7-governance-api)
8. [Security API](#8-security-api)
9. [Approval Center API](#9-approval-center-api)
10. [Telemetry API](#10-telemetry-api)
11. [WebSocket API](#11-websocket-api)

---

## 1. Authentication

### POST /auth/login

Authenticate a user and receive access and refresh tokens.

- **Method:** POST
- **Path:** `/auth/login`
- **Auth Required:** No (public)

**Request Body:**

```json
{
  "email": "user@example.com",
  "password": "your-password"
}
```

**Response Body (200 OK):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "dGhpcyBpcyBhIHJlZnJl...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "user": {
    "id": "usr_abc123",
    "email": "user@example.com",
    "name": "Jane Doe",
    "role": "admin"
  }
}
```

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com","password":"your-password"}'
```

---

### POST /auth/refresh

Refresh an expired access token using a valid refresh token.

- **Method:** POST
- **Path:** `/auth/refresh`
- **Auth Required:** No (uses refresh token)

**Request Body:**

```json
{
  "refresh_token": "dGhpcyBpcyBhIHJlZnJl..."
}
```

**Response Body (200 OK):**

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "bmV3IHJlZnJlc2ggdG9r...",
  "token_type": "Bearer",
  "expires_in": 3600
}
```

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"dGhpcyBpcyBhIHJlZnJl..."}'
```

---

### API Key Authentication

For programmatic access, include an API key in the `X-API-Key` header:

```bash
curl -X GET https://api.cortexprime.example.com/api/runtime/status \
  -H "X-API-Key: cp_key_live_abc123def456"
```

Alternatively, use the `Authorization: Bearer <token>` header with JWT tokens.

---

## 2. Runtime API

### POST /api/runtime/execute

Execute a runtime operation (mission, agent invocation, or custom command).

- **Method:** POST
- **Path:** `/api/runtime/execute`
- **Auth Required:** Yes (Bearer token or API key)

**Request Body:**

```json
{
  "type": "mission",
  "name": "Data Analysis Pipeline",
  "objectives": [
    {
      "id": "obj_001",
      "prompt": "Analyze the quarterly sales data and identify top 3 trends",
      "agent": "analyst-agent-v2"
    }
  ],
  "config": {
    "timeout": 300,
    "priority": "high",
    "max_tokens": 4096
  }
}
```

**Response Body (202 Accepted):**

```json
{
  "execution_id": "exec_xyz789",
  "status": "queued",
  "created_at": "2026-07-04T12:00:00Z",
  "estimated_completion": "2026-07-04T12:05:00Z"
}
```

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/api/runtime/execute \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{
    "type": "mission",
    "name": "Data Analysis Pipeline",
    "objectives": [{"id":"obj_001","prompt":"Analyze the quarterly sales data and identify top 3 trends","agent":"analyst-agent-v2"}],
    "config": {"timeout":300,"priority":"high","max_tokens":4096}
  }'
```

---

### GET /api/runtime/status

Retrieve the current runtime system status.

- **Method:** GET
- **Path:** `/api/runtime/status`
- **Auth Required:** Yes

**Response Body (200 OK):**

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 864000,
  "agents_connected": 12,
  "memory_usage_mb": 2048,
  "cpu_usage_percent": 45.2,
  "throughput_rps": 150,
  "error_rate_percent": 0.3,
  "avg_latency_ms": 120
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/runtime/status \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/runtime/agents

List all connected agents and their status.

- **Method:** GET
- **Path:** `/api/runtime/agents`
- **Auth Required:** Yes
- **Query Parameters:** `?status=running` (optional filter)

**Response Body (200 OK):**

```json
{
  "agents": [
    {
      "id": "agent_001",
      "name": "analyst-agent-v2",
      "type": "llm",
      "version": "2.1.0",
      "status": "running",
      "mission_id": "exec_xyz789",
      "cpu_percent": 30,
      "memory_mb": 512,
      "last_heartbeat": "2026-07-04T12:00:05Z",
      "uptime_seconds": 43200
    }
  ],
  "total": 1
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/runtime/agents \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/runtime/traces

Retrieve runtime execution traces for debugging and observability.

- **Method:** GET
- **Path:** `/api/runtime/traces`
- **Auth Required:** Yes
- **Query Parameters:** `?execution_id=exec_xyz789&limit=50&offset=0`

**Response Body (200 OK):**

```json
{
  "traces": [
    {
      "trace_id": "trace_aaa",
      "execution_id": "exec_xyz789",
      "span_id": "span_001",
      "parent_span_id": null,
      "operation": "agent.invoke",
      "start_time": "2026-07-04T12:00:01Z",
      "end_time": "2026-07-04T12:00:03Z",
      "duration_ms": 2150,
      "status": "ok",
      "metadata": {
        "agent": "analyst-agent-v2",
        "tokens_used": 450
      }
    }
  ],
  "total": 1,
  "limit": 50,
  "offset": 0
}
```

**Example cURL:**

```bash
curl -X GET "https://api.cortexprime.example.com/api/runtime/traces?execution_id=exec_xyz789&limit=10" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## 3. Memory API

### POST /api/memory/store

Store data into the agent's long-term or short-term memory.

- **Method:** POST
- **Path:** `/api/memory/store`
- **Auth Required:** Yes

**Request Body:**

```json
{
  "agent_id": "agent_001",
  "memory_type": "long_term",
  "key": "quarterly_analysis_results",
  "value": {
    "top_trends": ["AI adoption accelerating", "Cloud costs rising", "Edge computing growth"],
    "confidence": 0.92
  },
  "ttl_seconds": 2592000,
  "tags": ["analytics", "quarterly", "2026-q2"]
}
```

**Response Body (200 OK):**

```json
{
  "status": "stored",
  "memory_id": "mem_456",
  "key": "quarterly_analysis_results",
  "stored_at": "2026-07-04T12:00:10Z",
  "ttl_expires_at": "2026-08-03T12:00:10Z"
}
```

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/api/memory/store \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"agent_001","memory_type":"long_term","key":"quarterly_analysis_results","value":{"top_trends":["AI adoption accelerating","Cloud costs rising","Edge computing growth"],"confidence":0.92},"ttl_seconds":2592000,"tags":["analytics","quarterly","2026-q2"]}'
```

---

### POST /api/memory/search

Search across stored memory entries using semantic or keyword queries.

- **Method:** POST
- **Path:** `/api/memory/search`
- **Auth Required:** Yes

**Request Body:**

```json
{
  "agent_id": "agent_001",
  "query": "quarterly trends analysis",
  "memory_type": "long_term",
  "limit": 10,
  "min_score": 0.5,
  "tags": ["analytics"]
}
```

**Response Body (200 OK):**

```json
{
  "results": [
    {
      "memory_id": "mem_456",
      "key": "quarterly_analysis_results",
      "score": 0.94,
      "value": {
        "top_trends": ["AI adoption accelerating", "Cloud costs rising", "Edge computing growth"],
        "confidence": 0.92
      },
      "stored_at": "2026-07-04T12:00:10Z",
      "tags": ["analytics", "quarterly", "2026-q2"]
    }
  ],
  "total": 1
}
```

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/api/memory/search \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"agent_001","query":"quarterly trends analysis","memory_type":"long_term","limit":10,"min_score":0.5}'
```

---

### GET /api/memory/context/{session_id}

Retrieve the full memory context for a given session.

- **Method:** GET
- **Path:** `/api/memory/context/{session_id}`
- **Auth Required:** Yes

**Response Body (200 OK):**

```json
{
  "session_id": "sess_789",
  "agent_id": "agent_001",
  "short_term": [
    {
      "role": "user",
      "content": "Analyze quarterly sales",
      "timestamp": "2026-07-04T11:59:50Z"
    },
    {
      "role": "assistant",
      "content": "Analysis complete. Top trends identified.",
      "timestamp": "2026-07-04T12:00:05Z"
    }
  ],
  "long_term_keys": ["quarterly_analysis_results", "sales_forecast_q3"],
  "context_window_tokens": 2048
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/memory/context/sess_789 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/memory/status

Get memory system statistics.

- **Method:** GET
- **Path:** `/api/memory/status`
- **Auth Required:** Yes

**Response Body (200 OK):**

```json
{
  "total_entries": 15420,
  "total_agents": 12,
  "storage_used_mb": 256,
  "storage_limit_mb": 10240,
  "cache_hit_rate": 0.88,
  "avg_search_latency_ms": 45,
  "oldest_entry": "2026-04-01T00:00:00Z",
  "newest_entry": "2026-07-04T12:00:10Z"
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/memory/status \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## 4. Knowledge Graph API

### POST /api/graph/agent

Register or update an agent node in the knowledge graph.

- **Method:** POST
- **Path:** `/api/graph/agent`
- **Auth Required:** Yes

**Request Body:**

```json
{
  "agent_id": "agent_001",
  "name": "analyst-agent-v2",
  "type": "llm",
  "properties": {
    "version": "2.1.0",
    "capabilities": ["text_analysis", "data_visualization", "report_generation"],
    "model": "gpt-4o"
  }
}
```

**Response Body (200 OK):**

```json
{
  "node_id": "node_agent_001",
  "status": "created",
  "labels": ["Agent", "LLM"],
  "properties_count": 4
}
```

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/api/graph/agent \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"agent_id":"agent_001","name":"analyst-agent-v2","type":"llm","properties":{"version":"2.1.0","capabilities":["text_analysis","data_visualization","report_generation"],"model":"gpt-4o"}}'
```

---

### POST /api/graph/memory

Link a memory entry as a node in the knowledge graph.

- **Method:** POST
- **Path:** `/api/graph/memory`
- **Auth Required:** Yes

**Request Body:**

```json
{
  "memory_id": "mem_456",
  "agent_id": "agent_001",
  "key": "quarterly_analysis_results",
  "relationships": [
    {"target_id": "node_concept_trends", "type": "MENTIONS"},
    {"target_id": "node_agent_001", "type": "PRODUCED_BY"}
  ]
}
```

**Response Body (200 OK):**

```json
{
  "node_id": "node_mem_456",
  "status": "linked",
  "relationships_created": 2
}
```

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/api/graph/memory \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"memory_id":"mem_456","agent_id":"agent_001","key":"quarterly_analysis_results","relationships":[{"target_id":"node_concept_trends","type":"MENTIONS"},{"target_id":"node_agent_001","type":"PRODUCED_BY"}]}'
```

---

### POST /api/graph/concept

Create a concept node in the knowledge graph.

- **Method:** POST
- **Path:** `/api/graph/concept`
- **Auth Required:** Yes

**Request Body:**

```json
{
  "name": "AI Adoption Trends",
  "type": "concept",
  "properties": {
    "domain": "technology",
    "category": "trend",
    "confidence": 0.92
  },
  "relationships": [
    {"target_id": "node_mem_456", "type": "DERIVED_FROM"}
  ]
}
```

**Response Body (200 OK):**

```json
{
  "node_id": "node_concept_trends",
  "status": "created",
  "labels": ["Concept"],
  "relationships_created": 1
}
```

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/api/graph/concept \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"name":"AI Adoption Trends","type":"concept","properties":{"domain":"technology","category":"trend","confidence":0.92},"relationships":[{"target_id":"node_mem_456","type":"DERIVED_FROM"}]}'
```

---

### POST /api/graph/query

Query the knowledge graph using Cypher or natural language.

- **Method:** POST
- **Path:** `/api/graph/query`
- **Auth Required:** Yes

**Request Body:**

```json
{
  "query": "MATCH (a:Agent)-[:PRODUCED]->(m:Memory) WHERE a.name CONTAINS 'analyst' RETURN a, m LIMIT 10",
  "mode": "cypher"
}
```

Or with natural language:

```json
{
  "query": "What memories did the analyst agent produce?",
  "mode": "natural_language"
}
```

**Response Body (200 OK):**

```json
{
  "results": [
    {
      "agent": {
        "node_id": "node_agent_001",
        "name": "analyst-agent-v2",
        "type": "llm"
      },
      "memory": {
        "node_id": "node_mem_456",
        "key": "quarterly_analysis_results",
        "stored_at": "2026-07-04T12:00:10Z"
      }
    }
  ],
  "query_time_ms": 12,
  "total_results": 1
}
```

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/api/graph/query \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"query":"MATCH (a:Agent)-[:PRODUCED]->(m:Memory) WHERE a.name CONTAINS '"'"'analyst'"'"' RETURN a, m LIMIT 10","mode":"cypher"}'
```

---

## 5. Mission Replay API

### GET /api/mission-replay/{execution_id}

Retrieve full replay data for a completed mission execution.

- **Method:** GET
- **Path:** `/api/mission-replay/{execution_id}`
- **Auth Required:** Yes

**Response Body (200 OK):**

```json
{
  "execution_id": "exec_xyz789",
  "mission_name": "Data Analysis Pipeline",
  "status": "completed",
  "started_at": "2026-07-04T12:00:00Z",
  "completed_at": "2026-07-04T12:04:35Z",
  "duration_ms": 275000,
  "agents_involved": ["analyst-agent-v2", "summarizer-agent"],
  "objectives": [
    {
      "objective_id": "obj_001",
      "status": "succeeded",
      "agent": "analyst-agent-v2",
      "started_at": "2026-07-04T12:00:01Z",
      "completed_at": "2026-07-04T12:02:15Z",
      "events_count": 42
    }
  ],
  "decision_count": 8,
  "total_events": 156
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/mission-replay/exec_xyz789 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/mission-replay/{execution_id}/timeline

Get the chronological event timeline for a replay.

- **Method:** GET
- **Path:** `/api/mission-replay/{execution_id}/timeline`
- **Auth Required:** Yes
- **Query Parameters:** `?from=2026-07-04T12:00:00Z&to=2026-07-04T12:05:00Z&limit=100`

**Response Body (200 OK):**

```json
{
  "execution_id": "exec_xyz789",
  "events": [
    {
      "event_id": "evt_001",
      "timestamp": "2026-07-04T12:00:01Z",
      "type": "agent.invoke",
      "agent": "analyst-agent-v2",
      "data": {
        "input": "Analyze the quarterly sales data and identify top 3 trends",
        "tokens_in": 25
      }
    },
    {
      "event_id": "evt_002",
      "timestamp": "2026-07-04T12:00:02Z",
      "type": "memory.read",
      "agent": "analyst-agent-v2",
      "data": {
        "key": "previous_analysis",
        "found": true
      }
    }
  ],
  "total": 156,
  "limit": 100
}
```

**Example cURL:**

```bash
curl -X GET "https://api.cortexprime.example.com/api/mission-replay/exec_xyz789/timeline?limit=50" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/mission-replay/{execution_id}/graph

Get the execution graph (DAG) for a mission replay.

- **Method:** GET
- **Path:** `/api/mission-replay/{execution_id}/graph`
- **Auth Required:** Yes
- **Query Parameters:** `?format=json` or `?format=dot`

**Response Body (200 OK):**

```json
{
  "execution_id": "exec_xyz789",
  "nodes": [
    {"id": "obj_001", "type": "objective", "label": "Analyze quarterly sales", "status": "succeeded"},
    {"id": "obj_002", "type": "objective", "label": "Summarize findings", "status": "succeeded"},
    {"id": "decision_001", "type": "decision", "label": "Choose visualization type", "status": "executed"}
  ],
  "edges": [
    {"from": "obj_001", "to": "obj_002", "label": "depends_on"},
    {"from": "obj_001", "to": "decision_001", "label": "triggered"}
  ]
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/mission-replay/exec_xyz789/graph \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/mission-replay/

List all available replays with filtering and pagination.

- **Method:** GET
- **Path:** `/api/mission-replay/`
- **Auth Required:** Yes
- **Query Parameters:** `?status=completed&agent=analyst-agent-v2&from=2026-06-01&to=2026-07-04&page=1&per_page=20`

**Response Body (200 OK):**

```json
{
  "replays": [
    {
      "execution_id": "exec_xyz789",
      "mission_name": "Data Analysis Pipeline",
      "status": "completed",
      "started_at": "2026-07-04T12:00:00Z",
      "duration_ms": 275000,
      "agents": ["analyst-agent-v2", "summarizer-agent"],
      "objective_count": 2,
      "decision_count": 8
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20,
  "total_pages": 1
}
```

**Example cURL:**

```bash
curl -X GET "https://api.cortexprime.example.com/api/mission-replay/?status=completed&per_page=10" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## 6. Enterprise Replay API

All endpoints return replay data for specific domain entities. Each follows the pattern:
`GET /api/enterprise-replay/{domain}/{id}`

### GET /api/enterprise-replay/mission/{id}

- **Method:** GET
- **Path:** `/api/enterprise-replay/mission/{id}`
- **Auth Required:** Yes
- **Description:** Retrieve enterprise mission replay with full cross-domain context.

**Response Body (200 OK):**

```json
{
  "mission_id": "mission_001",
  "name": "Enterprise Data Pipeline",
  "status": "completed",
  "started_at": "2026-07-04T08:00:00Z",
  "completed_at": "2026-07-04T08:30:00Z",
  "domain": "enterprise",
  "worker_count": 5,
  "connector_count": 3,
  "decision_count": 24,
  "total_cost_usd": 12.45
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/enterprise-replay/mission/mission_001 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/enterprise-replay/workers/{id}

- **Method:** GET
- **Path:** `/api/enterprise-replay/workers/{id}`
- **Auth Required:** Yes
- **Description:** Retrieve worker agent replay data.

**Response Body (200 OK):**

```json
{
  "worker_id": "worker_001",
  "name": "data-processor-01",
  "status": "completed",
  "tasks_completed": 12,
  "total_duration_ms": 45000,
  "errors": 0,
  "throughput_items_per_sec": 25.3
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/enterprise-replay/workers/worker_001 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/enterprise-replay/connectors/{id}

- **Method:** GET
- **Path:** `/api/enterprise-replay/connectors/{id}`
- **Auth Required:** Yes
- **Description:** Retrieve connector (external system integration) replay.

**Response Body (200 OK):**

```json
{
  "connector_id": "conn_001",
  "type": "snowflake",
  "status": "connected",
  "records_read": 50000,
  "records_written": 1200,
  "total_bytes_transferred": 26214400,
  "avg_latency_ms": 85
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/enterprise-replay/connectors/conn_001 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/enterprise-replay/decisions/{id}

- **Method:** GET
- **Path:** `/api/enterprise-replay/decisions/{id}`
- **Auth Required:** Yes
- **Description:** Retrieve individual decision replay with full context.

**Response Body (200 OK):**

```json
{
  "decision_id": "dec_001",
  "agent": "analyst-agent-v2",
  "timestamp": "2026-07-04T12:02:00Z",
  "decision_type": "visualization_selection",
  "input_context": {
    "data_type": "timeseries",
    "dimensions": 3,
    "records": 1500
  },
  "output": {
    "chosen": "line_chart",
    "confidence": 0.87
  },
  "alternatives": [
    {"option": "bar_chart", "score": 0.72},
    {"option": "scatter_plot", "score": 0.45}
  ],
  "latency_ms": 320
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/enterprise-replay/decisions/dec_001 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/enterprise-replay/memory/{id}

- **Method:** GET
- **Path:** `/api/enterprise-replay/memory/{id}`
- **Auth Required:** Yes
- **Description:** Retrieve memory access replay for an entity.

**Response Body (200 OK):**

```json
{
  "memory_id": "mem_456",
  "agent_id": "agent_001",
  "accesses": [
    {"timestamp": "2026-07-04T12:00:02Z", "operation": "read", "latency_ms": 5},
    {"timestamp": "2026-07-04T12:00:10Z", "operation": "write", "latency_ms": 8}
  ],
  "total_reads": 1,
  "total_writes": 1,
  "size_bytes": 2048
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/enterprise-replay/memory/mem_456 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/enterprise-replay/knowledge-graph/{id}

- **Method:** GET
- **Path:** `/api/enterprise-replay/knowledge-graph/{id}`
- **Auth Required:** Yes
- **Description:** Retrieve knowledge graph operations replay.

**Response Body (200 OK):**

```json
{
  "graph_id": "node_concept_trends",
  "created_at": "2026-07-04T12:03:00Z",
  "relationships": [
    {"type": "DERIVED_FROM", "target": "node_mem_456", "created_at": "2026-07-04T12:03:01Z"}
  ],
  "query_count": 3,
  "last_queried_at": "2026-07-04T12:04:00Z"
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/enterprise-replay/knowledge-graph/node_concept_trends \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/enterprise-replay/costs/{id}

- **Method:** GET
- **Path:** `/api/enterprise-replay/costs/{id}`
- **Auth Required:** Yes
- **Description:** Retrieve cost breakdown for a mission or entity.

**Response Body (200 OK):**

```json
{
  "entity_id": "exec_xyz789",
  "entity_type": "execution",
  "total_cost_usd": 12.45,
  "breakdown": {
    "llm_tokens": {"input": 0.50, "output": 1.20, "total": 1.70},
    "compute": 5.25,
    "memory_storage": 0.80,
    "data_transfer": 2.10,
    "connector_calls": 2.60
  },
  "currency": "USD"
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/enterprise-replay/costs/exec_xyz789 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/enterprise-replay/events/{id}

- **Method:** GET
- **Path:** `/api/enterprise-replay/events/{id}`
- **Auth Required:** Yes
- **Description:** Retrieve all events for an entity.

**Response Body (200 OK):**

```json
{
  "entity_id": "exec_xyz789",
  "events": [
    {"event_id": "evt_001", "type": "agent.invoke", "timestamp": "2026-07-04T12:00:01Z"},
    {"event_id": "evt_002", "type": "memory.read", "timestamp": "2026-07-04T12:00:02Z"}
  ],
  "total": 156
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/enterprise-replay/events/exec_xyz789 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/enterprise-replay/timeline/{id}

- **Method:** GET
- **Path:** `/api/enterprise-replay/timeline/{id}`
- **Auth Required:** Yes
- **Description:** Get the full cross-domain timeline for an entity.

**Response Body (200 OK):**

```json
{
  "entity_id": "exec_xyz789",
  "start": "2026-07-04T12:00:00Z",
  "end": "2026-07-04T12:04:35Z",
  "events": [
    {"timestamp": "12:00:01", "domain": "runtime", "event": "agent.invoke", "detail": "analyst-agent-v2 started"},
    {"timestamp": "12:00:02", "domain": "memory", "event": "memory.read", "detail": "read previous_analysis"},
    {"timestamp": "12:02:00", "domain": "decision", "event": "decision.made", "detail": "chose line_chart"},
    {"timestamp": "12:04:30", "domain": "cost", "event": "cost.accrued", "detail": "$12.45 total"}
  ]
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/enterprise-replay/timeline/exec_xyz789 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/enterprise-replay/execution-graph/{id}

- **Method:** GET
- **Path:** `/api/enterprise-replay/execution-graph/{id}`
- **Auth Required:** Yes
- **Description:** Get the consolidated execution graph across domains.

**Response Body (200 OK):**

```json
{
  "entity_id": "exec_xyz789",
  "nodes": [
    {"id": "obj_001", "domain": "mission", "type": "objective", "label": "Analyze data"},
    {"id": "worker_001", "domain": "worker", "type": "task", "label": "Process batch 1"}
  ],
  "edges": [
    {"from": "obj_001", "to": "worker_001", "domain_cross": true},
    {"from": "worker_001", "to": "conn_001", "domain_cross": true}
  ],
  "domains_involved": ["mission", "worker", "connector", "memory", "decision"]
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/enterprise-replay/execution-graph/exec_xyz789 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/enterprise-replay/export/{id}

- **Method:** GET
- **Path:** `/api/enterprise-replay/export/{id}`
- **Auth Required:** Yes
- **Query Parameters:** `?format=json` (default), `?format=pdf`, `?format=csv`

**Response Body (200 OK — JSON format):**

```json
{
  "export_id": "export_001",
  "entity_id": "exec_xyz789",
  "format": "json",
  "generated_at": "2026-07-04T12:05:00Z",
  "data": { }
}
```

For PDF format, a `Content-Disposition: attachment` header is returned with the file.

**Example cURL:**

```bash
curl -X GET "https://api.cortexprime.example.com/api/enterprise-replay/export/exec_xyz789?format=json" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## 7. Governance API

### POST /governance/approval/request

Submit a new approval request for a governance policy check.

- **Method:** POST
- **Path:** `/governance/approval/request`
- **Auth Required:** Yes

**Request Body:**

```json
{
  "policy_id": "policy_data_export_01",
  "requester_id": "usr_abc123",
  "resource": "mission:exec_xyz789",
  "action": "export_to_external",
  "reason": "Need to share quarterly analysis with external partner",
  "risk_level": "medium",
  "context": {
    "destination": "partner-s3-bucket",
    "data_classification": "confidential",
    "record_count": 1500
  }
}
```

**Response Body (201 Created):**

```json
{
  "request_id": "apr_001",
  "status": "pending",
  "created_at": "2026-07-04T12:05:00Z",
  "estimated_review_time": "5 minutes"
}
```

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/governance/approval/request \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"policy_id":"policy_data_export_01","requester_id":"usr_abc123","resource":"mission:exec_xyz789","action":"export_to_external","reason":"Need to share quarterly analysis with external partner","risk_level":"medium","context":{"destination":"partner-s3-bucket","data_classification":"confidential","record_count":1500}}'
```

---

### POST /governance/approval/approve

Approve or reject a pending approval request.

- **Method:** POST
- **Path:** `/governance/approval/approve`
- **Auth Required:** Yes (Compliance Officer or Admin)

**Request Body:**

```json
{
  "request_id": "apr_001",
  "decision": "approved",
  "approver_id": "usr_admin_001",
  "comments": "Approved for external sharing under NDA. Expires in 7 days.",
  "expires_in_hours": 168
}
```

**Response Body (200 OK):**

```json
{
  "request_id": "apr_001",
  "status": "approved",
  "approved_at": "2026-07-04T12:06:00Z",
  "approved_by": "usr_admin_001",
  "expires_at": "2026-07-11T12:06:00Z"
}
```

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/governance/approval/approve \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"request_id":"apr_001","decision":"approved","approver_id":"usr_admin_001","comments":"Approved for external sharing under NDA. Expires in 7 days.","expires_in_hours":168}'
```

---

### GET /governance/approval/queue

Retrieve the current approval request queue, optionally filtered by status.

- **Method:** GET
- **Path:** `/governance/approval/queue`
- **Auth Required:** Yes (Compliance Officer or Admin)
- **Query Parameters:** `?status=pending&page=1&per_page=20`

**Response Body (200 OK):**

```json
{
  "queue": [
    {
      "request_id": "apr_001",
      "policy_id": "policy_data_export_01",
      "requester": "user@example.com",
      "resource": "mission:exec_xyz789",
      "action": "export_to_external",
      "risk_level": "medium",
      "status": "pending",
      "created_at": "2026-07-04T12:05:00Z"
    }
  ],
  "total": 1,
  "page": 1,
  "per_page": 20
}
```

**Example cURL:**

```bash
curl -X GET "https://api.cortexprime.example.com/governance/approval/queue?status=pending" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### POST /governance/emergency-stop

Immediately halt a specific mission or all missions globally.

- **Method:** POST
- **Path:** `/governance/emergency-stop`
- **Auth Required:** Yes (Admin only)

**Request Body:**

```json
{
  "scope": "mission",
  "target_id": "exec_xyz789",
  "reason": "Security breach detected in data pipeline",
  "initiated_by": "usr_admin_001",
  "notify_channels": ["in-app", "email"]
}
```

**Response Body (200 OK):**

```json
{
  "status": "stopped",
  "stopped_at": "2026-07-04T12:07:00Z",
  "affected_agents": 3,
  "affected_missions": 1,
  "incident_id": "inc_001"
}
```

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/governance/emergency-stop \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"scope":"mission","target_id":"exec_xyz789","reason":"Security breach detected in data pipeline","initiated_by":"usr_admin_001","notify_channels":["in-app","email"]}'
```

---

## 8. Security API

### POST /api/security/users

Create a new user or invite a user to the organization.

- **Method:** POST
- **Path:** `/api/security/users`
- **Auth Required:** Yes (Admin only)

**Request Body:**

```json
{
  "email": "newuser@example.com",
  "name": "John Smith",
  "role": "operator",
  "send_invite": true,
  "workspace_access": ["operations", "executive"]
}
```

**Response Body (201 Created):**

```json
{
  "user_id": "usr_def456",
  "email": "newuser@example.com",
  "name": "John Smith",
  "role": "operator",
  "status": "invited",
  "invite_sent_at": "2026-07-04T12:08:00Z",
  "workspace_access": ["operations", "executive"]
}
```

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/api/security/users \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"email":"newuser@example.com","name":"John Smith","role":"operator","send_invite":true,"workspace_access":["operations","executive"]}'
```

---

### GET /api/security/roles

List all roles and their associated permissions.

- **Method:** GET
- **Path:** `/api/security/roles`
- **Auth Required:** Yes (Admin only)

**Response Body (200 OK):**

```json
{
  "roles": [
    {
      "name": "admin",
      "description": "Full access to all features",
      "permissions": ["*"],
      "is_default": false
    },
    {
      "name": "operator",
      "description": "Access to missions and replay",
      "permissions": ["mission.create", "mission.run", "mission.view", "replay.view", "replay.export"],
      "is_default": true
    },
    {
      "name": "developer",
      "description": "Access to engineering tools and API keys",
      "permissions": ["api.explore", "api.keys", "sdk.access"],
      "is_default": false
    },
    {
      "name": "viewer",
      "description": "Read-only access to dashboards",
      "permissions": ["dashboard.view", "mission.view", "replay.view"],
      "is_default": false
    },
    {
      "name": "compliance_officer",
      "description": "Access to governance and audit",
      "permissions": ["governance.*", "audit.view", "approval.*"],
      "is_default": false
    }
  ]
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/security/roles \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### POST /api/security/api-keys

Generate a new API key for programmatic access.

- **Method:** POST
- **Path:** `/api/security/api-keys`
- **Auth Required:** Yes (Admin or Developer)

**Request Body:**

```json
{
  "name": "CI/CD Pipeline Key",
  "permissions": ["mission.create", "mission.view", "replay.view"],
  "expires_in_days": 90,
  "allowed_ips": ["10.0.0.0/8", "192.168.1.0/24"]
}
```

**Response Body (201 Created):**

```json
{
  "key_id": "key_001",
  "name": "CI/CD Pipeline Key",
  "api_key": "cp_key_live_abc123def456ghi789",
  "permissions": ["mission.create", "mission.view", "replay.view"],
  "created_at": "2026-07-04T12:09:00Z",
  "expires_at": "2026-10-02T12:09:00Z",
  "allowed_ips": ["10.0.0.0/8", "192.168.1.0/24"]
}
```

> **Important:** The `api_key` value is shown only once. Store it securely.

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/api/security/api-keys \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"name":"CI/CD Pipeline Key","permissions":["mission.create","mission.view","replay.view"],"expires_in_days":90,"allowed_ips":["10.0.0.0/8","192.168.1.0/24"]}'
```

---

### PUT /api/security/secrets

Store or update a secret in the secrets vault.

- **Method:** PUT
- **Path:** `/api/security/secrets`
- **Auth Required:** Yes (Admin only)

**Request Body:**

```json
{
  "name": "snowflake_password",
  "value": "s3cr3tP@ssw0rd!",
  "description": "Snowflake data warehouse password",
  "rotation_policy": "monthly",
  "tags": ["database", "snowflake"]
}
```

**Response Body (200 OK):**

```json
{
  "secret_id": "sec_001",
  "name": "snowflake_password",
  "status": "stored",
  "created_at": "2026-07-04T12:10:00Z",
  "next_rotation": "2026-08-04T12:10:00Z",
  "version": 1
}
```

**Example cURL:**

```bash
curl -X PUT https://api.cortexprime.example.com/api/security/secrets \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"name":"snowflake_password","value":"s3cr3tP@ssw0rd!","description":"Snowflake data warehouse password","rotation_policy":"monthly","tags":["database","snowflake"]}'
```

---

## 9. Approval Center API

### POST /api/approval-center/policies

Create a new approval policy.

- **Method:** POST
- **Path:** `/api/approval-center/policies`
- **Auth Required:** Yes (Admin or Compliance Officer)

**Request Body:**

```json
{
  "name": "External Data Export Policy",
  "description": "Requires approval for any data export to external destinations",
  "rules": [
    {
      "condition": "action == 'export_to_external'",
      "risk_level": ">= medium",
      "required_approvers": 1,
      "auto_approve_if": "data_classification == 'public'"
    }
  ],
  "enabled": true
}
```

**Response Body (201 Created):**

```json
{
  "policy_id": "policy_data_export_01",
  "name": "External Data Export Policy",
  "status": "active",
  "created_at": "2026-07-04T12:11:00Z",
  "rule_count": 1
}
```

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/api/approval-center/policies \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"name":"External Data Export Policy","description":"Requires approval for any data export to external destinations","rules":[{"condition":"action == '"'"'export_to_external'"'"'","risk_level":">= medium","required_approvers":1,"auto_approve_if":"data_classification == '"'"'public'"'"'"}],"enabled":true}'
```

---

### POST /api/approval-center/workflows

Create a new approval workflow.

- **Method:** POST
- **Path:** `/api/approval-center/workflows`
- **Auth Required:** Yes (Admin or Compliance Officer)

**Request Body:**

```json
{
  "name": "High Risk Export Workflow",
  "policy_id": "policy_data_export_01",
  "steps": [
    {
      "order": 1,
      "type": "parallel",
      "approvers": ["usr_compliance_001", "usr_compliance_002"],
      "required_votes": 1
    },
    {
      "order": 2,
      "type": "sequential",
      "approvers": ["usr_admin_001"],
      "required_votes": 1
    }
  ]
}
```

**Response Body (201 Created):**

```json
{
  "workflow_id": "wf_001",
  "name": "High Risk Export Workflow",
  "policy_id": "policy_data_export_01",
  "status": "active",
  "created_at": "2026-07-04T12:12:00Z",
  "step_count": 2
}
```

**Example cURL:**

```bash
curl -X POST https://api.cortexprime.example.com/api/approval-center/workflows \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..." \
  -H "Content-Type: application/json" \
  -d '{"name":"High Risk Export Workflow","policy_id":"policy_data_export_01","steps":[{"order":1,"type":"parallel","approvers":["usr_compliance_001","usr_compliance_002"],"required_votes":1},{"order":2,"type":"sequential","approvers":["usr_admin_001"],"required_votes":1}]}'
```

---

### GET /api/approval-center/workflows

List all approval workflows with optional filtering.

- **Method:** GET
- **Path:** `/api/approval-center/workflows`
- **Auth Required:** Yes (Admin or Compliance Officer)
- **Query Parameters:** `?status=active&policy_id=policy_data_export_01`

**Response Body (200 OK):**

```json
{
  "workflows": [
    {
      "workflow_id": "wf_001",
      "name": "High Risk Export Workflow",
      "policy_id": "policy_data_export_01",
      "status": "active",
      "step_count": 2,
      "created_at": "2026-07-04T12:12:00Z"
    }
  ],
  "total": 1
}
```

**Example cURL:**

```bash
curl -X GET "https://api.cortexprime.example.com/api/approval-center/workflows?status=active" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

## 10. Telemetry API

### GET /api/telemetry/runtime

Retrieve runtime telemetry metrics for a given time window.

- **Method:** GET
- **Path:** `/api/telemetry/runtime`
- **Auth Required:** Yes
- **Query Parameters:** `?from=2026-07-04T11:00:00Z&to=2026-07-04T12:00:00Z&granularity=1m`

**Response Body (200 OK):**

```json
{
  "metrics": [
    {
      "timestamp": "2026-07-04T11:00:00Z",
      "cpu_percent": 42.1,
      "memory_mb": 2048,
      "throughput_rps": 145,
      "error_rate_percent": 0.2,
      "avg_latency_ms": 118,
      "active_agents": 12,
      "queued_missions": 3
    }
  ],
  "granularity": "1m",
  "total_points": 60
}
```

**Example cURL:**

```bash
curl -X GET "https://api.cortexprime.example.com/api/telemetry/runtime?from=2026-07-04T11:00:00Z&to=2026-07-04T12:00:00Z&granularity=5m" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /api/telemetry/health

Get current system health status for all services.

- **Method:** GET
- **Path:** `/api/telemetry/health`
- **Auth Required:** Yes

**Response Body (200 OK):**

```json
{
  "status": "healthy",
  "services": [
    {"name": "api-gateway", "status": "healthy", "latency_ms": 5},
    {"name": "runtime-engine", "status": "healthy", "latency_ms": 12},
    {"name": "memory-store", "status": "healthy", "latency_ms": 8},
    {"name": "knowledge-graph", "status": "degraded", "latency_ms": 450, "message": "Replicating to secondary region"},
    {"name": "mission-orchestrator", "status": "healthy", "latency_ms": 15},
    {"name": "governance-service", "status": "healthy", "latency_ms": 10}
  ],
  "checked_at": "2026-07-04T12:00:00Z"
}
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/api/telemetry/health \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

---

### GET /metrics

Prometheus-formatted metrics endpoint for scraping by monitoring tools.

- **Method:** GET
- **Path:** `/metrics`
- **Auth Required:** Yes (API key recommended)
- **Response Format:** `text/plain; version=0.0.4`

**Response Body (200 OK):**

```
# HELP cortexprime_requests_total Total number of API requests
# TYPE cortexprime_requests_total counter
cortexprime_requests_total{method="POST",endpoint="/api/runtime/execute"} 1520
cortexprime_requests_total{method="GET",endpoint="/api/runtime/status"} 8900

# HELP cortexprime_agent_status Agent status (1=running, 0=offline)
# TYPE cortexprime_agent_status gauge
cortexprime_agent_status{agent_id="agent_001",name="analyst-agent-v2"} 1
cortexprime_agent_status{agent_id="agent_002",name="summarizer-agent"} 0

# HELP cortexprime_memory_usage_bytes Memory store usage
# TYPE cortexprime_memory_usage_bytes gauge
cortexprime_memory_usage_bytes{type="long_term"} 268435456
cortexprime_memory_usage_bytes{type="short_term"} 33554432

# HELP cortexprime_request_duration_ms Request duration histogram
# TYPE cortexprime_request_duration_ms histogram
cortexprime_request_duration_ms_bucket{le="50"} 5400
cortexprime_request_duration_ms_bucket{le="200"} 8700
cortexprime_request_duration_ms_bucket{le="1000"} 9200
cortexprime_request_duration_ms_bucket{le="+Inf"} 9500
cortexprime_request_duration_ms_sum 285000
cortexprime_request_duration_ms_count 9500
```

**Example cURL:**

```bash
curl -X GET https://api.cortexprime.example.com/metrics \
  -H "X-API-Key: cp_key_live_abc123def456"
```

---

## 11. WebSocket API

### Connection URL

```
wss://api.cortexprime.example.com/ws?token=<access_token>
```

- **Protocol:** WSS (WebSocket over TLS)
- **Authentication:** Pass your JWT access token as a query parameter
- **Reconnection:** Client should implement exponential backoff reconnection

### Authentication

```javascript
// JavaScript example
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

---

## Appendix: Common HTTP Status Codes

| Code | Description |
|------|-------------|
| `200 OK` | Request succeeded |
| `201 Created` | Resource created successfully |
| `202 Accepted` | Request accepted for asynchronous processing |
| `400 Bad Request` | Invalid request body or parameters |
| `401 Unauthorized` | Missing or invalid authentication |
| `403 Forbidden` | Authenticated but insufficient permissions |
| `404 Not Found` | Resource not found |
| `409 Conflict` | Resource state conflict |
| `429 Too Many Requests` | Rate limit exceeded |
| `500 Internal Server Error` | Server-side error |
| `503 Service Unavailable` | Service temporarily unavailable |

## Appendix: Error Response Format

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