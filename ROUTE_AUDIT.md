# ROUTE_AUDIT

## Scope

Validated live route exposure for the route families implicated in the release blocker sprint after restoring JWT availability and correcting non-API router mount prefixes.

## Nginx Endpoint Validation

Measured through `https://localhost` after backend restart and healthy status:

| Endpoint | Result | Notes |
| --- | --- | --- |
| `/api/auth/login` | `422` | Route exists; request rejected for invalid payload rather than 404. |
| `/api/auth/health` | `200` | Healthy. |
| `/api/research/history` | `401` | Route exists and auth is enforced. |
| `/api/memory/explorer/stats` | `401` | Route exists and auth is enforced. |
| `/api/costs/summary` | `401` | Route exists and auth is enforced. |
| `/api/voice/v2/health` | `200` | Healthy. |

Interpretation: the previously failing auth, research, memory explorer, cost, and voice surfaces no longer return `404` or `500`.

## Live Route Table

Captured from the running backend container:

### Auth

- `/api/auth/admin/revoke-user/{target_user_id}`
- `/api/auth/health`
- `/api/auth/login`
- `/api/auth/logout`
- `/api/auth/me`
- `/api/auth/refresh`
- `/api/auth/revoke-all`

### Research

- `/api/research/domain`
- `/api/research/history`
- `/api/research/news`
- `/api/research/search`

### Memory

- `/api/memory/explorer/graph`
- `/api/memory/explorer/search`
- `/api/memory/explorer/stats`
- `/api/memory/explorer/timeline`

### Governance Center

- `/api/governance-center/compliance`
- `/api/governance-center/events`
- `/api/governance-center/overview`
- `/api/governance-center/replay/{execution_id}`
- `/api/governance-center/risk`

### Governance

- `/governance/approve`
- `/governance/audit`
- `/governance/audit/summary`
- `/governance/audit/{execution_id}`
- `/governance/emergency-stop`
- `/governance/emergency-stop/deactivate`
- `/governance/health`
- `/governance/queue`
- `/governance/queue/pending`
- `/governance/reject`
- `/governance/request-approval`
- `/governance/safety/assess`
- `/governance/stop-browser`
- `/governance/stop-computer`
- `/governance/stop-mission`
- `/governance/stop-status`

### Executive

- `/api/executive/analytics`
- `/api/executive/snapshot`

### Voice

- `/api/voice/v2/health`
- `/api/voice/v2/session`
- `/api/voice/v2/session/{session_id}`
- `/api/voice/v2/session/{session_id}/history`
- `/api/voice/v2/session/{session_id}/reconnect`
- `/api/voice/v2/sessions`
- `/api/voice/v2/token`

### Cost

- `/api/costs/daily`
- `/api/costs/mission/{mission_id}`
- `/api/costs/providers`
- `/api/costs/summary`
- `/api/costs/user/{user_id}`

### Mission Replay

- `/api/mission-replay/`
- `/api/mission-replay/{execution_id}`
- `/api/mission-replay/{execution_id}/graph`
- `/api/mission-replay/{execution_id}/timeline`

## Startup Audit Highlights

Observed in backend startup logs after restart:

- `Memory Explorer routes registered at /api/memory/explorer`
- `Governance Center routes registered at /api/governance-center`
- `Executive routes registered at /api/executive`
- `Mission Replay routes registered at /api/mission-replay`
- `Live Research routes registered`
- `Voice V2 routes registered`
- `Cost Engine routes registered at /api/costs`

## Residual Findings

- Workspace routes are still unavailable because `python-multipart` is not installed in the running backend environment.
- JWT secrets are currently ephemeral in the live container because `JWT_SECRET_KEY` and `JWT_REFRESH_SECRET` are not set to strong values in the environment.
- The validated runtime correction is now also confirmed on the rebuilt production backend image after force recreation.