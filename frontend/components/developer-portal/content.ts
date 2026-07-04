export type SectionId =
  | "getting-started" | "architecture-explorer" | "rest-api-explorer" | "websocket-explorer"
  | "mission-sdk" | "worker-sdk" | "connector-sdk" | "memory-sdk" | "knowledge-graph-sdk"
  | "security-guide" | "deployment-guide" | "tutorials" | "code-playground"

export interface PortalSection {
  id: SectionId
  label: string
  icon: string
  description: string
}

export interface CodeExample {
  lang: string
  label: string
  code: string
}

export const SECTIONS: PortalSection[] = [
  { id: "getting-started", label: "Getting Started", icon: "🚀", description: "Installation, architecture overview, quick start, first mission" },
  { id: "architecture-explorer", label: "Architecture Explorer", icon: "🏗️", description: "Interactive platform diagram with module details" },
  { id: "rest-api-explorer", label: "REST API Explorer", icon: "🔌", description: "Interactive API docs with search, examples, and grouped endpoints" },
  { id: "websocket-explorer", label: "WebSocket Explorer", icon: "🔗", description: "Live event streams with payload examples" },
  { id: "mission-sdk", label: "Mission SDK", icon: "🎯", description: "Mission lifecycle, definition, execution, validation, retry, recovery" },
  { id: "worker-sdk", label: "Worker SDK", icon: "🤖", description: "Browser, Voice, Desktop workers — lifecycle, capabilities, telemetry" },
  { id: "connector-sdk", label: "Connector SDK", icon: "🔧", description: "How to build connectors — registration, auth, health, metrics, events" },
  { id: "memory-sdk", label: "Memory SDK", icon: "🧠", description: "Redis, working, semantic, episodic, reflection memory APIs" },
  { id: "knowledge-graph-sdk", label: "Knowledge Graph SDK", icon: "🕸️", description: "Neo4j entities, relationships, inference, traversal, policies" },
  { id: "security-guide", label: "Security Guide", icon: "🔒", description: "RBAC, ABAC, JWT, OAuth, secrets, API keys, approvals" },
  { id: "deployment-guide", label: "Deployment Guide", icon: "📦", description: "Docker, Kubernetes, Helm, air-gapped, cloud, scaling, monitoring" },
  { id: "tutorials", label: "Tutorials", icon: "📝", description: "Step-by-step: missions, connectors, workers, approvals, replay, certification" },
  { id: "code-playground", label: "Code Playground", icon: "💻", description: "Ready-to-copy examples in Python, TypeScript, REST, WebSocket" },
]

export const SECTION_CONTENT: Record<SectionId, { title: string; subtitle: string; markdown: string; codeExamples?: CodeExample[]; interactive?: boolean }> = {
  "getting-started": {
    title: "Getting Started",
    subtitle: "Install, understand, and run your first CortexPrime mission in minutes.",
    markdown: `## Installation

\`\`\`bash
# Clone the repository
git clone https://github.com/cortexprime/cortexprime.git
cd cortexprime

# Install backend dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend && npm install

# Configure environment
cp .env.example .env
# Edit .env with your API keys (OpenAI, LiveKit, Neo4j, etc.)

# Start with Docker Compose (recommended)
docker compose up -d

# Or start manually
# Terminal 1: Backend
uvicorn backend.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
\`\`\`

## Architecture Overview

CortexPrime is an autonomous AI operating system with a modular, event-driven architecture:

- **Frontend**: Next.js 16 React application with Zustand state management
- **Backend**: Python FastAPI with async runtime
- **Databases**: PostgreSQL (pgvector), Redis, Neo4j
- **Message Bus**: RabbitMQ (distributed), In-memory EventBus (local)
- **Workers**: Browser (Playwright), Voice (Deepgram/ElevenLabs/LiveKit), Desktop
- **Observability**: Prometheus metrics, Sentry errors, OpenTelemetry traces

## Quick Start

Run your first mission in 3 steps:

\`\`\`python
import requests

# 1. Authenticate
resp = requests.post("http://localhost:8000/auth/login", json={
    "username": "admin", "password": "your-password"
})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# 2. Execute a mission
resp = requests.post("http://localhost:8000/api/runtime/execute", json={
    "objective": "Research the latest AI trends and summarize findings"
}, headers=headers)
execution_id = resp.json()["execution_id"]

# 3. Stream results via WebSocket
# See WebSocket Explorer for connection details
\`\`\`

## Create Your First Mission

\`\`\`python
from backend.mission_library.definitions import SOFTWARE_RELEASE
from backend.mission_library.executor import MissionExecutor

executor = MissionExecutor(SOFTWARE_RELEASE)
result = await executor.execute(
    context={"version": "2.1.0", "environment": "staging"}
)
\`\`\`

## Run Your First Mission

\`\`\`bash
curl -X POST http://localhost:8000/api/runtime/execute \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"objective": "Summarize the top 5 AI papers from arXiv"}'
\`\`\``,
    codeExamples: [
      { lang: "python", label: "Installation Script", code: "pip install -r requirements.txt\ncd frontend && npm install" },
      { lang: "typescript", label: "Client Setup", code: "import { createClient } from '@cortexprime/sdk';\n\nconst client = createClient({\n  baseUrl: 'http://localhost:8000',\n  token: process.env.CORTEX_TOKEN\n});" },
    ]
  },

  "architecture-explorer": {
    title: "Architecture Explorer",
    subtitle: "Interactive diagram of all CortexPrime platform modules.",
    markdown: ``,
    interactive: true,
  },

  "rest-api-explorer": {
    title: "REST API Explorer",
    subtitle: "Browse, search, and test all CortexPrime API endpoints.",
    markdown: ``,
    interactive: true,
  },

  "websocket-explorer": {
    title: "WebSocket Explorer",
    subtitle: "Live event streams from all platform subsystems.",
    markdown: ``,
    interactive: true,
  },

  "mission-sdk": {
    title: "Mission SDK",
    subtitle: "Define, execute, validate, and recover missions programmatically.",
    markdown: `## Mission Lifecycle

Every mission follows a defined lifecycle:

\`INIT → PLANNING → RESEARCHING → REASONING → VALIDATING → GENERATING → MEMORY_UPDATE → COMPLETED\`

## Mission Definition

Missions are defined using the MissionLibrary:

\`\`\`python
from backend.mission_library.models import (
    MissionDefinition, MissionCategory, WorkerType,
    ConnectorType, GovernanceLevel, ExecutionStage
)

my_mission = MissionDefinition(
    mission_id="custom-research",
    category=MissionCategory.KNOWLEDGE_DISCOVERY,
    name="Custom Research Mission",
    description="Researches a topic and generates insights",
    objective_template="Research {topic} and provide key insights",
    required_workers=[WorkerType.BROWSER],
    required_connectors=[],
    governance_level=GovernanceLevel.STANDARD,
    execution_stages=[
        ExecutionStage.PLANNING,
        ExecutionStage.RESEARCHING,
        ExecutionStage.REASONING,
        ExecutionStage.GENERATING,
    ],
    success_criteria=["Research completed", "Insights generated"],
    retry_policy={"max_retries": 3, "backoff": "exponential"},
)
\`\`\`

## Mission Execution

\`\`\`python
import requests

resp = requests.post(
    "http://localhost:8000/api/runtime/execute",
    json={
        "objective": "Analyze Q3 financial reports for tech sector",
        "mission_id": "custom-research",
        "params": {"topic": "Q3 tech earnings"},
    },
    headers={"Authorization": f"Bearer {token}"}
)
execution_id = resp.json()["execution_id"]
\`\`\`

## Validation

\`\`\`python
from backend.safety.safety_guard import SafetyGuard

guard = SafetyGuard()
assessment = await guard.assess_action(
    agent="research",
    action="browse_web",
    context={"url": "https://example.com"}
)
print(f"Risk: {assessment.risk_level}")
print(f"Requires approval: {assessment.requires_approval}")
\`\`\`

## Retry & Recovery

\`\`\`python
from backend.mission_library.models import RetryPolicy, FailureRecovery

policy = RetryPolicy(
    max_retries=3,
    backoff="exponential",
    initial_delay=1.0,
    max_delay=60.0,
)

recovery = FailureRecovery(
    strategy="rollback",
    checkpoint_enabled=True,
    fallback_agents=["research", "planner"],
)
\`\`\``,
    codeExamples: [
      { lang: "python", label: "Define Mission", code: "from backend.mission_library.models import MissionDefinition\n\nmission = MissionDefinition(mission_id='my-mission', ...)" },
      { lang: "typescript", label: "Execute via API", code: "const res = await fetch('/api/runtime/execute', {\n  method: 'POST',\n  headers: { Authorization: `Bearer ${token}` },\n  body: JSON.stringify({ objective: '...' })\n});" },
    ]
  },

  "worker-sdk": {
    title: "Worker SDK",
    subtitle: "Build and integrate custom workers for browser, voice, and desktop automation.",
    markdown: `## Worker Types

CortexPrime supports three built-in worker types:

- **Browser Worker**: Playwright-based web automation
- **Voice Worker**: Deepgram STT + ElevenLabs TTS + LiveKit transport
- **Desktop Worker**: Computer-use agent for desktop automation

## Browser Worker

\`\`\`typescript
import { BrowserWorker } from '@/browser-worker/BrowserWorker';

const worker = new BrowserWorker();

await worker.start();
await worker.navigate('https://example.com');
const text = await worker.extract('.article-content');
await worker.screenshot('article.png');
await worker.stop();
\`\`\`

## Voice Worker

\`\`\`typescript
import { VoiceWorker } from '@/voice-worker/VoiceWorker';

const voice = new VoiceWorker();
await voice.startSession({
  sttProvider: 'deepgram',
  ttsProvider: 'elevenlabs',
  voice: 'Rachel'
});

voice.on('transcript', (text) => console.log('Heard:', text));
voice.on('response', (audio) => console.log('Speaking...'));
\`\`\`

## Desktop Worker

\`\`\`typescript
import { DesktopWorker } from '@/desktop-worker/DesktopWorker';

const desktop = new DesktopWorker();
await desktop.start();
await desktop.openApplication('Chrome');
await desktop.click({ x: 500, y: 300 });
await desktop.type('Hello, CortexPrime!');
\`\`\`

## Custom Worker

\`\`\`typescript
import { AbstractWorker } from '@/worker-framework/AbstractWorker';
import { WorkerCapability } from '@/worker-framework/types';

class MyCustomWorker extends AbstractWorker {
  get capabilities(): WorkerCapability[] {
    return [
      { id: 'custom_action', name: 'Custom Action', version: '1.0' }
    ];
  }

  async execute(task: string): Promise<unknown> {
    this.emit('worker:started', { task });
    const result = await this.performTask(task);
    this.emit('worker:completed', { task, result });
    return result;
  }
}
\`\`\`

## Worker Lifecycle

\`INITIALIZED → CONNECTED → READY → BUSY → IDLE → DISCONNECTED\`

## Telemetry

\`\`\`typescript
worker.on('telemetry', (metrics) => {
  console.log('Worker metrics:', {
    cpu: metrics.cpuUsage,
    memory: metrics.memoryUsage,
    actionsPerSecond: metrics.actionsPerSecond,
  });
});
\`\`\``,
    codeExamples: [
      { lang: "typescript", label: "Browser Worker", code: "const browser = new BrowserWorker();\nawait browser.start();" },
      { lang: "typescript", label: "Voice Worker", code: "const voice = new VoiceWorker();\nawait voice.startSession({...});" },
    ]
  },

  "connector-sdk": {
    title: "Connector SDK",
    subtitle: "Integrate any external service as a CortexPrime connector.",
    markdown: `## Connector Architecture

Every connector extends the \`AbstractConnector\` base class:

\`\`\`typescript
import { AbstractConnector } from '@/connector-framework/AbstractConnector';
import { ConnectorCapability } from '@/connector-framework/types';

class MyConnector extends AbstractConnector {
  id = 'my-connector';
  name = 'My Service Connector';

  async connect(): Promise<void> {
    // Initialize API client, authenticate, etc.
  }

  async disconnect(): Promise<void> {
    // Clean up resources
  }

  async execute(action: string, params: unknown): Promise<unknown> {
    this.emit('connector:called', { action, params });
    const result = await this.callApi(action, params);
    this.emit('connector:completed', { action, result });
    return result;
  }
}
\`\`\`

## Capability Registration

\`\`\`typescript
import { ConnectorRegistry } from '@/connector-framework/ConnectorRegistry';

const registry = ConnectorRegistry.getInstance();
registry.register({
  id: 'my-connector',
  name: 'My Connector',
  capabilities: [
    { id: 'read_data', name: 'Read Data', input: 'query', output: 'results' },
    { id: 'write_data', name: 'Write Data', input: 'record', output: 'id' },
  ],
  healthCheck: async () => ({ status: 'healthy', latency: 120 }),
});
\`\`\`

## Authentication

\`\`\`typescript
// OAuth2
await connector.authenticate({
  type: 'oauth2',
  clientId: process.env.CLIENT_ID,
  clientSecret: process.env.CLIENT_SECRET,
  scopes: ['read', 'write'],
});

// API Key
await connector.authenticate({
  type: 'api_key',
  apiKey: process.env.API_KEY,
  headerName: 'X-API-Key',
});
\`\`\`

## Metrics & Health

\`\`\`typescript
import { ConnectorMetricsCollector } from '@/connector-framework/ConnectorMetricsCollector';

const metrics = new ConnectorMetricsCollector('my-connector');
metrics.recordCall({ duration: 230, success: true });
metrics.recordError({ code: 'RATE_LIMITED', retryAfter: 30 });

const health = await connector.checkHealth();
// Returns: { status: 'healthy' | 'degraded' | 'unhealthy', latency: number, lastError?: string }
\`\`\`

## Events

\`\`\`typescript
import { cortexEventBus } from '@/event-bus';

// Publish connector events
cortexEventBus.publish({
  category: 'connector',
  type: 'connector:call_started',
  source: 'my-connector',
  data: { endpoint: '/api/data', method: 'GET' },
});

cortexEventBus.publish({
  category: 'connector',
  type: 'connector:call_completed',
  source: 'my-connector',
  data: { endpoint: '/api/data', status: 200, duration: 230 },
});
\`\`\``,
    codeExamples: [
      { lang: "typescript", label: "Connector Class", code: "class MyConnector extends AbstractConnector { ... }" },
      { lang: "typescript", label: "Register Connector", code: "ConnectorRegistry.getInstance().register({...});" },
    ]
  },

  "memory-sdk": {
    title: "Memory SDK",
    subtitle: "Work with CortexPrime's multi-tier memory system.",
    markdown: `## Memory Architecture

CortexPrime uses a four-tier memory system:

| Tier | Backend | TTL | Purpose |
|------|---------|-----|---------|
| Working | Redis | 6h | Active session state, chat messages, cognition cache |
| Episodic | PostgreSQL + pgvector | Permanent | Agent interaction events with vector embeddings |
| Semantic | PostgreSQL + pgvector | Permanent | Factual knowledge with vector search |
| Reflection | PostgreSQL | Permanent | Self-reflective entries and meta-cognition |

## Redis (Working Memory)

\`\`\`python
from backend.memory.stores.context_store import ContextStore

store = ContextStore()
await store.set_session_context(
    session_id="session-123",
    context={"current_task": "research", "progress": 0.6}
)
context = await store.get_session_context("session-123")
\`\`\`

## Working Memory

\`\`\`typescript
import { MemoryOrchestrator } from '@/cognitive-memory/MemoryOrchestrator';

const memory = new MemoryOrchestrator();
await memory.store({
  type: 'working',
  content: 'Current research focus: AI trends',
  sessionId: 'session-123',
  ttl: 3600, // 1 hour
});
\`\`\`

## Semantic Memory

\`\`\`python
from backend.memory.memory_orchestrator import MemoryOrchestrator

memory = MemoryOrchestrator()
await memory.store_semantic_knowledge(
    concept="Transformer Architecture",
    content="Neural network architecture introduced in 'Attention is All You Need'",
    source="research_paper",
    confidence=0.95,
)

results = await memory.search_memories(
    query="attention mechanism",
    memory_type="semantic",
    limit=5
)
\`\`\`

## Episodic Memory

\`\`\`python
await memory.store_cognition_event(
    session_id="session-123",
    agent="research",
    event_type="tool_call",
    content="Called browser tool to fetch arxiv papers",
    metadata={"url": "https://arxiv.org", "results": 10}
)

events = await memory.get_episodic_memory("session-123", limit=50)
\`\`\`

## Reflection Memory

\`\`\`python
await memory.store_reflection(
    session_id="session-123",
    reflection="The research approach worked well. Next time, narrow the search terms.",
    insight_type="process_improvement",
    confidence=0.8,
)
\`\`\`

## Memory Orchestrator API

\`\`\`python
# Store any memory type
await memory.store_cognition_event(...)
await memory.store_semantic_knowledge(...)
await memory.store_reflection(...)

# Retrieve context
context = await memory.retrieve_context(session_id="session-123")

# Search across all memory types
results = await memory.search_memories(query="machine learning", limit=10)

# Session management
await memory.init_session(session_id="session-123")
await memory.consolidate_session(session_id="session-123")
\`\`\``,
    codeExamples: [
      { lang: "python", label: "Store Memory", code: "await memory.store_semantic_knowledge(concept='...', content='...')" },
      { lang: "python", label: "Search Memory", code: "results = await memory.search_memories(query='...', limit=10)" },
    ]
  },

  "knowledge-graph-sdk": {
    title: "Knowledge Graph SDK",
    subtitle: "Work with the Neo4j-based knowledge graph for entities, relationships, and inference.",
    markdown: `## Graph Architecture

The knowledge graph uses **Neo4j** with three primary node types:

- **Agent nodes**: Represent AI agents and their capabilities
- **Memory nodes**: Represent stored knowledge and experiences
- **Mission nodes**: Represent executed missions and their outcomes

Relationships: \`PRODUCED\`, \`PART_OF\`, \`RELATED_TO\`, \`TRIGGERED\`

## Entities

\`\`\`python
from backend.memory.graph.cognition_graph import CognitionGraph

graph = CognitionGraph()

await graph.create_agent_node(
    agent_id="research-v2",
    name="Research Agent v2",
    capabilities=["web_search", "data_extraction", "summarization"],
    status="active",
)

await graph.create_memory_node(
    memory_id="mem-123",
    content_type="semantic",
    summary="Transformer architecture overview",
    embedding=[0.1, 0.2, ...],  # 1536-dimensional vector
)

await graph.create_mission_node(
    mission_id="mission-456",
    name="Q3 Market Research",
    status="completed",
    objective="Research Q3 market trends",
)
\`\`\`

## Relationships

\`\`\`python
# Link agent to memory (agent PRODUCED memory)
await graph.record_execution_step(
    execution_id="exec-789",
    agent_id="research-v2",
    action="created_insight",
    memory_id="mem-123",
    timestamp="2024-05-12T10:30:00Z",
)

# Query lineage
lineage = await graph.get_execution_lineage(execution_id="exec-789")
for item in lineage:
    print(f"{item['type']}: {item.get('name', '')}")

# Find related entities
related = await graph.get_related(entity_id="mem-123", max_depth=2)
\`\`\`

## Inference

\`\`\`typescript
import { GraphInferenceEngine } from '@/knowledge-graph/GraphInferenceEngine';

const inference = new GraphInferenceEngine();

// Add inference rules
inference.addRule({
  name: 'same_domain',
  condition: (a, b) => a.domain === b.domain,
  relationship: 'RELATED_TO',
  confidence: 0.8,
});

const results = await inference.infer(graph);
console.log(\`Found \${results.length} inferred relationships\`);
\`\`\`

## Graph Traversal

\`\`\`typescript
import { GraphTraversalEngine } from '@/knowledge-graph/GraphTraversalEngine';

const traversal = new GraphTraversalEngine();

// BFS from a starting node
const path = await traversal.bfs('agent-research', (node) => {
  return node.type === 'memory' && node.relevance > 0.8;
});

// Shortest path between two nodes
const shortest = await traversal.shortestPath('agent-orchestrator', 'mission-456');
\`\`\`

## Graph Policies

\`\`\`typescript
import { GraphPolicyEngine } from '@/knowledge-graph/GraphPolicyEngine';

const policies = new GraphPolicyEngine();
policies.addPolicy({
  id: 'max_entities',
  rule: (context) => context.entityCount < 10000,
  action: 'allow',
});
\`\`\``,
    codeExamples: [
      { lang: "python", label: "Create Entity", code: "await graph.create_agent_node(agent_id='...', name='...', ...)" },
      { lang: "typescript", label: "Graph Traversal", code: "const path = await traversal.bfs('start-node', predicate);" },
    ]
  },

  "security-guide": {
    title: "Security Guide",
    subtitle: "Authentication, authorization, secrets management, and best practices.",
    markdown: `## Authentication

### JWT (JSON Web Tokens)

\`\`\`python
import requests

# Login
resp = requests.post("http://localhost:8000/auth/login", json={
    "username": "user@example.com",
    "password": "secure-password",
})
token = resp.json()["access_token"]

# Use token in subsequent requests
headers = {"Authorization": f"Bearer {token}"}
resp = requests.get("http://localhost:8000/api/memory/status", headers=headers)
\`\`\`

### API Keys

\`\`\`bash
# Create an API key
curl -X POST http://localhost:8000/api/security/api-keys \\
  -H "Authorization: Bearer $TOKEN" \\
  -H "Content-Type: application/json" \\
  -d '{"name": "ci-cd-key", "permissions": ["mission:execute", "memory:read"]}'

# Use API key
curl http://localhost:8000/api/runtime/status \\
  -H "X-API-Key: cp_api_live_abc123..."
\`\`\`

## Authorization

### RBAC (Role-Based Access Control)

\`\`\`python
from backend.security_center.models import Role, Permission
from backend.security_center.rbac_abac import AccessControl

# Define roles
admin_role = Role(
    name="admin",
    permissions=[Permission(action="*", resource="*")]
)
analyst_role = Role(
    name="analyst",
    permissions=[
        Permission(action="read", resource="memory"),
        Permission(action="execute", resource="mission"),
        Permission(action="read", resource="analytics"),
    ]
)

# Check permission
ac = AccessControl()
allowed = await ac.check_permission(
    user_id="user-123",
    action="execute",
    resource="mission",
    context={"risk_level": "low"},
)
\`\`\`

### ABAC (Attribute-Based Access Control)

\`\`\`python
allowed = await ac.check_permission(
    user_id="user-123",
    action="approve",
    resource="approval",
    context={
        "risk_level": "high",
        "amount": 50000,
        "department": "engineering",
        "time_of_day": "09:00",
    },
)
# ABAC evaluates: risk_level == high AND amount > 10000 → requires executive approval
\`\`\`

## Secrets Management

\`\`\`python
from backend.security_center.secrets import SecretManager

secrets = SecretManager()
await secrets.store("openai_key", "sk-...", provider="vault")
key = await secrets.retrieve("openai_key")
\`\`\`

## Approvals

\`\`\`python
from backend.approval_center.workflows import ApprovalWorkflowEngine

workflow = ApprovalWorkflowEngine()
request = await workflow.create_workflow(
    mission_id="mission-123",
    action="deploy_to_production",
    risk_level="high",
    requested_by="user-456",
)
# Auto-routes through: Manager → Security → Executive
\`\`\`

## Best Practices

1. **Never hardcode secrets** — use the SecretManager or environment variables
2. **Use API keys for CI/CD** — JWT for interactive sessions
3. **Implement least privilege** — start with minimal permissions and expand
4. **Enable approval workflows** — for high-risk actions
5. **Audit all actions** — events are automatically recorded via EventBus
6. **Use RBAC + ABAC together** — RBAC for broad roles, ABAC for fine-grained context`,
    codeExamples: [
      { lang: "python", label: "JWT Auth", code: "resp = requests.post('/auth/login', json={...})" },
      { lang: "bash", label: "API Key", code: "curl -H 'X-API-Key: cp_api_...' http://localhost:8000/api/..." },
    ]
  },

  "deployment-guide": {
    title: "Deployment Guide",
    subtitle: "Deploy CortexPrime in any environment — Docker, Kubernetes, cloud, air-gapped.",
    markdown: `## Docker Compose (Quick Start)

\`\`\`yaml
# docker-compose.yml
version: "3.8"
services:
  cortex-backend:
    build: .
    ports: ["8000:8000"]
    environment:
      - DATABASE_URL=postgresql+asyncpg://user:pass@db:5432/cortex
      - REDIS_URL=redis://redis:6379
      - NEO4J_URI=bolt://neo4j:7687
    depends_on: [db, redis, neo4j]

  cortex-frontend:
    build: ./frontend
    ports: ["3000:3000"]
    environment:
      - NEXT_PUBLIC_API_URL=http://localhost:8000

  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: cortex
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
    volumes: [pgdata:/var/lib/postgresql/data]

  redis:
    image: redis:7-alpine

  neo4j:
    image: neo4j:5
    environment:
      NEO4J_AUTH: neo4j/password
    volumes: [neo4jdata:/data]

volumes: {pgdata:, neo4jdata:}
\`\`\`

## Kubernetes (Production)

\`\`\`yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cortex-backend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: cortex-backend
  template:
    metadata:
      labels:
        app: cortex-backend
    spec:
      containers:
      - name: backend
        image: cortexprime/backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: cortex-db
              key: url
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1"
        livenessProbe:
          httpGet: {path: /health, port: 8000}
        readinessProbe:
          httpGet: {path: /health, port: 8000}
---
apiVersion: v1
kind: Service
metadata:
  name: cortex-backend
spec:
  ports:
  - port: 8000
    targetPort: 8000
  selector:
    app: cortex-backend
\`\`\`

## Helm Chart

\`\`\`bash
# Add the CortexPrime Helm repository
helm repo add cortexprime https://helm.cortexprime.ai
helm install my-release cortexprime/cortexprime

# Customize values
helm install my-release cortexprime/cortexprime \\
  --set backend.replicas=5 \\
  --set postgresql.enabled=true \\
  --set redis.sentinel.enabled=true \\
  --set ingress.enabled=true \\
  --set ingress.hostname=cortex.example.com
\`\`\`

## Air-Gapped Installation

\`\`\`bash
# On a connected machine
docker pull cortexprime/backend:latest
docker pull cortexprime/frontend:latest
docker pull pgvector/pgvector:pg16
docker pull redis:7-alpine
docker pull neo4j:5
docker save ... > images.tar

# On the air-gapped machine
docker load < images.tar
docker compose up -d
\`\`\`

## Cloud Deployment

- **AWS**: ECS Fargate + RDS PostgreSQL (pgvector) + ElastiCache Redis + Neo4j Aura
- **GCP**: Cloud Run + Cloud SQL + Memorystore Redis + Neo4j Aura
- **Azure**: Container Apps + Azure Database for PostgreSQL + Azure Cache for Redis + Neo4j Aura

## Scaling

\`\`\`bash
# Horizontal pod autoscaling
kubectl autoscale deployment cortex-backend \\
  --cpu-percent=70 \\
  --min=3 \\
  --max=20

# Vertical scaling (resources)
kubectl set resources deployment cortex-backend \\
  --requests=cpu=500m,memory=1Gi \\
  --limits=cpu=2,memory=4Gi
\`\`\`

## Monitoring

- **Metrics**: Prometheus at \`/metrics\` endpoint
- **Dashboards**: Grafana with CortexPrime dashboard
- **Alerts**: Prometheus AlertManager rules
- **Logs**: Structured JSON logging to stdout (collect with Loki/ELK)
- **Traces**: OpenTelemetry (Jaeger backends)

## Backup & Recovery

\`\`\`bash
# PostgreSQL
pg_dump -h localhost -U user cortex > backup_$(date +%Y%m%d).sql

# Redis
redis-cli SAVE
cp /var/lib/redis/dump.rdb backup.rdb

# Neo4j
neo4j-admin dump --database=neo4j --to=backup.dump
\`\`\``,
    codeExamples: [
      { lang: "yaml", label: "Docker Compose", code: "version: '3.8'\nservices:\n  cortex-backend:\n    build: ." },
      { lang: "yaml", label: "K8s Deployment", code: "apiVersion: apps/v1\nkind: Deployment\nmetadata:\n  name: cortex-backend" },
    ]
  },

  "tutorials": {
    title: "Tutorials",
    subtitle: "Step-by-step guides for common CortexPrime tasks.",
    markdown: `## Build Your First Mission

\`\`\`python
# 1. Define the mission
from backend.mission_library.models import MissionDefinition

research_mission = MissionDefinition(
    mission_id="tutorial-research",
    name="Tutorial Research Mission",
    category="knowledge_discovery",
    objective_template="Research {topic} and provide a summary",
    required_workers=["browser"],
    governance_level="standard",
)

# 2. Execute via API
import requests

resp = requests.post(
    "http://localhost:8000/api/runtime/execute",
    json={"objective": "Research 'AI Agents' and summarize"},
    headers={"Authorization": f"Bearer {token}"}
)
exec_id = resp.json()["execution_id"]

# 3. Check results via replay
resp = requests.get(
    f"http://localhost:8000/api/mission-replay/{exec_id}",
    headers={"Authorization": f"Bearer {token}"}
)
print(resp.json()["summary"])
\`\`\`

## Create a Connector

\`\`\`typescript
// 1. Create the connector class
export class MyApiConnector extends AbstractConnector {
  id = 'my-api';
  name = 'My API Connector';

  async connect() {
    this.client = new MyApiClient({ apiKey: this.config.apiKey });
    await this.client.authenticate();
  }

  async execute(action: string, params: any) {
    if (action === 'getData') return this.client.get(params.endpoint);
    if (action === 'postData') return this.client.post(params.endpoint, params.body);
    throw new Error(\`Unknown action: \${action}\`);
  }
}

// 2. Register it
ConnectorRegistry.getInstance().register(new MyApiConnector());

// 3. Use it
const connector = ConnectorRegistry.getInstance().get('my-api');
const data = await connector.execute('getData', { endpoint: '/users' });
\`\`\`

## Create a Worker

\`\`\`typescript
export class MyCustomWorker extends AbstractWorker {
  async initialize() {
    this.capabilities = [
      { id: 'process', name: 'Process Data', input: 'raw', output: 'processed' }
    ];
  }

  async execute(task: { type: string; data: unknown }) {
    this.status = 'busy';
    this.emit('worker:started', { task });

    const result = await this.processData(task.data);

    this.emit('worker:completed', { task, result });
    this.status = 'idle';
    return result;
  }
}
\`\`\`

## Create an Approval Workflow

\`\`\`python
from backend.approval_center.workflows import ApprovalWorkflowEngine

workflow = ApprovalWorkflowEngine()

# Define a custom workflow
await workflow.create_workflow(
    mission_id="deploy-prod",
    action="deploy",
    risk_level="critical",
    requested_by="developer-1",
    steps=[
        {"role": "manager", "action": "approve"},
        {"role": "security_officer", "action": "approve"},
        {"role": "executive", "action": "approve"},
    ],
    timeout_minutes=60,
)
\`\`\`

## Use Replay

\`\`\`bash
# List available replays
curl http://localhost:8000/api/mission-replay/ \\
  -H "Authorization: Bearer $TOKEN"

# Get full replay data
curl http://localhost:8000/api/mission-replay/exec-123 \\
  -H "Authorization: Bearer $TOKEN"

# Get replay graph
curl http://localhost:8000/api/mission-replay/exec-123/graph \\
  -H "Authorization: Bearer $TOKEN"

# Export as JSON
curl http://localhost:8000/api/enterprise-replay/export/exec-123?format=json \\
  -H "Authorization: Bearer $TOKEN"
\`\`\`

## Run Certification

\`\`\`bash
# Run the full certification suite
python scripts/run_certification.py

# Check certification status
curl http://localhost:8000/api/certification/status \\
  -H "Authorization: Bearer $TOKEN"

# View certification report
curl http://localhost:8000/api/certification/report/latest \\
  -H "Authorization: Bearer $TOKEN"
\`\`\`

## Deploy CortexPrime

\`\`\`bash
# Production deployment
docker compose -f docker-compose.prod.yml up -d

# Verify deployment
curl http://localhost:8000/health
curl http://localhost:3000/api/health

# Check system status
curl http://localhost:8000/api/telemetry/health
\`\`\``,
    codeExamples: [
      { lang: "python", label: "First Mission", code: "mission = MissionDefinition(mission_id='tutorial', ...)" },
      { lang: "typescript", label: "Custom Connector", code: "class MyConnector extends AbstractConnector { ... }" },
    ]
  },

  "code-playground": {
    title: "Code Playground",
    subtitle: "Ready-to-copy code examples for every CortexPrime SDK.",
    markdown: ``,
    interactive: true,
  },
}