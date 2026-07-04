# RELEASE_BLOCKER_REPORT

## Verdict

`READY FOR E2E RE-TEST`

The blocker endpoints that were failing with `404` or `500` now resolve through nginx with expected route-exists responses (`200`, `401`, or `422`).

## Blockers

### Blocker

Auth, research, memory explorer, cost, and voice endpoints were missing or failing in the production runtime.

### Root Cause

- The production backend runtime was missing `PyJWT`, which caused multiple router imports to fail with `No module named 'jwt'`.
- Several routers with non-API internal prefixes still required mount-time `prefix="/api"` in `backend/main.py`.

### Fix Applied

- Added `PyJWT==2.10.1` to `requirements.txt`.
- Restored `prefix="/api"` mounts in `backend/main.py` for:
  - memory explorer
  - governance center
  - executive
  - mission replay
- Added route audit logging in `backend/main.py` startup.
- Applied the validated source fixes to the live backend container and restarted it to confirm runtime behavior.

### Validation Result

- `/api/auth/health` -> `200`
- `/api/auth/login` -> `422`
- `/api/research/history` -> `401`
- `/api/memory/explorer/stats` -> `401`
- `/api/costs/summary` -> `401`
- `/api/voice/v2/health` -> `200`

These results confirm that the previously blocked surfaces now exist and are routed correctly through nginx.

## Notes

- The live route audit confirms `/api/auth/*`, `/api/research/*`, `/api/memory/explorer/*`, `/api/costs/*`, `/api/voice/v2/*`, `/api/governance-center/*`, `/api/executive/*`, and `/api/mission-replay/*` are registered.
- A separate residual issue remains for workspace upload routes: `python-multipart` is missing in the running backend environment, so workspace routes are unavailable.
- JWT secrets are currently ephemeral in the live container and should be set explicitly in environment configuration before release hardening is considered complete.
- The backend production image rebuild now succeeds and the running backend container has been recreated from the rebuilt image.