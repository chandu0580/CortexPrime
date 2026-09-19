# PHASE 11.4 — Governed Autonomous Operations Implementation Map

- **Date:** 2026-09-11 · **Parent HEAD:** `b625ad2` (11.3 `ea3815d` + hosted model default) · **Branch:** `phase-1-foundation`
- **ADR:** `docs/adr/ADR-124-phase-11-4-governed-autonomous-operations.md` · **Verification:** `docs/PHASE_11_4_AUTONOMOUS_OPERATIONS_VERIFICATION_REPORT.md` · **Harness:** `scripts/phase114_autonomous_operations_harness.py` · **Provisioning:** `scripts/phase114_provision.sh`

## 1. Repository research (what was true at `b625ad2`)

| Component | State found | Consequence |
|---|---|---|
| `AutonomyPolicy` (Phase 8.8, ADR-078) | A0–A4, eleven ordered gates (stop, breaker, non-action, risk cap, version, calibration, assurance, drift, world, reversibility, approval); irreversible never autonomous; **no production caller** | reused as THE policy; two additive fields for the compensable path (D-4) |
| Calibration (ADR-077) | `CalibrationDatasetBuilder` / `ReliabilityEstimator` over `prediction` + `prediction_evaluation` reasoning rows and assurance verdicts, per prediction class | fed by every remediation (prediction before, evaluation after) |
| `cp_approval` + `SqlApprovalRepository` (ADR-121) | request / decide / withdraw / mark_consumed; `ApprovalFacts.is_valid_for`; `canonical_approval_digest` (ADR-090) | the ONE approval authority for human and delegated decisions; `decided_by` surfaced to authorization |
| `CapabilityAuthorizationService` | REQUIRE_APPROVAL for risk ≥ HIGH; approval digest checked by the gateway | + one rule: a non-human decider authorizes only a compensable, non-destructive capability (D-5) |
| Contained worker (9.9B/9.9C) | restart worker, envelope binding, token per execution, NetworkPolicy, RBAC verified | pattern reused for a second, separate rollback worker (D-2) |
| Kubernetes connector | deployment.get (revision, image), replicasets.list (revision), pods.list | evidence extended: uid, generation, observedGeneration, updated/unavailable replicas, paused, templateDigest, revisionHistoryLimit, conditions, PVC count; RS ownerUid + podTemplateDigest; pod ready + owner |
| `SqlIdempotencyStore` | claim(key, execution, digest) → first / repeat / conflict | action key and target fence (D-8) |
| `RecoveryAction` | RESUME / RETRY / RECONCILE / COMPENSATE / WAIT_FOR_HUMAN / FAIL | the vocabulary for bounded recovery (D-10) |
| `AssuranceVerifier` | COMPARE_WORLD_STATE with an independence firewall on the producer path | the verifier of remediation outcomes (D-9) |
| `GovernedModelBoundary` | schema firewall, durable span, scrubbed prompt | the remediation proposal boundary (D-11) |
| Phase 11.3 investigator | assessment with authority none; `on_outcome` absent | `on_outcome` hook → remediator |
| Product approvals | decision route with scoped authority, separation of duties, confirmation; execute route | decision route reused by humans; execute route refuses platform requests |

## 2. Real-world research applied

- **Kubernetes rollback semantics.** `kubectl rollout undo` is client-side: it copies the target ReplicaSet's pod template (minus `pod-template-hash`) into the Deployment; the server-side `rollback` subresource went away with `extensions/v1beta1`. Revisions live in the `deployment.kubernetes.io/revision` annotation on ReplicaSets; `revisionHistoryLimit` decides whether old revisions (and therefore the compensation) survive. A rollback renumbers the target revision and replaces pods — irreversible in history, compensable in declared state.
- **Optimistic concurrency.** JSON Patch `test` operations on `metadata.resourceVersion` and `metadata.uid` make the API server reject a write against a changed object; `dryRun=All` validates the exact patch server-side without persisting it.
- **Least privilege.** A namespace Role with `get,patch` on deployments and `list` on replicasets is sufficient; `kubectl auth can-i` with the token alone (no admin client certificate, which would override the token) is the verification.
- **Incident practice.** Rollback of a recent change is the standard first mitigation for a deploy-caused regression — and the wrong one for configuration, dependency or capacity failures, which is why the diagnosis must support the regression hypothesis and verification must confirm the incident ended.
- **AIOps auto-remediation and agent safety.** Industry guidance converges on graduated autonomy per action class, earned from outcome history, with fast revocation; indirect prompt injection through logs/annotations cannot be filtered to zero, so containment is structural (typed actions, schema, registry, no write path from text).

## 3. Architecture, as implemented

```
investigator (11.3) ── on_outcome ──▶ RemediationRuntime.offer                    backend/api/remediation_runtime.py
                                        │ assessment (cw_reasoning) ─ ROOT_CAUSE_IDENTIFIED / LIKELY_CAUSE?
                                        │ world: deployment.get + replicasets.list (reader SA, governed)
                                        │ MODEL ▶ GovernedRemediationProposalPort ▶ schema firewall
                                        │        (outage ▶ deterministic proposer ▶ recommendation only)
                                        ▼
                                RemediationPlanner.plan                             backend/api/remediation_planning.py
                                        │ registry ▶ diagnosis supports regression ▶ evidence ∈ investigation
                                        │ target = incident workload, UID-bound ▶ revision owned, template differs
                                        │ classify_action_risk ▶ blast radius ▶ compensation ▶ criteria
                                        │ POLICY: AutonomyPolicy.evaluate (calibration, breaker, caps …)
                                        │ action digest = canonical_approval_digest(parameters)
                                        ▼
                         cw_reasoning remediation_plan + remediation_event (append-only)
                                        │
                ┌───────────────────────┴───────────────────────────┐
         AUTONOMOUS (compensable,                               HUMAN_APPROVAL
         earned, policy on)                                     cp_approval pending ─▶ product decision route
         cp_approval decided_by policy:autonomy/…               (scoped authority, separation of duties)
                └───────────────────────┬───────────────────────────┘
                                        ▼
                               execute_plan: budget ▶ action-key claim ▶ STALE re-read ▶ target fence
                                        │ Prediction recorded
                                        ▼
  GovernedCapabilityWriter ▶ authorization (approval valid? delegated ⇒ compensable) ▶ gateway digest check
                                        ▼
  ContainedRollbackWorkerAdapter ─ HTTPS envelope + brokered token ─▶ contained-rollback-worker (Pod)
                                        │ binding ▶ authority window ▶ preconditions ▶ dry run ▶ JSON patch (test rv/uid)
                                        ▼
                                  Kubernetes API server
                                        ▼
  RemediationVerifier (reader SA) ▶ World observation/fact ▶ AssuranceVerifier ▶ verdict, discrepancy
                                        ▼
  _recover (bounded) ▶ escalated / resolved ▶ learned (PredictionEvaluation) ▶ closed
                                        ▼
  product API (GET only): /api/v1/remediation/{plans, plans/{id}, /replay, /cost, decisions, autonomy}
```

## 4. Lifecycle stages

`planned`, `proposal_rejected`, `prohibited`, `recommendation_only`, `autonomy_decided`, `approval_requested`, `approval_granted`, `approval_denied`, `approval_expired`, `stale`, `execution_refused`, `duplicate_suppressed`, `executing`, `executed`, `execution_failed`, `execution_unknown`, `verified`, `no_effect_confirmed`, `verification_failed`, `verification_insufficient`, `discrepancy`, `recovery_decided`, `escalated`, `learned`, `closed`. Replay maps them to the phases proposal → policy → approval → execution → verification → recovery → learning and reports causal gaps.

## 5. Files

### New

| File | Role |
|---|---|
| `workers/contained_k8s_rollback/worker.py`, `Dockerfile` | the contained rollback worker (stdlib, bound, preconditions, dry run, JSON patch) |
| `backend/contracts/remediation.py` | `RemediationPlan`, `ResourceTarget`, `BlastRadius`, `VerificationCriterion`, `RollbackStrategy`, `ProposalDecision`, stages, authorities, reversibility |
| `backend/intelligence/application/remediation_proposal.py` | proposal schema, governed proposal port, deterministic fallback proposer, system prompt |
| `backend/api/remediation_planning.py` | tool registry, `classify_action_risk`, `RemediationPlanner` |
| `backend/api/remediation_verification.py` | independent verifier, outcome proposition, discrepancy |
| `backend/api/remediation_runtime.py` | the loop: plan, govern, approve, stale check, claim, execute, verify, recover, learn, resume; embedded start |
| `backend/api/remediation_replay.py` | inert replay projection |
| `backend/api/product/remediation_routes.py` | GET plans, plan, replay, cost, decisions, autonomy metrics |
| `backend/api/contained_rollback_worker_factory.py` | composition of the rollback adapter and its credential provider |
| `scripts/phase114_provision.sh` | image, cert, SA/Role/RoleBinding, Deployment, Service, NetworkPolicy, forwarder, token-only RBAC checks |
| `scripts/phase114_autonomous_operations_harness.py` | the real-infrastructure verification |
| `tests/contexts/execution/test_contained_rollback_worker.py` | worker binding, preconditions, dry run, patch, refusals |
| `tests/contexts/execution/test_delegated_approval_authorization.py` | delegated approval valid only for compensable, non-destructive |
| `tests/intelligence/test_remediation_planning.py` | registry, risk, planner refusals and plan shape |
| `tests/intelligence/test_autonomy_compensable.py` | the compensable gate, default off, destructive never |
| `tests/intelligence/test_remediation_runtime.py` | lifecycle against fakes: approve, deny, expire, stale, duplicate, fence, lie, fail, unknown, no-effect, resume |
| `tests/harness/test_boundary_attacks.py`, `tests/intelligence/test_governed_reader_drive.py` (additions) | failure span on provider error (no key leak); dispatch-refusal code reaches the caller |

### Modified

| File | Change |
|---|---|
| `backend/contexts/execution/infrastructure/adapters/contained_worker.py` | `ContainedRollbackWorkerAdapter` (operation, envelope with `authority_expires_at`, required arguments); definite worker failures classified by status (`_failure_for_status`; the old `PROVIDER_ERROR` was never an enum member) |
| `backend/contexts/execution/infrastructure/adapters/connectors/kubernetes.py` | deployment / RS / pod evidence for identity, template digest, ownership, readiness; rollback profile; `pod_template_digest` |
| `backend/api/capability_execution_composition.py` | rollback catalog + connector; `build_remediation_runtime` composition root; the governed writer reports the gateway's dispatch-refusal code |
| `backend/contracts/intelligence/autonomy.py`, `backend/intelligence/application/autonomy.py` | `Capability.compensable`, `AutonomyPolicyConfig.compensable_autonomy`, gate 9 compensable path |
| `backend/contracts/intelligence/capability_profile.py` | `compensation` on write profiles |
| `backend/contexts/connectivity/application/authorization.py`, `infrastructure/sql_approval.py` | `ApprovalFacts.decided_by` / `is_delegated`; delegated-approval rule; `consumed_by_execution` — a consumed approval is refused (single use, D-13) |
| `backend/harness/llm_boundary.py` | a provider failure records a failure span (scrubbed cause) before re-raising (D-13) |
| `backend/world/application/reasoning.py` | kinds `remediation_plan`, `remediation_event` |
| `backend/api/observability_evidence.py` | freshness rules for `remediation-outcome`, `remediation-target` |
| `backend/observability/prometheus_metrics.py` | remediation counters and histograms |
| `backend/api/investigation_catalog.py`, `investigation_runtime.py` | rollout history template digests; `on_outcome`; honest monetary cost |
| `backend/api/product/app.py`, `approval_routes.py`, `assessment_routes.py`, `remediation.py` | router; rollback definition; execute route refuses platform requests; cost honesty; one `workload_of` |
| `backend/main.py` | embedded remediator beside the investigator |
| `.gitignore` | `.phase114.env`, `.phase114/` |

## 6. What was deliberately not built

A second policy engine, approval store, queue, scheduler, retry framework or
verifier; a migration; a shell or generic Kubernetes tool; automatic
compensation; a production credential adapter; monetary pricing (reported
UNKNOWN, never invented).
