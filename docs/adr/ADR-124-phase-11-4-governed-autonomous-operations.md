# ADR-124 — Governed autonomous operations: one typed, compensable remediation (a Deployment rollback to a known revision) executed by a contained least-privilege worker, planned from evidence, governed by the existing autonomy policy and approval authority, verified by an independent identity, recovered within explicit budgets, and learned from without granting itself authority

- **Status:** ACCEPTED — with **D-4 and D-5 PROPOSED, AWAITING OWNER RATIFICATION** (see *Decisions required*)
- **Date:** 2026-09-11
- **Phase:** 11.4 — real governed autonomous operations (GA Prompt 4/5)
- **Parents:** `ea3815d` — Phase 11.3 (ADR-123); `b625ad2` (hosted model default); ADR-086 (irreversible write needs isolation), ADR-088 (CodeTrust axis, ratified), ADR-089/090 (contained worker, canonical approval digest), ADR-080–085 (Kubernetes read surface), ADR-078 (controlled autonomy A0–A4, Phase 8.8), ADR-077 (calibration), ADR-066/067 (assurance), ADR-121 (one approval authority)
- **Evidence:** `docs/PHASE_11_4_AUTONOMOUS_OPERATIONS_IMPLEMENTATION_MAP.md`, `docs/PHASE_11_4_AUTONOMOUS_OPERATIONS_VERIFICATION_REPORT.md`, `scripts/phase114_autonomous_operations_harness.py`, `docs/phase114_autonomous_operations_report.json`
- **Change:** one contained worker image, one connector adapter, one commissioned write capability, one additive authorization rule, two additive autonomy fields, two reasoning kinds, the remediation runtime and its read-only product routes. **No migration. No new table. No new dependency. No cluster-admin. No arbitrary command or API.**

> **Numbering.** Highest used is 123; this is 124. Nothing overwritten.

## Context

Phase 11.3 ended at an evidence-backed assessment with authority `none`. The
repository already held every authority this phase needs and none of the loop:
a controlled autonomy policy (Phase 8.8, A0–A4, eleven ordered gates) that no
production path called; a calibration estimator over predictions and
independent verifications that no remediation fed; one approval authority
(`cp_approval`, ADR-121) with digest binding (ADR-090); an idempotency store; a
recovery vocabulary; an assurance verifier with an independence firewall; one
commissioned write (the 9.9 rollout restart) that is honestly IRREVERSIBLE and
has no compensation. The mandate asks for a real incident to be remediated
autonomously, for high-risk actions to require a human, and for nothing to be
called success that the world did not confirm. The tension it creates is the
one this ADR has to resolve without weakening L10: *an irreversible write
always faces a fresh human*.

## Decisions

### D-1 One typed action: `kubernetes.deployment.rollback`, IRREVERSIBLE and COMPENSABLE

The only write capability is a Deployment rollback to a known revision. It is
registered honestly as `irreversible_write` / `non_idempotent_write`: rolling a
Deployment back replaces its pods and consumes a revision number, and neither
comes back. Its contract **declares a compensation** — the same capability,
targeting the pre-action revision, whose ReplicaSet the controller retains —
which makes it *compensable* in the L10 sense (the declared state can be
restored by a second governed action; pod history cannot). The rollout restart
(ADR-086) stays irreversible without compensation and gains nothing from this
ADR. The model can name only `deployment.rollback` or `no_action`; the platform
registry classifies everything else as PROHIBITED (delete, exec, shell,
kubectl, cluster-admin, credential, secret, HTTP, scale-to-zero, drain …) or
UNKNOWN, and both are refusals.

### D-2 A separate contained worker with its own identity

`workers/contained_k8s_rollback` is a stdlib-only image (non-root, read-only
root filesystem, pid limit, egress NetworkPolicy to the API server only) bound
at deploy time to one tenant, one namespace, one capability id/version, one
provider id (`kubernetes-contained-rollback`) and one implementation digest. Its
ServiceAccount `cortex-rollbacker` holds a namespace Role of exactly
`deployments: get, patch` and `replicasets: list` — verified token-only against
the live API server (no update, delete, scale, RS patch, exec, secrets, other
namespaces, escalate, bind, impersonate; no cluster-admin anywhere). The worker
holds no standing credential: the platform's broker presents the token per
execution as the transport authorization header. `automountServiceAccountToken`
is false.

### D-3 The executor constructs the call; the worker re-checks the world before and during the write

The model proposes typed JSON; the planner turns it into parameters; the
worker constructs the Kubernetes request itself. Before writing it re-reads the
Deployment and its owned ReplicaSets and refuses on: target absent, UID
changed, generation changed, revision changed, running-template digest
changed, paused, `revisionHistoryLimit` too low to keep the compensation, the
target revision absent / ambiguous / drifted from the approved template digest,
or the pre-action ReplicaSet not retained. It then performs a **server-side dry
run of the exact JSON patch** and only then the write:
`test /metadata/uid`, `test /metadata/resourceVersion`, `replace /spec/template`
(the target ReplicaSet's template without `pod-template-hash`), and an
attribution annotation carrying the action digest. The `test` operations make
the API server itself the fence against a concurrent writer. The envelope
carries `authority_expires_at`; the worker refuses a lapsed window before the
dry run and again before the write.

### D-4 Mandate autonomy levels map onto the EXISTING A0–A4; compensable actions may earn delegation (PROPOSED)

No second autonomy system. The mandate's six levels map onto the repository's
five:

| Mandate | Meaning | Repository |
|---|---|---|
| A0 observe | read only | A0 |
| A1 recommend | no action | A2 recommend (fallback proposals are pinned here) |
| A2 auto low-risk reversible | autonomous | A4 under the LOW cap |
| A3 bounded under policy | autonomous within policy | A4 under the MEDIUM cap, **only when `compensable_autonomy` is on** |
| A4 high-impact | human approval | A3 approved action (HIGH cap) |
| A5 critical | prohibited / elevated | A1 cap; the planner refuses CRITICAL outright |

Two additive fields carry it: `Capability.compensable` (a DESTRUCTIVE capability
may not declare it) and `AutonomyPolicyConfig.compensable_autonomy` (default
**False**). Gate 9 (reversibility) lets a compensable, non-destructive
capability through only when the policy says so; every other gate is unchanged
and still runs first — emergency stop, circuit breaker, risk cap, version,
calibration (≥ 8 decided outcomes, support ≥ 0.8, assurance coverage ≥ 0.75),
assurance, drift, world freshness. The policy version string records the
choice (`…+compensable=1`) and is bound into every plan's parameters, hence into
its approval digest: turning the switch off makes every earlier approval a
different action (verified: STALE).

### D-5 A delegated approval lives in the ONE approval authority, and authorization refuses it for anything not compensable (PROPOSED)

When policy permits, the runtime records the decision as an approval in
`cp_approval` — requested by `platform:remediation-runtime`, decided by
`policy:autonomy/<version>`, justification naming the autonomy decision — so the
gateway's existing approval-digest check applies to autonomous actions exactly
as to human ones. The rule that stops this from becoming a way around L10 lives
**below every caller**, in `CapabilityAuthorizationService._snapshot`: an
approval whose decider is not `human:` is valid only for a capability whose
contract declares a compensation and whose side-effect class is not
DESTRUCTIVE. A policy-decided approval for the rollout restart authorizes
nothing (verified live). The product's human execute route refuses platform
requests (409), so a delegated approval cannot be driven from the product API.

### D-6 Risk is computed by the platform, factor by factor

`classify_action_risk` starts at the capability's implied risk
(`implied_risk_for`: IRREVERSIBLE → HIGH) and may lower it **one** level only if
every one of these holds: compensation verified available, non-production,
exactly one resource, no PersistentVolumeClaim in the pod template, the target
revision **observed healthy by the World Plane** (pod watch observations, not
assumption), replicas ≤ 10, namespace-scoped credential. Production or a wide
blast radius forces ≥ HIGH; DESTRUCTIVE is CRITICAL. The rationale lists every
factor (resource type, scope, blast radius, reversibility, customer impact
proxy, environment, credential sensitivity, data mutation, rollback
availability). A target revision nobody saw run is HIGH and needs a human.

### D-7 One explicit plan object, an append-only lifecycle, no migration

`RemediationPlan` (contracts) carries plan id, incident, investigation, tenant,
target (cluster, namespace, kind, name, UID, generation, revision, template
digest), diagnosis ref, evidence, action, parameters, risk, reversibility, blast
radius, expected state, verification criteria, rollback strategy, timeout,
approval requirement, authority, policy version, principal and action digest. A
plan with no evidence or no criteria, or AUTONOMOUS and IRREVERSIBLE, does not
construct. Plans and every lifecycle stage (planned → autonomy_decided →
approval_* → stale / duplicate_suppressed / executing → executed |
execution_failed | execution_unknown | execution_refused → verified |
verification_failed | no_effect_confirmed | verification_insufficient →
discrepancy → recovery_decided → escalated → learned → closed) are appended to
`cw_reasoning` as kinds `remediation_plan` and `remediation_event` (text kind;
no schema change). Proposals that never became plans are recorded as
`rdecision_*` events with their reasons.

### D-8 Stale-plan protection, idempotency and fencing before any write

Immediately before execution the runtime re-reads the target and refuses
(STALE) on: policy version changed, UID / generation / revision / template
changed, target revision no longer available with the approved template, or the
approval no longer valid for this tenant, capability and moment. It claims an
**action key** digest(tenant, approval digest, plan, UID) — a repeat is
DUPLICATE_SUPPRESSED — and a **target fence** digest(tenant, UID, generation) —
a second plan for the same target state is fenced. Mutations are never retried.
Beneath both, the API server's `test resourceVersion` makes concurrent writers
lose.

### D-9 Verification is independent: another identity, the World Plane, Assurance

The verifier never reads the executor's answer as evidence. Through the
**reader** ServiceAccount (a different credential and connector) it polls the
Deployment and its pods until the window closes, derives the proposition
`remediation_outcome = {templateDigest, rolledOut, available, crashLooping}`,
records it as a World observation and fact, and asks `AssuranceVerifier`
(COMPARE_WORLD_STATE) to verify the plan's expected state with producer path
`platform:remediation-planner/1` — so the platform verifier's independence
firewall applies. A verified outcome after an executor failure is recorded as a
**false failure**; a failed verification after an executor success is a **false
success**; an honest failure the world confirms changed nothing is
`no_effect_confirmed` (and does not trip the verification breaker).

### D-10 Recovery is bounded and never destructive

Budgets are explicit and recorded on every recovery event: mutation retries 0,
recovery attempts 1 (a new plan and a human), executions per incident 2.
VERIFIED closes resolved. A rollback that reached its template but did not end
the incident is a false diagnosis → WAIT_FOR_HUMAN → ESCALATED. An executor
claim the world contradicts → RECONCILE_EXTERNAL_STATE → ESCALATED. An unknown
outcome is reconciled by verification, never by re-running. A plan a crash
left at `executing` is reconciled on resume, never re-executed. No fallback
action exists; an unavailable rollback revision is a refusal.

### D-11 The model proposes through the governed boundary; failure never grants authority

`GovernedRemediationProposalPort` uses the existing `GovernedModelBoundary`
(scrubbed prompt, durable span, schema firewall). `RemediationProposalSchema`
is `extra=forbid`, requires a target with DNS-name patterns and at least one
evidence id; smuggled `approved` / `autonomy_level` fields are schema
rejections. Evidence must belong to the investigation. The target must be the
incident's own workload in the bound namespace (confused deputy refused). A
model outage falls back to a deterministic proposer whose plans are
**RECOMMENDATION_ONLY** — an outage never becomes an autonomy grant. Malformed
output is a rejected proposal, not a fallback trigger.

### D-12 Learning is advisory and autonomy is earned, then withdrawn fast

Every execution records a `Prediction` (expected state) and, after
verification, a `PredictionEvaluation` against the independent outcome;
Assurance records the verdict. Calibration reads those per prediction class
(subject type, predicate, environment, model identity, harness version). The
earned path is therefore evidence-based: with `compensable_autonomy` on, the
first eight outcomes of a model/harness class are human-approved; once
calibrated, a MEDIUM compensable plan may be delegated. One verification
failure trips the breaker and every following plan needs a human (fast down).
Nothing in the learning events changes policy by itself.

### D-13 Single use is enforced by authorization; refusals and failures say why (found by the record runs)

Reading the record runs' evidence rather than their verdicts found four defects,
each fixed below every caller rather than in the remediation runtime:

- **A consumed approval authorizes nothing again.** `cp_approval` recorded
  consumption and nothing enforced it (pre-existing since ADR-121): a single-use
  approval stayed valid for replays until it expired. `ApprovalFacts` now carries
  `consumed_by_execution` and `is_valid_for` refuses it — human or delegated.
  Both writers consume only after the governed write returns, so every re-check
  of the authorized execution precedes consumption.
- **A definite worker failure is a failure, not an unknown.** The contained
  adapter named a `ProviderFailure` member that never existed (latent since
  9.9C); 401/403/422 now map to their provider-neutral classes by status, and an
  unmapped status stays UNKNOWN_OUTCOME.
- **A gateway refusal at dispatch reaches the caller** as the gateway's own code
  (`approval_mismatch`), not `None`.
- **A failed model call leaves a span.** The governed boundary records a failure
  span with the scrubbed cause before re-raising; the remediation fallback keeps
  the scrubbed cause.

## What was not built, and why

- **No second autonomy, approval, idempotency or recovery system.** Every
  authority is an existing one; the runtime adds order and honesty.
- **No `kubectl rollout undo`.** It is client-side logic; the server-side
  rollback subresource was removed with `extensions/v1beta1`. The worker
  implements the documented semantics (template of the target ReplicaSet minus
  `pod-template-hash`) with preconditions `kubectl` does not have.
- **No production credential adapter.** The broker uses
  `DevelopmentCredentialProvider`, which refuses PRODUCTION; a production
  deployment needs a real secret-manager adapter (Decision required).
- **No automatic compensation.** The compensation exists and is declared; running
  it needs a new plan and a human (recovery attempt budget 1).

## Decisions required (owner)

1. **Ratify D-4/D-5: may a COMPENSABLE irreversible action earn policy-delegated
   autonomy?** The mandate's gates "at least one real controlled incident is
   autonomously remediated" and "high-risk actions require human approval" are
   met under this interpretation, and only under it. The switch is explicit,
   versioned, default off, and bound into every approval digest. Rejecting it
   leaves the platform on human approval for every rollback, with everything
   else in this ADR unchanged.
2. **Production credential brokering.** Choose the secret manager adapter
   before any non-development environment is commissioned.
3. **Compensation execution.** Whether a verified compensation (roll back the
   rollback) may itself ever be delegated, or always requires a human.

## Consequences

- The platform can now change a real system, and only through: a typed
  proposal → a platform plan → the existing autonomy policy → one approval
  authority → a digest-bound gateway → a contained, least-privilege worker that
  re-checks the world → an independent verifier.
- Every refusal names the layer that refused and the cluster is the ground
  truth for "nothing happened".
- Autonomy is a measured, revocable property of a (model, harness, action
  class), not a configuration flag alone.
