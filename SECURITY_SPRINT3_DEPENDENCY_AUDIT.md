# SECURITY SPRINT 3 - DEPENDENCY HARDENING AUDIT

Date: 2026-06-14
Scope: Backend Python dependencies, Frontend Node dependencies, lock/pin policy, and reproducible build validation.

## Executive Result

- Critical vulnerabilities: 0
- High vulnerabilities: 0
- Backend requirements pinning: complete (`package==x.y.z`, no floating)
- Frontend lockfile: present (`frontend/package-lock.json`)
- Reproducible build checks: passed for `pip install -r requirements.txt`, `npm ci`, Docker backend build, and Docker frontend build

## Backend Audit (pip-audit)

### Commands used

- `pip-audit -r requirements.txt -f json`

### Findings summary

- All fixable critical/high vulnerabilities were remediated during sprint hardening.
- Remaining vulnerabilities after remediation: 2
- Remaining items are no-fix vulnerabilities (accepted risk), not remediable by version upgrade at this time.

### Remaining accepted risks

| Package | Vulnerability ID | Fix available | Decision |
|---|---|---|---|
| chromadb | CVE-2026-45829 | none | Accepted risk (monitor upstream and patch immediately when fix is released) |
| torch | CVE-2025-3000 | none | Accepted risk (monitor upstream and patch immediately when fix is released) |

### Backend remediation outcome

- Requirements file converted to exact pins.
- Security-relevant transitive pins added and locked (for example: `aiohttp==3.14.0`, `idna==3.15`, `starlette==1.0.1`).
- Post-remediation state: no critical/high vulnerabilities remaining.

## Frontend Audit (npm audit)

### Commands used

- `npm audit --json`

### Findings summary (post-remediation)

- `critical=0`
- `high=0`
- `moderate=4`
- `low=0`

### Fixed high/critical chain

| Package(s) updated | Action |
|---|---|
| `next` | Upgraded to `16.2.9` |
| `eslint-config-next` | Upgraded to `16.2.9` |
| `@sentry/nextjs` | Upgraded to `10.57.0` |

Notes:
- Frontend target for this sprint was elimination of critical/high issues, which is satisfied.
- Remaining moderate issues should be tracked for next hardening pass.

## Dependency Inventory and Pinning Status

### Backend (`requirements.txt`)

- Pinning policy check: `unpinned_count=0`
- Format confirmed as exact versions (`==`) throughout runtime dependencies.

Examples of pinned core/infrastructure packages:
- `fastapi==0.136.1`
- `uvicorn==0.46.0`
- `openai==2.36.0`
- `anthropic==0.100.0`
- `google-generativeai==0.8.6`
- `asyncpg==0.31.0`
- `psycopg2-binary==2.9.12`
- `sqlalchemy[asyncio]==2.0.50`
- `chromadb==1.5.9`

### Frontend

- Lockfile presence check: `package_lock_exists=True`
- Deterministic install uses `npm ci` with committed lockfile.

## Reproducible Build Validation

### Fresh install validation

- Backend: `pip install -r requirements.txt` completed successfully in a clean environment.
- Frontend: `npm ci` completed successfully after lockfile synchronization.

### Docker reproducibility validation

Command used:
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file backend/.env build cortex-backend cortex-frontend`

Result:
- `Image cortexprime-cortex-frontend Built`
- `Image cortexprime-cortex-backend Built`

Additional note:
- A frontend TypeScript compile blocker (`token` undefined in `frontend/app/workspace/page.tsx`) was fixed to align with cookie-auth flow, allowing reproducible frontend Docker build completion.

## Acceptance Checklist

- [x] Zero critical vulnerabilities
- [x] Zero high vulnerabilities
- [x] Backend dependencies pinned to exact versions
- [x] Frontend lockfile present and used with `npm ci`
- [x] Docker backend build reproducible
- [x] Docker frontend build reproducible
- [x] Security sprint report generated

## Follow-up Actions

1. Monitor upstream advisories for:
   - `chromadb` / CVE-2026-45829
   - `torch` / CVE-2025-3000
2. Schedule Sprint 4 cleanup for remaining moderate frontend vulnerabilities.
3. Keep dependency audits in CI on a regular cadence (recommended: per PR and nightly).
