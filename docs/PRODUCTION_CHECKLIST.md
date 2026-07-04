# CortexPrime — Production Readiness Checklist

Run this checklist before every production deployment.  
Mark each item ✅ before proceeding to the next section.

---

## Section 1 — Secrets & Credentials

- [ ] `JWT_SECRET_KEY` is ≥32 characters and cryptographically random (`secrets.token_urlsafe(48)`)
- [ ] `JWT_REFRESH_SECRET` is ≥32 characters and **different** from `JWT_SECRET_KEY`
- [ ] `POSTGRES_PASSWORD` is strong and not the default
- [ ] `OPENAI_API_KEY` is valid and has sufficient quota
- [ ] No secrets committed to git (`git log --all -S "sk-" -- backend/.env` returns nothing)
- [ ] `backend/.env` is listed in `.gitignore`
- [ ] `SENTRY_DSN` is set (both backend and `NEXT_PUBLIC_SENTRY_DSN` for frontend)
- [ ] `ANTHROPIC_API_KEY` / `GOOGLE_API_KEY` set if those providers are used
- [ ] RabbitMQ default credentials changed from `guest:guest`
- [ ] Redis `requirepass` set if Redis is network-exposed

**Verification:**
```bash
grep -r "sk-" .git/    # should return nothing
curl -sk https://yourdomain.com/health/system | python3 -m json.tool | grep sentry
```

---

## Section 2 — TLS / HTTPS

- [ ] TLS certificate is valid (not self-signed in production)
- [ ] Certificate is from a trusted CA (e.g. Let's Encrypt)
- [ ] Certificate expiry is >30 days away
- [ ] HSTS header is present (`Strict-Transport-Security`)
- [ ] HTTP redirects to HTTPS (nginx `return 301 https://$host$request_uri`)
- [ ] Certificate covers the correct domain(s)
- [ ] Auto-renewal is configured (`certbot renew --dry-run`)

**Verification:**
```bash
curl -sk https://yourdomain.com -D - | grep -i "strict-transport"
openssl s_client -connect yourdomain.com:443 -showcerts 2>&1 | grep "Not After"
```

---

## Section 3 — Database

- [ ] PostgreSQL is running and healthy
- [ ] pgvector extension is installed (`SELECT * FROM pg_extension WHERE extname='vector'`)
- [ ] Alembic migrations are at head (`alembic current` shows `0004 (head)`)
- [ ] `alembic_version` table exists and has correct revision
- [ ] `cost_tracking` table exists (created outside Alembic in v0.9)
- [ ] Database backup is running (cron job configured)
- [ ] Last backup is <24 hours old
- [ ] Backup restore has been tested (dry run)
- [ ] Connection pool settings match expected load

**Verification:**
```bash
docker exec cortex-postgres psql -U cortex -d cortexdb \
  -c "SELECT version_num FROM alembic_version;"
docker exec cortex-postgres psql -U cortex -d cortexdb \
  -c "\dt"  # list all tables
ls -lh backups/*.sql* | tail -3
```

---

## Section 4 — Monitoring & Alerting

- [ ] Prometheus is running and scraping (`/metrics` returns `cortex_*` metrics)
- [ ] Grafana is running with 3 dashboards loaded
- [ ] `/health/system` returns `status: healthy` or known degraded reason
- [ ] Sentry is receiving test events (trigger a test error to verify)
- [ ] Uptime monitor configured for `https://yourdomain.com/health`
- [ ] Alert channel (Slack/PagerDuty/email) is configured for:
  - [ ] Backend `status: critical`
  - [ ] SSL certificate expiry <14 days
  - [ ] Error rate >5% in 5-minute window
  - [ ] Disk usage >80%

**Verification:**
```bash
curl -sk https://yourdomain.com/metrics | grep "^cortex_missions"
curl -sk https://yourdomain.com/health/system | python3 -m json.tool | head -10
```

---

## Section 5 — Security Headers

- [ ] `X-Frame-Options: DENY` present
- [ ] `X-Content-Type-Options: nosniff` present
- [ ] `Referrer-Policy: strict-origin-when-cross-origin` present
- [ ] `Strict-Transport-Security` present with `max-age≥31536000`
- [ ] `Content-Security-Policy` present
- [ ] `Permissions-Policy` present
- [ ] `/docs` and `/redoc` return 404 in production (`ENV=production`)
- [ ] CORS `allow_origins` is NOT `*` — only exact frontend URL

**Verification:**
```bash
curl -sk https://yourdomain.com -D - 2>&1 | grep -iE "x-frame|x-content|strict-transport|content-security"
curl -sk -o /dev/null -w "%{http_code}" https://yourdomain.com/docs   # should be 404
curl -sk -o /dev/null -w "%{http_code}" https://yourdomain.com/redoc  # should be 404
```

---

## Section 6 — Rate Limiting

- [ ] `RATE_LIMIT_ENABLED=true`
- [ ] Redis rate limiter is active (check startup logs: "Rate Limit middleware active")
- [ ] `/api/auth/login` has stricter limit (5/sec at nginx level)
- [ ] WebSocket `WS_AUTH_REQUIRED=true`
- [ ] 429 responses include `Retry-After` header

**Verification:**
```bash
# Should return 429 after 5 rapid requests to auth
for i in {1..10}; do
  curl -sk -o /dev/null -w "%{http_code}\n" -X POST https://yourdomain.com/api/auth/login \
    -H "Content-Type: application/json" -d '{"username":"test","password":"test"}'
done
```

---

## Section 7 — Observability (Sprint 3)

- [ ] `X-Request-ID` header present on every response
- [ ] `/health/system` shows `request_tracing: healthy`
- [ ] `/health/system` shows `exception_handler: healthy`
- [ ] 500 errors return standard envelope (no traceback in response body)
- [ ] 404 errors return `{"success": false, "error": {"code": "NOT_FOUND", ...}}`
- [ ] Structured logs (JSON) visible in `docker logs cortex-backend`

**Verification:**
```bash
curl -sk https://yourdomain.com/health -D - | grep -i "x-request-id"
curl -sk https://yourdomain.com/api/nonexistent | python3 -m json.tool
docker logs cortex-backend --tail 5 | python3 -m json.tool
```

---

## Section 8 — Performance

- [ ] Backend running 4 uvicorn workers (`--workers 4` in prod override)
- [ ] Docker resource limits set (`cpus`, `memory` in docker-compose.prod.yml)
- [ ] Redis connection pool is sized correctly
- [ ] PostgreSQL `max_connections` appropriate for worker count
- [ ] nginx `worker_processes auto` is set
- [ ] Response times <500ms for `/health` and `/health/system`

**Verification:**
```bash
docker stats --no-stream
time curl -sk https://yourdomain.com/health > /dev/null
time curl -sk https://yourdomain.com/health/system > /dev/null
```

---

## Section 9 — CI/CD

- [ ] GitHub Actions `test.yml` passes on `main` branch
- [ ] GitHub Actions `security.yml` has run within last 7 days
- [ ] No critical vulnerabilities in latest `pip-audit` report
- [ ] Branch protection enabled on `main` (require PR + CI pass)
- [ ] Release workflow tested with a pre-release tag
- [ ] Docker images in GHCR are accessible

### Branch Protection Rules (GitHub → Settings → Branches)

**`main` branch:**
- Require a pull request before merging: ✓
- Require status checks to pass: `backend-test`, `frontend-build`
- Require conversation resolution before merging: ✓
- Restrict force pushes: ✓
- Restrict deletions: ✓

**`develop` branch:**
- Require a pull request before merging: ✓
- Require status checks to pass: `backend-test`, `frontend-build`

**`release/*` branches:**
- Require a pull request: ✓
- Restrict pushes to maintainers only: ✓

---

## Section 10 — Final Smoke Test

Run these in sequence after each production deploy:

```bash
DOMAIN="https://yourdomain.com"

echo "=== Root ===" ; curl -sk "${DOMAIN}" -o /dev/null -w "%{http_code}\n"
echo "=== Health ===" ; curl -sk "${DOMAIN}/health" | python3 -m json.tool | grep status
echo "=== System health ===" ; curl -sk "${DOMAIN}/health/system" | python3 -m json.tool | grep '"status"' | head -3
echo "=== Metrics ===" ; curl -sk "${DOMAIN}/metrics" | grep "^cortex_" | head -3
echo "=== Auth (expect 422) ===" ; curl -sk -X POST "${DOMAIN}/api/auth/login" -w "\n%{http_code}\n"
echo "=== 404 envelope ===" ; curl -sk "${DOMAIN}/api/this-does-not-exist" | python3 -m json.tool
echo "=== Request ID ===" ; curl -sk -D - "${DOMAIN}/health" 2>&1 | grep -i "x-request-id"
echo "=== Showcase ===" ; curl -sk "${DOMAIN}/showcase" -o /dev/null -w "%{http_code}\n"
```

**All checks should return HTTP 200 except:**
- `/api/auth/login` (no body) → 422 (validation error)
- `/api/this-does-not-exist` → 404 with error envelope

---

## Release Approval Sign-off

| Role | Name | Date | Signature |
|---|---|---|---|
| Engineering Lead | | | |
| Security Review | | | |
| DevOps / Infra | | | |

> Production deploys to `main` require all three sign-offs.
> Hotfix deploys require Engineering Lead + one other approver.
