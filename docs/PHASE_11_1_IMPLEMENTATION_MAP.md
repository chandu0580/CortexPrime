# PHASE 11.1 — Implementation Map: the trust boundary

- **Date:** 2026-09-10 · **Parent HEAD:** `e67a4a7` (Phase 11.0 audit) · **Branch:** `phase-1-foundation`
- **ADR:** `docs/adr/ADR-121-phase-11-1-trust-boundary.md` · **Verification:** `docs/PHASE_11_1_VERIFICATION_REPORT.md` · **Harness:** `scripts/phase111_boundary_harness.py`
- **Nature:** implementation, application layer only. No migration, no schema change, no dependency change, no governed-plane module changed.

## 1. Reconnaissance: what the perimeter actually was (FACT, from the repository at `e67a4a7`)

A static census of every `APIRouter` in `backend/` (router-level `dependencies=` and per-route `Depends(require_*)`, scratch script kept out of the tree) counted:

| Measure | Count |
|---|---|
| Router objects with at least one route | 180 |
| Unauthenticated **state-changing** routes (POST/PUT/PATCH/DELETE) | **394** |
| Unauthenticated **read** routes | **543** |
| Modules with router-level authentication | 9 (`memory_routes`, `approval_center_routes`, `cost_intelligence`, `fleet`, `workflow_designer`, `policy_simulation`, `executive_analytics`, `mcp` (2 of 3), `product` (separate process)) |

The 11.0 audit's "38 unauthenticated ingest/webhook routes" counted three modules. The application-wide number is above. Specific findings that shaped the design:

| # | Finding | Where | Class |
|---|---|---|---|
| R-1 | terraform `init/plan/apply/destroy/workspaces/select` and ArgoCD `sync/refresh/rollback` reachable with **no authentication at all** and outside the ADR-038 guard; Phase 9.11's "0 ungated surfaces" census missed them because they never say "execute" | `enterprise_infrastructure_routes.py` | P0 |
| R-2 | `POST /api/github/webhook/payload` accepted the **signing secret in the request body** — a verification the caller controls | `enterprise_github_routes.py:100` | P0 |
| R-3 | An unverified GitHub delivery was parsed, **recorded, emitted on the event bus** and answered 200 `verified:false`; no secret configured meant every delivery was "accepted, unverified" | `enterprise_github_integration.py:233-275` | P1 |
| R-4 | `TenantContextMiddleware` copied an **unauthenticated `X-Tenant-ID`** into the tenant context and from there into `RedisKeys._tp()` — the Redis key namespace of the request; its token branch used a per-request `InMemoryKeyStore` from the retired identity subsystem and never validated a real token | `identity/tenant/tenant_context.py`, `infrastructure/redis/keys.py:78` | P1 |
| R-5 | The V1 approval centre's approver/overrider was a **query parameter**; approvals replay real provider writes through `enterprise_approval_action_dispatcher` (five executors) | `approval_center_routes.py` | P1 |
| R-6 | The documented SSRF primitive is `backend/mcp/connectors/web.py` (constructor-quarantined since 4.4), but `enterprise_cicd_intelligence.get_workflow_logs` fetched a provider-supplied `logs_url` with a bare `httpx` client, the V1 HTTP sandbox tool dialled any URL, and the sandbox `git clone` took any scheme; the only V1 defence was the prefix regex in `guardrails_engine.check_external` | multiple | P1 |
| R-7 | `/api/triggers` (policies that auto-generate missions) and `/api/incidents` had no authentication | `autonomous_trigger_routes.py`, `enterprise_incidents_routes.py` | P1 |
| R-8 | The product API is a **separate process** (ADR-094); nothing in `backend.main` is governed except `/api/auth/*` and `/api/tenants` | `backend/api/product/server.py` | design fact |
| R-9 | Kubernetes-state ingestion (`/ingest/pod` etc.) is *additionally* fenced inside the service by the Phase 9.11 world-state guard (`LEGACY_EXECUTION_DISABLED`) — discovered by the harness, not the census | `enterprise_infrastructure_intelligence.py` | fact |
| R-10 | The revocation list fails **open** when Redis is unavailable in `development/dev/local/test` environments by module default, closed otherwise | `auth/token_blacklist.py:50-67` | recorded |

## 2. Trust boundary map (as implemented)

```
EXTERNAL ACTOR
   │
   ▼  RateLimitMiddleware          buckets: webhook 120/min per source, ingest 300/min per identity (+ existing)
   ▼  AuthPerimeterMiddleware      default-deny: verified token (bearer|cookie) unless PUBLIC or SIGNED_INGRESS
   │                               V1 tenant fence: CORTEXPRIME_V1_TENANT_ID (declared ⇒ equality; undeclared ⇒ tenant-less only)
   ▼  TenantContextMiddleware      tenant from the VERIFIED token only; header may restate, never choose
   ▼  GuardrailsMiddleware         (existing) top-level instruction fields screened
   ▼  RequestIDMiddleware, CORS    (existing)
   │
   ├─ PUBLIC: /health*, */health (subsystem liveness probes), /docs, /openapi.json, /redoc, /metrics, /api/auth/*
   ├─ SIGNED INGRESS: /api/github/webhook (HMAC), /api/gitlab/webhook (token)
   │        └─ ingress_boundary.verify_*_delivery  → 503 unconfigured / 401 unverified / principal(tenant=declared|unbound)
   │        └─ receiver (replay dedupe by delivery id) → IngressEnvelope → audit(accepted)
   ├─ TOKEN INGRESS: /api/infrastructure/ingest/*, /webhook/kubernetes, /otel/v1/traces
   │        └─ require_ingest_principal (require_user + fence + body bound) → schema → IngressEnvelope → audit
   ├─ V1 EXECUTION SURFACES: guard_legacy_execution (503 default) — 18 inventoried, incl. terraform/ArgoCD/launch-mission/approval-centre
   ├─ V1 READS/WRITES (everything else): authenticated + fenced; data stays tenant-unaware (D1 FENCE)
   └─ GOVERNED (this process): /api/tenants (require_admin), /api/auth/* — fence-exempt
                                product API: separate process, product_context only (unchanged)

OUTBOUND (V1): outbound_guard.judge_outbound_url / guarded_get at the request boundary
               → CI log fetch, HTTP sandbox tool, MCP web connector, sandbox git clone, guardrails.check_external
```

For every path that can reach a state-changing capability:

| Path | Identity | Tenant | Authority | Approval | Credential | Audit | Verification |
|---|---|---|---|---|---|---|---|
| Governed remediation (product API, separate process) | `product_context` (token) | token, live `cp_tenant` | scoped grants (ADR-098/100) | `cp_approval` + action digest (ADR-090) | broker, worker holds none (ADR-089) | `cw_*`, `cp_*` ledgers | independent read (ADR-091) — **unchanged** |
| V1 terraform / ArgoCD / launch-mission / approval-centre mutations | perimeter token | fence | **none → refused by `guard_legacy_execution` (503)** | none → refused | process env (never reached) | perimeter/guard logs | n/a (refused) |
| V1 ingestion (token) | perimeter + `require_ingest_principal` | token = declared V1 tenant | n/a (advisory stores) | n/a | none | `ingress.accepted/rejected` | n/a; K8s-state writes also fenced by 9.11 guard |
| Provider webhooks | provider secret (HMAC / token) | declared V1 tenant or `single-tenant-unbound` | n/a (advisory) | n/a | none | `ingress.accepted/rejected` | n/a |
| Outbound from V1 code | n/a | n/a | address policy at the request | n/a | caller headers never cross origin | warning log with reason | n/a |

Out of scope, explicitly: per-integration webhook→tenant mapping (Phase 11.3, D3); tenant scoping of V1 stores (D1 durable answer); a production trigger (11.2).

## 3. V1 data classification (STEP 3)

| Class | What | Handling in 11.1 |
|---|---|---|
| **TENANT_SCOPED** | infrastructure intelligence (clusters/pods/deployments/alerts/logs/traces), incidents (`alert_incident_history.json`), mission replay (Redis `cx:replay:*` + PG 0025), V1 memory (episodic/semantic/reflection), knowledge entries, cost tracking, approval-centre workflows, trigger policies/history, webhook delivery history, analytics | **fenced**: readable/writable only by the declared V1 tenant's identities; not scoped inside the store |
| **SYSTEM_SCOPED** | rate-limit counters (`cx:rl:*`), revocation list, health, metrics, connector singletons, router availability | unchanged; counters keyed by identity |
| **DERIVED_SCOPED** | correlator incidents, recommendations, learning patterns, dashboards | derived from tenant-scoped inputs ⇒ same fence |
| **SHARED_READONLY** | approval policies (`approval_center/policies.py` constants), `SUPPORTED_PLATFORMS`, `INFRA_EVENTS`, `TRIGGER_SOURCES` | authenticated read |
| **UNKNOWN → decided as fenced** | V1 event bus, cognition streams (`cx:cog:*`), workspace/research stores | fence; ownership question deferred to D1's durable answer |

Redis: `RedisKeys._tp()` namespaces by the DB tenant context, which now comes only from the verified token. Under one tenant per deployment, keys cannot collide across tenants; within the tenant they are keyed as before.

## 4. Files changed

### New
| File | Purpose |
|---|---|
| `backend/safety/auth_perimeter.py` | `AuthPerimeterMiddleware`, PUBLIC / SIGNED_INGRESS / FENCE_EXEMPT lists, `v1_tenant_verdict`, `PerimeterIdentity` |
| `backend/safety/ingress_boundary.py` | `IngressPrincipal`, `IngressEnvelope`, `require_ingest_principal`, `bound_body`, `audit_ingress`, `verify_github_delivery`, `verify_gitlab_delivery` |
| `backend/safety/outbound_guard.py` | `judge_outbound_url`, `assert_outbound_url`, `guarded_get` (pinned connect, per-hop judgement, bounded body) |
| `scripts/phase111_boundary_harness.py` | real-app red team + failure + integrity harness |
| `tests/test_auth_perimeter.py`, `tests/test_ingress_boundary.py`, `tests/test_outbound_guard.py`, `tests/test_trust_boundary_injection.py` | permanent tests |
| `docs/adr/ADR-121-…`, `docs/PHASE_11_1_IMPLEMENTATION_MAP.md`, `docs/PHASE_11_1_VERIFICATION_REPORT.md`, `docs/phase111_boundary_report.json` | record |

### Changed (surgical)
| File | Change |
|---|---|
| `backend/main.py` | installs `AuthPerimeterMiddleware` unconditionally, between tenant-context and rate-limit registration |
| `backend/auth/dependencies.py` | `verify_request_token()` extracted; `_decode_and_verify` delegates — one verifier for routes and edge |
| `backend/identity/tenant/tenant_context.py` | tenant from the verified token only; header honoured only when equal; context cleared in `finally` |
| `backend/api/enterprise_github_routes.py` | `router` (require_user) + `webhook_router` (HMAC via boundary); verify-first; `/webhook/payload` **removed**; `translate`/`launch-mission` behind the legacy guard; unused `json` import dropped |
| `backend/api/enterprise_gitlab_routes.py` | same split; verify-first |
| `backend/api/router_registry.py` | registers both webhook routers |
| `backend/api/enterprise_infrastructure_routes.py` | router-level `require_user`; 12 ingest routes + K8s webhook + OTLP through `require_ingest_principal` with envelope + audit; terraform ×5 and ArgoCD ×3 behind the legacy guard |
| `backend/api/legacy_execution_boundary.py` | 4 inventory entries added (18 total), all `gated=True` |
| `backend/api/approval_center_routes.py` | mutations behind the legacy guard; `_bind_actor` binds approver/from_user/overridden_by to the token subject |
| `backend/api/autonomous_trigger_routes.py`, `backend/api/enterprise_incidents_routes.py` | router-level `require_user` |
| `backend/services/enterprise_github_integration.py`, `backend/services/enterprise_gitlab_integration.py` | module-level `verify_github_signature` / `verify_gitlab_token`; receivers delegate |
| `backend/services/enterprise_cicd_intelligence.py` | `logs_url` fetched through `guarded_get` |
| `backend/execution/sandbox/interfaces.py` | HTTP sandbox: judged, pinned connect, redirects off, `trust_env=False` |
| `backend/mcp/connectors/web.py` | judged per fetch; `follow_redirects=False`, `trust_env=False` |
| `backend/services/enterprise_execution_sandbox.py` | `git clone` URL judged (https only) before the subprocess |
| `backend/safety/guardrails_engine.py` | `check_external` uses the classifier instead of the prefix regex |
| `backend/safety/rate_limiter.py` | `webhook` and `ingest` buckets + classification |
| `backend/api/legacy_network_inventory.py` | web-connector disposition text updated to the truth |
| `frontend/components/dashboard/Sidebar.tsx` | `/investigator` and `/approvals` entries |
| `.env.example` | new variables documented |
| `tests/test_enterprise_github_routes_webhook.py`, `tests/test_enterprise_gitlab_routes_webhook.py`, `tests/test_enterprise_incidents_routes.py`, `tests/test_identity_tenant_context.py` | expectations moved to the new contract (unverified → 401/503; header alone sets nothing; reads need identity) |

### Not changed (deliberately)
`backend/contexts/*`, `backend/world`, `backend/assurance`, `backend/intelligence`, `backend/platform/*`, `backend/api/product/*`, every migration, `requirements*.txt`, `package.json`.

## 5. Production trigger readiness (STEP 13)

`backend/api/kubernetes_watch_driver.py` is complete and crash-safe (ADR-083) and has no production runner. What 11.2 needs, and what 11.1 delivers toward it:

| Requirement | State after 11.1 |
|---|---|
| A supervised process that composes reader/observer/repository/leadership-store/clock and loops `KubernetesWatchDriver` | **not built** (11.2) |
| A credential path (KUBECONFIG, read-only) | exists (ADR-082) |
| Lease/fencing for a single leader | exists (`cp_node_lease`, ADR-092) |
| Authenticated, tenant-bound ingress for pushed signals | **delivered**: token ingestion with fence and envelope; provider webhooks verify-first |
| A place where an external signal cannot become an instruction | **delivered**: envelope trust, guard on the V1 launch path, model-output firewall unchanged |
| No autonomous provider write | **preserved**: 0 writes; every V1 write surface refuses by default |

No production triggering was enabled.

## 6. Environment variables introduced

| Variable | Default | Meaning |
|---|---|---|
| `CORTEXPRIME_V1_TENANT_ID` | unset | the one tenant the V1 surface serves (see ADR-121 D-2) |
| `CORTEXPRIME_INGRESS_MAX_BODY_BYTES` | 1048576 | bound on ingestion/webhook bodies |
| `RATE_LIMIT_WEBHOOK` | 120 | webhook deliveries per minute per source |
| `RATE_LIMIT_INGEST` | 300 | ingestion calls per minute per identity |
| `GITHUB_WEBHOOK_SECRET` / `GITLAB_WEBHOOK_SECRET` | unset | now **required** for the webhook to accept anything |
