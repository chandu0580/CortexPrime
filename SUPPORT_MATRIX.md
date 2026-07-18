# Support Matrix — CortexPrime v1.0.0

## Platform Support

### Operating Systems

| OS | Support | Notes |
|----|---------|-------|
| Linux (Ubuntu 22.04+) | ✅ Full | Primary development target |
| Linux (Debian 12+) | ✅ Full | |
| Linux (RHEL 9+) | ✅ Full | |
| macOS 14+ (Sonoma) | ✅ Development | Not production-supported |
| Windows Server 2022 | ⚠️ Limited | WSL2 required for Docker |
| Windows 11 | ⚠️ Limited | WSL2 required for Docker |

### Architecture

| Architecture | Support | Notes |
|-------------|---------|-------|
| x86_64 / amd64 | ✅ Full | Primary target |
| arm64 / aarch64 | ✅ Full | Apple Silicon, AWS Graviton |
| armv7 | ❌ Not supported | |

---

## Browser Support

### Desktop Browsers (Frontend)

| Browser | Minimum Version | Notes |
|---------|----------------|-------|
| Google Chrome | 120+ | ✅ Full support |
| Mozilla Firefox | 120+ | ✅ Full support |
| Apple Safari | 17+ | ✅ Full support |
| Microsoft Edge | 120+ | ✅ Full support |
| Opera | 100+ | ⚠️ Community support |
| Brave | 1.60+ | ✅ Full support |

### Browser Worker Automation

| Browser | Support | Notes |
|---------|---------|-------|
| Chromium | ✅ Full | Primary Playwright target |
| Firefox | ⚠️ Limited | Reduced action set |
| WebKit | ⚠️ Limited | Safari technology preview |

---

## Database Support

| Database | Min Version | Rec Version | Driver | Notes |
|----------|-------------|-------------|--------|-------|
| PostgreSQL | 15 | 16 | asyncpg | Required for primary storage |
| pgvector | 0.5.0 | 0.7.0 | — | Required for vector search |
| Redis | 7.0 | 7.2 | redis-py | Required for cache + working memory |
| Neo4j | 5.0 | 5.15 | neo4j | Required for knowledge graph |

### Database Sizing Guidelines

| Users | PostgreSQL | Redis | Neo4j |
|-------|-----------|-------|-------|
| 100 | db.t3.medium (4GB) | cache.t3.micro (0.5GB) | db.t3.medium (4GB) |
| 500 | db.r5.large (16GB) | cache.r5.large (13GB) | db.r5.large (16GB) |
| 1,000 | db.r5.xlarge (32GB) | cache.r5.xlarge (26GB) | db.r5.xlarge (32GB) |
| 5,000 | db.r5.2xlarge (64GB) + read replica | cache.r5.2xlarge (52GB) cluster | db.r5.2xlarge (64GB) cluster |
| 10,000 | db.r5.4xlarge (128GB) + 2 read replicas | cache.r5.4xlarge (105GB) cluster | db.r5.4xlarge (128GB) 3-node cluster |

---

## Container & Orchestration

| Platform | Min Version | Rec Version | Notes |
|----------|-------------|-------------|-------|
| Docker Engine | 24.0 | 25.0+ | Required for container runtime |
| Docker Compose | 2.24 | 2.27+ | For local/standalone deployments |
| Kubernetes | 1.28 | 1.30+ | For production deployments |
| Helm | 3.12 | 3.14+ | For K8s package management |
| containerd | 1.7 | 1.7+ | CRI runtime |

---

## Cloud Provider Support

| Provider | Services | Status |
|----------|----------|--------|
| AWS | ECS Fargate, EKS, RDS PostgreSQL, ElastiCache Redis, Neo4j Aura | ✅ Certified |
| GCP | Cloud Run, GKE, Cloud SQL, Memorystore Redis, Neo4j Aura | ✅ Certified |
| Azure | Container Apps, AKS, Azure Database for PostgreSQL, Azure Cache for Redis, Neo4j Aura | ✅ Certified |
| On-Premise | Docker Compose, Self-managed K8s | ✅ Supported |

---

## LLM Provider Support

| Provider | Models | Support |
|----------|--------|---------|
| OpenAI | GPT-4, GPT-4 Turbo, GPT-4o, GPT-3.5 Turbo | ✅ Full |
| Anthropic | Claude 3 Opus, Claude 3 Sonnet, Claude 3 Haiku | ✅ Full |
| Google | Gemini 1.5 Pro, Gemini 1.5 Flash | ✅ Full |
| Azure OpenAI | GPT-4, GPT-4 Turbo, GPT-3.5 Turbo | ✅ Full |

---

## Voice Provider Support

| Provider | Service | Support |
|----------|---------|---------|
| Deepgram | Speech-to-Text (STT) | ✅ Full |
| ElevenLabs | Text-to-Speech (TTS) | ✅ Full |
| LiveKit | WebRTC Transport | ✅ Full |

---

## Browser Automation

| Provider | Tool | Support |
|----------|------|---------|
| Playwright | Browser automation | ✅ Full |

---

## Secrets Management

| Provider | Support | Notes |
|----------|---------|-------|
| HashiCorp Vault | ✅ Full | Recommended |
| Azure Key Vault | ✅ Full | Azure deployments |
| AWS Secrets Manager | ✅ Full | AWS deployments |
| Environment Variables | ✅ Supported | Development only |

---

## Monitoring & Observability

| Tool | Integration | Support |
|------|-------------|---------|
| Prometheus | Metrics export at /metrics | ✅ Full |
| Grafana | Dashboard import available | ✅ Full |
| Sentry | Error tracking SDK | ✅ Full |
| OpenTelemetry | Trace export (Jaeger) | ⚠️ Beta |

---

## Network Requirements

### Ports

| Port | Protocol | Service | Required |
|------|----------|---------|----------|
| 8000 | HTTP/WS | Backend API | ✅ |
| 3000 | HTTP | Frontend | ✅ |
| 5432 | PostgreSQL | Database | Internal only |
| 6379 | Redis | Cache | Internal only |
| 7687 | Bolt | Neo4j | Internal only |
| 5672 | AMQP | RabbitMQ | Internal only |
| 9090 | HTTP | Prometheus | Optional |
| 9093 | HTTP | AlertManager | Optional |

---

## Deprecation Notices

- **Beta Configuration Format**: The `.env` format used in pre-1.0.0 betas is deprecated. Use `.env.example` as the new template.

---

## End of Life Schedule

| Version | Release Date | EOL Date |
|---------|-------------|----------|
| v1.0.0 (stable) | July 2026 | January 2027 |

---

*For upgrade instructions, see [UPGRADE_GUIDE.md](./UPGRADE_GUIDE.md).*