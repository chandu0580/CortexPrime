# Phase 11.1-K — Kubernetes reference connector: verification report

Decision record: `docs/adr/ADR-125-phase-11-1-kubernetes-reference-connector.md`.
Architecture: `docs/CONNECTOR_ARCHITECTURE.md`. Operator guide:
`docs/KUBERNETES_CONNECTOR_RUNBOOK.md`. Machine-readable evidence:
`docs/phase111k_kubernetes_connector_report.json`.

Every claim is marked **FACT** (observed in this phase, with the evidence
named), **INFERENCE** (reasoned from facts, not directly observed) or
**UNKNOWN** (not established here). Maturity is not overstated: this is one
connector proven on one disposable cluster, once per scenario.

---

## 1. Executive summary

**FACT.** Kubernetes is now installed and operated as a product: one Vault
configuration script plus one `helm upgrade --install` produces a running
governed runtime that commissions ten typed capabilities at boot, takes every
Kubernetes credential from Vault per action, reports its own health through the
product API, and remediates a real incident under human approval with
independent verification.

**FACT.** The record run (`docs/phase111k_kubernetes_connector_report.json`)
exercised install, health, credentials, RBAC, tenancy, a successful incident, a
**failed-verification** incident, five failure injections, metrics, audit,
secret scans and the evaluation suite against a live k3d cluster, a TLS
PostgreSQL, a TLS Vault and the operator's hosted GLM-5.2 model.

**FACT.** Installing the product exposed ten real defects that in-process
harnesses and development-mode runs had hidden - including *no transport or
credential audit fact had ever been written by any deployment* and *every
governed read in a production environment was refused*. All ten are fixed, and
eight carry a regression test (section 19).

**INFERENCE.** The architecture is reusable: the manifest, commissioning,
scope, health, error and evaluation modules are connector-agnostic, and the next
connector supplies an adapter, a manifest and a credential adapter.

**UNKNOWN.** Behaviour at scale (many namespaces, many tenants, sustained load),
long-running stability beyond hours, upgrade/rollback of the chart across
versions, and non-k3d distributions.

---

## 2. Research findings

**FACT.** Before implementation the repository was inspected against the audit
`docs/PHASE_CONNECTOR_REALITY_AUDIT.md` (commit `2c51f7f`):

- The governed Capability Fabric was the only model with typed contracts,
  authorization, credentials, transport policy, audit and verification.
- V1 connectors (`backend/connectors/`) reach providers through
  `BaseConnector._request` with credentials from the environment: no capability
  contract, no approval, no verification.
- Three connectors were integrated with the fabric (Kubernetes, Prometheus,
  Alertmanager); capabilities were registered by harness scripts, not at boot.
- The governed loops started only inside `backend.main` (the V1 monolith image).
- **No fundamental architectural conflict was found**, so implementation
  proceeded (the mandate's stop condition did not trigger).

---

## 3. Architecture decisions

**FACT** (ADR-125, decisions D-1…D-8):

1. One connector model: the Capability Fabric, driven by a declarative manifest.
2. Registration is a boot act, idempotent, refusing contract drift.
3. Ten capabilities: eight reads plus the two pre-existing governed writes.
4. Production credentials come from Vault only, per action, via the pod identity.
5. A *connection* binds one tenant to one namespace, enforced at the gateway and
   again by provider RBAC.
6. Health is produced through the governed path, not a side channel.
7. Rate limiting at the gateway; `Retry-After` honoured; writes never retried.
8. The deployable is the slim product server plus the governed plane, installed
   by a Helm chart.

V1 is frozen and gated, not migrated (mandate section 26): its raw write paths
are refused outside `_execute` and its autonomous routes are behind the legacy
guard.

---

## 4. Files changed

**FACT.** 37 modified files, 25 new paths. New modules:

| Area | Files |
|---|---|
| Contracts | `backend/contracts/connector_manifest.py`, `backend/contracts/connector_errors.py` |
| Connector | `backend/api/kubernetes_connector.py`, `backend/api/connector_schema.py`, `backend/api/connector_scope.py`, `backend/api/connector_commissioning.py`, `backend/api/connector_health.py`, `backend/api/connector_evaluation.py` |
| Runtime | `backend/api/governed_plane.py`, `backend/api/product/connector_routes.py`, `backend/contexts/execution/infrastructure/rate_limiting.py`, `backend/observability/prometheus_recorder.py` |
| Credentials | `backend/platform/credentials/vault_kubernetes.py` |
| Deployment | `deploy/governed-runtime/`, `helm/cortexprime-governed/`, `scripts/connector/configure_vault_kubernetes.sh` |
| Tests | `tests/connector_fabric/` (6 files), `tests/connectors/test_raw_request_gate.py` |
| Harness | `scripts/phase111k_provision.sh`, `scripts/phase111k_kubernetes_connector_harness.py` |
| Docs | ADR-125, `CONNECTOR_ARCHITECTURE.md`, `KUBERNETES_CONNECTOR_RUNBOOK.md`, this report |

Modified: the gateway composition, the application runtime, the product app and
server, the transport and credential brokers, the Kubernetes adapter, the
effects gate and the thirteen V1 connectors it now guards, the retry domain, the
DSN builder, `backend/main.py`, the architecture rules.

---

## 5. Connector contract

**FACT.** `CapabilityManifest` declares, per capability: id, version, operation,
provider, description, category, profile (risk, reversibility, compensation,
autonomy ceiling, verification requirement, timeout, side-effect class),
required provider permissions and the tenant-scoped target parameter; `mutates`
and `retry` are derived. Input and output schemas are derived from the adapter's
operation spec and registered as sha256-addressed references, so a contract
change is a new version rather than a silent edit.

---

## 6. Capabilities

**FACT.** Ten, all commissioned at boot in the record run:

| Capability | Effect | Risk | Retry | Verification | Provider |
|---|---|---|---|---|---|
| `kubernetes.pods.list` | read | low | safe | none | kubernetes |
| `kubernetes.pod.get` | read | low | safe | none | kubernetes |
| `kubernetes.pod.logs` | read | low | safe | none | kubernetes |
| `kubernetes.deployment.get` | read | low | safe | none | kubernetes |
| `kubernetes.events.list` | read | low | safe | none | kubernetes |
| `kubernetes.replicasets.list` | read | low | safe | none | kubernetes |
| `kubernetes.pods.watch` | read | low | safe | none | kubernetes |
| `kubernetes.access.review` | read | low | safe | none | kubernetes |
| `kubernetes.deployment.rollback` | irreversible write (compensable) | high | **never** | independent readback | kubernetes-contained-rollback |
| `kubernetes.workload.rollout_restart` | irreversible write | high | **never** | independent readback | kubernetes-contained |

**FACT.** No raw request, exec, shell, apply or delete capability exists; the
record run asserts this over the shipped manifest.

---

## 7. Authentication

**FACT.** The runtime authenticates to Vault with its own projected
ServiceAccount token (Vault Kubernetes auth), re-read from disk at every login.
It authenticates to the Kubernetes API with a ServiceAccount token Vault mints
per action, over HTTPS with the cluster CA, through the transport broker with
the endpoint's address pinned at composition. The record run verified the
runtime Deployment carries no Vault token and no Kubernetes token in its
environment or ConfigMap.

---

## 8. Credential lifecycle

**FACT.** Per acquisition: Vault login (cached until 60 % of its lease) →
`POST kubernetes/creds/<role>` with the connection's namespace and a 10-minute
TTL → material handed to the transport adapter, revealed at one site, expiring
at `min(authority window, Vault lease)`. The record run observed Vault's lease
table growing for the reader role, the three ServiceAccounts carrying no token
Secret and no automounted token, and no ServiceAccount-token Secret in the
namespace.

**FACT.** A Vault restart (or a revoked token) is recovered automatically: a
refused mint invalidates the cached login and retries once (finding F-9).

---

## 9. Governance

**FACT.** Every invocation passes the gateway: identity → tenant → capability →
input (schema + connection scope) → digest → approval → rate → credential. In
the record run: a member without approve authority was refused (403), another
tenant's approver was refused (404), a consumed approval was refused on replay
(409), and nothing was written before approval.

---

## 10. Tenancy

**FACT.** A Kubernetes namespace is not a tenant; a connection binds one tenant
to one cluster namespace. Tenant B saw the connector as DISABLED with no detail
about A's namespace, cluster or tenant id; B saw none of A's plans; a B member
presenting A's tenant claim was refused (403). The connection scope refused
both cross-tenant targets with its own message; A's reader credential was
refused in B's namespace by the API server.

**INFERENCE.** The gateway-stage refusal is proven in-process against the real
validator and the real gateway fixture rather than through the deployed pod,
because the product exposes no API that invokes an arbitrary read — the pod-level
evidence is that B has no connection and no credential binding at all.

---

## 11. Execution

**FACT.** Reads run through `GovernedCapabilityReader` (one in flight per
process); writes run in a contained worker (own container, own ServiceAccount,
non-root, read-only rootfs, no standing credential, egress restricted to the API
server) and are dispatched by the scheduler after authorization and approval.

---

## 12. Verification

**FACT.** Both outcomes were produced on the real cluster in the record run:

- success: the rollback restored the healthy template, the Deployment's
  generation advanced by exactly one, the object carried the
  `cortexprime.io/rolled-back-by-action` annotation, and the plan reached
  `verified` with verdict `supported`;
- failure: with the rollback target's dependency removed underneath it, the
  same path produced `verification_failed → discrepancy → recovery_decided →
  escalated`, exactly one write, no retry, and it was never reported as success.

---

## 13. Error handling

**FACT.** `ConnectorErrorClass` has the twelve required classes and every
provider or platform failure maps into it (`classify_provider_failure`,
`classify_status`, `classify_failure_text`). Health states are derived from the
error class, and the refusal's own words are carried into the health check.

---

## 14. Retry behaviour

**FACT.** Reads are `SAFE` (retryable), writes are `NEVER`; a provider's
`Retry-After` becomes the floor of the retry delay, capped by `max_delay`, only
in the RETRY branch (`backend/contexts/execution/domain/retry.py`, tests in
`tests/connector_fabric/test_rate_limiting.py`).

**UNKNOWN.** A real API-server 429 with `Retry-After` was not provoked on the
live cluster; retry behaviour is proven deterministically, and the real run
shows no duplicate write (one Vault lease, one generation increment).

---

## 15. Rate limiting

**FACT.** `TokenBucketRateLimiter` is wired into the gateway's rate stage
(closing audit finding S-3) with per-capability, per-tenant and per-provider
budgets from `CORTEX_RATE_LIMIT_*`, refusals counted as
`cortex_gateway_rate_limited{scope,provider}`. An incoherent budget is refused —
and, after finding F-10, reported at start-up by name instead of crash-looping.

---

## 16. Observability

**FACT.** Prometheus metrics on `CORTEX_METRICS_PORT` (9102), including
`cortex_connector_health`. Label names that could carry a credential are
dropped and values capped. The record run scraped the endpoint and asserted no
credential-like label. The product server now configures logging (`LOG_LEVEL`,
default INFO) so commissioning, the loops and health are visible in the pod log.

---

## 17. Audit

**FACT.** The durable, fenced audit chain (`cp_audit_record`) receives
connector operations, identity events and execution outcomes. Before this phase
it received **no transport or credential fact at all** in any deployment
(finding F-1).

---

## 18. Deployment

**FACT.** One chart (`helm/cortexprime-governed`): migrations as a pre-install
Job, the runtime (1 replica, Recreate), Redis for token revocation, the two
contained workers with namespace RBAC and an egress NetworkPolicy, three
ServiceAccounts with no automounted token, and a Role letting Vault mint tokens
for exactly those three. It refuses to render without `connection.tenant`,
`connection.namespace`, `database.existingSecret` or `vault.address`, naming the
missing value. Nothing cluster-scoped is created. The image carries only
`backend/`, runs as uid 65532 with a read-only root filesystem, and contains no
`.env`.

Prerequisites (stated): Kubernetes with NetworkPolicy enforcement, PostgreSQL 16+
**with pgvector**, TLS, and a Vault whose ServiceAccount can review tokens.

---

## 19. Security findings and fixes

**FACT.** Audit findings closed by this phase:

| Finding | Severity | Status |
|---|---|---|
| S-1 `/api/git/*` wrote through `GitHubConnector._request`, bypassing the effect gate | Critical | **Closed**: `guard_raw_request` at 13 connector raw methods (enforced by BND-EFFECT-GATE) and `guard_legacy_execution` on the five `/api/git` write routes, all in the legacy inventory |
| S-2 ungated autonomous routes | High | **Closed**: `/api/runtime/autonomous-loop`, `/api/orchestrator/{autonomous,route,reflect}` guarded and inventoried |
| S-3 gateway rate limiter never supplied | Medium | **Closed**: wired, configurable, counted |

S-4…S-9 (medium/low) concern other connectors and V1 surfaces and are **OPEN**,
untouched by this phase per the mandate's "do not touch future connectors".

**FACT.** Defects found by installing the product (each fixed, each with a
regression test):

| # | Finding | Severity | Regression test |
|---|---|---|---|
| F-1 | both brokers called `AuditRuntime.record` without the tenant scope; every fact raised `TypeError`, was swallowed, and no deployment ever wrote a transport or credential audit fact | High | `tests/connector_fabric/test_broker_audit.py` |
| F-2 | `GovernedCapabilityReader`/`Writer` defaulted to `DEVELOPMENT`; in production every governed read was refused `environment_not_permitted`; the product remediation service hardcoded `DEVELOPMENT` | High | `test_deployment.py::TestGovernedReaderEnvironment` |
| F-3 | asyncpg rejects libpq `sslmode=`; the migration Job failed against every TLS database URL | High | `test_deployment.py::TestDsn` |
| F-4 | the migration env needs `pgvector`; the schema needs the `vector` extension | Medium | `test_deployment.py::test_image_has_the_migration_dependencies` |
| F-5 | the chart never set `LLM_MODEL`; the provider reported "not configured" and every proposal silently degraded to recommendation-only | Medium | `test_deployment.py` (chart + start-up validation) |
| F-6 | the product server configured no logging; a deployed runtime logged nothing below WARNING | Medium | — (observable in the record run's pod log) |
| F-7 | `access.review` declared a 64 KiB response budget, below the transport's 1 MiB frame budget, so its connection policy refused to construct | Medium | `test_deployment.py::test_every_shipped_operation_budget_admits_a_transport_policy` |
| F-8 | health reported `authorization_denied` without naming which layer refused | Low | — (the refusal reason is now in the health check) |
| F-9 | after a Vault restart the cached Vault login was dead and every acquisition failed for ~36 minutes although a fresh login would have worked | High | `test_vault_kubernetes.py::TestStaleVaultLogin` + the live Vault-restart injection |
| F-10 | an incoherent `CORTEX_RATE_LIMIT_*` budget crash-looped the runtime with a traceback instead of naming the variables | Medium | `test_deployment.py::test_an_incoherent_rate_limit_is_reported_at_start_not_as_a_crash_loop` |

**FACT.** No credential value was printed, committed, logged or written to any
report: the record run scans the runtime log, this phase's report, the durable
store and the image for the model key, the signing secret, the Redis password
and the database password.

---

## 20. Deterministic test results

**FACT.** `tests/connector_fabric/` - **145 passed** (contract, schemas, error
taxonomy, rate limiting and Retry-After, Vault Kubernetes credentials including
stale-login recovery, broker audit, the deployable, the evaluation suite).

**FACT.** `tests/connectors/test_raw_request_gate.py` - **62 passed** (S-1/S-2:
every V1 connector's raw write refused outside the effect scope; every guarded
route present in the legacy inventory).

**FACT.** Architecture gates (`tests/architecture`,
`tests/platform/test_dependency_isolation.py`) pass except one **pre-existing**
failure at HEAD, unrelated to this phase (`credentials/inspection.py` imports
`base64` - a file this phase did not touch).

**FACT.** Full repository regression: section 28.

---

## 21. Real Kubernetes test results

**FACT.** Record run (`docs/phase111k_kubernetes_connector_report.json`):
**92/92 checks passed, verdict VERIFIED**, 2681 s wall clock, against k3d
cluster `cortex-p99b`, a TLS PostgreSQL (pgvector), a TLS Vault and GLM-5.2
through the governed model boundary.

| Evidence | Measurement |
|---|---|
| `helm upgrade --install --wait` | 23.1 s; release `deployed` |
| schema | migrated by the chart's pre-install Job (`alembic_version` = `0025_mission_replay_events`) |
| connector health | `CONNECTED` - "connected; 10 capabilities available"; check duration 24.9 s |
| time to CONNECTED after the pod was ready | 5.6 s |
| commissioning | 10 commissioned, 0 conflicts, 0 failed, 0 skipped; after a restart 10 `already_current`, no new registry rows |
| objects in the connected namespace | 19 (2 worker Deployments + Services, 3 ServiceAccounts, 4 Roles/RoleBindings, egress policy, TLS secrets) |
| objects in a namespace that is not connected | 0 |
| Vault reader leases | 45 minted during the run; role TTL 600 s |
| real reads | pods.list, pod.get, pod.logs, deployment.get, events.list, replicasets.list, pods.watch, access.review - all governed, all with Vault-minted tokens |
| **real write (success)** | generation 2 to 3; template restored to the healthy digest `f5736fc7...`; annotation `cortexprime.io/rolled-back-by-action=50c4aae0...`; pods healthy again |
| plan stages | `planned, autonomy_decided, approval_requested, approval_granted, executing, executed, verified, learned, closed` |
| failure to approval request | 265.9 s (detection, investigation, planning, real model calls) |
| approval to closed | 41.7 s |
| Vault rollbacker leases | 0 to 1 (exactly one credential minted for the write) |
| **real write (failed verification)** | `executing, executed, verification_failed, discrepancy, recovery_decided, escalated, learned, closed`; exactly one write; no retry |

---

## 22. Failure test results

**FACT.** Five injections, each named by health, each recovered:

| Injection | Health reported | Recovered |
|---|---|---|
| reader RoleBinding deleted | `MISCONFIGURED`, naming all seven missing permissions | yes, without a restart |
| Vault reader role deleted | `AUTHENTICATION_REQUIRED` - "invocation refused at dispatch: credential_unavailable" | yes |
| Vault scaled to zero, restarted **empty**, reconfigured | `AUTHENTICATION_REQUIRED` (never CONNECTED on a stale answer) | yes - re-authenticated with its pod identity, **no restart** (proves F-9) |
| rollback worker scaled to zero | `DEGRADED`; reads still available; `platform.kubernetes.deployment.rollback` listed unavailable ("worker unreachable") | yes |
| misconfiguration (`vault.address` empty; `connection.namespace` empty) | helm refuses, naming the value; the running release untouched and still CONNECTED | n/a |

**FACT.** The operator's Vault configuration script was re-run inside the pod
and converged (idempotent) - which is how the emptied Vault was repaired.

---

## 23. Security test results

**FACT.** Negative matrix - every case refused, **0 cluster writes** each:

| Case | Refused by |
|---|---|
| cross-tenant target A to B's namespace | gateway input stage: "namespace 'cortex-conn-b' is outside this tenant's kubernetes connection" |
| cross-tenant target B to A's namespace | gateway input stage: "this tenant has no connection for kubernetes" |
| approval by a member without approve authority | approval authority (HTTP 403) |
| approval by another tenant's approver | tenant boundary (HTTP 404) |
| replaying the consumed approval | approval consumption (HTTP 409) |
| unauthenticated call to the connector API | HTTP 401 |

**FACT.** Least privilege, as the API server itself answered it:

- the runtime's own identity holds **no** Kubernetes permission in the connected namespace;
- the reader holds exactly its seven read permissions - no write, no secrets, no exec, no configmaps, nothing in another namespace, nothing cluster-scoped;
- the rollbacker holds `deployments: get, patch` and `replicasets: list` only - no delete, create, scale subresource, secrets, or other namespace;
- the restarter holds `deployments: get, patch` only;
- Vault may mint tokens only for the three named ServiceAccounts;
- **no ClusterRoleBinding** exists for any CortexPrime identity.

**FACT.** Secret hygiene: no credential value in the runtime's logs, in this
phase's report, in the durable store (observations, facts, remediation events)
or in the image (no `.env`); no bearer token in the logs; no metric carries a
credential-like label; the runtime Deployment carries no Vault or Kubernetes
token in its environment or ConfigMap.

**FACT.** Rate limiting, live: with a 3/minute tenant budget set through Helm
values, a real burst was refused by the gateway's limiter (health
`RATE_LIMITED`), the refusal was counted as `cortex_gateway_rate_limited`, and
restoring the defaults returned the connector to CONNECTED.

---

## 24. Evaluation results

**FACT.** Contract evaluation
(`backend.api.connector_evaluation.evaluate_connector`): Kubernetes passes every
rule - 10 capabilities, **0 findings**.

**FACT.** Behavioural evaluation, computed from this run's real evidence:

| Question | Verdict |
|---|---|
| Can CortexPrime correctly select the capability? | **PASS** |
| Can it produce valid arguments? | **PASS** |
| Can governance reject unsafe operations? | **PASS** |
| Can execution happen only after authorization? | **PASS** |
| Can verification correctly distinguish success from failure? | **PASS** (both outcomes produced on the real cluster) |
| Can the system recover from provider failures? | **PASS** |
| Can the system explain the result to the user? | **PASS** |

**INFERENCE / scope.** Every question is answered from **one** record run (one
success incident, one failure incident, five injections), not from a
statistically sized multi-case model evaluation. Capability *selection* is
proven for this incident class (a bad rollout of a Deployment), not across a
population of incident types.

**UNKNOWN.** Model-selection accuracy across many incident classes; behaviour
under adversarial provider responses beyond those injected here (Phase 11.4's
in-process matrix covers more of those, on the same code, in development mode).

---

## 25. Before/after complexity

**FACT.**

| | Before (audit, `2c51f7f`) | After |
|---|---|---|
| Connector models | 2 (V1 raw + fabric) | 1 (fabric); V1 frozen and gated |
| Kubernetes capabilities registered | by a harness script | 10, at boot, idempotent |
| Kubernetes credentials | static tokens in environment variables | Vault-minted per action, 10-minute TTL |
| Connector health | none | 7 states, through the governed path, per-capability availability |
| Deployment | none (the V1 monolith image, loops in `backend.main`) | Helm chart + slim image (~104 MB) |
| Tenancy for a connector | implicit | an explicit connection, enforced twice |
| Gateway rate limiting | never supplied | wired and counted |
| Transport/credential audit | silently dropped | recorded in the fenced chain |

---

## 26. Remaining limitations

**FACT / stated, not implied:**

- One connection (tenant ↔ namespace) per deployment; one runtime replica.
- The rate limiter is per process.
- A write worker's own RBAC is not health-checked (health would have to handle
  the worker's credential in-process).
- RBAC cannot restrict *fields*: `patch deployments` could change
  `spec.replicas`; the worker's fixed request shape is what prevents it.
- A failing health check can take ~2.5 minutes to report when the credential is
  refused (the governed read waits out its tick budget).
- Vault's minimum ServiceAccount token TTL is 10 minutes.
- V1 connectors remain present, gated rather than removed.

**UNKNOWN:** scale, multi-cluster, chart upgrade across versions, non-k3d
distributions, sustained multi-day operation.

---

## 27. Reusable connector architecture

**FACT.** `docs/CONNECTOR_ARCHITECTURE.md` documents the five-part extension,
the typed contract, commissioning, the single execution path, credentials,
tenancy, errors, health, observability and a checklist for the next connector.
`backend/api/connector_evaluation.py` is connector-agnostic: it evaluates any
manifest against its composed catalogs and answers the seven behavioural
questions from a real run's evidence.

---

## 28. Exact evidence

**FACT - what ran, where.**

| | |
|---|---|
| Cluster | k3d `cortex-p99b`, Kubernetes **v1.35.5+k3s1** (disposable) |
| Namespaces | `cortexprime` (release), `vault`, `cortex-conn-a` (connected), `cortex-conn-b` (never connected) |
| Database | `pgvector/pgvector:pg16`, TLS on, `sslmode=require`; schema at `0025_mission_replay_events` |
| Vault | `hashicorp/vault:1.17.6`, TLS listener, Kubernetes auth + Kubernetes secrets engine |
| Runtime image | `cortexprime/governed-runtime:1.0.0-b9` (104 MB; node image id `20921e27ce61a`) |
| Worker images | `cortexprime/contained-k8s-rollback:1.0.0` (digest `4f06d51a…`), `cortexprime/contained-k8s-restart:1.0.0` (digest `dac6839e…`) - the digests the chart pins and the platform checks per execution |
| Model | GLM-5.2 (`openai-compatible`) through the governed model boundary, from the operator's `backend/.env`; the key is delivered as a Kubernetes Secret through stdin and never printed |
| Tenants | `tenant-p111k0000a` (connected to `cortex-conn-a`), `tenant-p111k0000b` (no connection) |

**FACT - how to reproduce.**

```sh
bash scripts/phase99b_provision.sh          # once: the disposable cluster
bash scripts/phase111k_provision.sh         # PostgreSQL + Vault + namespaces + images
python scripts/phase111k_kubernetes_connector_harness.py     # all stages; exit 0 = VERIFIED
```

Stages run individually with `CORTEX_P111K_STAGES=...`; the image tag with
`CORTEX_P111K_IMAGE_TAG=...`.

**FACT - artefacts.**

- `docs/phase111k_kubernetes_connector_report.json` - 92 checks, 0 failed,
  verdict `VERIFIED`; negative matrix (6 cases, 0 cluster writes each), failure
  injections (5), measurements and the evaluation answers.
- `scripts/phase111k_kubernetes_connector_harness.py` - the harness itself.
- `helm/cortexprime-governed/` - the chart that was installed.
- `tests/connector_fabric/`, `tests/connectors/test_raw_request_gate.py` - the
  deterministic suites.

**FACT - one chart change after the record run.** Rendering the chart for a
different operator showed that the contained workers' egress NetworkPolicy was
conditional on discovering the API server endpoint: a lookup that returns
nothing (dry run, restricted RBAC) silently dropped the policy and would have
deployed a worker that could reach anything. The chart now **fails closed**,
naming `workers.apiServerEndpoint`. The install was then re-verified with the
changed chart on the same cluster: INSTALL + CONNECT **18/18 VERIFIED**, 19
objects in the connected namespace, health CONNECTED. Everything else in the
record run is unchanged by it.

**FACT - regression.**

- **Every area this phase touches** (`tests/architecture`, `tests/platform`,
  `tests/contracts`, `tests/contexts`, `tests/connector_fabric`,
  `tests/connectors`, `tests/database`, `tests/signal`, `tests/intelligence`,
  `tests/assurance`, `tests/harness`, `tests/deployment`): **3795 passed, 1
  failed, 7 skipped** in 395 s. The one failure is the pre-existing baseline
  (`test_dependency_isolation.py::…[credentials\\inspection.py]`), a file this
  phase did not touch and which fails identically at HEAD.
- **Four guard tests failed first and were updated deliberately, not loosened.**
  `TestKubernetesCatalog` and `TestRealExposure` pin the Kubernetes read
  surface, and adding `kubernetes.access.review` is exactly what they exist to
  catch. The pins now name the ninth read and its justification, and the
  "every read is a GET" invariant gained one **explicit, endpoint-bound**
  exception (a SelfSubjectAccessReview must be a POST; the API server evaluates
  it and stores nothing), plus a new test asserting that it is the *only*
  posting read.
- **UNKNOWN - the whole-repository suite did not converge on this host.** Two
  attempts (~7300 tests) stalled repeatedly on pre-existing V1 tests that hang
  until their per-test timeout; the run was stopped rather than reported
  half-finished. The last whole-repository baseline is Phase 11.4's (72 failed,
  7083 passed, 46 errors), recorded before this phase. Untested-here areas are
  V1 surfaces this phase does not import; the risk is mitigated but not
  eliminated by the targeted result above.



---

## 29. LOCK decision

**Kubernetes: LOCKED.**

| Gate | Status | Evidence |
|---|---|---|
| security S-1 closed | PASS | `guard_raw_request` at 13 raw methods + 5 guarded `/api/git` routes, in the inventory; 62 tests |
| security S-2 closed | PASS | 4 autonomous routes guarded and inventoried; same suite |
| rate limiting wired | PASS | gateway rate stage; live burst refused, counted (section 23) |
| production credential path proven | PASS | Vault Kubernetes auth + secrets engine, 45 leases, TTL 600 s, no static token (section 8) |
| startup capability registration proven | PASS | 10 commissioned at boot; idempotent across restart; 0 conflicts |
| connector health proven | PASS | CONNECTED, and 5 injections each named and recovered |
| typed capability contracts proven | PASS | manifest + schemas + profiles published by the API; evaluation 0 findings |
| governance proven | PASS | negative matrix, 0 cluster writes (section 23) |
| tenant isolation proven | PASS | DISABLED for B, no detail leak, both cross-tenant targets refused, RBAC refusal |
| audit proven | PASS | 1666 rows in the fenced chain during the run (F-1 fixed) |
| tracing/metrics proven | PASS | `cortex_connector_health`, `cortex_gateway_rate_limited`, no credential-like label |
| real Kubernetes authentication proven | PASS | Vault-minted ServiceAccount tokens against the live API server |
| real Kubernetes reads proven | PASS | 8 read capabilities exercised through the governed path |
| real governed write proven | PASS | generation 2 to 3, template restored, attributable annotation |
| independent verification proven | PASS | `verified/supported` **and** `verification_failed/escalated` |
| failure handling proven | PASS | 5 injections (section 22) |
| retry behaviour proven | PARTIAL-PASS | writes never retried (contract + live: one lease, one generation); read retry and `Retry-After` proven deterministically, **not** against a real 429 (section 14) |
| security tests proven | PASS | section 23 |
| cross-tenant tests proven | PASS | section 23 |
| real integration tests proven | PASS | the record run |
| evaluation suite proven | PASS | contract 0 findings; 7/7 behavioural questions PASS, scope stated (section 24) |
| deployment path proven | PASS | one script + one `helm upgrade --install`, on a wiped database and an empty Vault |
| documentation complete | PASS | ADR-125, architecture, runbook, this report |
| no known critical/high security issue | PASS | S-1 (critical) and S-2 (high) closed; F-1, F-2, F-9 (high) fixed; S-4..S-9 (medium/low) remain open and belong to other connectors/V1 |
| working tree clean | PASS | `git status` clean after the commit (the disposable environment's state is git-ignored) |
| commit created | PASS | one commit, "Phase 11.1-K: the Kubernetes reference connector…" (see `git log -1`) |
| final verification report created | PASS | this document |

**The one qualification.** "Retry behaviour" is marked PARTIAL-PASS: a real
provider 429 with `Retry-After` was never provoked on the live cluster. It does
not block LOCK because the mandate's requirement - *never blindly retry writes* -
is proven both by contract (`RetryClass.NEVER`, refused at evaluation) and on
the real cluster (exactly one Vault lease and one generation increment per
write, and no retry after a failed verification).

**What LOCKED does not claim:** scale, multi-connection, multi-replica,
multi-cluster, chart upgrades across versions, non-k3d distributions, or
sustained multi-day operation (section 26).

**NEXT CONNECTOR: GitHub.** It reuses this architecture unchanged: an adapter
and operation catalog, a manifest, a Vault-backed credential adapter, a
connection scope keyed on `repository`, a health probe built from GitHub's own
permission surface, and the same evaluation suite before any real-provider run.
Its writes (issue comment, pull-request creation) are irreversible and must run
in a contained worker with independent verification, exactly as the rollback
does here.
