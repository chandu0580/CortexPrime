# ADR-121 — The trust boundary: default-deny authentication at the edge, a single-tenant fence for the V1 surface, verify-first ingestion, one approval authority, and an outbound guard at the request boundary

- **Status:** ACCEPTED (decision D1 interpreted as **FENCE** for this phase; ratification of that interpretation requested in `docs/PHASE_11_1_VERIFICATION_REPORT.md` §Decisions)
- **Date:** 2026-09-10
- **Phase:** 11.1 — autonomy boundary hardening
- **Parents:** `e67a4a7` — Phase 11.0 audit (G-01, G-05, G-06, G-07, G-08, G-24); ADR-038 (the legacy execution boundary); ADR-059 / ADR-088 (isolation and consequence); ADR-090 / ADR-113 (the governed approval and its digest); ADR-094 (the product API is a separate process); Phase 4.4 transport fabric (`backend/platform/transport/ssrf.py`)
- **Evidence:** `docs/PHASE_11_1_IMPLEMENTATION_MAP.md`, `docs/PHASE_11_1_VERIFICATION_REPORT.md`, `scripts/phase111_boundary_harness.py`
- **Change:** application-layer only. **No migration. No schema change. No new dependency. No governed-plane module touched.**

> **Numbering.** Highest used is 120; this is 121. Nothing overwritten.

## Context

Phase 11.0 measured the V1 surface honestly: 180 routers, of which roughly
ninety declare no authentication anywhere. At the start of this phase the
static census (`docs/PHASE_11_1_IMPLEMENTATION_MAP.md` §1) counted **394
unauthenticated state-changing routes and 543 unauthenticated reads** — far
more than the 38 the audit named, because the audit counted three modules and
the census counted the application. Among them: terraform `apply`/`destroy`
and ArgoCD `sync`/`rollback` with **no authentication of any kind**, a GitHub
route that accepted the webhook **secret in the request body**, a webhook
receiver that *recorded and emitted* unverified deliveries and answered 200,
an approval centre whose approver was a query parameter, and a tenant-context
middleware that copied an unauthenticated `X-Tenant-ID` header straight into
the Redis key namespace.

The governed engine (approval bound to an action digest, scoped authority,
fenced execution, independent verification) is real and verified. The
perimeter around it was not. This phase makes the perimeter true without
redesigning what it protects.

## Decisions

### D-1 Authentication is enforced once, at the edge, default-deny

`backend.safety.auth_perimeter.AuthPerimeterMiddleware` is installed
unconditionally in `backend/main.py`, just inside the rate limiter and
outside every other middleware. Every request needs a verified access token
(bearer or the HttpOnly cookie) unless its path is on one of two explicit
lists:

- **PUBLIC** — health (`/health`, `/health/*`, and every subsystem liveness probe
  whose last path segment is `health`, as the existing auth-enforcement contract
  already names them), OpenAPI, `/metrics`, and `/api/auth/*` (the routes that
  mint tokens; those that need one enforce it themselves).
- **SIGNED INGRESS** — `/api/github/webhook` and `/api/gitlab/webhook`, which
  authenticate by a provider secret verified by the route (D-3).

The perimeter reuses `backend.auth.dependencies.verify_request_token` — the
same signature, expiry and Redis-revocation check `require_user` uses — so the
edge and the routes cannot disagree about what a live token is. A verifier
crash is a refusal. Authentication proves identity; it grants nothing.

*Rejected alternative:* per-router `dependencies=[Depends(require_user)]` on
~90 routers. That is a rewrite, it leaves the next router to remember, and a
missed one is a silent hole. The perimeter makes the omission impossible.

### D-2 The V1 surface serves one tenant per deployment, and says which

The V1 stores cannot scope by tenant (35 of 57 tables, every Redis and JSON
store). This phase does not add `tenant_id` to them (out of scope and not
decided). It makes the only honest statement available: **a V1 deployment
serves exactly one tenant**, declared by `CORTEXPRIME_V1_TENANT_ID`.

- Declared: a token is admitted to a V1 route only when its verified
  `tenant_id` equals the declared tenant. Any other tenant, and any token
  without a tenant, is refused (403, audited as `perimeter.tenant_refused`).
- Undeclared: only tokens **without** a tenant claim are admitted (the
  single-operator install). A tenant-bearing token is refused with the
  instruction to declare the binding.

Governed tenant-aware surfaces in the same process (`/api/tenants`,
`/api/auth/*`) are exempt from the fence; the product API is a separate
process (ADR-094) and unaffected. `TenantContextMiddleware` now derives the
tenant from the verified token only; a header that disagrees is logged and
ignored.

This is decision **D1 interpreted as FENCE**. Scoping or retiring the V1
stores remains open and is listed for ratification.

### D-3 Ingestion is verified before it is parsed, and every decision is audited

`backend.safety.ingress_boundary` is the one place external data becomes an
event:

- Webhooks: the provider secret is verified **before** the body is parsed,
  before replay detection, before anything is recorded. Wrong or missing →
  401. No secret configured → **503**, never "accepted but unverified". The
  route that accepted the secret in the request body is removed.
- Token-authenticated ingestion (`/api/infrastructure/ingest/*`,
  `/webhook/kubernetes`, `/otel/v1/traces`): identity and tenant come from the
  verified token and the fence; the body is bounded
  (`CORTEXPRIME_INGRESS_MAX_BODY_BYTES`, 1 MiB); the payload must be a JSON
  object; the accepted event carries an `IngressEnvelope` — canonical identity
  `sha256(source|event_type|event_id)`, payload digest, `trust =
  untrusted_external`, `delivery = at-least-once`.
- Every accept and reject is written through the existing audit logger with
  who / tenant / source / integration / event id / reason / request id and
  **never** the payload or a secret. Audit is fire-and-forget (cached in
  process, persisted asynchronously) — an unreachable audit database cannot
  hold a request for a connect timeout, and it cannot reverse a refusal.
- Webhook tenant: the declared V1 tenant, or the literal
  `single-tenant-unbound` when none is declared. **No per-integration tenant
  mapping is invented**; that is Phase 11.3's governed ingress contract (D3).
- Exactly-once is not claimed. The provider receivers deduplicate by delivery
  id within their file-backed history; token ingestion carries an identity a
  consumer *may* deduplicate on, and no V1 consumer does.

### D-4 One approval authority; the V1 approval centre is fenced

`backend/approval_center` is an in-memory workflow engine with no tenant and
no action digest, whose approvals are replayed as real provider writes by
`enterprise_approval_action_dispatcher`. It is a second approval authority
beside `cp_approval` (ADR-090/113). Its mutation routes now sit behind
`guard_legacy_execution` (refused by default) and, when the migration flag is
set, the acting identity is the **token subject** — a request that names a
different approver is refused. Reads remain available to a verified identity.
The governed approval path is unchanged and re-verified by the 10.7–10.14
harness chain.

### D-5 Newly discovered execution surfaces join the ADR-038 inventory

Terraform `init/plan/apply/destroy/workspaces/select`, ArgoCD
`sync/refresh/rollback`, GitHub `translate/launch-mission` and the approval
centre mutations were reachable without a token and outside the legacy guard.
They are now gated (503 by default) and **inventoried** in
`LEGACY_EXECUTION_SURFACES` with `gated=True`, because an inventory that
implies coverage it lacks would be believed.

### D-6 Outbound requests are judged at the request boundary, by parsing

`backend.safety.outbound_guard` composes the transport fabric's own
judgement (`parse_url_structure`, `classify_literal`, `SystemAddressResolver`)
into `judge_outbound_url` and `guarded_get`. It refuses loopback, RFC1918,
link-local (all cloud metadata addresses), unique/site-local IPv6,
carrier-grade NAT, multicast, unspecified, broadcast and reserved ranges;
unsupported schemes; embedded credentials; control characters; decimal, hex,
octal and abbreviated IPv4; IPv4-mapped IPv6; and any hostname that resolves
to any of those (a host with one public and one private answer is refused).
`guarded_get` connects to the **judged address** with the original `Host` and
SNI, follows at most a few redirects and re-judges every hop, never forwards
caller headers across an origin, and reads a bounded body.

Applied at the real call sites: the CI workflow-log fetch
(`enterprise_cicd_intelligence`), the V1 HTTP sandbox tool, the quarantined
MCP web connector (redirects now off), the sandbox `git clone`, and
`guardrails_engine.check_external`, whose prefix regex is replaced by the
classifier. No new dependency: `httpx` and the fabric were already present.

### D-7 Untrusted data is contained, not sanitised

External text is data. It carries `trust = untrusted_external` for life; the
envelope takes tenant and principal from the boundary and ignores
authority-shaped keys in the payload; the governed model boundary's output
firewall (`extra="forbid"`) rejects every authoritative field; and the only V1
path from external text to execution (`launch-mission`) is behind the guard.
**Prompt-injection prevention is not claimed** — containment is: nothing an
external payload says can change a tenant, grant authority, claim an
approval, or invoke a tool.

## Consequences

- Every V1 route now requires a session. The frontend already sends the
  HttpOnly cookie with `credentials: "include"`, so logged-in users see no
  change; **any script or dashboard that pushed to `/api/infrastructure/...`
  without a token stops working** — that was the hole.
- A deployment with tenant memberships must set `CORTEXPRIME_V1_TENANT_ID` or
  its V1 pages answer 403 with the instruction. A single-operator install
  needs nothing.
- Webhooks without a configured secret are refused (503) instead of accepted
  unverified. Operators must set `GITHUB_WEBHOOK_SECRET` /
  `GITLAB_WEBHOOK_SECRET`.
- Two new rate-limit buckets (`webhook` 120/min per source, `ingest` 300/min
  per identity), env-configurable.
- The product pages `/investigator` and `/approvals` are linked from the
  sidebar; they were already real (Phases 10.1–10.4).

## Limitations (stated, not hidden)

- The fence is not scoping: within the declared tenant, V1 data remains
  tenant-unaware. Redis replay keys and rate-limit identities still carry no
  tenant; under one tenant per deployment they cannot collide across tenants.
- `guarded_get` pins addresses; a subprocess that resolves for itself (`git
  clone`) is judged but not pinned — a rebinding window remains there.
- Ingestion audit persistence is best-effort by the existing audit logger's
  design; the decision is enforced before the audit is written.
- `/metrics` remains public (Prometheus scrape); it carries request counters,
  no tenant data.
- The GuardrailsMiddleware screens top-level instruction-shaped fields only;
  nested payload text is not screened — by design it is data, not prompt.

## Decisions requested of the owner

- **D1 ratification:** FENCE (this ADR) as the interim answer, with scoping or
  per-feature retirement of the V1 stores as the durable one.
- Whether `/metrics` should require a token in production deployments.
