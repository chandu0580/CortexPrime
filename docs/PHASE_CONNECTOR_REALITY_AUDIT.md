# CortexPrime Connector Reality Audit

- **Date:** 2026-09-19 · **HEAD audited:** `e9dfd63` (branch `phase-1-foundation`, clean tree) · **Type:** discovery only. No source, test, configuration or dependency was changed.
- **Method:** a repository-wide census of code, tests, runtime composition, deployment artifacts and recorded real-run evidence. Documentation was never accepted as proof of implementation.
- **Evidence labels used throughout:**
  - **[V]** verified directly while writing this document (file read, grep, or command output);
  - **[C]** code-read evidence with file:line, gathered by four read-only audit passes (V1 connectors, governed plane, MCP/agents/tools, integrations/UX/deployment);
  - **[R]** a recorded real-infrastructure run (machine report or verification report with a verdict).
  - **FACT / INFERENCE / UNKNOWN** in section 22 as the mandate asks.

---

## 1. Executive Summary

**CortexPrime has two connector worlds that do not meet.**

1. **The governed plane** (`backend/contexts/execution/…`, the Capability Fabric, invocation gateway, credential and transport brokers, approval authority, Assurance). It is architecturally sound and proven on real infrastructure for **three external systems only**: **Kubernetes** (reads, watch, a contained restart, a contained rollback), **Prometheus** (six fixed-query reads) and **Alertmanager** (inbound signal ingest). Record runs: 11.2 63/63, 11.3 81/81, 11.4 98/98 ×3, 9.10 95/95, 9.11 92/92, chain 10.7–10.14 [R].
2. **The V1 plane** (`backend/connectors/`, 19 connectors). Every connector holds real HTTP/SDK client code with real authentication, but **none has ever been shown communicating with its real system** (every test mocks the network [C]). All are **quarantined for writes only**; reads are ungoverned, and none is reachable through the Capability Fabric.

**Nothing is production-ready.** Even the three integrated connectors lack a production credential path:
- the only credential provider in use is `DevelopmentCredentialProvider`, which refuses PRODUCTION [C];
- the Vault adapter was never exercised [V].

They also lack three more things:
- **boot-time commissioning:** every capability is registered by a harness or an operator [C];
- **a deployment artifact:** no helm, compose or CI file configures the governed runtime [V];
- **an effective rate limiter:** no caller ever supplies one [V].

**Three security findings are new in this audit, and one contradicts an earlier verified claim.**
- **S-1 [V]:** `POST /api/git/*` (mounted, perimeter auth only) reaches `GitHubConnector._request(...)` writes: branch delete, blob, tree, commit and ref push, PR patch, comments. These **bypass the V1 effect gate and the legacy flag**. Phase 6.1 recorded "UNGOVERNED KNOWN SIDE-EFFECT PATHS = 0", and this path contradicts it.
- **S-2 [V]:** `POST /api/runtime/autonomous-loop`, `/api/orchestrator/autonomous` and `/api/orchestrator/route` have **no legacy guard**, while their sibling `/execute` routes do. The first reaches Tavily and Azure OpenAI directly; the last reaches a host screen-analysis effect [C].
- **S-3 [V]:** the gateway's rate limiter is never wired: `build_invocation_gateway(rate_limiter=None)` by default, and no caller passes one.

**Totals (29 connectors in scope):** 24 targets plus 5 meaningful non-target integrations (CircleCI, ArgoCD, Docker, Terraform, MCP).

| State | Count | Connectors |
|---|---|---|
| PRODUCTION_READY | **0** | — |
| INTEGRATED | **3** | Kubernetes, Prometheus, Alertmanager (ingest only) |
| IMPLEMENTED | 0 | — |
| PARTIAL | **20** | Grafana, OpenTelemetry, Loki, GitHub, GitLab, GitHub Actions, GitLab CI/CD, Jenkins, Azure DevOps, ServiceNow, Slack, Teams, Jira, Confluence, Notion, CircleCI, ArgoCD, Docker, Terraform, MCP |
| PLANNED_ONLY | **2** | PagerDuty, Email/SMTP (documented as notification channels in `docs/ARCHITECTURE_GUIDE.md:1308-1315`; no code) |
| NOT_IMPLEMENTED | **4** | Elastic, AWS, Azure, GCP (as operations connectors) |

---

## 2. Current Product Architecture

What exists, as code:

| Layer | Governed implementation | V1 implementation |
|---|---|---|
| Agents / reasoning | Intelligence Plane: investigation engine plus remediation proposal port through `GovernedModelBoundary` (schema `extra=forbid`, scrubbed prompts, fail-closed trace) [C] | Three agent systems (`backend/agents/builtin`, runtime cognition agents, `backend/orchestrator`), none enforcing capability permissions [C] |
| Connectors | `contexts/execution/infrastructure/adapters/connectors/{kubernetes,prometheus,grafana,github}.py`, plus contained workers and the MCP/Agent adapters [C] | `backend/connectors/*.py` (19) with an in-memory `connector_registry` [C] |
| Capabilities | Durable versioned registry, lifecycle, trust, binding and resolution (`contexts/connectivity`) [C] | `BaseConnector.get_operations()` turns every public async method into a planner operation [C] |
| Governance | Invocation gateway admission chain, authorization, one approval authority (`cp_approval`), action and approval digests, AutonomyPolicy [C][R] | Effect gate plus the `CORTEXPRIME_ENABLE_LEGACY_EXECUTION` flag, for writes only [C] |
| Execution | Contained workers (restart, rollback) with least-privilege ServiceAccounts [R] | Direct connector calls when the flag is set [C] |
| Verification | `AssuranceVerifier` plus `RemediationVerifier` under a separate reader identity [R] | none |
| Interfaces | Product API `/api/v1/*` (investigations, approvals, world state, remediation) [C] | Web UI (V1 connector pages), `/api/*` V1 routes [C] |

"SIMPLE OUTSIDE" is **not** met today (section 20). The governed path is configured only by environment variables and local provisioning scripts, and no user-facing surface configures it.

---

## 3. Connector Inventory

| # | Connector | Plane(s) | Primary state | One-line evidence |
|---|---|---|---|---|
| 1 | Kubernetes | governed + V1 | **INTEGRATED** | Real HTTPS reads, watch, contained restart and rollback on k3d; verified 11.4 98/98 ×3 [R] |
| 2 | Prometheus | governed + V1 | **INTEGRATED** | Six fixed PromQL reads against a real Prometheus (11.3 81/81) [R] |
| 3 | Alertmanager | governed ingest | **INTEGRATED** (ingest only) | `POST /api/signals/alertmanager` fed by a real Alertmanager (11.2 63/63) [R]; no outbound operations |
| 4 | Grafana | governed + V1 | PARTIAL | Governed adapter (create_folder, get_folder) run live once in the Phase 6.1 slice (412/403 recorded, `PHASE_6_1_VERIFICATION_REPORT.md:58`) [R], unused by the product runtime [C]; V1 reads have no auth supplied [C] |
| 5 | OpenTelemetry | V1 ingest | PARTIAL | OTLP protobuf/JSON **decoder** behind `POST /api/infrastructure/otel/v1/traces`; no query of any OTel backend; own-telemetry exporter is dead code [C] |
| 6 | Loki | V1 | PARTIAL | httpx reads, no auth, ungoverned, never run live [C] |
| 7 | Elastic | — | NOT_IMPLEMENTED | Strings only; `infrastructure/opensearch` is CortexPrime's own store, not a connector [C] |
| 8 | GitHub | governed + V1 | PARTIAL | Governed adapter (3 reads, 2 writes) behind default-off `CORTEX_ENABLE_GITHUB`, Vault-only credential, never run live [C]; V1 client real but unverified, with the S-1 write bypass [V] |
| 9 | GitLab | V1 + webhook | PARTIAL | V1 httpx client; signed `POST /api/gitlab/webhook` ingest [C] |
| 10 | GitHub Actions | V1 (inside GitHub) | PARTIAL | Workflow and run operations in `connectors/github.py` [C] |
| 11 | GitLab CI/CD | V1 | PARTIAL | `connectors/gitlab_ci.py` pipelines, jobs, runners; `list_variables` returns secret values [C] |
| 12 | Jenkins | V1 | PARTIAL | httpx plus basic auth; unverified [C] |
| 13 | Azure DevOps | V1 | PARTIAL | httpx plus PAT; unverified [C] |
| 14 | AWS | — | NOT_IMPLEMENTED | Only a Secrets Manager `get_secret_value` in `security_center/auth_providers.py:354-372` [C] |
| 15 | Azure | — | NOT_IMPLEMENTED | Only Key Vault and Azure AD OAuth (identity) [C] |
| 16 | GCP | — | NOT_IMPLEMENTED | Only Google OAuth (identity) and the Gemini LLM adapter [C] |
| 17 | PagerDuty | — | PLANNED_ONLY | Documented (`ARCHITECTURE_GUIDE.md:1314`); only an Alertmanager receiver config in `infra/prometheus/alertmanager.yml:30-32` [C] |
| 18 | ServiceNow | V1 | PARTIAL | Table API client; unverified [C] |
| 19 | Slack | V1 | PARTIAL | Web API client; no ChatOps receiver [C] |
| 20 | Microsoft Teams | V1 | PARTIAL | Static Graph bearer token, no OAuth refresh [C] |
| 21 | Email / SMTP | — | PLANNED_ONLY | Documented (`ARCHITECTURE_GUIDE.md:1312`); no `smtplib` or SendGrid anywhere [C] |
| 22 | Jira | V1 | PARTIAL | Only `get_issue` is a read; the routes call methods that do not exist; hard-coded default tenant URL [C] |
| 23 | Confluence | V1 | PARTIAL | httpx; unverified [C] |
| 24 | Notion | V1 | PARTIAL | httpx; one route calls `query_database()` without its required argument [C] |
| 25 | CircleCI | V1 | PARTIAL | httpx; unverified [C] |
| 26 | ArgoCD | V1 | PARTIAL | Token never supplied; default `localhost:8080` [C] |
| 27 | Docker | V1 | PARTIAL | Docker SDK; `list_containers` returns container env vars [C] |
| 28 | Terraform | V1 | PARTIAL | subprocess CLI; `initialize()` is refused by the gate, so it is never ready without the flag [C] |
| 29 | MCP | governed + V1 | PARTIAL | Governed `McpToolAdapter` (JSON-RPC over HTTP) built by no composition; V1 `mcp_registry` is empty at runtime [C] |

Other external integrations that are **not operations connectors**, listed for completeness:

| Integration | State | Notes |
|---|---|---|
| LLM providers (9 adapters: openai-compatible, openai, anthropic, gemini, groq, deepseek, openrouter, together, ollama) | openai-compatible **INTEGRATED** through `GovernedModelBoundary` [R 11.3, 11.4]; others unverified | `/api/llm/*` also exposes providers directly to any authenticated user, outside the boundary [C] |
| Vault | governed adapter PARTIAL (never exercised [V]); V1 hvac client in use at boot [C] | credential backend |
| OAuth IdPs (Azure AD, Google, Okta, Keycloak; second OIDC/SAML stack) | code exists, no dedicated tests [C] | identity |
| Tavily | real httpx client, ungoverned [C] | research |
| LiveKit | token minting; a V1 test opens a real connection (regression hang in 11.4) [V] | voice |
| Sentry | CortexPrime's own error telemetry [C] | observability of self |
| GitHub / GitLab webhooks | signed ingress [C] | inbound |
| OpenSearch, RabbitMQ, Neo4j, Redis | internal infrastructure [C] | not connectors |

---

## 4. 24-Connector Target Audit

Legend: **Y** yes · **N** no · **P** partial · **U** unknown. "Fabric" means discoverable and invocable through the governed Capability Fabric.

| Connector | State | Auth | Read | Write | Capabilities | Fabric | Governance | Audit | Verification | Real Integration Test | Security Test | Production Ready |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Kubernetes | INTEGRATED | Y (SA token, TLS) | Y | Y (restart, rollback; contained) | Y (8 read ops + 2 write) | Y (harness/operator-commissioned) | Y | Y | Y (independent reader + Assurance) | Y [R] | Y (RBAC can-i, red team) [R] | **N** |
| Prometheus | INTEGRATED | P (token slot; test Prometheus unauthenticated) | Y | N | Y (6 fixed queries) | Y | Y (reads) | Y | n/a | Y [R] | P | **N** |
| Grafana | PARTIAL | P | P | P (create_folder, unselectable in-process) | P (2 ops) | N (not in product runtime) | P | P | N | P (Phase 6.1 only) | N | N |
| OpenTelemetry | PARTIAL | P (JWT ingest) | N (no query) | N | N | N | P (ingress principal) | P | N | N | P (`test_ingress_boundary.py`) | N |
| Alertmanager | INTEGRATED (ingest) | Y (JWT + governed ingest principal) | n/a | N | N (ingest only) | P (World observations) | Y | Y | n/a | Y [R] | Y (11.1/11.2) | **N** |
| Loki | PARTIAL | N | P | N | N | N | N | N | N | N | N | N |
| Elastic | NOT_IMPLEMENTED | N | N | N | N | N | N | N | N | N | N | N |
| GitHub | PARTIAL | P (V1 PAT; governed Vault-only, never run) | P | P (V1 gated **except S-1**) | P (governed 5 ops declared) | N (default off) | P | P | N | N | P (V1 effect-gate tests) | N |
| GitLab | PARTIAL | P | P | P (gated) | N | N | P | P | N | N | P (signed-webhook tests) | N |
| GitHub Actions | PARTIAL | P | P | P (gated) | N | N | P | P | N | N | N | N |
| GitLab CI/CD | PARTIAL | P | P | P (gated) | N | N | P | P | N | N | N | N |
| Jenkins | PARTIAL | P | P | P (gated) | N | N | P | P | N | N | N | N |
| Azure DevOps | PARTIAL | P | P | P (gated) | N | N | P | P | N | N | N | N |
| AWS | NOT_IMPLEMENTED | N | N | N | N | N | N | N | N | N | N | N |
| Azure | NOT_IMPLEMENTED | N | N | N | N | N | N | N | N | N | N | N |
| GCP | NOT_IMPLEMENTED | N | N | N | N | N | N | N | N | N | N | N |
| PagerDuty | PLANNED_ONLY | N | N | N | N | N | N | N | N | N | N | N |
| ServiceNow | PARTIAL | P | P | P (gated) | N | N | P | P | N | N | N | N |
| Slack | PARTIAL | P | P | P (gated) | N | N | P | P | N | N | N | N |
| Microsoft Teams | PARTIAL | P (static token) | P | P (gated) | N | N | P | P | N | N | N | N |
| Email / SMTP | PLANNED_ONLY | N | N | N | N | N | N | N | N | N | N | N |
| Jira | PARTIAL | P | P (1 op) | P (gated) | N | N | P | P | N | N | N | N |
| Confluence | PARTIAL | P | P | P (gated) | N | N | P | P | N | N | N | N |
| Notion | PARTIAL | P | P | P (gated) | N | N | P | P | N | N | N | N |

"Governance P" for V1 means that only the write effect gate exists; there is no policy, approval, tenant scoping or digest. "Audit P" for V1 means `ConnectorActivityService` records an operation after the fact, for the 13 of 19 connectors that route through `_execute` [C].

---

## 5. Existing Connectors (INTEGRATED)

**Kubernetes (governed)** [C][R]
- **Reads:** `kubernetes.pods.list`, `pod.get`, `pod.logs`, `deployment.get`, `events.list`, `replicasets.list`, `pods.watch` (GET, READ). `deployments.list` is declared only.
- **Writes:**
  - `kubernetes.workload.rollout_restart`, through the contained worker `workers/contained_k8s_restart`;
  - `kubernetes.deployment.rollback`, through the contained worker `workers/contained_k8s_rollback`. It dry-runs server-side and uses `test uid/resourceVersion`.
  - An in-process `rollout_restart` exists but is declared only.
- **Auth:** `CORTEX_KUBERNETES_URL/TOKEN/TENANT` (HTTPS mandatory), with the CA from `CORTEX_TLS_CA_BUNDLE`. Worker tokens are `CORTEX_P99B_RESTART_TOKEN` and `CORTEX_ROLLBACK_WORKER_TOKEN`. All are delivered by the credential broker as the transport Authorization header (one `reveal()` site, `platform/transport/httpx_adapter.py:473`).
- **Proven:** real k3d reads, watch, restart and rollback; RBAC checked with token-only identities; 18-class red team at 0 writes; independent verification; replay; audit.
- **Not production-ready because:**
  - there is no production credential adapter, and tokens are 2-hour to 24-hour manual mints;
  - capabilities are commissioned by harness or operator, not at boot;
  - no deployment artifact exists;
  - the rate limiter is unwired and connectivity/credential/transport metrics are not emitted (metrics port is `None`) [C];
  - there is no runbook, and setup takes about 22 manual steps (section 20).

**Prometheus (governed)** [C][R]
- **Operations:** `prometheus.pod_restarts`, `self_build_info`, `pod_memory_bytes`, `pod_memory_ratio`, `deployment_unavailable`, `pod_restarts_range`. The PromQL is fixed at composition and scoped to one namespace, with no caller-supplied query.
- **Output checks:** `status:error` on a 200 is treated as a failure, and the normalizer rejects unexpected shapes.
- **Proven** against a real Prometheus scraping kube-state-metrics and cAdvisor (11.3).
- **Missing:**
  - the auth path is never exercised, because the test Prometheus is unauthenticated;
  - no production credential;
  - the namespace is bound at composition, so a multi-namespace product needs one composition per namespace.

**Alertmanager (ingest)** [C][R]
- **Route:** `POST /api/signals/alertmanager`, using a JWT plus a governed ingest principal. The tenant comes from the token.
- **Limits:** body ≤ 1 MiB; ≤ 200 alerts per payload.
- **Storage:** observations go to the World Plane ledger.
- **Proven** with a real Alertmanager (11.2).
- **Gaps:**
  - the route is not HMAC-signed; it sits outside `SIGNED_INGRESS`, so Alertmanager must hold a CortexPrime JWT;
  - the shipped `infra/prometheus/alertmanager.yml` has no receiver pointing at CortexPrime;
  - there are no outbound operations (silences, alert queries).

---

## 6. Partial Connectors

**Common to all 19 V1 connectors [C]:**
- **Registration:** registered at boot (`backend/main.py:1040-1076`) into the in-memory `connector_registry`.
- **Credentials:** copied once from environment into `CredentialService` (`api/connector_credential_composition.py:53-74`).
- **Gating:**
  - writes refuse unless `CORTEXPRIME_ENABLE_LEGACY_EXECUTION` is set (`connectors/effects.py:244-254`);
  - reads are ungated;
  - the HTTP surface `/api/connectors/*` returns 503 unless `CORTEXPRIME_ENABLE_LEGACY_CONNECTIVITY` is set.
- **Shared base:** `base.py` / `base_connector.py` is mostly unused and buggy. The circuit breaker is handed an async function but is synchronous, so it never trips, and `self.__cb` is name-mangled [C].
- **Tests:** every test mocks the network.

Per-connector defects found:

| Connector | Distinct defects (all [C]) |
|---|---|
| GitHub | S-1 bypass through `enterprise_git_operations.py` (`_request` writes at :131, :261-286, :356-363, :406, :505-521, :782-840 [V]) |
| GitLab CI | `list_variables` returns CI variable **values**; `download_artifact` skips `_execute` |
| Jira | routes call `list_projects`/`list_issues`, which do not exist; hard-coded default base URL to a personal Atlassian site (`jira.py:43-44`) |
| Notion | `/api/connectors/notion/databases` calls `query_database()` without its required argument |
| Teams | static bearer token, no OAuth refresh |
| Docker | `configure()` writes `os.environ`; `list_containers` returns env vars; `get_registry_repositories` is a stub |
| Kubernetes (V1) | no request timeout; `configure()` writes `os.environ` |
| ArgoCD, Grafana (V1) | token never supplied; localhost defaults |
| Loki, Prometheus (V1) | no auth; `tail` is simulated |
| Terraform | never ready without the flag; `GET /terraform/version` raises TypeError; `apply` auto-approves by default (gated) |
| Azure DevOps | `enterprise_git_operations` references `azure._organization`, which does not exist |
| Grafana (governed) | `create_folder` is a FIXED REVERSIBLE_WRITE on an AMBIENT worker, so the isolation matrix makes it unselectable in-process |
| GitHub (governed) | Vault-only credential; AMBIENT worker, so its writes are refused `isolation_insufficient` |
| MCP (governed) | `McpToolAdapter` is built by no composition; `mcp_source()` builds a new empty registry, so discovery finds nothing |
| OpenTelemetry | decoder only; `backend/core/tracing.py` exporter is never called |

---

## 7. Planned Connectors

PagerDuty and Email/SMTP are documented as notification channels in `docs/ARCHITECTURE_GUIDE.md:1308-1315` and `docs/ADMINISTRATOR_GUIDE.md:1138,1469`. No client code exists for either [C]. The PagerDuty "integration" is Alertmanager's own receiver config, and that config is not deployed.

---

## 8. Missing Connectors

**Elastic, AWS, Azure, GCP**, as operations connectors. Only identity, secret or LLM uses of the cloud SDKs exist [C]. No cloud resource read or write capability exists anywhere.

---

## 9. Capability Inventory

Only capabilities that exist in code are listed. "Commissioned" means registered, validated, enabled and trusted in the durable registry. **No capability is commissioned by product boot.** Commissioning happens in harness scripts (for example `scripts/phase114_autonomous_operations_harness.py:293-317`) or by an operator [C].

| Capability id | Provider | Implementation | R/W | Input schema | Output validation | Governance | Audit | Tests / real run |
|---|---|---|---|---|---|---|---|---|
| platform.kubernetes.pods.list | kubernetes | `connectors/kubernetes.py` catalog | R | ns (RESOURCE_SEGMENT), labelSelector, limit | resourceVersion required; normalizer | gateway admission | gateway plus brokers | unit plus 9.2/11.2 [R] |
| platform.kubernetes.pod.get | kubernetes | same | R | ns, name | same | same | same | [R] |
| platform.kubernetes.pod.logs | kubernetes | same | R | tailLines 1-500, sinceSeconds, previous | lineCount | same | same | 11.3 [R] |
| platform.kubernetes.deployment.get | kubernetes | same | R | ns, name | template digest, generation, conditions | same | same | 11.3/11.4 [R] |
| platform.kubernetes.events.list | kubernetes | same | R | limit, fieldSelector | eventCount | same | same | 11.3 [R] |
| platform.kubernetes.replicasets.list | kubernetes | same | R | ns, label, limit | revision, ownerUid, template digest | same | same | 11.3/11.4 [R] |
| platform.kubernetes.pods.watch | kubernetes | same | R | resourceVersion, timeoutSeconds 1-20 | watch decoder, ≤64 events | same | same | 9.3/11.2 [R] |
| (declared) kubernetes.deployments.list | kubernetes | same | R | ns, label, limit | — | — | — | none |
| platform.kubernetes.workload.rollout_restart | kubernetes-contained | `contained_worker_catalog`, worker image | W (IRREVERSIBLE) | namespace, name | worker evidence | approval required, digest, CONTAINED | yes | 9.9C/9.10/9.11, chain 10.7 [R] |
| platform.kubernetes.deployment.rollback | kubernetes-contained-rollback | rollback catalog, worker image | W (IRREVERSIBLE, compensable) | 10 typed params (uid, generations, revisions, digests, plan, policy) | dry-run digest check, worker evidence | approval or earned delegation, digest, single use | yes | 11.4 98/98 ×3 [R] |
| prometheus.pod_restarts / self_build_info / pod_memory_bytes / pod_memory_ratio / deployment_unavailable / pod_restarts_range | prometheus | `connectors/prometheus.py` | R | none (range: start/end) | status/shape normalizer | gateway | yes | 9.4/11.3 [R] |
| folder.create_folder / folder.get_folder | grafana | `connectors/grafana.py` | W / R | title, uid | — | gateway (write unselectable) | yes | Phase 6.1 only |
| repository.get_repository / get_issue / get_pull_request / create_issue / create_issue_comment | github | `connectors/github.py` (governed) | R / W | owner, repo, number, TEXT | rate-limit classification | gateway (writes refused, AMBIENT) | yes | **none** |
| widget.create (+1 read) | controlled (scripted) | `controlled_provider_factory.py` | W / R | — | — | gateway | yes | harness only |

**V1 operations** are not Capability Fabric capabilities. They are planner-visible methods via `BaseConnector.get_operations()`, roughly 300 across 19 connectors, and are enumerated per connector in the V1 code-read (GitHub alone has 37 reads and 24 writes) [C]. They have no input or output schema beyond required-parameter checks (`registry.validate_operation`) [C].

---

## 10. Agent Inventory

| Agent / system | Purpose | Model | Tools / connectors | Guardrails | Tracing / eval | Production path |
|---|---|---|---|---|---|---|
| **Investigation engine** (governed) | Evidence-backed differential diagnosis | `CORTEX_INVESTIGATION_MODEL_PROVIDER` (glm-5.2 via openai-compatible in 11.3/11.4); deterministic plan if unset | Frozen **read-only** allowlist of governed Kubernetes and Prometheus reads via `GovernedCapabilityReader` | schema firewall, scrubbed prompts, read-only registry | `cp_harness_trace` spans; categorical confidence; calibration | **Yes**, embedded in `backend.main` when `CORTEX_DURABLE_URL` and signal env are set [C][R] |
| **Remediation proposer** (governed) | Proposes `deployment.rollback` or `no_action` | `CORTEX_REMEDIATION_MODEL_*` | None; the platform plans and executes | schema, tool registry (PROHIBITED/UNKNOWN), planner target binding, AutonomyPolicy | spans, autonomy metrics, calibration | **Yes** when `CORTEX_REMEDIATION_ENABLED=1` [R] |
| V1 builtin agents (Planner, Research, PlatformEngineer, SRE, Security, Compliance, Release, QA) | deterministic helpers | none | V1 services; create SHELL execution records | none; ReleaseAgent **fails open** on governance exceptions | none | gated routes only [C] |
| V1 cognition agents (Research, Optimizer, Reflection, Planner, Critic, Memory, Orchestrator) | cognition pipeline | Tavily, Azure OpenAI and the LLM gateway called **directly** | direct vendor calls | none | Redis/Neo4j tracer | reachable via the **ungated** `/api/runtime/autonomous-loop` (S-2) [V][C] |
| `backend/orchestrator` (master runtime, agent router, reasoning loop, reflection) | V1 autonomy | LLM gateway | computer agent (screen analysis) | none | — | `/route`, `/autonomous`, `/reflect` **ungated** (S-2) [V] |
| Agent SDKs (`backend/agent_sdk`, `cortexprime-agent-sdk`) | developer scaffolding | — | in-memory tool registry | none | — | not used by the runtime [C] |

**Doctrine check.** "Agents reason, Connectors connect, Capabilities operate, Governance decides, Executors act, Verifiers prove" **holds for the governed plane** [R]. It **does not hold** for V1:
- V1 agents call vendors directly (`optimizer_agent.py:7`, `research_agent.py:133`);
- the V1 tool registry runs handlers without approval;
- two V1 routes fail open;
- three routes are ungated (S-2);
- `/api/llm/*` gives any authenticated user direct provider access outside `GovernedModelBoundary` [C].

---

## 11. Capability Fabric Status

| Feature | Status | Evidence |
|---|---|---|
| Capability registry (durable, versioned) | REAL | `contexts/connectivity/application/service.py`, `infrastructure/sql_repository.py` [C] |
| Connector (worker) registry and directory | REAL | `worker_directory.py`, `worker_commissioning.py` [C] |
| Capability discovery | PARTIAL | `application/discovery.py` exists, but the HTTP discovery routes write to a **separate in-memory** registry; MCP discovery source is empty [C][V] |
| Capability routing / resolution / binding | REAL | `application/resolution.py`, `SqlBindingRepository` [C] |
| Capability metadata / contracts / profiles | REAL | `domain/contract.py`, `contracts/intelligence/capability_profile.py` [C] |
| Capability permissions (authorization, approval, digest) | REAL | invocation gateway admission chain; `cp_approval`; single use enforced (11.4 F-12) [R] |
| Capability lifecycle (draft→enabled→retired; trust; quarantine) | REAL (states) / PARTIAL (no automatic quarantine trigger) | `domain/lifecycle.py` [C] |
| HTTP capability management API | PARTIAL, disconnected | `/api/v1/capabilities` uses `InMemoryCapabilityRepository` (`api/capability_routes.py:67`) [V]. Registrations over HTTP never reach the governed runtime |
| Boot-time commissioning | MISSING | the signal worker refuses to start unless read capabilities already exist and never registers them [V] |
| Connector health | PARTIAL | `WorkerAvailability` is recorded, never probed [C] |
| Connector auth lifecycle (rotation, expiry) | PARTIAL | expiry bound to the authority window; no rotation; Vault `revoke`/`validate` are stubs [C] |
| Connector rate limits | MISSING in effect | gateway gate exists, `rate_limiter` never supplied [V]; provider 429 is classified only |
| Connector retries | PARTIAL | deterministic retry policy; `Retry-After` ignored; non-idempotent writes never retried [C] |
| Connector observability | PARTIAL | fabric metric families defined but the metrics port is `None` [C]; signal, investigation and remediation Prometheus counters are real [R] |
| SSRF / egress control | REAL | `platform/transport/ssrf.py`, DNS pinning, no redirects, `trust_env` off [C][R 11.1] |
| Production credential provider | MISSING (unexercised) | Vault adapter present, no test or run [V]; everything in use is `DevelopmentCredentialProvider` [C] |

---

## 12. MCP Status

| Item | Status [C] |
|---|---|
| MCP server exposed by CortexPrime | **None** (`/api/v2/mcp/*` is a REST facade, not the MCP protocol) |
| MCP SDK dependency | **None** in any manifest |
| Governed MCP client (`McpToolAdapter`) | Implemented: JSON-RPC over HTTP, per-invocation initialize plus one `tools/call`, tool name copied from the binding, tenant-scoped session. **No composition builds it, no MCP server is configured, and it has no tests.** SSE response parsing: UNKNOWN |
| V1 MCP stack (`backend/mcp`) | In-process registry, **empty at runtime**; `authenticate()` always True; filesystem tool unconfined (never registered); web tool behind the outbound guard |
| Tool discovery | static per binding (governed); V1 dynamic registration route gated; `mcp_source()` builds an empty registry |
| Tool governance / approval / audit | governed: full gateway chain (unexercised); V1: only the legacy flag, logs only |

**Conclusion:** MCP is not the current architecture. A governed MCP seam exists and fits the fabric, since each MCP tool would be a capability, but it has never carried a call.

---

## 13. Credential Architecture

| Connector | Mechanism | Store | Rotation |
|---|---|---|---|
| Kubernetes (governed reads) | KUBERNETES_RBAC + TOKEN (ServiceAccount TokenRequest) | ENVIRONMENT_SECRET → `DevelopmentCredentialProvider` → credential broker | manual re-mint (2 h) |
| Kubernetes contained workers | KUBERNETES_RBAC + TOKEN, delivered per request as the transport Authorization header; the worker holds no standing credential | ENVIRONMENT_SECRET / token file | manual (2 h / 24 h) |
| Prometheus (governed) | TOKEN slot (bearer) | ENVIRONMENT_SECRET | none |
| Grafana (governed) | API_KEY (bearer) | ENVIRONMENT_SECRET | none |
| GitHub (governed) | TOKEN (PAT) | **VAULT only** (unexercised) | none |
| V1: GitHub, GitLab, Jira, Confluence, Notion, ServiceNow, Slack, Teams, Azure DevOps, Jenkins, CircleCI | TOKEN / API_KEY / basic (PAT, API token, password) | ENVIRONMENT_SECRET copied into in-process `CredentialService` | none |
| V1: ArgoCD, Grafana | TOKEN via constructor only (never supplied) | — | — |
| V1: Loki, Prometheus | none | — | — |
| V1: Kubernetes, Docker | kubeconfig / in-cluster SA; Docker socket or TLS env | ENVIRONMENT / file | — |
| Terraform | inherits the full process environment (CLOUD_IAM via provider env) | ENVIRONMENT | — |
| MCP (governed) | per-server credential via broker | VAULT (unconfigured) | — |

The credential **architecture** is sound: one `reveal()` site, per-execution scoped grants, and no credential in any stored row, as verified by 11.4 S.1 [R]. The **operations** are not: there is no production provider, no rotation, and no OAuth flow for any SaaS connector.

---

## 14. Governance Integration

- **Governed plane:**
  - Every invocation is admitted by `SecureCapabilityInvocationGateway.admit`: identity → tenancy → binding → authorization → delegation → worker (code-trust × effect isolation matrix) → input → action digest → approval digest → obligations → freshness → lease → rate (no-op) → credential [C].
  - Writes require approval: human, or policy-delegated only for compensable capabilities (ADR-124).
  - Approvals are single-use [R].
- **V1 plane:** a write effect gate plus an environment flag. No policy, approval, tenant scope or digest. Reads are ungoverned. **S-1 bypasses even the flag** [V].

---

## 15. Audit Integration

- **Governed:**
  - gateway EXECUTION_SUCCEEDED/FAILED/REFUSED;
  - credential and transport broker facts;
  - POLICY_EVALUATED and APPROVAL_* events;
  - the audit chain verified end to end over 1,645 records in 11.4 [R].
  - **Defect:** broker audit writes fail silently (`exc_info=False`) and never block the action [C][R].
- **V1:** `ConnectorActivityService.record` runs after the fact for the 13 connectors that use `_execute`. ArgoCD, Grafana, Loki, Prometheus, OpenTelemetry and Terraform record nothing. The user is always "system" [C].

---

## 16. Verification Integration

Independent world-state verification exists **only** for governed Kubernetes writes:
- `RemediationVerifier` uses a separate reader ServiceAccount;
- `AssuranceVerifier` enforces independence;
- it distinguishes false success, false failure and no effect [R].

The restart capability's readback verification exists in harnesses (9.10) but not as a product-runtime verifier for human-approved restarts [C]. No V1 connector has verification.

---

## 17. Testing Matrix

Counts are test files or harnesses, not individual tests. "Real" means the external system was really reached.

| Connector | Unit (deterministic) | Mock-provider | Contract / schema | Real API | Security | Failure | Rate-limit | Auth | Tenant isolation | Governance | Audit | Observability | E2E |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Kubernetes (governed) | Y (≈6 files) | Y | Y (catalog, normalizer) | **Y** (9.2–11.4) | Y (red team, RBAC) | Y (crash, 401, 403, stale) | N | Y | Y | Y | Y | P | **Y** (11.4) |
| Prometheus (governed) | Y | Y | Y | **Y** (9.4, 11.3) | P | P (absent series) | N | N | P | Y | Y | N | Y (11.3) |
| Alertmanager | Y (`tests/signal/*`) | Y | Y (v4 schema) | **Y** (11.2) | Y | P | N | Y | Y | Y | Y | N | Y (11.2) |
| Grafana (governed) | catalog-refusal only | — | — | P (6.1) | N | P (6.1) | N | N | N | P | N | N | N |
| GitHub (governed) | **none** | — | — | N | N | N | N | N | N | N | N | N | N |
| MCP (governed) | **none** | — | — | N | N | N | N | N | N | N | N | N | N |
| V1 (all 19) | Y (mocked `_request`) | Y | N | **N** | P (effect-gate suite) | P | N | P (credential-check mocks) | N | P (gate) | N | N | N |

**Additional gaps:**
- No unit tests exist for `CredentialBroker`, `VaultCredentialAdapter`, `DevelopmentCredentialProvider`, the SSRF guard, `HttpxTransportAdapter`, `CapabilityService` or `ContainedWorkerAdapter`. These are covered only by harnesses and architecture tests [C].
- Some V1 tests call gated writes without setting the flag, so they are likely stale. That is an inference; they were not run in this audit [C].

**Deterministic vs real, per the testing principle.** The governed plane has both layers:
- deterministic unit tests for routing, schemas, registration, state transitions, guardrails and retries;
- real-infrastructure harnesses for authentication, provider behaviour, errors and semantics.

The V1 plane has only the deterministic layer.

---

## 18. Security Matrix

| Area | Governed (K8s / Prometheus / Alertmanager) | V1 connectors |
|---|---|---|
| Tenant isolation | Y (token tenant, scoped reads, worker tenant binding) [R] | **N** (process singletons, no tenant) |
| Credential isolation | Y (per-execution grant, one reveal site, separate reader/writer identities) [R] | N (process-wide `CredentialService`; Docker/K8s write `os.environ`) |
| Authorization / least privilege | Y (namespace Role, can-i verified) [R] | N (whatever the token grants) |
| SSRF / URL validation | Y (transport SSRF guard, pinned DNS) [R] | P (V1 web MCP tool guarded; connectors use configured base URLs) |
| Prompt / tool / response injection | Y (schema firewall, registry, injection scenario E) [R] | N (planner prompt built from all operations) |
| Secret / logging leakage | Y (S.1 row scan) [R] | **N** (GitLab `list_variables`, Docker env in `list_containers`) |
| Cross-tenant access | refused [R] | not modelled |
| Write authorization / approval / digest | Y [R] | gate flag only; **S-1 bypass** [V] |
| Audit | Y [R] | P |

**Open security findings, not fixed per mandate:**

| ID | Severity | Finding | Evidence |
|---|---|---|---|
| S-1 | **Critical** | `/api/git/*` (mounted by `router_registry.py:828`) → `enterprise_git_operations` → `GitHubConnector._request` writes, bypassing the effect gate and the legacy flag; not in the legacy inventory. Contradicts Phase 6.1's "0 ungoverned side-effect paths" | [V] |
| S-2 | High | `/api/runtime/autonomous-loop`, `/api/orchestrator/autonomous`, `/api/orchestrator/route` have no legacy guard (siblings do); `/api/orchestrator/reflect` also, per [C] | [V][C] |
| S-3 | Medium | gateway rate limiter never supplied | [V] |
| S-4 | Medium | `/api/llm/*` lets any authenticated user call external providers outside the governed boundary | [C] |
| S-5 | Medium | V1 governance fails open (ReleaseAgent; browser governance check) | [C] |
| S-6 | Medium | secret-bearing V1 reads (GitLab CI variables, Docker container env) | [C] |
| S-7 | Low | Jira hard-coded default base URL to a personal Atlassian site | [C] |
| S-8 | Low | docker-compose backend `VAULT_TOKEN` has a hard-coded dev default | [C] |
| S-9 | Low | Alertmanager ingest relies on a JWT rather than a signature | [C] |

---

## 19. Real-World Integration Evidence

Counted only where CortexPrime authenticated, reached the real system, executed a capability, received a real response and normalized it.

| System | Evidence | Verdict |
|---|---|---|
| Kubernetes | 9.2 (real HTTPS reads, 401/403/TLS failures), 9.3 watch, 9.9C/9.10/9.11 (contained restart; 9.10 95/95, 9.11 92/92), 11.2 63/63, 11.3 81/81, 11.4 98/98 in runs 8, 10 and 11, chain 10.7 155/155 (2026-09-19) | **VERIFIED** [R] |
| Prometheus | 9.4, 11.3 (kube-state-metrics and cAdvisor through a real Prometheus) | **VERIFIED** [R] |
| Alertmanager | 11.2 (real Prometheus → Alertmanager → CortexPrime webhook) | **VERIFIED** [R] |
| Hosted LLM (openai-compatible, GLM-5.2) | 11.3 model pass, 11.4 runs 8/10/11 | **VERIFIED** [R] (not a connector) |
| Grafana | Phase 6.1 vertical slice: live 412 and 403 recorded | historical, **not** re-verified; no current product path |
| All other connectors | none | **NOT VERIFIED** |

**Real integrations verified: 3 connectors** (Kubernetes, Prometheus, Alertmanager).

---

## 20. Complexity / UX Audit

**How users interact with connectors today [C]:**
- **Web UI:** `frontend/app/integrations`, `enterprise-connectors/ConnectorAuthentication.tsx` and others. These target only the V1 `/api/connectors/*`, which returns **503 by default**. The UI promises "encrypted at rest" while the backend stores credentials in a process singleton.
- **Governed path:** there is **no UI, API or CLI**. It is configured only through environment variables and `CORTEX_CONNECTOR_FACTORIES`.
- **CLI:** agent-package scaffolding only.
- **ChatOps:** none; no Slack or Teams inbound receiver.
- **Agent-driven or automatic discovery:** no.

**Operator burden for the one proven connector (Kubernetes, governed) [C]:**

| Dimension | Count |
|---|---|
| Provisioning steps | ≈22 (`phase99b_provision.sh` ≈12 plus `phase114_provision.sh` ≈10) |
| Credentials to create and hold | 4 ServiceAccount tokens (reader, restarter, other, rollbacker), 2 TLS keypairs, 1 CA bundle, Postgres credentials |
| Environment variables | ≈45 across runtime, Kubernetes, Prometheus, restart worker, rollback worker, signal, investigation and remediation (section 20a) |
| Kubernetes concepts exposed | ServiceAccount, Role, ClusterRole, bindings, TokenRequest, CA bundle, NodePort, NetworkPolicy, securityContext, pid limits |
| CortexPrime concepts exposed | capability id and version, implementation digest, tenant id, worker binding (8 `CORTEX_BIND_*`), connector factory paths, commissioning |
| Manual decisions | namespace scope, token lifetime, worker digests, tenant binding, which capabilities to commission |
| Recurring actions | re-mint tokens every 2 h (reader and restart) and every 24 h (rollback); certificates last 2 or 7 days |
| UI screens | 0 |
| Env naming mismatch | `.phase114.env` names `CORTEX_P114_ROLLBACK_TOKEN_FILE`; the backend reads `CORTEX_ROLLBACK_WORKER_TOKEN`; only the harness maps them |

*20a. Env var families required:* `CORTEX_DURABLE_URL`, `CORTEX_CONNECTOR_FACTORIES`, `CORTEX_TLS_CA_BUNDLE`, `CORTEX_KUBERNETES_{URL,TOKEN,TENANT}`, `CORTEX_PROMETHEUS_{URL,TOKEN,TENANT,NAMESPACE}`, `CORTEX_P99B_*` (6), `CORTEX_ROLLBACK_*` (6), `CORTEX_SIGNAL_*` (≈13), `CORTEX_INVESTIGATION_*` (9), `CORTEX_REMEDIATION_*` (14) [C].

**Where users must understand internal complexity today:** ServiceAccounts and RBAC, token minting and expiry, CA bundles, capability ids and versions, implementation digests, worker bindings, tenant ids, factory module paths, commissioning order, and the two unrelated legacy flags.

**Opportunities to absorb complexity** (these are observations, not a roadmap):
- a single "connect cluster" flow that generates the namespace Role, ServiceAccounts and NetworkPolicy from one manifest;
- automatic commissioning of a connector's declared capabilities at boot;
- a production credential provider with automatic token renewal (TokenRequest refresh);
- workers that derive their binding from the commissioned capability;
- one product surface (UI, CLI, API) over the governed path, with the V1 connector pages retired.

---

## 21. Connector Dependency Graph

```text
CortexPrime
   │
   ├── Agents ─────────── Investigation engine (reads) · Remediation proposer (proposals only)
   │                         │ reads through                      │ writes through
   ├── Capability Fabric ─── registry · resolution · gateway · credential/transport brokers
   │                         (missing: boot commissioning, rate limiter, prod credentials, metrics)
   ├── Governance ────────── authorization · cp_approval (single use) · AutonomyPolicy · digests
   ├── Verification ──────── AssuranceVerifier · RemediationVerifier (separate reader identity)
   │
   └── Connectors
          │
          ├── Kubernetes ◄── foundation: subject of every incident, only write path, only verifier target
          │     ├── Prometheus      (metrics about Kubernetes workloads; namespace-scoped)
          │     └── Alertmanager    (inbound alerts about the same workloads → signal fabric)
          │
          ├── GitHub / GitLab (+ Actions / CI) ◄── depends on: Kubernetes deployment identity
          │        (answers "which change caused the regression" for h-deployment-regression;
          │         must first close S-1 and move off V1)
          │
          ├── Loki / Elastic / OpenTelemetry ◄── depends on: Kubernetes pod identity (log/trace evidence)
          ├── Grafana ◄── depends on: Prometheus/Loki (dashboards/annotations; mostly presentation)
          │
          ├── Slack / Teams ◄── depends on: approval authority (out-of-band approval & notification)
          ├── PagerDuty / ServiceNow / Jira ◄── depends on: incident lifecycle + approval (records, paging)
          ├── Confluence / Notion ◄── depends on: investigation outcomes (runbooks, postmortems)
          │
          ├── ArgoCD / Jenkins / Azure DevOps / CircleCI / Terraform ◄── depend on: GitHub/GitLab change model
          └── AWS / Azure / GCP ◄── depend on: production credential provider (cloud IAM), new isolation work
```

**Architectural order, not popularity.** Every connector above depends on fabric pieces that exist only in a development form: production credentials, boot commissioning, the rate limiter, metrics and a deployment artifact. Kubernetes is the only connector that exercises all of them, including writes and verification. **Finishing Kubernetes to PRODUCTION_READY first productionizes the shared fabric** that every later connector inherits.

---

## 22. Current Product Maturity

**Scoring method.** Each area is scored against 5 stated criteria:
1. implemented in code;
2. wired into the product runtime at boot;
3. proven on real infrastructure;
4. deployable through a shipped artifact;
5. operable without harness scripts.

Score = criteria met ÷ 5. PARTIAL counts as half. The percentages follow mechanically from these criteria, which are listed so that they can be challenged.

| Area | 1 Code | 2 Boot | 3 Real | 4 Deploy | 5 Operable | Score | Label and basis |
|---|---|---|---|---|---|---|---|
| Security (perimeter, tenancy, SSRF) | Y | Y | Y | P | P | 80% | FACT: 11.1 137/137; S-1/S-2 open holes |
| Ingestion (signal fabric) | Y | Y (env-gated) | Y | N | P | 60% | FACT: 11.2 63/63; no deploy artifact |
| Detection | Y | Y (env-gated) | Y | N | P | 60% | FACT: 11.3 |
| Investigation | Y | Y (env-gated) | Y | N | P | 60% | FACT: 11.3 81/81 |
| Connectors | P (3 of 29 integrated) | P | P | N | N | 30% | FACT: section 3 |
| Capability Fabric | Y | P (no commissioning) | Y | N | N | 50% | FACT: section 11 |
| Governance | Y | Y | Y | N | P | 70% | FACT: 11.4, chain |
| Execution | Y | P (env-gated remediator) | Y | N | N | 50% | FACT: 11.4 |
| Verification | Y | P | Y | N | N | 50% | FACT: 11.4 |
| Recovery | Y | P | Y | N | N | 50% | FACT: 11.4 (bounded, escalates) |
| Learning | Y (advisory calibration) | P | Y | N | N | 50% | FACT: calibration in 11.4 |
| Observability (self) | P (fabric metrics unemitted; signal and remediation counters real) | P | P | P (ServiceMonitor in helm) | P | 50% | FACT/INFERENCE |
| Deployment | P (helm/compose for V1 only) | N | N | P | N | 20% | FACT: no governed config in any artifact [V] |
| **GA readiness** | — | — | — | — | — | **≈15%** | INFERENCE: GA needs production credentials, deploy artifacts, operable setup, and more than one connector locked; none is met |

**UNKNOWN:**
- behaviour at production scale (one small cluster only);
- multi-namespace and multi-cluster operation;
- whether the V1 startup watcher loops run in production;
- live behaviour of the Vault adapter;
- the current Grafana behaviour.

---

## 23. OpenAI / Anthropic Implementation Comparison

Primary sources consulted on 2026-09-19:

| Principle | Source | CortexPrime today |
|---|---|---|
| "Simple, composable patterns rather than complex frameworks"; add complexity only when it demonstrably improves outcomes | Anthropic, *Building effective agents* | Governed plane: composable, one chain, one approval authority. V1: three agent systems, two registries, a planner fed ≈300 raw operations, which is the opposite pattern |
| Treat the agent–computer interface (tool design, documentation, examples) as carefully as a human interface; extensive sandbox testing; guardrails | Anthropic, *Building effective agents* | Governed tools are few, typed and read-only with fixed queries. V1 exposes every public method as a tool |
| Build "a few thoughtful tools targeting specific high-impact workflows" rather than wrapping every endpoint; namespacing; return high-signal context; iterate tools against evaluations, including with Claude Code | Anthropic, *Writing effective tools for agents* | The governed Prometheus design (6 fixed queries) matches. No tool-level evaluation suite exists yet; the harnesses are regression suites, not tool evals |
| Orchestrating via code is "more deterministic and predictable"; invest in evals; tracing and guardrails as core primitives | OpenAI Agents SDK docs (orchestration) and OpenAI developer guidance on evals and deterministic tool mocks | Matches: the platform orchestrates by code (planner, policy, gateway) and the model only proposes. Deterministic tests exist for orchestration and schemas; spans trace every model call |
| Deterministic tests for orchestration, separate real environments for provider behaviour | Mandate's stated OpenAI boundary. OpenAI guidance found recommends deterministic tool mocks for comparable eval runs plus integration testing; an exact page stating this boundary was **not found** | Governed plane follows it (unit tests plus real k3d harnesses). V1 has only mocks |

**Takeaway.** The completion standard in section 24 applies these principles as gates. It does not adopt any framework.

---

## 24. Connector Completion Standard

A connector is **COMPLETE (LOCKED)** only when every stage below has evidence. Missing evidence means NOT COMPLETE.

| Stage | Required evidence |
|---|---|
| Research | Provider API, auth model, rate limits, error semantics, least-privilege scopes documented with sources |
| Design | ADR: capability list (few, high-signal, typed), side-effect class per capability, isolation tier, compensation (if any), verification method |
| Implementation | Governed adapter in `contexts/execution/.../connectors`; **no V1 path**; typed parameters only; fixed or validated queries |
| Authentication | Production credential provider (not `DevelopmentCredentialProvider`), scoped per tenant; rotation or renewal proven |
| Capabilities | Each capability declared with input spec, output validation or normalizer, max response size, timeout |
| Capability registration | Commissioned **at boot** from declared contracts (no harness), idempotent, visible through the durable registry and the product API |
| Governance | Gateway admission; writes need approval; delegation only for compensable capabilities; digest binding; single use |
| Audit | Gateway and broker facts recorded; audit-write failure visible; chain verifies end to end |
| Observability | Connectivity, credential and transport metrics emitted; per-capability latency, errors and rate-limit counters |
| Error handling | Provider errors mapped to existing `ProviderFailure` classes (guard test); ambiguity never reported as success; `Retry-After` honoured |
| Security | Tenant isolation, SSRF, injection (tool and response), secret-leak row scan, least-privilege verification against the real provider |
| Real integration | Harness against the real provider (disposable where writes exist): auth success and failure, every capability, normalized output, recorded machine report |
| Failure testing | 401, 403, 404, 409, 429, timeout, partial response, provider outage, worker crash (if contained), concurrent write (if write) |
| Evaluation | Tool-level eval: can the reasoning layer choose and use the capabilities correctly on realistic tasks; tracked across iterations |
| Documentation | ADR, implementation map, verification report, **operator runbook** (setup, rotation, revocation, incident) |
| Production hardening | Deployment artifact (helm values), rate limits enforced, health probed, removal of the V1 counterpart (or a documented freeze) |

Then **LOCK** the connector (record the commit and report) and move to the next.

---

## 25. Recommended Connector Order

This order is based on the dependency graph, not popularity.

1. **Kubernetes → LOCK.** It is INTEGRATED and its write, verification and governance paths are proven. The missing items are exactly the shared fabric pieces every connector needs: production credential provider and renewal, boot commissioning, rate limiter, metrics, deployment artifact, runbook, and one simple operator flow. Doing them here productionizes the fabric once.
2. **Prometheus → LOCK.** Shares all fabric work; adds its authentication path and multi-namespace scoping.
3. **Alertmanager → LOCK.** Signed ingest, and a shipped receiver config pointing at CortexPrime.
4. **GitHub (governed) → LOCK.** Answers the next diagnostic question ("which change caused the regression"). **Precondition:** close S-1 and decide the fate of the V1 GitHub paths.
5. **Slack or Teams.** Out-of-band approval and notification over the existing approval authority.

Everything after these is out of scope for this evidence-based audit.

---

## 26. Remaining Work (observed, not planned)

- Close S-1 and S-2. The governance boundary is not intact while these exist.
- Wire the rate limiter and the fabric metrics.
- Build a production credential provider and exercise it for real.
- Commission capabilities at boot, and connect the HTTP capability API to the durable registry.
- Ship a deployment artifact for the governed runtime (helm values, signal worker, RBAC manifests).
- Replace the V1 connector UI with a governed setup surface.
- Decide the V1 plane's future: 19 connectors, three agent systems, the V1 MCP stack.
- Add unit tests for the credential broker, transport, SSRF guard and Vault adapter.
- Fix broker audit writes that fail silently.
- Declare undeclared test dependencies (`aiosqlite`, `pytest-timeout`) and isolate V1 tests that make real network connections (LiveKit).

---

## 27. Unknowns

- Whether S-1 is reachable in any real deployment. It requires a configured `GITHUB_TOKEN`, and the default compose and helm files do not set one.
- Current Grafana behaviour; the only live evidence is from Phase 6.1.
- `McpToolAdapter` SSE response handling.
- Whether V1 dispatchers ever execute the SHELL execution records created by builtin agents.
- Whether the V1 startup watcher loops run continuously in production.
- Governed-plane behaviour at production scale: many namespaces, clusters, tenants and sustained load.
- Whether the Alertmanager config in `infra/` is pre-processed for environment variables.

---

## 28. Decisions Required

1. **V1 plane:** retire, freeze or migrate the 19 V1 connectors, three V1 agent systems and the V1 MCP stack. Their existence doubles the attack surface (S-1, S-2) and confuses the UX.
2. **S-1 / S-2 remediation timing:** these are governance-boundary holes found during a no-change audit.
3. **Production credential backend:** Vault, a cloud secret manager or Kubernetes-native. It gates every connector's PRODUCTION_READY status.
4. **Adopt the Connector Completion Standard** (section 24) as the definition of done, including the operator runbook and a deployment artifact.
5. **First connector:** confirm Kubernetes-to-LOCK as the next phase (section 25), rather than starting a new connector.
6. **MCP strategy:** whether governed MCP (one server = one provider, one tool = one capability) is a product surface, and in which direction (consume, expose, or both).
7. **Ratification still owed from 11.4:** ADR-124 D-4/D-5, compensable autonomy.
