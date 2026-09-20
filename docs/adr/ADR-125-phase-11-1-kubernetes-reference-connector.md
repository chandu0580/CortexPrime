# ADR-125 — The Kubernetes reference connector: one manifest-driven connector architecture, Vault-issued per-action credentials, boot-time commissioning, a tenant↔target connection enforced twice, connector health through the governed path, and a Helm-installed governed runtime

- **Status:** ACCEPTED
- **Date:** 2026-09-19
- **Phase:** 11.1-K — Kubernetes reference connector
- **Parents:** `2c51f7f` (connector reality audit: S-1..S-9), `e9dfd63` (ADR-124), ADR-121 (trust boundary), ADR-122 (signal fabric), ADR-086/089/090 (contained workers, approval digest), ADR-056 (fenced audit)
- **Evidence:** `docs/PHASE_11_1_KUBERNETES_CONNECTOR_VERIFICATION.md`, `scripts/phase111k_kubernetes_connector_harness.py`, `docs/phase111k_kubernetes_connector_report.json`, `tests/connector_fabric/`
- **Change:** no migration, no new table, no new third-party dependency in `backend/` (the slim image pins versions the repository already uses). No cluster-wide RBAC. No arbitrary API, shell or raw client.

> **Numbering.** Highest used is 124; this is 125.

## Context

The audit (`2c51f7f`) found 29 connectors and none production-ready. Three were
integrated with the governed Capability Fabric; the rest were V1 connectors
with raw write paths (S-1, S-2), and the gateway's rate stage was never wired
(S-3). Even the integrated Kubernetes connector could only be run by a harness:
capabilities were registered by a script, credentials were static tokens in
environment variables, health did not exist, the governed loops started only
inside the V1 monolith, and there was no install path.

## Decisions

### D-1 One connector architecture: the Capability Fabric, driven by a manifest

A connector is a `CORTEX_CONNECTOR_FACTORIES` extension returning adapters, one
`ConnectorManifest`, connection scopes, credential-provider builders and health
probes (`docs/CONNECTOR_ARCHITECTURE.md`). The manifest is pure
(`backend/contracts/connector_manifest.py`); schemas are content-addressed
(`backend/api/connector_schema.py`). V1 connectors are frozen: their raw
non-GET requests are refused outside `_execute`'s effect scope
(`guard_raw_request`, enforced by BND-EFFECT-GATE), and the V1 write routes
under `/api/git`, `/api/orchestrator/{autonomous,route,reflect}` and
`/api/runtime/autonomous-loop` pass `guard_legacy_execution` (closes S-1, S-2).

### D-2 Registration is a boot act, idempotent, and refuses contract drift

`commission_connector` registers every manifest capability with its full
contract, validates, enables and trusts it; an identical contract is
`already_current`, a different one under the same version is a `conflict`
reported by health, never an overwrite.

### D-3 Ten capabilities, and why only these

Eight reads (pods.list, pod.get, pod.logs, deployment.get, events.list,
replicasets.list, pods.watch, access.review) and the two writes that already
existed with contained workers and independent verification (deployment.rollback,
workload.rollout_restart). `deployments.list` is in the catalog but used by
nothing, so it is not shipped. No write was invented to look complete.

### D-4 Credentials: Vault only in production, per action, from the pod identity

The runtime logs in to Vault with its projected ServiceAccount token (Kubernetes
auth) and asks Vault's Kubernetes secrets engine for a short-lived token (TTL
≥ 10 min, Vault's minimum) for one of three namespace-confined ServiceAccounts
per provider. The broker reveals it at one site. Static tokens are a
development path and are refused in production (extension, env validation).

### D-5 Tenancy: a connection binds a tenant to a target; enforced twice

`ConnectionScope(tenant, providers, targets)`; the gateway input stage refuses a
target outside the invoking tenant's connection, and the provider refuses it
again because the credential minted for that tenant is RBAC-confined to the
connected namespace. The product API reports another tenant's connection as
DISABLED with no detail.

### D-6 Health is produced through the governed path

`kubernetes.access.review` (SelfSubjectAccessReview) is a governed READ; the
probe runs one per required permission in the connection tenant's context with
its own Vault-issued credential, then checks each worker's `/healthz` over
verified TLS through the transport broker. States: CONNECTED, DEGRADED,
AUTHENTICATION_REQUIRED, RATE_LIMITED, UNAVAILABLE, MISCONFIGURED, DISABLED.
Each failing check carries the refusal's own words.

### D-7 Rate limiting at the gateway; Retry-After honoured; writes never retried

Token buckets per tenant+capability, tenant and provider
(`CORTEX_RATE_LIMIT_*`), refusals counted. A provider's `Retry-After` is a floor
on read retries; writes are NEVER-retry by contract.

### D-8 The deployable: the slim product server with the governed plane

`start_governed_plane` is the one place the loops start (used by
`backend.main` and by `backend.api.product.server` with
`CORTEX_RUN_GOVERNED_PLANE=1`). The image `deploy/governed-runtime` carries only
`backend/`, runs non-root with a read-only root filesystem. The chart
`helm/cortexprime-governed` installs migrations (pre-install Job), the runtime,
Redis for token revocation, the two contained workers, their egress policy and
namespace-only RBAC, and refuses to render without its four required values.

## Findings from the installed product (all fixed in this phase)

Each was invisible to in-process harnesses and development-mode runs, and
surfaced only when the product was installed the way an operator installs it.

| # | Finding | Severity | Fix |
|---|---|---|---|
| F-1 | Transport and credential brokers called `AuditRuntime.record` without the tenant scope; every fact raised `TypeError`, was swallowed, and **the durable audit chain received no transport or credential fact in any deployment** | High | pass `TenantScope` + actor; log the cause; regression tests against a real `AuditRuntime` |
| F-2 | `GovernedCapabilityReader` (and the writer, by inheritance) defaulted to `DEVELOPMENT`; in production every governed read was refused `environment_not_permitted`; the product remediation service hardcoded `DEVELOPMENT` | High | the runtime's own environment |
| F-3 | asyncpg refuses libpq `sslmode=`; the migration Job failed for every TLS database URL | High | translate to `ssl=` for asyncpg, keep `sslmode` for psycopg2 |
| F-4 | the migration env loads ORM models needing `pgvector`; the schema needs the `vector` extension | Medium | image dependency; documented database prerequisite |
| F-5 | the chart did not give the model adapter `LLM_MODEL`; every proposal degraded to recommendation-only (fail-safe, but silent) | Medium | chart sets it; start-up validation names a half-configured model |
| F-6 | the product server configured no logging; a deployed runtime logged nothing below WARNING | Medium | `LOG_LEVEL` (default INFO) |
| F-7 | `access.review` declared a 64 KiB response budget, below the transport's 1 MiB frame budget; the policy refused to construct | Medium (own bug) | 1 MiB; test over every shipped operation |
| F-8 | health said `authorization_denied` without which layer refused | Low | the refusal reason is carried into the check |
| F-9 | after a Vault restart the cached Vault login was dead and every acquisition failed for the rest of its cached lifetime (~36 min) although a fresh login would have worked at once | High | a refused mint invalidates the login and retries once; proven live by destroying and reconfiguring Vault under a running runtime |
| F-10 | an incoherent `CORTEX_RATE_LIMIT_*` budget (per-capability above per-tenant) crash-looped the runtime with a traceback | Medium | start-up validation names the variables |

## Consequences

- Kubernetes is installable with one Vault step and one `helm` command and
  reports its own health. The architecture is the template for the next
  connector. Record run: **92/92 VERIFIED**
  (`docs/phase111k_kubernetes_connector_report.json`), including one governed
  rollback that the world confirmed and one whose verification FAILED and was
  escalated without a retry.
- Stated limits: one connection per deployment; one runtime replica; per-process
  rate limiter; a write worker's own RBAC is not health-checked; RBAC cannot
  restrict fields of a `patch deployments` (the worker's fixed request shape
  does); the V1 connectors are gated, not migrated.
