# PHASE 9.0 — DevOps Capability Fabric Discovery & Governed Action Expansion

Date: 2026-08-12 · Branch `phase-1-foundation` · Companion ADR: ADR-080 · **Discovery only — no code, no migration, no connector, no execution/governance/credential change.**

Every claim is labeled **[FACT]** (verified in the tree), **[SOURCE]** (file:line), **[INFERENCE]** (reasoning from facts), or **[PROPOSAL]** (a recommendation for a later phase). Nothing here is implemented.

---

## 1. Executive summary

**[FACT]** CortexPrime's control architecture (Phases 5–8) is complete and disciplined, but its **real DevOps capability surface in the governed execution path is tiny**: exactly **two real providers, seven operations** — GitHub (3 reads + 2 writes, credential-blocked in practice) and Grafana (1 read + 1 write, the only governed write proven end-to-end) — plus one scripted test provider (`controlled`/widget). [SOURCE] `backend/contexts/execution/infrastructure/adapters/connectors/{github.py:212-369,grafana.py:120-178}`, `backend/api/controlled_provider_factory.py:45-80`.

**[FACT]** A **large V1 connector library** exists — 19 connectors covering nearly every DevOps tool (Kubernetes, Docker, Terraform, GitHub/GitLab/Jenkins/CircleCI/Azure DevOps/ArgoCD, Prometheus/Loki/OpenTelemetry/Grafana, Slack/Teams/Jira/ServiceNow/Confluence/Notion) — but **none is registered as a governed `ProviderOperationSpec`**; all are the legacy `BaseConnector` pattern, fail-closed behind `CORTEXPRIME_ENABLE_LEGACY_EXECUTION`. [SOURCE] `backend/main.py:1004-1032`, `backend/connectors/effects.py`.

**[FACT]** **No governed-plane code can reach an external system without the full chain** (identity → tenant → capability → authorization → lease → gateway → audit → execution). The only governed egress is the sanctioned `platform.transport` broker and the `backend.connectors` V1 quarantine (writes fail-closed behind `BND-EFFECT-GATE` + the legacy flag). [SOURCE] Agent-B scan; `boundary_rules.py` (the plane-fence rules).

**[INFERENCE]** The smallest real capability fabric that proves the CortexPrime loop (World → Evidence → Investigation → Prediction → Governed Action → Independent Verification → Learned Experience → Earned Authority) is a **read-first Kubernetes incident investigator**: strangle the existing K8s reads into a *governed* `ProviderOperationSpec` connector that preserves `resourceVersion`, feed observations into the World Plane, run the 8.x investigation/prediction/assurance/calibration/autonomy stack, and keep remediation human (A1/A2) until a governed, independently-verifiable, reversible K8s write exists. **No new executor/gateway/approval/world-store/assurance/memory system is required** — every one already exists.

**[FACT]** Two hard blockers remain, both pre-existing and untouched: (a) the **Phase 5.5 credential blocker** — no real GitHub/cloud provider credential authenticates in this environment [SOURCE] `docs/adr/ADR-049...md:11-16`; (b) the **Kubernetes WATCH blocker** — the V1 connector strips `resourceVersion`, has no `watch()`, and no 410 recovery [SOURCE] `backend/connectors/kubernetes.py` (grep: zero `resourceVersion`/`watch` hits), `docs/PHASE_7_COMPLETION_ASSESSMENT.md:53`.

---

## 2. Capability inventory

### 2.1 GOVERNED-REAL (in the real execution path today)

| Provider | Operation | Method / Path | SideEffectClass | R/W | Credential |
|---|---|---|---|---|---|
| GitHub | `repository.get_repository` | GET /repos/{o}/{r} | READ | read | bearer (blocked P5.5) |
| GitHub | `repository.get_issue` | GET .../issues/{n} | READ | read | ″ |
| GitHub | `repository.get_pull_request` | GET .../pulls/{n} | READ | read | ″ |
| GitHub | `repository.create_issue` | POST .../issues | IRREVERSIBLE_WRITE | write | ″ |
| GitHub | `repository.create_issue_comment` | POST .../comments | IRREVERSIBLE_WRITE | write | ″ |
| Grafana | `folder.get_folder` | GET /api/folders/{uid} | READ | read | `CORTEX_GRAFANA_TOKEN` (dev) |
| Grafana | `folder.create_folder` | POST /api/folders | REVERSIBLE_WRITE | write | ″ |

**[SOURCE]** `github.py:212-369`, `grafana.py:120-178`; wiring `capability_execution_composition.py:413/508`, `production_connectivity.py:426/722`, `grafana_provider_factory.py:31-75`.
**[FACT]** GitHub's real credential is blocked (Phase 5.5); Grafana's `folder.create_folder` is the **only governed real write proven end-to-end**. **[FACT]** No governed GitHub CI/CD, deploy, workflow, or list operation exists — the governed catalog has only these 5 GitHub ops.

### 2.2 GOVERNED-TEST-ONLY

| Provider | Operation | Effect | Purpose |
|---|---|---|---|
| controlled | `widget.create` | REVERSIBLE_WRITE | scripted crash/replay evidence |
| controlled | `widget.get` | READ | scripted read-back |

**[SOURCE]** `backend/api/controlled_provider_factory.py:45-80`. Runs every real gate, answers from a script, refuses PRODUCTION four ways, `CORTEX_CONTROLLED_PROVIDER`-gated. This is what every Phase 6/8 harness executes against.

### 2.3 QUARANTINED V1 connectors (19) — read/write class from `connectors/effects.py`

| Connector | R/W | Notable write ops (fail-closed) | Class |
|---|---|---|---|
| **Kubernetes** | **READ-ONLY** (write set empty) | — | OBSERVE |
| **Prometheus / Loki / OpenTelemetry / Grafana(V1)** | READ-ONLY | — | OBSERVE |
| **Docker** | R+W | pull/remove/prune image, restart_container | OBSERVE+MODIFY |
| **Terraform** | ALL WRITE (each spawns subprocess) | plan/apply/destroy/state_* | PLAN/MODIFY/CRITICAL |
| **GitHub(V1)** | R+W (24 writes) | create/merge PR, create_deployment, dispatch/rerun_workflow, create_release, update_branch_protection | full CI/CD+deploy |
| **GitLab CI / Jenkins / CircleCI / Azure DevOps** | R+W | pipeline/job trigger·cancel·retry | CI/CD |
| **ArgoCD** | R+W | sync/rollback/refresh_application | GitOps/CD |
| **Slack / Teams** | R+W | send_message, create_channel | notify |
| **Jira / ServiceNow / Confluence / Notion** | R+W | create/update/transition issue·incident·change·page | ticketing |

**[SOURCE]** `backend/connectors/effects.py:67-254`, `backend/main.py:1004-1032`. **[FACT]** All behind `CORTEXPRIME_ENABLE_LEGACY_EXECUTION`; **writes** refuse by default via `assert_effect_permitted` (first line of `BaseConnector._execute`); **reads pass ungoverned** with a process-wide credential (documented at `effects.py:26-29`). None uses `ProviderOperationSpec`.

### 2.4 ENTIRELY ABSENT

**[FACT]** No AWS/Azure/GCP **infrastructure control** (EC2/ECS/EKS/RDS/ELB/CloudWatch/IAM/S3), no PagerDuty, OpsGenie, Datadog, New Relic, Sentry, Splunk, DNS/Route53/Cloudflare, no dedicated load-balancer connector. AWS/Azure/Vault appear **only** as credential/secrets-read backends (`security_center/auth_providers.py:343-357`, `platform/credentials/vault.py`), not DevOps connectors. **[FACT]** `backend/connector/` (singular) is a **deleted** module (only stale `.pyc`, no `.py`).

---

## 3. Direct-action bypass inventory

**[FACT]** Within the strictly-governed planes (`backend/contexts`, `backend/platform.credentials`, `backend/world`, `backend/assurance`, `backend/intelligence`, `backend/harness`) there is **no** HTTP-client / cloud-SDK / subprocess / `eval`/`exec` import that reaches an external system. The only hits are `urllib.parse` string parsing and attribute-`getattr`. Fenced by ERROR-severity rules: `BND-WORLD-CANNOT-EXECUTE`, `BND-ASSURANCE-CANNOT-EXECUTE`, `BND-INTELLIGENCE-CANNOT-EXECUTE`, `BND-HARNESS-NO-EXECUTION`/`-NO-DYNAMIC-DISPATCH`/`-CREDENTIALS`, `BND-DIRECT-HTTP`, `BND-PROVIDER-SDK`, `BND-PROCESS-SPAWN`, `BND-AMBIENT-CREDENTIALS`. [SOURCE] Agent-B scan; `boundary_rules.py:1695-1721`.

**[FACT]** The two governed-plane external-egress points are both accounted for: (1) `backend/platform/transport/*` — the **sanctioned** ADR-041 gateway transport (`KEEP`); (2) `backend/connectors/*` — the **V1 quarantine** whose writes are fail-closed behind `BND-EFFECT-GATE` + the legacy flag, reads ungoverned.

**Residual bypasses (all QUARANTINED V1 / OTHER planes, gated by the legacy flag):**

| Path | file:line | Class |
|---|---|---|
| `getattr(connector, operation)` dynamic dispatch | `services/enterprise_mission_orchestrator.py:484`, `services/verification_service.py:143+`, `services/enterprise_watchers.py:66` | **QUARANTINE** (legacy-flag gated) |
| raw `exec(command,...)` | `execution/sandbox/interfaces.py:282` | **QUARANTINE** (sandbox) |
| `boto3`/`botocore`/`azure` SDK client construction | `security_center/auth_providers.py:343-357` | **REPLACE/QUARANTINE** — **caught by NO boundary rule** (gap, §23) |
| V1 connector reads (ungoverned, process-wide credential) | `connectors/base.py:9`, `effects.py:26-29` | **MIGRATE** (strangle to governed reads) |

**[INFERENCE]** No governed-plane bypass exists today. The residual risks live in V1/OTHER planes, are legacy-flag-gated, and one real fitness gap (boto3/azure SDK construction outside the governed plane) should be closed if any cloud read is ever added (§23).

---

## 4. Capability taxonomy

**[INFERENCE, derived from `SideEffectClass` + `connectors/effects.py` semantics]** Mapping real operations onto categories:

| Category | Definition | Example operations (from the tree) |
|---|---|---|
| **OBSERVE** | READ, no state change, safe to retry | K8s list/get pod·deployment·events·logs·nodes; Prometheus query/query_range; Loki query; Grafana get_folder; GitHub get_repository/get_issue |
| **DIAGNOSE** | pure reasoning over observations (no provider) | investigation engine, differential diagnosis (8.4) — no side effect |
| **PLAN** | generate a proposed change, no effect | Terraform `plan` (V1, but subprocess → currently WRITE-classed); model-proposed remediation (8.5) |
| **SIMULATE** | dry-run / what-if | Terraform `plan`, `--dry-run` (not yet governed) |
| **MODIFY** | REVERSIBLE_WRITE / IRREVERSIBLE_WRITE | Grafana create_folder (REVERSIBLE); Docker restart_container; ArgoCD sync; GitHub create_issue (IRREVERSIBLE) |
| **ROLLBACK** | restore a prior known state | ArgoCD rollback_application; K8s `rollout undo` (does not exist as an op) |
| **VERIFY** | independent read-back after a MODIFY | any OBSERVE re-run through the Assurance verifier (7.7) |

**[FACT]** Terraform's `plan` is currently WRITE-classed because it spawns a subprocess [SOURCE] `effects.py:124-129` — so "PLAN" is not cleanly separable from side-effect today.

---

## 5. Capability contract assessment (Part D)

**[FACT]** The governed capability/binding contracts already carry ~7 of the 15 Phase-9 desired fields cleanly; ~4 partially; **5 are genuine gaps on the governed `CapabilityContract`**. [SOURCE] `backend/contexts/connectivity/domain/contract.py:150-171`, `commands.py:38-98`, `provider_operation.py:281-329`.

| Field | Status | Evidence |
|---|---|---|
| capability_ref, provider, operation, side_effect_class, required_permissions, idempotency (`idempotency_supported`/`supports_idempotency_key`), timeout (`timeout_seconds`) | **EXISTS** | `contract.py:155-172`, `provider_operation.py:312-319` |
| reversibility | **PARTIAL** — encoded via `side_effect_class`; a first-class `reversible` bool exists only on the **Phase-8 intelligence `Capability`** (`autonomy.py:65`), decoupled from the governed contract |
| rollback_capability | **PARTIAL** — `compensation_capability: Optional[str]` + `cancellable`/`retryable` (`contract.py:169`) |
| tenant_scope | **PARTIAL** — `tenancy`/`tenant_id`/`shared_with` (`definition.py:169-173`) |
| policy_version | **PARTIAL / different level** — on the binding (`authorization_policy_version`) not the contract |
| **resource_scope** | **[GAP]** — only at credential-resolution (`CredentialScope.resource`) and on `AutonomyScope.resource_class` |
| **risk_classification** | **[GAP]** — risk lives only in the Phase-8 autonomy plane, not on the governed capability |
| **verification_requirement** | **[GAP]** — nearest is capability `trust`/`TrustState`; no per-capability verification requirement |
| **autonomy_ceiling** | **[GAP]** — lives in `AutonomyPolicyConfig`/`AutonomyScope`, not on the capability |
| **rate_limit** | **[GAP]** — infra only (`safety/rate_limiter.py`), not a capability field |

**[INFERENCE — the central Phase 9.1 gap]** `reversible`, `risk`, `verification_requirement`, and `autonomy_ceiling` semantics **already exist**, but on the **Phase-8 intelligence/autonomy plane** (`backend/contracts/intelligence/autonomy.py`), **decoupled** from the governed connectivity `CapabilityContract` that actually governs execution. **The Phase 9.1 job is a contract bridge**, not new semantics: let a governed capability declare (or reference) its risk classification, reversibility, verification requirement, and autonomy ceiling so the `AutonomyPolicy` (8.8) can evaluate a real capability, and the EXECUTING gate can bind them — reusing `RiskClassification`, `Capability`, `AutonomyPolicy`, `SideEffectClass`, and the existing `CapabilityContract`. **[PROPOSAL]** Do this by composition/reference (a capability names its `RiskClassification` + `autonomy_ceiling` + `verification_requirement`), never by duplicating the risk/autonomy types.

---

## 6. Read-first strategy (Part E)

**[PROPOSAL]** The first production capability set is READ-only, strangled into governed `ProviderOperationSpec` connectors, each feeding: `provider READ → governed execution (exec_id) → Observation → Fact/Belief → WorldQuery → evidence`. The World Plane never calls a provider (`BND-WORLD-CANNOT-EXECUTE` enforces this).

Priority (evidence-ordered):
1. **Kubernetes state** (pod/deployment/node) — reads exist in V1 (`kubernetes.py`), must be re-implemented as a governed read connector preserving `resourceVersion` (§9).
2. **Kubernetes events + logs** — `list_events`, `get_pod_logs` exist in V1.
3. **Prometheus / Loki** — `query`/`query_range` reads exist in V1 (read-only connectors, §13).
4. **GitHub CI/CD state** — governed reads exist (get_repository/issue/PR) but the real credential is Phase-5.5-blocked; V1 has the CI/CD reads.
5. **Terraform state observation** — read-only `state show` (currently subprocess-WRITE-classed, §12).
6. **AWS infrastructure state** — **absent**; deferred (§10).

---

## 7. Write capability strategy (Part F)

**[FACT]** Today the only governed real write is Grafana `folder.create_folder` (REVERSIBLE_WRITE) — a dashboard-folder create, **not an incident remediation**. **[FACT]** No governed Kubernetes write exists (write set empty); K8s restart/scale/rollback are **not** connector methods anywhere. **[FACT]** GitHub writes exist governed but are credential-blocked and IRREVERSIBLE (create_issue/comment).

**[INFERENCE]** There is **no evidence-supported governed remediation write available today**. A first reversible write must be **built** as a governed `ProviderOperationSpec` with: a declared reversible SideEffectClass, an independent read-back verification, a known rollback, and an autonomy ceiling. **[PROPOSAL]** The first write candidate (Phase 9.6) is a **Kubernetes rollout restart of a stateless deployment in a development namespace** — reversible (a restart re-creates pods; the prior state is the same Deployment spec), low blast radius, independently verifiable (read pod readiness back), idempotent-ish (a restart annotation), with a known failure state (pods fail readiness → escalate). **Do not enable it merely because it is an example** — it is proposed *because* it is the only candidate the read fabric can independently verify, and only after §9/§16/§17/§18 are satisfied.

---

## 8. Incident vertical candidates (Part H/T)

| Candidate | Observations available | Governed write available | Verifiable | Rollback | Blast | Verdict |
|---|---|---|---|---|---|---|
| **K8s CrashLoopBackOff / deployment failure** | pods/deployments/events/logs (V1 reads → strangle) | none yet (restart to be built 9.6) | yes (readiness read-back) | restart/rollback | low (dev) | **RECOMMENDED (read-first)** |
| Failed CI deployment | GitHub/GitLab CI reads (V1); governed GH reads credential-blocked | none governed | partial | rerun | medium | DEFER (credential-blocked) |
| Config drift (Terraform) | Terraform state (subprocess) | apply (all-write, subprocess) | plan-diff | apply prior | high | DEFER (Terraform not governed, §12) |
| Service unavailable | Prometheus/Loki + K8s | none | yes | — | varies | Follow-on to K8s vertical |
| Resource exhaustion | Prometheus/K8s metrics | scale (not an op) | yes | scale-down | medium | Follow-on |

**[INFERENCE]** **Kubernetes deployment-failure / CrashLoopBackOff investigator** is the first vertical: the richest read surface already exists, it is independently verifiable via read-back, it has a natural low-blast reversible write (restart) to build later, and it does not depend on the credential-blocked providers.

---

## 9. Kubernetes assessment (Part I) — **[BLOCKER: yes]**

**[FACT]** `backend/connectors/kubernetes.py` is a **V1 read-only** connector (`BaseConnector`, effect-gated, write set empty) exposing `list/get` pod·deployment·node·events·logs·namespaces·pvcs·services. [SOURCE] `kubernetes.py:31,144-625`, `effects.py:116,201-206`.

**[FACT/BLOCKER]** It **strips `resourceVersion`** on every LIST (extracts only `.items`, discards the envelope's `metadata.resource_version`), has **no `watch()`**, and **no 410/Gone recovery** (`_api_call` retries only {429,500,502,503,504}). Grep finds zero `resourceVersion`/`watch`/`_continue` hits. [SOURCE] `kubernetes.py:213-241,307-342,27-28,131-138`; Phase-7.4 report §13.

**[INFERENCE]** WATCH **cannot be safely built on the current connector** — doing so would require fabricating continuity, silently restarting from "latest", a second connector, or a World→Kubernetes socket — **every one a STOP condition**. **[PROPOSAL]** Sequence: (9.2) build a **governed** K8s LIST/GET connector as a `ProviderOperationSpec` set that **preserves `resourceVersion`** in the response evidence; (9.3) add WATCH (`ExecutionMode.STREAMING` exists in the contract vocabulary at `contract.py:93`, unused) with 410 → re-LIST-from-scratch recovery, resuming from the preserved `resourceVersion`. **[FACT]** K8s auth via `KUBECONFIG`/in-cluster service-account is an **allowed ambient-infra path** (excluded from `BND-AMBIENT-CREDENTIALS` as a local infra endpoint, not a provider credential) [SOURCE] `connector_credential_composition.py:24-28`, `kubernetes.py:49-53` — so K8s reads do not require the Phase-5.5-blocked provider-credential fabric.

---

## 10. AWS assessment (Part J)

**[FACT]** No AWS DevOps connector exists; `boto3` is used only for Secrets Manager reads (`auth_providers.py:354-369`). **[INFERENCE]** AWS infra reads (EC2/RDS/ELB/CloudWatch) are **entirely absent** and **credential-blocked** (Phase 5.5 class). **[PROPOSAL — DEFER]** AWS read fabric is a later phase (≥9.7), and only for the minimum surface a chosen incident class needs; credential handling must reuse the governed credential composition (no ambient fallback — enforced by `BND-AMBIENT-CREDENTIALS`, but note `boto3` client construction is not covered by `BND-PROVIDER-SDK` today, §23). **STOP** honestly: real AWS credentials are unavailable, so AWS remains BLOCKED.

---

## 11. GitHub assessment (Part K)

**[FACT]** Governed GitHub has 5 ops (3 read, 2 IRREVERSIBLE write); the real credential is **Phase-5.5-blocked** [SOURCE] `ADR-049...md:11-16`. The V1 GitHub connector has the full CI/CD + deploy surface (rerun_workflow, create_deployment) but is quarantined and legacy-flag-gated. **[PROPOSAL — DEFER]** GitHub CI/CD governed reads (workflow/run/job/logs/deployment) are valuable for a CI incident vertical, but (a) the credential blocker stands and (b) writes (rerun/deploy) are IRREVERSIBLE and need risk+rollback+verification defined first. Phase 5.5 blocker **remains untouched**; no credential is manufactured or inspected here.

---

## 12. Terraform assessment (Part L)

**[FACT]** The V1 Terraform connector classifies **every** op as WRITE because each spawns a subprocess (`asyncio.create_subprocess_exec`), including `plan`/`state show` [SOURCE] `connectors/terraform.py:161`, `effects.py:124-129`. It is one of the four `BND-PROCESS-SPAWN`-allowlisted modules. **[INFERENCE]** Terraform must **not** become an uncontrolled execution path. The correct model (Part L): World observes Terraform *state* (a read), Intelligence proposes a change, the harness generates a deterministic `plan`, human/governance approves, and `apply` runs as an **existing governed capability** with verification. **[FACT/BLOCKER]** The current subprocess integration cannot preserve this without a governed `ProviderOperationSpec` wrapper; `plan` is not cleanly side-effect-free today. **[PROPOSAL — DEFER]** Terraform is a late-phase, human-approved-only capability; not part of the first vertical.

---

## 13. Observability assessment (Part M)

**[FACT]** Prometheus, Loki, OpenTelemetry, and Grafana(V1) are **read-only** V1 connectors [SOURCE] `effects.py:120,213-227`. **[INFERENCE, Phase-7 mapping]** For the World Plane these are **derived, non-authoritative** sources: metrics/logs are instrument readings, not the system of record. They must consume the Phase-7 discipline — `SourceAuthority` (a metric is SINGLE_SOURCE unless corroborated), `SourceLineage` (Prometheus scraping the same exporter as Grafana shares lineage → not independent), `FreshnessPolicy` (a stale metric ≠ FALSE), and `Corroboration` (K8s API + Prometheus agreeing = CORROBORATED). **Never turn telemetry into truth because it is newer** — the World Plane's authority≠recency rule (7.4) governs. **[PROPOSAL]** Observability governed reads are Phase 9.4 (corroborating World sources for the K8s vertical), each strangled into a governed `ProviderOperationSpec` read.

---

## 14. Risk / blast-radius matrix (Part N)

**[PROPOSAL, reusing `RiskFactors`/`RiskLevel`/`SideEffectClass` — deterministic, operation-specific, no global score]**

| Capability | Operation | Env | SideEffectClass | RiskLevel | Reversible | Verification | Autonomy ceiling |
|---|---|---|---|---|---|---|---|
| Kubernetes | list/get pods, deployments, events, logs | any | READ | LOW | n/a | n/a (observe) | A1 |
| Prometheus | query / query_range | any | READ | LOW | n/a | n/a | A1 |
| Grafana | folder.get_folder | any | READ | LOW | n/a | n/a | A1 |
| Grafana | folder.create_folder | dev | REVERSIBLE_WRITE | LOW | yes | read-back folder | A3 (candidate) |
| Kubernetes | rollout restart (to build) | dev | REVERSIBLE_WRITE | LOW–MEDIUM | yes | pod readiness read-back | A3–A4 (dev), A3 (prod) |
| Kubernetes | scale deployment (to build) | dev | REVERSIBLE_WRITE | MEDIUM | yes (scale back) | replica read-back | A3 |
| ArgoCD | rollback_application | prod | REVERSIBLE_WRITE | MEDIUM | yes | sync-status read-back | A2–A3 |
| GitHub | create_issue | any | IRREVERSIBLE_WRITE | MEDIUM | no | n/a | A2 (human) |
| Terraform | apply | prod | IRREVERSIBLE_WRITE | HIGH | partial | plan-diff read-back | A2–A3 (human) |
| Terraform | destroy | prod | DESTRUCTIVE | CRITICAL | no | — | A1 (never autonomous) |

**[FACT]** Risk stays operation-specific and computed from declared `RiskFactors`; `RiskLevel` caps autonomy via `AutonomyPolicyConfig.cap_for_risk` (LOW→A4 … CRITICAL→A1). No single global risk score.

---

## 15. Autonomy matrix (Part O)

**[PROPOSAL — `AutonomyPolicy` remains the authority; these are ceilings, earned per §16-18 evidence]**

| Capability | Operation | Environment | Max Autonomy (ceiling) | Rationale |
|---|---|---|---|---|
| Kubernetes | get/list (observe) | prod | A1 | read-only; no action |
| Kubernetes | rollout restart (stateless) | dev | A4 candidate | reversible, low blast, verifiable |
| Kubernetes | rollout restart (stateless) | prod | A3 candidate | reversible, but production blast |
| Kubernetes | scale (non-critical) | dev | A3 | reversible, medium blast |
| Grafana | create_folder | dev | A3 | reversible, but not incident-relevant |
| ArgoCD | rollback | prod | A2/A3 | reversible if prior revision verified |
| Terraform | plan | prod | A2 | proposal only |
| Terraform | apply | prod | A3 (human) | IRREVERSIBLE, high blast |
| Terraform | destroy | prod | A1 (never) | destructive |
| GitHub | create_issue/comment | any | A2 | IRREVERSIBLE, human owns |

**[FACT]** These are **ceilings**, not grants. `AutonomyPolicy.evaluate` (8.8) grants the effective level only when calibration (8.7) + assurance coverage + fresh non-conflicted world + reversibility + no drift + compatible version all hold, and downgrades on drift/conflict/stop/breaker.

---

## 16. Verification matrix (Part P)

| Action | Expected effect | Observation | Outcome | Assurance procedure |
|---|---|---|---|---|
| K8s rollout restart | pods recreated, readiness=True | list pods for the deployment (governed read) | exec_ref + observed readiness | independent read-back via `COMPARE_WORLD_STATE`/`INSPECT_EXECUTION_RESULT` (7.7) |
| K8s scale | replica count = N, all ready | get deployment + list pods | observed replicas | independent read-back |
| Grafana create_folder | folder exists with uid | folder.get_folder | observed folder | independent read-back (proven pattern) |
| ArgoCD rollback | app synced to prior revision | get application status | observed sync/health | independent read-back |
| GitHub create_issue | issue exists | get_issue | observed issue | read-back (but IRREVERSIBLE) |

**[FACT/INFERENCE]** **If an operation cannot be independently read back, it is unsuitable for autonomous execution.** K8s restart/scale and Grafana folder are verifiable via existing read shapes; Terraform apply is only partially verifiable (plan-diff), so it stays human-approved.

---

## 17. Rollback matrix (Part Q)

| Action | Rollback operation | Rollback authority | Rollback verification | Failure state |
|---|---|---|---|---|
| K8s rollout restart | (re-)apply prior Deployment spec / `rollout undo` | same governed capability, A3 | pod readiness read-back | pods unready → escalate (human) |
| K8s scale N→M | scale back M→N | governed capability | replica read-back | mismatch → escalate |
| Grafana create_folder | delete_folder (to build) | governed capability | folder.get_folder returns 404 | folder persists → escalate |
| ArgoCD rollback | forward-sync to prior good | governed capability | sync read-back | out-of-sync → escalate |
| Terraform apply | apply previous state | human-only | plan-diff | drift → human |

**[FACT/INFERENCE]** **No autonomous write without a known failure strategy.** K8s restart/scale have deterministic rollbacks; anything without one (create_issue, destroy) is capped below autonomous execution or requires explicit human escalation policy.

---

## 18. Idempotency / unknown-commit matrix (Part R)

| Provider op | Idempotency key | Provider semantics | Retry | Unknown-commit | Obs dedup | Exec ref |
|---|---|---|---|---|---|---|
| K8s rollout restart | restart annotation (deterministic) | NON_IDEMPOTENT_WRITE unless keyed | governed retry (leased) | re-list pods; same-state dedups | `observation_identity` (7.2) | exec_id |
| K8s scale | target replica (declarative → idempotent) | idempotent (desired state) | governed retry | re-read replicas | 7.2 dedup | exec_id |
| Grafana create_folder | folder uid | NON_IDEMPOTENT_WRITE | governed retry | 409 on repeat; read-back | 7.2 dedup | exec_id |
| GitHub create_issue | none | NON_IDEMPOTENT_WRITE | no auto-retry | duplicate issue risk | — | exec_id |

**[FACT]** `ProviderOperationSpec.supports_idempotency_key`/`idempotency_header` exist [SOURCE] `provider_operation.py:312-313`; `EffectSemantics.UNKNOWN` is never treated as safe. **At-least-once remains the default; exactly-once is not claimed.** A declarative scale is naturally idempotent; a restart/create is not and needs a key or dedup via read-back.

---

## 19. Experience integration (Part S)

**[FACT]** Phase 8.6 experience is a reference-only projection that can inform hypothesis generation, test selection, and prioritization, and is injected as a labelled HISTORICAL context section — but it **can never authorize action** (no `to_fact`/`to_outcome`, and `BND-MODEL-CANNOT-CREATE-FACT`). **[INFERENCE]** For the K8s vertical, prior CrashLoopBackOff episodes inform the differential ("last time it was an image pull error"), but the current investigation must acquire its own governed evidence and the `AutonomyPolicy` consumes only *independent* calibration — historical experience ≠ current truth, and it is structurally outside the autonomy decision (`BND-AUTONOMY-NOT-MODEL-DRIVEN`).

---

## 20. Product UX (Part U)

**[PROPOSAL]** The DevOps engineer's flow, exposing structured evidence, never chain-of-thought:
1. establish tenant/context → 2. governed World reads (pods/events/logs) → 3. build durable investigation → 4. differential diagnosis → 5. deterministic evidence-gap + test selection → 6. governed investigation (more reads) → 7. propose likely cause (with evidence refs) → 8. predict remediation → 9. `AutonomyPolicy` evaluates authority (scoped, from calibration/assurance/risk) → 10. request digest-bound human approval if required → 11. execute through the ONE gateway → 12. independent read-back verification (Assurance) → 13. report outcome + verdict + evidence → 14. record experience + calibration.
**[FACT]** Every stage already exists (Phases 5–8); the UI surfaces `AutonomyDecision.to_dict`, the calibration `ReliabilityEstimate`, the assurance `Verdict`, the World `WorldQueryResult` — all structured, none hidden.

---

## 21. V1 strangler plan (Part V)

**[PROPOSAL] — no dual execution, no shadow write, no second authority.**

| V1 capability | Classification | Rationale |
|---|---|---|
| K8s reads (list/get/logs/events) | **MIGRATE** → governed `ProviderOperationSpec` (9.2), preserving resourceVersion | first vertical's read surface |
| Prometheus/Loki reads | **MIGRATE** → governed reads (9.4) | corroborating World sources |
| K8s writes (restart/scale) | **REPLACE** (build governed, do not enable V1) | none exist in V1 anyway |
| Grafana(V1) reads | **QUARANTINE** (governed Grafana already exists for the needed ops) | avoid duplication |
| GitHub(V1) CI/CD | **QUARANTINE** until governed + credential-unblocked | credential blocker |
| Terraform | **QUARANTINE** → later governed, human-approved plan/apply | subprocess execution path |
| ArgoCD, GitLab/Jenkins/CircleCI/Azure DevOps | **QUARANTINE** | not first-vertical |
| Slack/Teams/Jira/ServiceNow/Confluence/Notion | **QUARANTINE** (notify/ticket, not remediation) | out of scope |
| `backend/connector/` (singular, .pyc only) | **DELETE** (already source-removed) | dead bytecode |
| `enterprise_mission_orchestrator` `getattr(connector, op)` | **QUARANTINE** (legacy-flag gated) then **DELETE** as capabilities migrate | the internal bypass |

**[FACT]** All V1 writes stay fail-closed behind `CORTEXPRIME_ENABLE_LEGACY_EXECUTION`; migration means a governed `ProviderOperationSpec` replaces the V1 read/write, never a parallel path.

---

## 22. Credential / security assessment (Part W)

**[FACT]** The governed credential fabric is fail-closed and correct: `CredentialRef` carries no secret; `CredentialScope.covers()` enforces subset + resource-binding (confused-deputy guard); credentials minted **last** (stage 13), lifetime ≤ 900s bound to the authority window; the broker refuses any broader/wrong-tenant/wrong-resource/expired/cached/env credential ("No fallback, anywhere"); `IssuedCredential` blocks serialization; audit stores only grant metadata. [SOURCE] `contracts/credential.py`, `invocation_gateway.py:1356-1439`, `broker.py:1-76`.

**[FACT]** The secret firewall `find_secrets` scans four ways (key-name / value-shape / credential-type / encoded) and `assert_no_secrets` raises on any finding [SOURCE] `inspection.py:79-161` — the tripwire behind every World/Fact/Belief/Investigation/Prediction/Trace/Experience/Audit write.

**[FACT]** **Phase 5.5 credential blocker is INTACT and untouched** — no real GitHub/cloud credential authenticates; `DevelopmentCredentialProvider` refuses production and holds no secrets of its own. **No secret material** enters World/Fact/Belief/Investigation/Prediction/Trace/Experience/Audit — only references/digests/effects. **[FACT]** `KUBECONFIG`/`DOCKER_HOST`/`VAULT_TOKEN` are deliberately excluded from `BND-AMBIENT-CREDENTIALS` as infra endpoints/bootstrap — so K8s in-cluster auth is an allowed ambient-infra path, consistent with a read-only connector.

---

## 23. Fitness-rule assessment (Part X)

**[FACT]** 23 boundary rules exist; the governed-plane fences are comprehensive (§3). **[FACT] Two real gaps:**
1. **`boto3`/`botocore`/`azure` SDK client construction is caught by NO rule** — `BND-PROVIDER-SDK` covers only `docker`/`kubernetes` [SOURCE] `boundary_rules.py:637`. Currently only in the OTHER-plane `security_center`; **[PROPOSAL]** extend `BND-PROVIDER-SDK`'s SDK set (or add `BND-NO-CLOUD-SDK-OUTSIDE-CONNECTOR`) before any AWS/Azure read is added — CURRENT=PASS (governed plane imports none), SYNTHETIC=FAIL.
2. **V1 connector reads are ungoverned** (process-wide credential) — acceptable while quarantined, but a strangled governed read must route through the credential fabric; **[PROPOSAL]** when K8s reads migrate, the ungoverned read path should be closed.

**[PROPOSAL] genuinely-new rules for Phase 9.1+ (only if the capability-contract bridge lands):**
- `BND-WRITE-CAPABILITY-DECLARES-RISK-AND-VERIFICATION` — a governed capability with `side_effect_class.mutates` must declare a `RiskClassification` + `verification_requirement` + reversibility. CURRENT would need the §5 bridge first; SYNTHETIC=FAIL (a mutating capability with no risk/verification).
- `BND-CAPABILITY-AUTONOMY-CEILING-REQUIRED` — a governed write capability must declare an `autonomy_ceiling`.
**[INFERENCE]** `BND-MODEL-CANNOT-PROMOTE-AUTONOMY`, `BND-AUTONOMY-CANNOT-BYPASS-GOVERNANCE`, `BND-CALIBRATION-CANNOT-AUTHORIZE`, `BND-NO-DIRECT-PROVIDER-ACTION`, `BND-NO-AMBIENT-CREDENTIALS` are **already enforced** by existing rules (`BND-AUTONOMY-NOT-MODEL-DRIVEN`, `BND-INTELLIGENCE-CANNOT-EXECUTE`, `BND-EFFECT-GATE`, `BND-AMBIENT-CREDENTIALS`) — **do not add cosmetic duplicates**.

---

## 24. Competitive / strategic analysis (Part Y)

**[INFERENCE, from public knowledge of the 2026 landscape — not repository facts]**

- **Code agents (Cursor, Claude Code, GitHub Copilot, Google Jules, OpenAI Codex, Amazon Q Developer):** operate on *code* in a dev/CI sandbox; they open PRs and run tests. Execution is sandboxed; the **PR + human review is the approval boundary**; "verification" is running the test suite, not reading production world state. They do **not** maintain a bitemporal World model, do **not** separate model reasoning from world truth (model output can become a suggestion acted on), and treat **model confidence as the uncertainty signal** (verbalized, not calibrated to outcomes). Autonomy is sandbox-scoped + PR-gated, not earned from empirical reliability.
- **AIOps / incident agents (Datadog Bits AI, PagerDuty AIOps, incident copilots):** observe telemetry, correlate alerts, suggest/auto-run runbooks. They **do** act on infra, but "truth" is telemetry (**newer ≈ truer**, no source-authority/lineage/freshness discipline), verification is often the **same** signal that triggered (correlated, not independent), and governance is static RBAC + runbook approval, not calibrated/revocable earned autonomy.
- **Kubernetes AI agents (k8sgpt and copilots):** diagnose from kubectl/logs, suggest fixes; writes via `kubectl apply` + human. No independent assurance plane, no calibration, no bitemporal world.
- **Infra copilots (Pulumi/Terraform AI):** generate IaC; apply via existing CI/CD + review.

**[INFERENCE] Common structural gaps across all:** (a) model confidence treated as signal, not calibrated to real outcomes; (b) telemetry-as-truth (no bitemporal World, no authority/lineage/freshness — newer overwrites); (c) verification by the same source that produced the claim, not an independent plane; (d) autonomy is role/RBAC-static, not earned from empirical reliability and revocable on drift; (e) no durable, replay-safe, crash-safe governed execution with per-action policy + hash-chained audit; (f) model output can become truth/action without a firewall.

**[INFERENCE — honest framing]** CortexPrime's tested differentiator is **WORLD + EVIDENCE + INVESTIGATION + ASSURANCE + EARNED AUTHORITY + GOVERNED EXECUTION** — an epistemic + governance discipline the shipping systems structurally lack. **But the honest counter-fact is that CortexPrime has essentially zero real production capability today** (7 governed ops, GitHub credential-blocked, K8s read-only-and-ungoverned), while the competitors have broad real capability with weaker discipline. **Phase 9 is precisely the test of whether the discipline survives contact with real capability.** No uniqueness is claimed beyond the discipline; the bet is that the discipline is worth more than breadth for production remediation.

---

## 25. Recommended Phase 9 roadmap

**[PROPOSAL] — evidence-ordered; smaller than the phase's suggested outline where evidence warrants.**

| Phase | Deliverable | Why |
|---|---|---|
| **9.1** | **Capability-contract bridge + registry**: let a governed capability declare/reference `RiskClassification` + reversibility + `verification_requirement` + `autonomy_ceiling` + `resource_scope`, reusing Phase-8 `Capability`/`AutonomyPolicy`/`RiskLevel` (the §5 gap). No new risk/autonomy semantics. | Unblocks every governed write's earned-authority evaluation |
| **9.2** | **Governed Kubernetes READ connector** (`ProviderOperationSpec`, preserves `resourceVersion`): list/get pods·deployments·events·logs. Feeds Observation→Fact→WorldQuery. | The first vertical's read surface; unblocks WATCH |
| **9.3** | **Kubernetes WATCH** (resourceVersion continuity + 410 → re-LIST recovery) on the 9.2 connector. No fabricated continuity. | Real-time world for the vertical |
| **9.4** | **Observability governed reads** (Prometheus/Loki) as corroborating World sources, with authority/lineage/freshness. | Corroboration, not telemetry-as-truth |
| **9.5** | **K8s deployment-failure / CrashLoopBackOff investigator vertical** (read-only, A0–A2): full loop minus write. | Proves World→Evidence→Investigation→Prediction→Verification→Experience end-to-end on a real read surface |
| **9.6** | **First governed reversible WRITE**: K8s rollout restart of a stateless dev deployment — risk-declared, independently read-back-verified, with a known rollback + autonomy ceiling. | Proves governed action + earned authority + verification on a real write |
| **9.7** | **AWS/GitHub governed reads** (credential-gated; behind the fitness gap closure of §23). DEFERRED until credentials exist. | Breadth after the vertical is proven |
| **9.8** | **V1 strangler + production hardening + final integration gate.** | Shrink the quarantine; no dual path |

**[FACT]** Every phase reuses the existing executor/scheduler/gateway/approval/audit/world-store/assurance/calibration/autonomy — **no second authority of any kind**.

---

## 26. Explicit DEFER / REJECT list

**[PROPOSAL]**
- **REJECT (structural):** enabling any V1 write connector directly (Terraform apply/destroy, ArgoCD sync, GitHub V1 deploy, Docker restart) — they bypass the governed capability contract and the earned-authority evaluation.
- **REJECT:** K8s WATCH on the current V1 connector (fabricated continuity = STOP condition).
- **REJECT:** treating telemetry (Prometheus/Grafana) as authoritative because it is newer (violates authority≠recency, 7.4).
- **REJECT:** any global "agent trust score."
- **DEFER:** AWS/Azure/GCP infra connectors (absent + credential-blocked) — ≥9.7.
- **DEFER:** GitHub governed writes and CI/CD reads (Phase-5.5 credential blocker) — until real credentials exist.
- **DEFER:** Terraform governed plan/apply (human-approved only) — late phase.
- **DEFER:** Datadog/PagerDuty/DNS/LB (absent; not needed for the first vertical).

---

## 27. Stop-condition results

**[FACT]** Checked against the phase's STOP conditions for the **recommended read-first K8s vertical (9.2–9.5)**:

| Stop condition | Triggered? | Evidence |
|---|---|---|
| Capability requires bypassing the One Plane of Action | **No** | governed `ProviderOperationSpec` read routes through the gateway |
| A connector must own credentials | **No** | K8s uses KUBECONFIG (allowed infra path); provider creds via the fabric |
| World must directly call a provider | **No** | reads go execution→Observation→WorldQuery; `BND-WORLD-CANNOT-EXECUTE` holds |
| Operation cannot be independently verified | **No (reads)** / **must hold for writes** | read-back exists; §16 gates writes |
| Autonomy semantics must be invented | **No** | 8.8 `AutonomyPolicy` reused |
| Rollback unknown for an autonomous write | **N/A (read-first)** / **gate for 9.6** | §17 requires it before any autonomous write |
| Tenant scope cannot be established | **No** | tenant is structural on every contract |
| Provider semantics unclear | **No (K8s reads)** | list/get well-defined |
| An existing authority must be duplicated | **No** | reuse only |
| Only way is to weaken L1–L16 | **No** | no invariant weakened |
| Real credentials required but unavailable | **YES for GitHub/AWS/cloud** | Phase-5.5 blocker → those DEFERRED/BLOCKED; K8s in-cluster/kubeconfig is an allowed path |
| A V1 path cannot be safely quarantined | **No** | all V1 writes fail-closed behind the legacy flag |

**[INFERENCE]** The read-first Kubernetes vertical triggers **no** structural stop condition; the only real stop is the **credential blocker for cloud/GitHub providers**, which correctly DEFERS those to later phases and does not block the K8s read fabric (KUBECONFIG path). Where a real cluster is unavailable (no budget, per project context), 9.5 is proven against the K8s read *shape* + the controlled/scripted provider, honestly labeled — no fabrication.

---

## 28. Phase 9.1 Definition of Done

**[PROPOSAL]** Phase 9.1 (Capability-contract bridge + registry) is complete when:
- [ ] A governed capability can **declare or reference** its `RiskClassification`, reversibility, `verification_requirement`, `autonomy_ceiling`, and `resource_scope` — by **reuse/composition** of the existing `RiskLevel`/`RiskFactors`/`Capability`/`AutonomyPolicy`/`SideEffectClass`, never by duplicating those types.
- [ ] The `AutonomyPolicy` (8.8) can evaluate a **real governed capability** (not a synthetic `Capability`), and the investigation EXECUTING gate binds the resulting decision.
- [ ] No new executor/scheduler/gateway/approval/audit/world-store/assurance/calibration/autonomy system is created; no connector is added; no migration; no credential access.
- [ ] Fitness: `BND-WRITE-CAPABILITY-DECLARES-RISK-AND-VERIFICATION` (and/or `-AUTONOMY-CEILING-REQUIRED`) added **only if genuinely new**, CURRENT=PASS / SYNTHETIC=FAIL; the boto3/azure SDK gap (§23) closed or explicitly deferred with a rationale.
- [ ] Contracts + a projection/derivation are preferred over any new table; if a table is genuinely required it is append-only/immutable/tenant-scoped/secret-firewalled/deterministic.
- [ ] Unit tests + a real-Postgres harness prove a governed capability's risk/verification/autonomy-ceiling flows through `AutonomyPolicy` → EXECUTING gate → gateway on the **controlled provider** (real credentials still blocked, labelled).
- [ ] ADR-081 + a Phase 9.1 verification report; regression green; the architecture gate passes.
- [ ] L1–L16, One Plane of Action, World immutability, independent Assurance, tenant isolation, the secret firewall, and the **Phase 5.5 credential blocker** remain intact and untouched.

---

### Closing [INFERENCE]

Phases 5–8 built the control architecture; Phase 9 tests it against real DevOps capability. The evidence says: **build the smallest read-first Kubernetes fabric**, bridge the capability contract to the Phase-8 risk/autonomy plane, and earn the first reversible write only when it can be independently verified and rolled back. The differentiator (World + Evidence + Investigation + Assurance + Earned Authority + Governed Execution) is real but unproven against production; the honest first product loop is a **governed, read-first, human-supervised Kubernetes incident investigator** — with everything above it already built.
