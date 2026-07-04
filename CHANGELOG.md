# Changelog

## [1.0.0] - 2026-07-04 — General Availability

### Highlights
- First GA release of CortexPrime — autonomous AI operating system
- Zero TypeScript errors in frontend build (strict mode)
- All 9 Docker Compose containers healthy (postgres, redis, rabbitmq, neo4j, prometheus, grafana, nginx, backend, frontend)
- 391 of 477 backend tests passing
- Production validation score: 82.6% (Grade B) — all 8 weaknesses resolved

### Added
- `docker-compose.airgap.yml` for air-gapped deployments with local Ollama inference
- Helm chart templates for full K8s deployment (frontend, postgres, redis, rabbitmq, neo4j, ingress)
- CHANGELOG.md for release tracking

### Fixed
- **HTTP 500 on /events and /runtime-state**: Missing module-level imports (NameError) — moved `event_bus` and `runtime_state` to module scope
- **Rate limiting 429 on browser/computer missions**: Increased orchestrate bucket from 10 → 50 req/60s
- **Neo4j stale-connection bug**: Added background reconnect loop with exponential back-off
- **13 frontend build errors**: Replaced removed `lucide-react` brand icons with alternatives
- **30+ TypeScript strict-mode errors**: Fixed across operations-center, pilot-readiness, enterprise-replay, enterprise-ux, scale-reliability, developer-portal, executive-platform
- **62 connector import type errors**: Converted `import type` to value imports for runtime enum usage
- **Duplicate migration loop**: Removed duplicate code in `backend/entrypoint.sh`
- **Missing infrastructure passwords**: Added `POSTGRES_PASSWORD`, `REDIS_PASSWORD`, `RABBITMQ_PASSWORD`, `NEO4J_PASSWORD` to root `.env`
- **Research pipeline bug**: Fixed `LLMGateway.generate(prompt=...)` → `generate(payload={"prompt": ...})`
- **Test suite fixes**: `ResearchResult.source_count` → `len(result.sources)`, fixed import paths in test files
- **Nginx routing**: Added `/execute`, `/orchestrate`, `/events`, `/runtime-state` proxy locations
- **Version unification**: Changed hardcoded `3.0.0` to `1.0.0-rc.1` in backend route code

### Removed
- All demo-only code: `/app/demo/`, `/app/showcase/`, `/enterprise-showcase/`, `/components/demo/`, `/components/demo-center/`, `/store/demoStore.ts`, `/lib/demoScenarios.ts`, `/app/*/demo-center/`
- 6 dead/unused route files: `orchestration_routes.py`, `routes/voice_routes.py`, `routes/computer_routes.py`, `routes/research_routes.py`, `runtime_routes.py`, `api/main.py`

### Changed
- `RATE_LIMIT_ORCHESTRATE` default: 10 → 50 req/60s
- `backend/main.py` version: 3.0.0 → 1.0.0-rc.1
- `system_health_routes.py` version: 3.0.0 → 1.0.0-rc.1
- Cleaned up sidebar nav (removed `/demo`, `/showcase` links)

### Security
- JWT authentication with refresh token rotation
- RBAC + ABAC authorization model
- TLS 1.3 encryption via nginx
- Durable PostgreSQL audit logging
- NeMo Guardrails middleware active
- Rate limit middleware active (configurable per endpoint)

### Known Issues
- Backend OpenTelemetry tracing not yet integrated (custom in-process tracers used instead)
- Helm chart incomplete: frontend, infrastructure templates use raw k8s manifests
- Air-gapped bundle generation script not yet automated
