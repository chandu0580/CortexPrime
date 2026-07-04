# Security Sprint 1 - Privileged Route Authentication Audit

Date: 2026-06-14

## Scope

Audited all router modules under:
- `backend/api/`
- `backend/api/routes/`

Goal: ensure privileged endpoints enforce `Depends(require_user)` or `Depends(require_admin)`.

## Routes Audited

- `backend/api/auth_routes.py`
- `backend/api/computer_routes.py`
- `backend/api/cost_routes.py`
- `backend/api/executive_routes.py`
- `backend/api/governance_center_routes.py`
- `backend/api/governance_routes.py`
- `backend/api/graph_routes.py`
- `backend/api/llm_health_routes.py`
- `backend/api/memory_explorer_routes.py`
- `backend/api/memory_routes.py`
- `backend/api/metrics_routes.py`
- `backend/api/mission_execution_routes.py`
- `backend/api/mission_replay_routes.py`
- `backend/api/operator_routes.py`
- `backend/api/orchestration_routes.py`
- `backend/api/rabbitmq_routes.py`
- `backend/api/research_routes.py`
- `backend/api/runtime_api.py`
- `backend/api/system_health_routes.py`
- `backend/api/telemetry_routes.py`
- `backend/api/vector_search_routes.py`
- `backend/api/workspace_routes.py`
- `backend/api/routes/computer_routes.py`
- `backend/api/routes/mission_routes.py`
- `backend/api/routes/orchestrator_routes.py`
- `backend/api/routes/research_routes.py`
- `backend/api/routes/voice_routes.py`

## Routes Fixed In This Sprint

### Added `require_user`

- `backend/api/cost_routes.py`
  - Router-level protection on `/api/costs/*`
- `backend/api/rabbitmq_routes.py`
  - Router-level protection on `/api/rabbitmq/*`
- `backend/api/llm_health_routes.py`
  - Protected `GET /health/llm/telemetry`
- `backend/api/orchestration_routes.py`
  - Router-level protection for legacy orchestration route
- `backend/api/routes/mission_routes.py`
  - Router-level protection for legacy mission management routes
- `backend/api/routes/orchestrator_routes.py`
  - Router-level protection for legacy orchestrator routes

### Added `require_admin`

- `backend/api/rabbitmq_routes.py`
  - `POST /api/rabbitmq/dlq/replay/{message_id}`
  - `DELETE /api/rabbitmq/dlq`
- `backend/api/llm_health_routes.py`
  - `POST /health/llm/reset`
- `backend/api/governance_routes.py`
  - `POST /governance/approve`
  - `POST /governance/reject`
  - `POST /governance/emergency-stop`
  - `POST /governance/emergency-stop/deactivate`
  - `POST /governance/stop-mission`
  - `POST /governance/stop-browser`
  - `POST /governance/stop-computer`
- `backend/api/operator_routes.py`
  - `POST /operator/execute`

## Routes Already Protected

- Mission execution API (`backend/api/mission_execution_routes.py`) used `Depends(require_user)`
- Runtime API (`backend/api/runtime_api.py`) has router-level `Depends(require_user)`
- Workspace API (`backend/api/workspace_routes.py`) has router-level `Depends(require_user)`
- Operator read routes (`/operator/monitors`, `/operator/screen/current`, `/operator/screen/capture`, `/operator/active-missions`, `/operator/missions/{execution_id}`) already had `require_user`
- Governance read and non-override routes already had `require_user`
- Memory, Memory Explorer, Telemetry, Research, Executive, Governance Center routes were already user-protected

## Routes Requiring Admin Role

- Replay queues and RabbitMQ management:
  - `POST /api/rabbitmq/dlq/replay/{message_id}`
  - `DELETE /api/rabbitmq/dlq`
- Governance override and emergency controls:
  - `POST /governance/approve`
  - `POST /governance/reject`
  - `POST /governance/emergency-stop`
  - `POST /governance/emergency-stop/deactivate`
  - `POST /governance/stop-mission`
  - `POST /governance/stop-browser`
  - `POST /governance/stop-computer`
- Operator administrative action:
  - `POST /operator/execute`
- LLM telemetry reset:
  - `POST /health/llm/reset`

## Test Coverage Added

Added: `tests/test_security_sprint1_auth_routes.py`

Covers:
- unauthenticated calls to privileged routes return `401`
- authenticated standard routes return `200`
- admin-only routes return `403` for non-admin role

## Validation

Executed:

`c:/projects/cortexprime/venv/Scripts/python.exe -m pytest tests/test_security_sprint1_auth_routes.py -q`

Result:
- `9 passed`
