# CortexPrime Architecture

## 1. Overall Architecture

CortexPrime is an async-native, event-driven cognitive orchestration platform built on FastAPI (Python 3.13). It coordinates multi-agent workflows through a 6-stage cognition pipeline, with enterprise connectors, real-time streaming, and comprehensive governance.

```mermaid
graph TB
    subgraph Clients
        UI["Web UI / CLI"]
        API["REST API Clients"]
        WS["WebSocket Clients"]
    end

    subgraph Gateway["API Gateway Layer"]
        FW["CORS Middleware"]
        RID["RequestID Middleware"]
        GR["Guardrails Middleware"]
        RL["Rate Limit Middleware"]
        PM["Prometheus Middleware"]
    end

    subgraph Core["Application Core (FastAPI)"]
        RT["~30+ Route Modules"]
        EV["EventBus"]
        MR["Mission Runtime"]
        WE["Workflow Engine"]
        MSE["Mission Skill Engine"]
        VE["Verification Engine"]
    end

    subgraph Pipeline["Cognition Pipeline"]
        PL["Planner"]
        RS["Research"]
        CR["Critic"]
        OP["Optimizer"]
        RF["Reflection"]
        MM["Memory"]
    end

    subgraph Connectors["Connector Framework"]
        GH["GitHub"]
        JI["Jira"]
        SL["Slack"]
        TE["Teams"]
        AZ["Azure DevOps"]
        SN["ServiceNow"]
        CF["Confluence"]
        NT["Notion"]
    end

    subgraph Storage["Data Layer"]
        PG[("PostgreSQL 16\n+ pgvector")]
        RD[("Redis 7.2")]
        N4[("Neo4j 5.18")]
        CB[("ChromaDB")]
    end

    subgraph Infra["Infrastructure"]
        MQ["RabbitMQ 3.13\n6 Exchanges / 13 Queues"]
        PR["Prometheus"]
        GF["Grafana"]
        SNT["Sentry"]
    end

    subgraph Services["Support Services"]
        HC["Health Center"]
        BR["Backup & Restore"]
        MM["Maintenance Mode"]
        OR["Operational Reports"]
        AL["Analytics"]
        TL["Timeline"]
        RP["Replay System"]
        GV["Governance"]
    end

    UI --> FW
    API --> FW
    WS --> FW
    FW --> RID
    RID --> GR
    GR --> RL
    RL --> PM
    PM --> RT
    RT --> EV
    RT --> MR
    MR --> WE
    MR --> MSE
    MR --> VE
    MR --> Pipeline
    MR --> Connectors
    EV --> MQ
    EV --> N4
    EV --> RD
    EV --> PG
    MR --> Storage
    Pipeline --> Storage
    Services --> Storage
    Services --> MQ
    HC -.->|"Probes 17 subsystems"| Core
    HC -.->|"Probes 17 subsystems"| Storage
    HC -.->|"Probes 17 subsystems"| Infra
    HC -.->|"Probes 17 subsystems"| Connectors
```

### Runtime Layers

| Layer | Store | Use Case |
|-------|-------|----------|
| In-Memory | `RuntimeState` (Python dict) | Hot path, sub-millisecond access |
| Cache | `RuntimeStateStore` (Redis 7.2) | Session tracking, token blacklist, cognition cache, replay hot store |
| Persisted | Neo4j 5.18 | Cognitive graph: agents, memories, concepts, world models |

### Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Backend | FastAPI + async Python 3.13 | HTTP/WebSocket server |
| Async Runtime | asyncio | Coroutine orchestration |
| Database | PostgreSQL 16 + pgvector | Primary store with vector embeddings |
| Cache | Redis 7.2 | Session, tokens, cache, hot replay |
| Message Broker | RabbitMQ 3.13 | Async orchestration, agent messaging |
| Graph Engine | Neo4j 5.18 | Cognitive graph |
| Vector Store | ChromaDB | Local vector fallback |
| Metrics | Prometheus + Grafana | Observability |
| Errors | Sentry | Error tracking |

---

## 2. Mission Runtime

The `MissionRuntimeService.execute_mission()` is the main entry point for all mission execution.

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant MR as MissionRuntime
    participant PL as Pipeline
    participant CX as Connectors
    participant VE as Verification
    participant MQ as EventBus/RabbitMQ
    participant PG as PostgreSQL
    participant RD as Redis
    participant N4 as Neo4j

    C->>MR: execute_mission()
    MR->>MR: INIT
    MR->>MR: Guardrails Check
    MR->>MR: Governance Assessment
    MR->>MR: Emergency Stop Check
    MR->>RD: Load RuntimeState

    MR->>PL: PLANNING
    PL->>MR: Mission Plan

    MR->>CX: TOOL_SELECTION
    CX-->>MR: Selected Tools

    MR->>CX: TOOL_EXECUTION
    CX->>VE: Verify Result
    VE-->>CX: Verified
    CX-->>MR: Tool Results

    MR->>PL: SKILL_EXECUTION
    PL-->>MR: Skill Output

    MR->>PL: RESEARCHING
    PL-->>MR: Research Data

    MR->>PL: REASONING
    PL-->>MR: Reasoning Chain

    MR->>PL: VALIDATING
    PL-->>MR: Validation Result

    MR->>PL: GENERATING
    PL-->>MR: Final Output

    MR->>PL: MEMORY_UPDATE
    PL->>N4: Persist Memory

    MR->>MQ: Publish CognitionEvent
    MR->>PG: Persist Mission Record

    MR-->>C: Stream tokens via WebSocket
    C-->>MR: Continue / Cancel / Emergency Stop

    MR->>RD: Update RuntimeState
```

### Pipeline Stages

| Stage | Description |
|-------|-------------|
| INIT | Initialize runtime state, validate inputs |
| PLANNING | Decompose mission into steps |
| TOOL_SELECTION | Select appropriate connectors/tools |
| TOOL_EXECUTION | Execute connectors with retry + verification |
| SKILL_EXECUTION | Execute mission skills |
| RESEARCHING | Gather relevant context and data |
| REASONING | LLM-driven reasoning chain |
| VALIDATING | Verify outputs against criteria |
| GENERATING | Generate final response |
| MEMORY_UPDATE | Persist to cognitive graph |
| COMPLETED | Finalize and emit events |

### Key Features

- LLM token streaming via WebSocket
- Connector execution with exponential backoff retry (1s-30s with jitter)
- Post-execution verification with read-back
- Emergency stop (global + per-execution)
- Guardrails checks on all input/output

---

## 3. Workflow Engine

Manages approval gates, emergency stops, and workflow orchestration.

```mermaid
stateDiagram-v2
    [*] --> Pending: Create ApprovalRequest
    
    Pending --> Approved: Approve
    Pending --> Rejected: Reject
    Pending --> TimedOut: Timeout
    
    Approved --> InProgress: Execute
    Rejected --> [*]
    TimedOut --> [*]
    
    InProgress --> Completed: Success
    InProgress --> Failed: Error
    InProgress --> Stopped: Emergency Stop
    
    Completed --> [*]
    Failed --> [*]
    Stopped --> [*]
    
    state EmergencyStopController {
        [*] --> Active
        Active --> Triggered: stop()
        Triggered --> Reset: reset()
        Reset --> Active
    }

    state ApprovalWorkflowEngine {
        [*] --> Creating
        Creating --> AwaitingApproval: create()
        AwaitingApproval --> Approved: approve()
        AwaitingApproval --> Rejected: reject()
        AwaitingApproval --> Delegated: delegate()
        AwaitingApproval --> Bypassed: break_glass()
        Approved --> Executing
        Delegated --> AwaitingApproval
        Bypassed --> Executing
    }
```

### Components

| Component | Description |
|-----------|-------------|
| `ApprovalQueue` | asyncio.Event-based approval gates |
| `ApprovalRequest` | Lifecycle: pending → approved/rejected/timed_out |
| `EmergencyStopController` | Global + per-execution + per-agent stop |
| `ApprovalWorkflowEngine` | Create, approve, reject, delegate, break-glass |

---

## 4. Mission Skill Engine

Executes modular skills within the mission pipeline. Skills are registered components that encapsulate specific capabilities (code execution, data transformation, LLM prompts, etc.).

```mermaid
graph LR
    subgraph MSE["Mission Skill Engine"]
        SR["Skill Registry"]
        SM["Skill Manager"]
    end

    subgraph Skills
        S1["Code Skill"]
        S2["Prompt Skill"]
        S3["Data Skill"]
        S4["Custom Skill"]
    end

    subgraph Pipeline
        PL["Planner"]
        MR["Mission Runtime"]
    end

    PL -->|"resolve_skills()"| SR
    SR --> SM
    SM -->|"execute()"| Skills
    Skills -->|"result"| SM
    SM -->|"output"| MR
```

### Skill Lifecycle

1. **Registration** — Skills register with the Skill Registry at startup
2. **Resolution** — Planner resolves required skills from mission plan
3. **Execution** — Skill Manager executes each skill with context
4. **Verification** — Results pass through Verification Engine
5. **Completion** — Output merged into mission state

---

## 5. Verification Engine

Post-execution verification service that performs read-back validation on connector/ skill outputs.

```mermaid
flowchart LR
    A["Connector/Skill Output"] --> B["VerificationService.verify()"]
    B --> C{"Retry Policy\n3 attempts"}
    C -->|"Attempt 1"| D["Read-Back Check"]
    D --> E{"Match?"}
    E -->|"Yes"| F["Verified ✓"]
    E -->|"No"| G["Retry with\nExponential Backoff"]
    G --> C
    C -->|"Exhausted"| H["Verification Failed ✗"]
    C -->|"429/502/503/504"| I["Retry with Jitter\n1s-30s"]
    I --> C
```

### Configuration

| Parameter | Value |
|-----------|-------|
| Max Retries | 3 |
| Backoff Range | 1s – 30s |
| Jitter | Enabled (randomized) |
| RETRYABLE_STATUSES | 429, 502, 503, 504 |

---

## 6. Connector Framework

Eight enterprise connectors with a common abstract base.

```mermaid
graph TB
    subgraph Registry["ConnectorRegistry (Singleton)"]
        REG["register()\nfind_by_operation()\nfind_by_keyword()\nfind_by_capability()"]
    end

    subgraph Base["BaseConnector (ABC)"]
        INIT["initialize()"]
        HLTH["health()"]
        CFG["configure()"]
        OPS["get_operations()"]
        EXEC["_execute()"]
    end

    subgraph Connectors
        GH["GitHubConnector"]
        JI["JiraConnector"]
        SL["SlackConnector"]
        TE["TeamsConnector"]
        AZ["AzureDevOpsConnector"]
        SN["ServiceNowConnector"]
        CF["ConfluenceConnector"]
        NT["NotionConnector"]
    end

    subgraph Common["Common Patterns"]
        HTTP["httpx.AsyncClient"]
        ENV["Env-based Credentials"]
        RET["3-Retry Exp. Backoff\n+ Jitter"]
        VS["VerificationService\nPost-Write Read-Back"]
        ACT["ActivityService\nDB + Events + Audit"]
    end

    Base --> Registry
    Registry --> Connectors
    Connectors --> Common
    Connectors --> ACT

    ACT --> PG[("PostgreSQL")]
    ACT --> MQ["RabbitMQ"]
```

### Connector Matrix

| Connector | Auth | Key Operations |
|-----------|------|----------------|
| GitHub | Token | repos, issues, PRs, commits, actions |
| Jira | Token/Basic | issues, projects, sprints, boards |
| Slack | Bot Token | messages, channels, users, files |
| Teams | OAuth | messages, teams, channels, members |
| Azure DevOps | PAT | repos, pipelines, work items, builds |
| ServiceNow | Basic | incidents, changes, requests, cmdb |
| Confluence | Token | pages, spaces, attachments, search |
| Notion | Integration Token | pages, databases, blocks, users |

### Activity Recording

Each connector execution triggers `ActivityService` which:
1. Records activity to PostgreSQL
2. Publishes events to EventBus/RabbitMQ
3. Writes audit log entries

---

## 7. Replay System

Dual-layer persistence for mission event replay with 26 canonical event types.

```mermaid
graph TB
    subgraph Sources["Event Sources"]
        MR["Mission Runtime"]
        CX["Connectors"]
        PL["Pipeline Stages"]
        GV["Governance"]
        WE["Workflow Engine"]
    end

    subgraph Replay["MissionReplayStore"]
        REC["record(event)"]
        GET["get_events()\nget_summary()\nget_timeline()\nget_graph()"]
    end

    subgraph HotLayer["Hot Layer (Redis)"]
        RPUSH["RPUSH + LTRIM + EXPIRE"]
        MEM["In-Memory Fallback"]
    end

    subgraph ColdLayer["Cold Layer (PostgreSQL)"]
        EVT["replay_events table"]
    end

    subgraph Consumers["Consumers"]
        TL["Timeline"]
        AL["Analytics"]
        OR["Operational Reports"]
        DBG["Debug/Investigation"]
    end

    Sources --> CE["CognitionEvent"]
    CE --> REC
    REC --> RPUSH
    RPUSH -->|"Hot"| TL
    RPUSH -->|"Hot"| DBG
    REC --> EVT
    EVT --> AL
    EVT --> OR

    RPUSH -.->|"Fallback"| MEM
```

### Event Lifecycle

| Phase | Location | Duration |
|-------|----------|----------|
| Record | Redis RPUSH | ~1ms |
| Hot Retention | Redis (LTRIM + EXPIRE) | Configurable TTL |
| Cold Persistence | PostgreSQL | Indefinite |
| Fallback | In-memory list | Until service restart |

### 26 Canonical Event Types

Mapped from `CognitionEvent` — includes mission lifecycle events, connector calls, pipeline stage transitions, governance decisions, approval actions, errors, and system events.

---

## 8. Timeline

Temporal view of mission execution with event ordering and causal relationships.

```mermaid
graph LR
    subgraph Events["CognitionEvent Stream"]
        E1["Event @ T1"]
        E2["Event @ T2"]
        E3["Event @ T3"]
        E4["Event @ T4"]
        E5["Event @ T5"]
    end

    subgraph Timeline["Timeline Service"]
        ORD["Ordering & Correlation"]
        CAU["Causal Links"]
        AGG["Aggregation"]
    end

    subgraph Output
        TL["get_timeline()"]
        GR["get_graph()"]
        SU["get_summary()"]
    end

    Events --> ORD
    ORD --> CAU
    CAU --> AGG
    AGG --> TL
    AGG --> GR
    AGG --> SU

    TL --> UI["Timeline View"]
    GR --> UI
    SU --> UI
```

### Features
- Event ordering with causal links
- Correlation across concurrent missions
- Aggregation into summary views
- Graph-based visualization support

---

## 9. Analytics

Metrics, aggregations, and insights derived from mission execution data.

```mermaid
graph TB
    subgraph Sources
        MR["Mission Records"]
        RP["Replay Events"]
        AL["Audit Logs"]
        AP["Approval Records"]
    end

    subgraph Analytics["Analytics Engine"]
        COL["Collection & Aggregation"]
        MET["Metric Computation"]
        TRD["Trend Detection"]
    end

    subgraph Storage
        PG[("PostgreSQL\nanalytics tables")]
        PR[("Prometheus")]
    end

    subgraph Outputs
        DASH["Grafana Dashboards"]
        OR["Operational Reports"]
        ALR["Alerts"]
    end

    Sources --> COL
    COL --> MET
    MET --> TRD
    MET --> PG
    COL --> PR
    PR --> DASH
    PG --> OR
    PG --> ALR
    TRD --> ALR
```

### Tracked Metrics
- Mission counts (total, by status, by type)
- Success/failure rates
- Connector utilization
- Workflow utilization
- Approval statistics (avg approval time, rejection rate, break-glass frequency)
- Cost metrics (LLM token usage, compute time)

---

## 10. Governance

Multi-layered security and compliance system.

```mermaid
graph TB
    subgraph Input["Client Request"]
        REQ["HTTP Request\nPOST/PUT/PATCH"]
    end

    subgraph Middleware["Request Pipeline"]
        GM["GuardrailsMiddleware\nASGI Layer"]
        RL["RateLimiter\nRedis Sliding Window"]
    end

    subgraph Guardrails["GuardrailsEngine"]
        INJ["Injection Detection"]
        JB["Jailbreak Detection"]
        CL["Credential Leak Detection"]
        UT["Unsafe Tool Detection"]
    end

    subgraph Permissions["PermissionEngine"]
        RBAC["Role-Based Access\nADMIN / OPERATOR\nUSER / READONLY"]
    end

    subgraph Audit["AuditLogger"]
        LOG["Fire-and-Forget\nPostgreSQL Logging"]
    end

    subgraph Emergency["EmergencyStopController"]
        GLB["Global Stop"]
        EXEC["Per-Execution Stop"]
        AGT["Per-Agent Stop"]
    end

    subgraph Response["Response"]
        OK["200 OK"]
        ERR["4xx/5xx Error"]
    end

    Input --> GM
    GM --> RL
    RL --> Guardrails
    Guardrails -->|"Pass"| Permissions
    Guardrails -->|"Block"| ERR
    Permissions -->|"Authorized"| Audit
    Permissions -->|"Denied"| ERR
    Audit --> Emergency
    Emergency -->|"Active"| ERR
    Emergency -->|"Inactive"| OK

    subgraph Storage
        PG[("PostgreSQL")]
    end

    Audit --> PG
    RL -.->|"Fallback"| IP["In-Process Fallback"]
```

### Governance Components

| Component | Mechanism | Scope |
|-----------|-----------|-------|
| GuardrailsMiddleware | ASGI middleware | All POST/PUT/PATCH requests |
| GuardrailsEngine | Regex-based checks | Injection, jailbreak, credential leak, unsafe tools |
| RateLimiter | Redis sliding-window + in-process fallback | Per-client rate limiting |
| PermissionEngine | Role-based (RBAC) | ADMIN/OPERATOR/USER/READONLY |
| AuditLogger | Fire-and-forget to PostgreSQL | All mission and governance events |
| EmergencyStopController | Global + per-execution + per-agent | Immediate mission halt |

---

## 11. Health Center

> **Retired in Phase 10.29 (ADR-119).** The Health Center API/model surface was removed from the repository. Discovery (Phases 10.23, 10.27, 10.28) found no production consumer, no frontend client, no operator workflow and no table on any database; the routes had been mounted at `/api/api/…` since their introduction and answered `UndefinedTableError` on every migration-built database. The historical description is preserved in git history and in `docs/PHASE_10_27_GA_SURFACE_DECISION_DISCOVERY.md`.

## 12. Backup & Restore

> **Retired in Phase 10.29 (ADR-119).** The file-based Backup & Restore API/model surface was removed from the repository. Discovery (Phases 10.23, 10.27, 10.28) found no production consumer, no frontend client, no operator workflow and no table on any database; the routes had been mounted at `/api/api/…` since their introduction and answered `UndefinedTableError` on every migration-built database. The historical description is preserved in git history and in `docs/PHASE_10_27_GA_SURFACE_DECISION_DISCOVERY.md`.

GA backup/DR is `scripts/backup-database.sh` and the Helm `backup-cronjob.yaml` (`pg_dump`); they are unaffected and remain the documented mechanism (Administrator Guide §11, DR Runbook §2).

## 13. Maintenance Mode

> **Retired in Phase 10.29 (ADR-119).** The Maintenance Mode API/model surface was removed from the repository. Discovery (Phases 10.23, 10.27, 10.28) found no production consumer, no frontend client, no operator workflow and no table on any database; the routes had been mounted at `/api/api/…` since their introduction and answered `UndefinedTableError` on every migration-built database. The historical description is preserved in git history and in `docs/PHASE_10_27_GA_SURFACE_DECISION_DISCOVERY.md`.

The integration point this section previously documented — `should_block_new_mission()` "called by Mission Runtime before starting missions" — was never implemented; no caller existed in any commit (Phase 10.28). Mission admission is unchanged by the retirement.

## 14. Operational Reports

> **Retired in Phase 10.29 (ADR-119).** The Operational Reports API/model surface was removed from the repository. Discovery (Phases 10.23, 10.27, 10.28) found no production consumer, no frontend client, no operator workflow and no table on any database; the routes had been mounted at `/api/api/…` since their introduction and answered `UndefinedTableError` on every migration-built database. The historical description is preserved in git history and in `docs/PHASE_10_27_GA_SURFACE_DECISION_DISCOVERY.md`.

The report schedule this section previously documented had no scheduler behind it.

## Infrastructure Topology

```mermaid
graph TB
    subgraph Network["Network Zone"]
        LB["Load Balancer"]
        subgraph App["Application Servers"]
            API1["FastAPI Instance 1"]
            API2["FastAPI Instance 2"]
            API3["FastAPI Instance N"]
        end
        LB --> API1
        LB --> API2
        LB --> API3
    end

    subgraph Data["Data Layer"]
        PG[("PostgreSQL 16\nPrimary")]
        PGR[("PostgreSQL 16\nReplica")]
        RD[("Redis 7.2\nCluster")]
        N4[("Neo4j 5.18\nCluster")]
        CB[("ChromaDB")]
    end

    subgraph Message["Message Layer"]
        RMQ[("RabbitMQ 3.13\nCluster")]
    end

    subgraph Observability["Observability"]
        PR["Prometheus"]
        GF["Grafana"]
        SNT["Sentry"]
    end

    subgraph Storage["File Storage"]
        BK["Backup Directory"]
    end

    API1 --> PG
    API1 --> PGR
    API1 --> RD
    API1 --> N4
    API1 --> CB
    API1 --> RMQ
    API1 --> PR
    API1 --> SNT
    API1 --> BK

    API2 --> PG
    API2 --> PGR
    API2 --> RD
    API2 --> N4
    API2 --> CB
    API2 --> RMQ
    API2 --> PR
    API2 --> SNT
    API2 --> BK

    API3 --> PG
    API3 --> PGR
    API3 --> RD
    API3 --> N4
    API3 --> CB
    API3 --> RMQ
    API3 --> PR
    API3 --> SNT
    API3 --> BK

    PR --> GF
    PG --> PGR
```

---

## Deployment Topology

```mermaid
graph TB
    subgraph Env["Environment"]
        DEV["Development"]
        STG["Staging"]
        PRD["Production"]
    end

    subgraph CI["CI/CD Pipeline"]
        SRC["Source Control"]
        BLD["Build & Test"]
        PKG["Package"]
        DEP["Deploy"]
    end

    subgraph Container["Container Layer"]
        DKR["Docker Images"]
        subgraph Services
            API["cortex-api"]
            WRK["cortex-worker"]
            SCH["cortex-scheduler"]
        end
    end

    subgraph Orchestration["Orchestration"]
        K8S["Kubernetes / Docker Compose"]
    end

    subgraph Scaling["Scaling"]
        HPA["Horizontal Pod Autoscaler"]
    end

    SRC --> BLD
    BLD --> PKG
    PKG --> DKR
    DKR --> DEP
    DEP --> DEV
    DEV --> STG
    STG --> PRD

    K8S --> API
    K8S --> WRK
    K8S --> SCH
    HPA --> API
    HPA --> WRK

    subgraph Proxies["Entry Points"]
        NGINX["Nginx / Traefik"]
        CDN["CDN / CloudFront"]
    end

    CDN --> NGINX
    NGINX --> K8S
```

---

## Event Flow — CognitionEvent Lifecycle

```mermaid
graph LR
    subgraph Producers
        MR["Mission Runtime"]
        CX["Connector Framework"]
        PL["Cognition Pipeline"]
        GV["Governance"]
        WE["Workflow Engine"]
    end

    subgraph Bus["EventBus"]
        CE["CognitionEvent"]
        WS["WebSocket Broadcast"]
    end

    subgraph Streams["Message Routes"]
        RMQ["RabbitMQ\n6 Exchanges\n13 Queues"]
    end

    subgraph Consumers
        RP["Replay Store"]
        TL["Timeline"]
        AL["Analytics"]
        N4["Neo4j Graph"]
        MT["Metrics"]
    end

    subgraph Persistence
        RD[("Redis\nHot Replay")]
        PG[("PostgreSQL\nCold Replay")]
    end

    MR --> CE
    CX --> CE
    PL --> CE
    GV --> CE
    WE --> CE

    CE --> WS
    CE --> RMQ

    RMQ --> RP
    RMQ --> TL
    RMQ --> AL
    RMQ --> N4
    RMQ --> MT

    RP --> RD
    RP --> PG
    WS --> UI["WebSocket Clients"]
```

### 26 Canonical Event Types

| Category | Event Types |
|----------|-------------|
| Mission | mission.created, mission.started, mission.completed, mission.failed, mission.cancelled |
| Pipeline | pipeline.stage_started, pipeline.stage_completed, pipeline.stage_failed |
| Connector | connector.invoked, connector.success, connector.failed, connector.retry |
| Governance | guardrails.blocked, guardrails.warning, rate_limit.exceeded, auth.denied |
| Workflow | approval.created, approval.approved, approval.rejected, approval.timed_out, approval.break_glass |
| Emergency | emergency.stop_global, emergency.stop_execution, emergency.stop_agent |
| System | system.startup, system.shutdown, health.status_change, error.unhandled |

---

## Singleton Pattern

All services follow the module-level singleton pattern:

```python
# Every service module follows this pattern
_service = None

def get_service():
    global _service
    if _service is None:
        _service = ServiceClass()
    return _service
```

Services using this pattern: `MissionRuntimeService`, `ConnectorRegistry`, `GuardrailsEngine`, `RateLimiter`, `PermissionEngine`, `EmergencyStopController`, `HealthCenterService`, `MaintenanceManager`, `MissionReplayStore`.

---

## Graceful Degradation

All ~30+ route modules implement graceful degradation fallbacks. If a dependency (Redis, Neo4j, RabbitMQ) is unavailable, the system:
1. Falls back to in-memory alternatives where possible
2. Returns degraded response with warning header via `X-Degraded: <component>`
3. Logs degradation to Sentry and audit log
4. Continues serving remaining functionality
