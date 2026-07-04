# SECURITY SPRINT 4 - CSP HARDENING & SECURITY HEADER VALIDATION

Date: 2026-06-14
Scope: Nginx browser security headers, frontend CSP hardening, live header validation, and CSP regression coverage.

## Executive Result

- Root HTML now serves a nonce-based CSP for scripts.
- `unsafe-inline` removed from nginx-managed CSP.
- `unsafe-eval` removed from production CSP.
- HSTS, frame protection, content-type protection, referrer policy, permissions policy, and CSP validated on root and backend/ops routes.
- Automated regression coverage added in `tests/test_security_headers.py`.

## Headers Audited

- `Content-Security-Policy`
- `Strict-Transport-Security`
- `X-Frame-Options`
- `X-Content-Type-Options`
- `Referrer-Policy`
- `Permissions-Policy`

## Changes Implemented

### 1) Nginx header hardening split by route type

Files changed:
- `infra/nginx/conf.d/cortex.conf`

Outcome:
- Retained global hardened headers at the HTTPS server level for frontend responses.
- Removed the old server-wide CSP that allowed `script-src 'unsafe-inline'` and `style-src 'unsafe-inline'`.
- Added explicit locked-down CSP on backend/operational locations:
  - `/api/*`
  - `/api/auth/*`
  - `/health*`
  - `/metrics`
  - `/ws`
  - `/docs`, `/redoc`, `/openapi.json`
  - `/computer/*`, `/operator/*`
- Restored the full header set inside those locations because nginx `add_header` directives do not inherit once a location defines its own headers.

Backend/ops CSP now returns:

```http
Content-Security-Policy: default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none';
```

### 2) Frontend nonce-based CSP

Files changed:
- `frontend/middleware.ts`
- `frontend/app/layout.tsx`

Outcome:
- Middleware now generates a per-request nonce (`x-nonce`).
- Frontend HTML responses now emit a request-scoped CSP using:

```http
script-src 'self' 'nonce-<value>' 'strict-dynamic'
```

- The middleware injects the CSP into both request and response headers so Next.js can attach the nonce to framework bootstrap scripts automatically.
- Root layout was made request-aware with `await headers()` so nonce injection remains available during SSR.

Root CSP now returns:

```http
default-src 'self';
script-src 'self' 'nonce-<value>' 'strict-dynamic';
style-src 'self';
style-src-elem 'self';
style-src-attr 'unsafe-inline';
img-src 'self' data: blob:;
font-src 'self' data:;
connect-src 'self' https: wss:;
media-src 'self' blob:;
object-src 'none';
frame-ancestors 'none';
base-uri 'self';
form-action 'self';
upgrade-insecure-requests;
```

## Unsafe Directive Status

### Removed

- `unsafe-inline` removed from nginx CSP.
- `unsafe-eval` removed from production CSP.

### Remaining and Why

- `style-src-attr 'unsafe-inline'` remains on frontend HTML responses.
- Reason: the current React UI still uses extensive inline `style={...}` attributes across the requested UI surfaces, including Executive Center, Governance Center, Replay, Memory Explorer, Demo Mode, Showcase, and shared components. Those style attributes are not covered by script nonces.
- This is a narrower allowance than the prior `style-src 'unsafe-inline'`, but it is still a remaining CSP weakness.

## Validation Evidence

### Commands executed

- `curl -k -I https://localhost/`
- `curl -k -I https://localhost/api/health`
- `curl -k -I https://localhost/health`
- `curl -k -I https://localhost/metrics`
- `curl -k https://localhost/`
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file backend/.env exec cortex-nginx nginx -t`
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file backend/.env exec cortex-nginx nginx -s reload`
- `cd frontend && npm run build`
- `docker compose -f docker-compose.yml -f docker-compose.prod.yml --env-file backend/.env up -d --build cortex-frontend cortex-nginx`
- `python -m pytest tests/test_security_headers.py -q`

### Live root header result

Observed on `https://localhost/`:

- `Content-Security-Policy` present
- `Strict-Transport-Security` present
- `X-Frame-Options` present
- `X-Content-Type-Options` present
- `Referrer-Policy` present
- `Permissions-Policy` present
- `x-nonce` present
- `script-src` no longer includes `unsafe-inline`
- `script-src` no longer includes `unsafe-eval`

### Live backend/ops header result

Observed on `https://localhost/health` and `https://localhost/metrics`:

- `Content-Security-Policy` present
- `Strict-Transport-Security` present
- `X-Frame-Options` present
- `X-Content-Type-Options` present
- `Referrer-Policy` present
- `Permissions-Policy` present

Observed on `https://localhost/api/health`:

- Headers are present and hardened.
- The route currently returns `404 Not Found` because the backend health endpoints are exposed as `/health` and `/health/system`, not `/api/health`.

### HTML evidence

Raw HTML fetched from `https://localhost/` showed:

- Next.js framework scripts still include inline bootstrap blocks.
- After the nonce middleware change, live root responses now emit `x-nonce`, allowing those scripts to run under nonce-based CSP rather than broad inline script allowance.

## Browser Validation

### Completed

- Browser-compatible CSP behavior was validated indirectly by:
  - successful frontend production build
  - successful frontend container rebuild
  - live root responses returning nonce-bearing CSP
  - live root responses returning nonce-tagged preload links

### Blockers / limitations

- Automated integrated-browser validation against `https://localhost` was blocked by the self-signed local TLS certificate (`ERR_CERT_AUTHORITY_INVALID`).
- Several requested routes are auth-protected by middleware:
  - `/executive`
  - `/governance-center`
  - `/memory-explorer`
  - `/replay`
  - `/demo`
- Without a valid authenticated browser session, those route surfaces could not be fully rendered in-browser for console/network inspection during this run.

## Automated Tests Added

New file:
- `tests/test_security_headers.py`

Coverage:
- nginx config contains all required hardened headers
- backend/ops routes emit locked-down CSP
- nginx config no longer contains `unsafe-inline` or `unsafe-eval`
- frontend middleware contains nonce-based script CSP
- root layout forces request-aware rendering needed for nonce injection

## Build / Runtime Validation Results

- `frontend` production build: passed
- `cortex-nginx` config test: passed
- `cortex-frontend` rebuild and redeploy: passed
- live header validation via `curl`: passed for root, `/health`, `/metrics`, and header presence on `/api/health`

## Remaining Risks

1. Full elimination of inline style allowance is not complete.
2. `style-src-attr 'unsafe-inline'` remains necessary until inline React style props are refactored into classes, CSS variables, or nonce-compatible style tags.
3. `frontend/middleware.ts` builds successfully, but Next.js 16 warns that the `middleware` file convention is deprecated in favor of `proxy.ts`; this is not a functional issue today, but should be migrated in a follow-up hardening pass.
4. Local browser-console validation on self-signed HTTPS remains partially blocked until the certificate is trusted by the integrated browser.

## Acceptance Status

- No `unsafe-eval`: achieved in production CSP.
- No broad `unsafe-inline` for scripts: achieved.
- All required security headers present on root: achieved.
- All required security headers present on backend/ops routes tested: achieved.
- Automated tests added: achieved.
- Audit report generated: achieved.
- Full removal of all inline style allowance: not yet achieved.

## Recommended Follow-up

1. Migrate `frontend/middleware.ts` to `frontend/proxy.ts` to match current Next.js guidance.
2. Refactor inline React `style={...}` usage on the protected dashboard routes so `style-src-attr 'unsafe-inline'` can be removed.
3. Re-run browser console/security tab validation after trusting the local TLS certificate and authenticating into protected routes.