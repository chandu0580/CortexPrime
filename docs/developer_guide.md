# CortexPrime — Developer Guide

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Development Setup](#2-development-setup)
3. [Backend Architecture](#3-backend-architecture)
4. [Frontend Architecture](#4-frontend-architecture)
5. [Coding Conventions](#5-coding-conventions)
6. [Adding a Connector](#6-adding-a-connector)
7. [Adding a Workflow](#7-adding-a-workflow)
8. [Adding a Mission Skill](#8-adding-a-mission-skill)
9. [Testing Strategy](#9-testing-strategy)
10. [Performance Considerations](#10-performance-considerations)

---

## 1. Project Structure

```
cortexprime/
├── backend/                    # Python FastAPI application
│   ├── main.py                 # App entry, lifespan, route registration
│   ├── config.py               # pydantic-settings configuration
│   ├── dependencies.py         # FastAPI dependency injection
│   ├── api/                    # Route modules (30+ files)
│   │   ├── auth_routes.py
│   │   ├── mission_replay_routes.py
│   │   ├── enterprise_replay_routes.py
│   │   ├── system_health_routes.py
│   │   ├── diagnostics_routes.py
│   │   ├── approval_center_routes.py
│   │   └── ... (30+ route files)
│   ├── auth/                   # Authentication subsystem
│   │   ├── dependencies.py
│   │   ├── jwt_handler.py
│   │   └── token_blacklist.py
│   ├── connectors/             # Enterprise connectors (8)
│   │   ├── base.py             # BaseConnector abstract class
│   │   ├── registry.py         # Connector registry
│   │   ├── github.py
│   │   ├── jira.py
│   │   ├── slack.py
│   │   ├── teams.py
│   │   ├── azure_devops.py
│   │   ├── servicenow.py
│   │   ├── confluence.py
│   │   └── notion.py
│   ├── services/               # Business logic services
│   │   ├── mission_runtime.py
│   │   ├── mission_replay_store.py
│   │   └── activity_service.py
│   ├── events/                 # Event bus subsystem
│   │   ├── event_bus.py
│   │   └── event_models.py
│   ├── memory/                 # Memory system
│   ├── infrastructure/         # Redis, Neo4j, RabbitMQ, PostgreSQL clients
│   ├── database/               # ORM models, migrations (Alembic)
│   ├── websocket/              # WebSocket connection pool
│   ├── analytics/              # Cost engine, metrics
│   ├── approval_center/        # Approval workflows, policies
│   ├── ...                     # Additional subsystems
│   ├── .env                    # Local environment (gitignored)
│   ├── .env.example            # Environment template
│   └── entrypoint.sh           # Docker entrypoint (alembic + uvicorn)
│
├── frontend/                   # Next.js 16 TypeScript application
│   ├── app/                    # App Router pages
│   ├── components/             # React components
│   ├── store/                  # Zustand state stores
│   ├── lib/                    # Shared utilities
│   ├── public/                 # Static assets
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.ts
│
├── tests/                      # Python test suite
│   ├── conftest.py             # pytest config
│   ├── helpers.py              # Mock factories
│   ├── test_*.py               # 30+ test files
│   ├── benchmarks/             # Performance tests
│   └── production_validation/  # E2E validation suite
│
├── infra/                      # Infrastructure configs
│   ├── nginx/                  # Reverse proxy configs
│   ├── prometheus/             # Prometheus scrape config
│   ├── postgres/               # Init SQL
│   ├── kubernetes/             # K8s manifests
│   └── helm/                   # Helm chart
│
├── scripts/                    # Utility scripts
│   ├── validate_release.py     # Pre-release validation
│   └── generate-certs.sh       # TLS certificate generator
│
├── docker-compose.yml          # Development stack
├── docker-compose.prod.yml     # Production stack
├── docker-compose.airgap.yml   # Air-gapped stack
├── requirements.txt            # Python dependencies
├── requirements-dev.txt        # Dev/test dependencies
├── pyproject.toml              # Build config + tool settings
└── package.json                # Root workspace scripts
```

## 2. Development Setup

### Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Backend runtime |
| Node.js | 20+ | Frontend build |
| Docker | 24.0+ | Containerized services |
| Docker Compose | 2.20+ | Multi-service orchestration |

### Backend Setup

```bash
# Clone the repository
git clone <repo-url> cortexprime
cd cortexprime

# Create and activate virtual environment
python -m venv venv
# Windows: venv\Scripts\activate
# Linux/Mac: source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
pip install -r requirements-dev.txt

# Install Playwright browsers (for browser automation)
playwright install --with-deps chromium

# Copy environment file
cp backend/.env.example backend/.env
# Edit backend/.env with your keys
```

### Frontend Setup

```bash
cd frontend
npm install
```

### Running Locally

**Full stack (Docker):**
```bash
docker compose -f docker-compose.yml up -d --build
```

**Backend only (local Python):**
```bash
cd backend
uvicorn backend.main:app --reload --port 8000
```

**Frontend only (local Node):**
```bash
cd frontend
npm run dev
```

### Verification

```bash
# Backend health check
curl http://localhost:8000/health

# API docs
open http://localhost:8000/docs

# Frontend
open http://localhost:3000
```

---

## 3. Backend Architecture

### FastAPI Application (`backend/main.py`)

The application follows a modular pattern with ~1900 lines across:
- 12-step startup lifecycle (database, cache, queues, connectors)
- 10-step shutdown lifecycle (graceful drain, cleanup)
- 30+ route modules registered via `app.include_router()`

**Startup sequence:**
1. Load environment variables
2. Initialize PostgreSQL connection pool
3. Initialize Redis client
4. Initialize Neo4j driver
5. Initialize RabbitMQ connection
6. Initialize Prometheus metrics
7. Initialize Sentry SDK
8. Initialize event bus
9. Seed built-in connectors
10. Register route modules
11. Configure CORS middleware
12. Start background tasks

### Dependency Injection

Every route module uses FastAPI's `Depends()` for clean separation:

```python
@router.post("/missions")
async def create_mission(
    payload: MissionCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    bus: EventBus = Depends(get_event_bus),
) -> MissionResponse:
```

Key dependency providers are in `backend/dependencies.py`:
- `get_db_session` — Async SQLAlchemy session per request
- `get_redis_client` — Singleton Redis connection pool
- `get_current_user` — JWT → user hydration
- `get_event_bus` — Pub/sub event distribution

### Async Execution Model

All I/O uses `asyncio`. CPU-bound work (embedding, encryption) is offloaded to a thread pool:

```python
loop = asyncio.get_running_loop()
embedding = await loop.run_in_executor(thread_pool, generate_embedding, text)
```

### Error Handling

Every route module wraps handler bodies in try/except blocks that return structured error responses:

```python
try:
    result = await service.process(data)
    return JSONResponse(content=result, status_code=200)
except ServiceError as e:
    return JSONResponse(content={"error": str(e)}, status_code=e.status_code)
```

### Configuration

All settings are in `backend/config.py` using `pydantic-settings`:

```python
class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    BACKEND_PORT: int = 8000
    DATABASE_URL: str = "postgresql+asyncpg://..."
    REDIS_URL: str = "redis://..."
    # ... 50+ additional settings

    model_config = SettingsConfigDict(env_file=".env")
```

---

## 4. Frontend Architecture

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Framework | Next.js 16 (App Router) |
| UI Library | React 19 |
| State Management | Zustand 5.x |
| Styling | Tailwind CSS 4.x |
| Real-Time | WebSocket |
| Charts | Recharts |

### Directory Structure

```
frontend/
├── app/                    # Next.js App Router pages
│   ├── (auth)/             # Login, signup, OAuth
│   └── (dashboard)/        # Main app routes
│       ├── missions/
│       ├── connectors/
│       ├── admin/
│       └── developer/
├── components/             # Shared React components
│   ├── ui/                 # Primitive UI components
│   ├── layout/             # App shell, sidebar, topbar
│   └── enterprise-*/       # Enterprise feature modules
├── store/                  # Zustand stores
│   ├── authStore.ts
│   ├── missionStore.ts
│   ├── replayStore.ts
│   ├── runtimeStore.ts
│   └── ...
└── lib/                    # Shared utilities
```

### State Management (Zustand)

Stores follow a consistent pattern:

```typescript
interface MissionState {
  missions: Mission[]
  activeMissionId: string | null
  isLoading: boolean
  error: string | null

  // Actions
  fetchMissions: () => Promise<void>
  createMission: (data: MissionCreate) => Promise<void>
  setActiveMission: (id: string) => void
}

export const useMissionStore = create<MissionState>()(
  persist(
    (set, get) => ({
      missions: [],
      activeMissionId: null,
      isLoading: false,
      error: null,

      fetchMissions: async () => {
        set({ isLoading: true })
        try {
          const missions = await api.getMissions()
          set({ missions, isLoading: false })
        } catch (e) {
          set({ error: e.message, isLoading: false })
        }
      },
      // ...
    }),
    { name: 'mission-storage', partialize: (state) => ({ missions: state.missions }) }
  )
)
```

### Component Conventions

- Components are in `components/` grouped by feature
- Each component is a single file with PascalCase name
- Props are typed with TypeScript interfaces
- Use `tailwind-merge` + `clsx` for conditional styles

---

## 5. Coding Conventions

### Python (Backend)

| Rule | Standard |
|------|----------|
| Line length | 120 characters |
| Python version | 3.11+ |
| Formatter | Ruff |
| Type hints | Required on all function signatures |
| Async | Use `async def` for all I/O operations |
| Error handling | Structured exception hierarchy |
| Logging | Structured JSON via standard library logging |

**Lint commands:**
```bash
ruff check backend/
ruff format --check backend/
mypy backend/
```

### TypeScript (Frontend)

| Rule | Standard |
|------|----------|
| Line length | 120 characters (Prettier default) |
| Formatter | ESLint (via `eslint-config-next`) |
| Strict mode | `strict: true` in tsconfig |
| Naming | camelCase for variables, PascalCase for components |
| State | Zustand stores, no Redux |

**Lint commands:**
```bash
npm run lint     # ESLint
npx tsc --noEmit # TypeScript check
```

### Commit Messages

Use conventional commits: `type(scope): description`

Examples:
- `feat(connectors): add GitLab connector`
- `fix(mission): handle timeout in long-running missions`
- `docs(api): update endpoint schemas`

---

## 6. Adding a Connector

### Step 1: Create the connector class

In `backend/connectors/`, create a new file (e.g., `gitlab.py`):

```python
from backend.connectors.base import BaseConnector
from backend.connectors.registry import ConnectorRegistry

@ConnectorRegistry.register("gitlab")
class GitLabConnector(BaseConnector):
    """GitLab integration connector."""

    async def initialize(self, config: ConnectorConfig) -> None:
        self.base_url = config.get("base_url", "https://gitlab.com")
        self.token = config.get("access_token")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.token}"},
        )

    async def health_check(self) -> HealthStatus:
        try:
            resp = await self.client.get("/api/v4/version")
            return HealthStatus.healthy() if resp.status_code == 200 else HealthStatus.unhealthy()
        except Exception as e:
            return HealthStatus.unhealthy(detail=str(e))

    async def execute(self, action: ConnectorAction) -> ConnectorResult:
        if action.type == "create_issue":
            return await self._create_issue(action.params)
        elif action.type == "list_projects":
            return await self._list_projects(action.params)
        raise ValueError(f"Unknown action: {action.type}")

    async def shutdown(self) -> None:
        await self.client.aclose()

    @property
    def capabilities(self) -> list[Capability]:
        return [
            Capability(name="create_issue", description="Create a GitLab issue"),
            Capability(name="list_projects", description="List accessible projects"),
        ]

    @property
    def metadata(self) -> ConnectorMetadata:
        return ConnectorMetadata(
            name="GitLab",
            version="1.0.0",
            auth_method="personal_access_token",
        )
```

### Step 2: Add credential requirements

Update `CONNECTOR_CREDENTIALS` in the registry or config:

```python
CONNECTOR_CREDENTIALS["gitlab"] = {
    "required": ["access_token", "base_url"],
    "optional": ["project_id", "webhook_secret"],
}
```

### Step 3: Register in main.py

Add the import in `backend/main.py`:

```python
from backend.connectors import gitlab  # auto-registers via decorator
```

### Step 4: Add configuration UI

In `frontend/components/connectors/`, add a `GitLabConfig.tsx` form component for the admin UI.

---

## 7. Adding a Workflow

Workflows define multi-step approval or execution pipelines.

### Step 1: Define the workflow

In the appropriate module (e.g., `backend/approval_center/workflows.py`):

```python
class EscalatingApprovalWorkflow(ApprovalWorkflow):
    """Approval workflow that escalates after timeout."""

    def __init__(self, config: WorkflowConfig):
        super().__init__(config)
        self.escalation_minutes = config.get("escalation_minutes", 60)
        self.escalation_target = config.get("escalation_target")

    async def create(self, request: ApprovalRequest) -> Approval:
        approval = await super().create(request)
        # Schedule escalation task
        asyncio.create_task(self._schedule_escalation(approval.id))
        return approval

    async def _schedule_escalation(self, approval_id: UUID):
        await asyncio.sleep(self.escalation_minutes * 60)
        approval = await self.get(approval_id)
        if approval.status == "pending":
            await self.escalate(approval_id, target=self.escalation_target)
```

### Step 2: Register the route

Add endpoints in the appropriate route module:

```python
@router.post("/workflows/escalating")
async def create_escalating_workflow(
    config: WorkflowConfig,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> WorkflowResponse:
    workflow = EscalatingApprovalWorkflow(config)
    result = await workflow.create(config.request)
    return WorkflowResponse(id=result.id, status=result.status)
```

---

## 8. Adding a Mission Skill

Mission Skills are composable capabilities that the mission runtime can invoke.

### Step 1: Create the skill module

In `backend/services/mission_skills/`:

```python
from backend.services.mission_skills.base import BaseSkill

class DataAnalysisSkill(BaseSkill):
    name = "data_analysis"
    description = "Analyze structured data and produce insights"

    async def execute(self, context: SkillContext, params: dict) -> SkillResult:
        data = params.get("data")
        analysis_type = params.get("type", "summary")

        # Use LLM to analyze
        prompt = self._build_prompt(data, analysis_type)
        response = await context.llm.complete(prompt)

        return SkillResult(
            success=True,
            output=response.content,
            metadata={"tokens_used": response.tokens_used},
        )

    def _build_prompt(self, data: list, analysis_type: str) -> str:
        return f"""Analyze the following data using {analysis_type} analysis:
{json.dumps(data, indent=2)}

Provide: key insights, trends, anomalies, and recommendations."""
```

### Step 2: Register the skill

Either via decorator or explicit registration in the runtime:

```python
from backend.services.mission_skills.registry import SkillRegistry

SkillRegistry.register(DataAnalysisSkill)
```

---

## 9. Testing Strategy

### Test Pyramid

| Layer | Tool | Location | Count |
|-------|------|----------|-------|
| Unit tests | pytest | `tests/test_*.py` | 30+ files |
| Integration | pytest + asyncio | `tests/test_*_e2e.py` | Included |
| Performance | pytest-benchmark | `tests/benchmarks/` | 7 files |
| Validation | Custom framework | `tests/production_validation/` | 12 categories |

### Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=backend --cov-report=html

# Specific test file
pytest tests/test_mission_runtime.py -v

# Benchmark tests
pytest tests/benchmarks/ --benchmark-only

# Production validation suite
python scripts/validate_release.py
```

### Test Patterns

**Mocking infrastructure:**
```python
from tests.helpers import _mock_mission_runtime

async def test_mission_flow():
    mock = _mock_mission_runtime()
    # Mock returns MagicMock/AsyncMock for all attributes
```

**Async tests:**
```python
@pytest.mark.asyncio
async def test_event_bus_publish():
    bus = EventBus()
    await bus.emit(Event(type="mission.created", payload={}))
    # Assert subscriber received event
```

**Fixtures in conftest.py:**
```python
@pytest.fixture
async def db_session():
    # Create test database session
    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()
```

### Production Validation Suite

The `tests/production_validation/` directory contains 12 category tests (`cat01`–`cat10`) that validate:
- Long-running sessions
- Multi-agent stress tests
- Voice pipeline
- Browser agent
- Computer agent
- Governance flows
- Security controls
- Research operations
- Recovery scenarios
- Scoring/metrics

Run with:
```bash
python -m tests.production_validation.runner
```

---

## 10. Performance Considerations

### Backend

| Area | Guideline | Why |
|------|-----------|-----|
| Database connections | Pool size 20, max overflow 10 | Avoid connection starvation |
| Redis operations | Pipeline/batch where possible | Reduce round-trips |
| LLM calls | Cache common queries | Reduce cost and latency |
| File operations | Async I/O only | Don't block event loop |
| Thread pool | CPU-bound work only | Embedding, encryption, PDF |
| Memory tiers | Working → Episodic → Semantic → Reflection | Cost-efficient retrieval |

### Frontend

| Area | Guideline |
|------|-----------|
| Bundle size | Use dynamic imports for heavy components |
| API calls | React Query for caching and deduplication |
| WebSocket | Subscribe to specific channels, not global |
| State | Zustand with selectors to prevent re-renders |
| Images | Next.js Image component with lazy loading |

### Database

```sql
-- Essential indexes for query performance
CREATE INDEX idx_missions_user_status ON missions(user_id, status);
CREATE INDEX idx_missions_created ON missions(created_at DESC);
CREATE INDEX idx_events_type_time ON events(type, timestamp);
CREATE INDEX idx_memory_tier ON memory_entries(tier, user_id);
```

### Monitoring

Key performance metrics to watch:
- `cortex_http_request_duration_ms` — API latency (p95 < 500ms)
- `cortex_db_connection_pool_usage` — Connection pool saturation
- `cortex_worker_queue_depth` — Worker backlog
- `cortex_llm_token_usage` — Cost tracking

### Common Anti-Patterns

- **Synchronous HTTP calls in async routes** — Use `httpx.AsyncClient`
- **Missing connection pooling** — Reuse `AsyncSession`, `AsyncRedis`
- **N+1 queries in graph traversal** — Batch with Cypher `MATCH`
- **Large payloads in events** — Pass references, not data
- **Blocking the event loop** — Use `run_in_executor` for CPU work
