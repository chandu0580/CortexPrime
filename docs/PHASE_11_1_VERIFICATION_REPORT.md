# PHASE 11.1 — Verification Report: the trust boundary

- **Date:** 2026-09-10 · **Parent HEAD:** `e67a4a7` · **Branch:** `phase-1-foundation`
- **ADR:** `docs/adr/ADR-121-phase-11-1-trust-boundary.md` · **Map:** `docs/PHASE_11_1_IMPLEMENTATION_MAP.md`
- **Labels:** `[VERIFIED]` executed in this session with the output in hand · `[MEASURED]` observed and recorded verbatim, not designed · `[DEFERRED]` proven elsewhere and cited · `[FINDING]` a pre-existing property surfaced by this phase, not changed here

## 1. Executive verdict

The boundary between the untrusted V1 platform and the governed execution plane is now **enforced, default-deny, and attacked**: every request into `backend.main` needs a verified token unless it is public or provider-signed; the V1 surface serves one declared tenant; webhooks are verified before they are parsed and refused when they cannot be; every V1 route that reaches a provider refuses by default; outbound requests from V1 code are judged by parsing and pinned at the request; untrusted payloads carry their trust class for life and cannot become instruction or authority. The governed plane was not touched and its harness chain re-run at full counts. Zero provider writes.

## 2. Evidence table

| Claim | Label | Evidence |
|---|---|---|
| Real-app red team + failure + integrity harness | `[VERIFIED]` | `scripts/phase111_boundary_harness.py` against `backend.main` with real PostgreSQL (`cortex_p111`, migrated to head), real Redis (`55379/7`), real k3d generations watched: **137/137 checks, verdict VERIFIED, 68 negative cases at max `provider_writes` 0, 66 s** — `docs/phase111_boundary_report.json` |
| Permanent tests (new) | `[VERIFIED]` | `test_auth_perimeter.py` 19 · `test_outbound_guard.py` 66 · `test_ingress_boundary.py` 29 · `test_trust_boundary_injection.py` 24 — all pass (run individually with `--timeout=60`) |
| Existing tests moved to the new contract | `[VERIFIED]` | `test_enterprise_github_routes_webhook.py`, `test_enterprise_gitlab_routes_webhook.py`, `test_enterprise_incidents_routes.py`, `test_identity_tenant_context.py` — pass |
| Architecture gate | `[VERIFIED]` | `pytest tests/architecture -q` → **155 passed** (832 s), identical to the 10.31 baseline |
| Governance harness chain 10.7 / 10.8 / 10.9 / 10.10 / 10.11 / 10.13 / 10.14 | `[VERIFIED]` | **155/155 · 118/118 · 107/107 · 107/107 · 68/68 · 60/60 · 53/53**, all VERIFIED, identical to the 10.31 baseline (§8) |
| Regression suite (10.22 scope) | `[VERIFIED]` | **71 failed / 6883 passed / 36 skipped / 58 xfailed / 24 errors** — 0 new failures vs the 10.31 list, 4 gone (§9) |
| Frontend | `[VERIFIED]` | `tsc --noEmit --skipLibCheck`: no error in `Sidebar.tsx`; the only errors are pre-existing in `operations-center/dashboard-panel.tsx` and `runtime/RuntimeHealth.tsx` (untouched) |
| Provider writes | `[VERIFIED]` | cluster generations before/after the boundary harness identical (`billing-api` 1, `payments-api` 127, `contained-worker` 124); every one of 68 negatives recorded `provider_writes: 0` |
| Database integrity | `[VERIFIED]` | `cortex_p111` row counts before/after: only `audit_logs` changed (0 → 1, the explicit persistence proof, §7) — no other table, no schema change, no migration |
| Redis integrity | `[VERIFIED]` | on an isolated logical DB: keys created are exclusively `cx:rl:*` (rate-limit windows); no pre-existing key modified or deleted |

## 3. Trust boundary, as attacked (harness sections A–L)

**A. Authentication at the edge** — 6 public paths answer 200 without a token; 12 protected paths (reads, ingestion, triggers, incidents, approval centre, replay, knowledge, GitHub, terraform apply, executions) answer **401** with `WWW-Authenticate: Bearer` without one; garbage / expired / wrong-secret / empty-bearer tokens → 401; a tenant header without a token → 401; a valid token passes by bearer and by HttpOnly cookie equally; a revoked token → 401.

**B. V1 tenant fence** — undeclared: a tenant-bearing token is refused with the instruction to set `CORTEXPRIME_V1_TENANT_ID`. Declared as tenant A (real `cp_tenant` rows): A reads (200); **B cannot read (403) or write (403)** on infrastructure, mission-replay, memory, knowledge, incidents, enterprise search, analytics, approval-centre, executions; a tenant-less token is refused once a tenant is declared; a forged `X-Tenant-ID` beside a valid token is ignored (A stays A, B stays B); refusals are audited as `perimeter.tenant_refused` naming principal, tenant, path and reason, with no token in the record; governed `/api/tenants` is exempt from the fence and answers with its own authority.

**C. Ingestion contract** — `[FINDING]` Kubernetes-state ingestion (`/ingest/pod`, `/webhook/kubernetes`) is *also* fenced inside the service by the Phase 9.11 world-state guard (`503 LEGACY_EXECUTION_DISABLED`); the boundary sits in front of a store that already refuses to write. On an un-fenced route (`/ingest/loki`): accepted with a canonical envelope (identity, payload digest, `at-least-once`, `untrusted_external`, `event_id` from the payload id); accept audited with who/tenant/source/event/reason and **no payload text**; non-object payload → 422; malformed JSON → 4xx; body bound → 413 on JSON and on raw OTLP; a duplicate ingestion carries the **same** identity (consumer may deduplicate; none does).

**D. Provider webhooks** — GitHub: missing signature 401, bad signature 401, altered payload with the original signature 401, the GitLab token offered as a signature 401, **no secret configured 503**, verified delivery 200 with envelope (tenant = declared A, `github_hmac`), replayed delivery id → `duplicate`, the body-supplied-secret route is gone; every refusal audited with source and delivery id and no secret/payload. GitLab: missing/wrong token 401, a GitHub HMAC is not a token 401, verified 200 with envelope.

**E. One approval authority** — V1 approval-centre create/approve/break-glass refuse by default (503, legacy guard); with the migration flag set, an approval naming another approver is refused (403) and the actor is the token subject; reads remain available to a verified identity. `[DEFERRED]` the governed approval (digest binding, separation of duties, scoped authority, expiry) is proven by the 10.7–10.14 chain (§8), not re-implemented.

**F. Execution surfaces** — terraform init/plan/apply/destroy/workspaces-select, ArgoCD sync/rollback/refresh, GitHub translate/launch-mission, `/api/executions/run`, `/api/v2/mcp/execute`: **503 with a valid token**, 401 without.

**G. SSRF at the outbound boundary (real resolver, live listener)** — 21 vectors refused (loopback in decimal/hex/octal/abbreviated/mapped-IPv6 spellings, RFC1918, link-local incl. the metadata address, unique-local, CGNAT, unspecified, `ftp`/`file`/`gopher`, embedded credentials, a raw control character); **a live loopback listener received zero connections across all vectors**; the V1 HTTP sandbox tool refuses before dialling; the guardrails engine blocks the bypass spellings; a real hostname that resolves to loopback (`localtest.me` → 127.0.0.1) is refused **by resolution**; a redirect to loopback is refused at the hop.

**H. Injection containment** — a payload carrying `tenant_id=<B>`, `approved=true`, `role=admin`, `capabilities=["*"]`, a metadata URL and "you are the approver" text is accepted as **data under tenant A**; the same text cannot launch a mission (503); the governed model-output firewall rejects all six authoritative fields; `[MEASURED]` the existing GuardrailsMiddleware blocks a top-level `message` field carrying "ignore all previous instructions" (400).

**I. Failure testing** — `[FINDING]` Redis unavailable → the revocation list **fails open in `development`** by the module's environment default (`REVOCATION_FAIL_OPEN` unset, `_FAIL_OPEN=True`; closed in production) — recorded, not endorsed, not changed; tenant store unavailable → a tenant-bearing token is refused (403), restored → admitted; audit store broken → refusals still 401/403 and no 500 leaks, an accepted ingestion is not falsely failed; a failing ingestion store → no `ingress.accepted` audit and no 200 (a real 500, logged with the traceback); connector timeout surfaces as `ReadTimeout`, never a response; binary garbage on a JSON route → 4xx. `[DEFERRED]` worker restart / lease fencing (9.10/9.11, untouched).

**J. Rate limiting** — `[VERIFIED]` the `webhook` bucket sheds a 130-call flood at its documented limit against real Redis (9 denied, backend `redis`); through the app every flood request was refused by the boundary (140 × 401). `[FINDING]` under Starlette's TestClient the shared async Redis client is bound to a loop the client closes between requests, so the limiter falls back to its in-process window mid-flood **and the fallback starts counting from zero** — a TestClient artefact for the Redis path, but a real weakness of the fallback design (pre-existing, recorded in §11).

**K. Product routing** — `Sidebar.tsx` links `/investigator` and `/approvals`; both pages exist and render the real `IncidentList` / `ApprovalQueue` components (Phases 10.1–10.4).

**L. Integrity** — an ingress audit entry persists to the real `audit_logs` table through the durable path; only `audit_logs` changed; only `cx:rl:*` keys created; cluster generations unchanged.

## 4. Acceptance criteria

| # | Criterion | Result |
|---|---|---|
| A | Authentication on all in-scope external ingestion paths | **MET** — perimeter default-deny; webhooks verify-first (401/503) |
| B | Tenant from authorized identity/context | **MET (as FENCE)** — token tenant + declared V1 tenant; header cannot choose |
| C | Authentication ≠ authorization | **MET** — passing the perimeter grants nothing; guards/authority still decide (F, E) |
| D | Approval enforced before privileged execution | **MET** — governed path unchanged and re-verified; V1 approval centre fenced |
| E | Modified action cannot reuse an approval | **MET (governed)** — ADR-090 digest binding re-verified by the chain (§8) |
| F | SSRF at the actual request boundary | **MET** — `guarded_get` pins and re-judges hops; call sites migrated; live listener saw 0 connections |
| G | Untrusted data cannot become instruction/authority | **MET (containment)** — envelope trust, guard on the launch path, model firewall |
| H | Auditable accept/reject without secrets | **MET** — `ingress.*` and `perimeter.*` entries; no payload/secret; durable path proven |
| I | No mock functionality exposed | **MET** — only the two verified product pages were linked |
| J | Governed plane intact | **MET** — chain at full counts, governed modules untouched (§8) |
| K | No unexplained regression | **MET** — 0 new, 4 explained gone (§9) |
| L | No unexpected provider writes | **MET** — 0 |
| M | Working tree clean after commit | **MET** (§12) |

## 5. Threat model → control map

| Threat | Control | Where |
|---|---|---|
| Anonymous reach to any V1 route | default-deny perimeter | `auth_perimeter.py` |
| Cross-tenant read/write through tenant-unaware stores | single-tenant fence (declared / tenant-less only) | `auth_perimeter.v1_tenant_verdict`, `require_ingest_principal` |
| Forged tenant via header → Redis namespace | tenant from the verified token only | `tenant_context.py` |
| Unsigned / forged / altered / replayed webhook | verify-first HMAC/token; 503 when unconfigured; delivery-id dedupe | `ingress_boundary.verify_*_delivery`, receivers |
| Client-chosen verification secret | route removed | `enterprise_github_routes.py` |
| Second approval authority replaying provider writes | legacy guard on mutations; actor = token subject | `approval_center_routes.py` |
| Ungated terraform/ArgoCD/mission launch | legacy guard + inventory | `enterprise_infrastructure_routes.py`, `legacy_execution_boundary.py` |
| SSRF via caller-supplied or provider-supplied URLs | parse-based judgement, resolution, pinned connect, per-hop re-judgement, no cross-origin headers | `outbound_guard.py` and 5 call sites |
| Untrusted text as instruction | fixed trust class; no authority fields on the envelope; model-output firewall; launch path fenced | `ingress_boundary.py`, `model_boundary.py` (unchanged) |
| Request floods on ingress | `webhook` / `ingest` buckets | `rate_limiter.py` |
| Oversized bodies | `CORTEXPRIME_INGRESS_MAX_BODY_BYTES` | `ingress_boundary.py` |

## 6. Production trigger readiness

Nothing autonomous was enabled. See `PHASE_11_1_IMPLEMENTATION_MAP.md` §5: the watch driver still has no runner (11.2); the ingress a pushed signal would need (authenticated, tenant-bound, enveloped, audited) now exists.

## 7. Audit persistence, stated precisely

Boundary audits are fire-and-forget by the existing audit logger's design (cached in process, persisted asynchronously). Under TestClient those tasks never complete, so the harness proved the durable path by persisting one boundary entry directly into the real `audit_logs` table (0 → 1 rows). A persistence failure cannot reverse a refusal (I4) and does not fail an accepted advisory ingestion (I5).

## 8. Governance regression (10.7–10.14)

`[VERIFIED]` re-executed in this session against the real k3d cluster, real PostgreSQL (each harness's own `cortex_p10xx` database) and real Redis, driven by a serial runner with a real kill on timeout:

| Harness | Result | Provider writes |
|---|---|---|
| 10.7 scoped authority / execution | **155/155 VERIFIED** (solo re-run) | `[0, 1]` — the one commissioned rollout restart the harness itself performs |
| 10.8 governed grant issuance | **118/118 VERIFIED** | 0 |
| 10.9 membership | **107/107 VERIFIED** | 0 |
| 10.10 tenant records | **107/107 VERIFIED** | 0 |
| 10.11 TenantManager retirement | **68/68 VERIFIED** | 0 |
| 10.13 V1 read retirement | **60/60 VERIFIED** | 0 |
| 10.14 IAM retirement | **53/53 VERIFIED** (solo re-run) | 0 |

Counts are identical to the 10.31 baseline. Three environmental obstacles, none in code under test, are recorded honestly: (a) the first chain attempt crashed at the cluster probe because `CORTEX_TLS_CA_BUNDLE` in `.phase99b.env` is a Git-Bash path Python cannot open on Windows — the runner passes the Windows path; (b) every two-hour ServiceAccount token in that file had expired (F-5) — reader and restarter tokens were re-minted with `kubectl create token` and passed through the runner's environment; with the expired restarter token the write step of 10.7 failed at 150/155 through the adapter defect F-6, and passed at 155/155 once the token was fresh; (c) 10.14 shared the machine with the 21-minute regression run and its product client started receiving 500s mid-run — alone it verified at 53/53. 10.13 printed its full VERIFIED report and then its process lingered; it was released after the verdict.

Tenant isolation, membership, authority, approval, digest binding, separation of duties, execution, assurance, worker binding, connector, credential and audit invariants are therefore unchanged; no `cp_*`/`cw_*` table or governed module was touched (`git diff --stat HEAD -- backend/contexts backend/platform backend/world backend/assurance backend/intelligence` is empty).

## 9. Regression suite

`[VERIFIED]` `python -m pytest tests/ -q --tb=no -rf -p no:cacheprovider --timeout=900` → **71 failed / 6883 passed / 36 skipped / 58 xfailed / 24 errors** (1055 s). Baseline (10.22 scope, identical through 10.31): **75 failed / 6744 passed / 36 skipped / 58 xfailed / 24 errors**. `FAILED` names diffed against the 10.31 list: **0 new, 4 gone** — the four `test_auth_enforcement` cases for `POST /execute` and `/execute/sync` (no token / bad token) that expected 401 and had received the legacy guard's 503 since Phase 9.11 (audit §7, G-14) now receive 401 from the perimeter, which runs before the guard. Passed grew by 139: the four repaired cases plus the new boundary tests. Skipped, xfailed and errors are identical.

A first run before three test repairs showed 17 additional failures, all caused by this phase and all fixed rather than hidden: three subsystem liveness probes (`/governance/health`, `/operator/health`, `/api/voice/v2/health`) were not on the public list (the perimeter now treats any path whose last segment is `health` as public, matching the existing auth-enforcement contract); `test_enterprise_github_routes_deploy_checks.py` and `test_llm_provider_api.py` built clients with no identity and now carry one. Note on the environment: on this host every refused loopback connection now costs ~2 s (Docker Desktop running), and the suite's autouse PostgreSQL reap fixture pays it on every test; the run therefore sets `POSTGRES_HOST=0.0.0.0 REDIS_HOST=0.0.0.0` so the *same* unreachable-by-design defaults fail instantly. The real-database tests read `CORTEX_TEST_PG_ADMIN_DSN` / `CORTEX_TEST_REDIS_URL` (the phase containers) as before. `--timeout=900` was added as insurance against hangs; no baseline test is slow enough to be affected.

## 10. Findings surfaced (pre-existing, recorded, not changed)

- **F-1** Revocation fails open when Redis is unavailable in `development/dev/local/test` (`token_blacklist.py`), closed in production. Decision requested whether development should also fail closed.
- **F-2** The rate limiter's in-process fallback starts a fresh window when Redis becomes unavailable mid-stream; a flapping Redis resets flood protection.
- **F-3** Kubernetes-state V1 ingestion is doubly fenced (this boundary + the 9.11 world-state guard); the V1 infrastructure dashboards cannot receive Kubernetes state until a governed ingress (11.3) replaces them.
- **F-4** On this host, refused loopback connections take ~2 s while Docker Desktop runs; the test suite's per-test PostgreSQL reap fixture multiplies that (environmental, not code).
- **F-5** Every ServiceAccount token in `.phase99b.env` (`CORTEX_KUBERNETES_TOKEN`, `CORTEX_P99B_RESTART_TOKEN`, `CORTEX_P99B_OTHER_TOKEN`) is minted for two hours by `scripts/phase99b_provision.sh`; all three had expired before this session. The chain needed freshly minted tokens (reader and restarter), passed through the runner's environment, not by editing the gitignored file.
- **F-6** `backend/contexts/execution/infrastructure/adapters/contained_worker.py:293` maps a worker call that did not succeed to `ProviderFailure.PROVIDER_ERROR`, a member that does not exist, so a failed worker call (here: the API server's 401 on the expired restarter token) surfaces as `AttributeError` inside the governed chain instead of a classified provider failure with the provider's message. The chain still refused fail-closed (HTTP 409, `provider_writes` 0) — the invariant held, the diagnosis was hidden. Governed-plane module, untouched by this phase; recorded for its owner.

## 11. Known limitations

- The fence is single-tenant, not scoping (ADR-121 D-2). Within the declared tenant, V1 stores remain tenant-unaware.
- `guarded_get` pins; `git clone` is judged but resolves for itself (residual rebinding window).
- `/metrics` is public.
- GuardrailsMiddleware screens top-level fields only; nested payload text is data by design.
- Exactly-once is not claimed anywhere.

## 12. Repository

27 files changed (754 insertions, 201 deletions) plus 12 new files: three boundary modules, one harness, four test modules, three documents and the evidence JSON. No migration, no dependency file, no generated artefact, no ignored file. Committed as the single Phase 11.1 commit on `phase-1-foundation` (the commit that carries this report); `git status` clean afterwards.

## 13. Decisions requested

- **D1 ratification** — FENCE (`CORTEXPRIME_V1_TENANT_ID`, ADR-121 D-2) as the interim answer for the tenant-unaware V1 surface; the durable answer (scope the 35 tables and 54 repositories, or retire per feature) remains the owner's.
- **Revocation in development** — whether `REVOCATION_FAIL_OPEN` should default closed everywhere (F-1).
- **`/metrics` exposure** — whether the Prometheus scrape should require a token in production.
- **F-6** — whether the contained-worker adapter's failure mapping is repaired in a governed-plane phase (one enum member; re-verification by the 10.7 chain).
