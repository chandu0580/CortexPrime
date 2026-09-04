# Phase 9.6 — Verification Report

**Phase:** First verifiable Kubernetes remediation
**Date:** 2026-09-04
**Branch:** `phase-1-foundation`
**ADR:** ADR-086
**Harness:** `scripts/phase96_reversible_remediation_harness.py`
**Provisioner:** `scripts/phase96_provision.sh`

---

## Definition of Done: **NOT MET**

Phase 9.6's Definition of Done required **one real, verifiable Kubernetes write
against a real cluster, performed through the governed chain after the platform
earned the authority to do it.**

**No write was performed.** The platform refused it, correctly, by its own
isolation invariant. Nothing was weakened to obtain a green result. The phase is
reported **BLOCKED**, and the Definition of Done moves unchanged to Phase 9.7.

The decisive measurement of this phase is a negative:

```
provider_writes        = 0
total_provider_dials   = 1   (a GET)
distinct HTTP methods  = ['GET']
restart annotation on the live cluster = <none>
```

---

## Environment (real, disposable)

| Component | What it actually was |
|---|---|
| Kubernetes | Real k3d cluster `cortex-p96`, real TLS, real ServiceAccount token |
| RBAC | One namespace, `verbs: ["get", "patch"]` on deployments |
| Database | Real PostgreSQL (fresh database, real migrations) |
| Workloads | `payments-api` (regression → CrashLoopBackOff, 3 restarts, exitCode=1) and `config-consumer` (envFrom-ConfigMap fault, fixed post-start) |
| Observability | Real Prometheus + kube-state-metrics in-cluster |

No scripted provider stood in for the real one at any decisive point. Where the
real write could not be performed, it is reported as not performed — it was not
simulated.

---

## Results

**Harness:** 53/53 checks passed. **Exit code 2 (NOT VERIFIED) — by design.**
**Unit tests:** 400/400 passed in `tests/intelligence/` — 46 of them Phase 9.6's
(`tests/intelligence/test_governed_remediation.py`).
**Architecture gate:** PASS — 35 passed, 0 failed, 6 skipped, 1181 modules.

### A. The operation, declared honestly — [VERIFIED]

- [VERIFIED] Exactly one write operation exists in the Kubernetes catalog:
  `kubernetes.workload.rollout_restart`.
- [VERIFIED] It is declared `IRREVERSIBLE_WRITE`. A rollout restart has no
  inverse operation: it mutates the pod template, creating a new ReplicaSet
  revision and terminating every running pod. Removing the annotation produces
  another forward mutation, not a restoration. It is **not** called reversible
  merely because it is operationally common.
- [VERIFIED] It is declared `NON_IDEMPOTENT_WRITE`, so execution must never
  blind-retry it.
- [VERIFIED] It requires `INDEPENDENT_READBACK` verification.
- [VERIFIED] Its autonomy ceiling is `A3_APPROVED_ACTION` — never delegated.
- [VERIFIED] The platform **derives** `RiskLevel.HIGH` from that classification.
  The model performs no part of this evaluation.

### B. Blast radius — [VERIFIED]

- [VERIFIED] The provider operation declares exactly two parameters:
  `['name', 'namespace']`. There is no selector, list or wildcard field to fill.
- [VERIFIED] `RemediationTarget` refuses at construction: `cortex-p96/*`,
  `*/app`, and `cortex-p96/a,b` are all rejected.
- [VERIFIED] One workload, one namespace, one action. No bulk restart, no
  cluster-wide action, no namespace wildcard, no label-selector fan-out.

### C. The request document — [VERIFIED]

- [VERIFIED] `KubernetesRestartBodyBuilder` produces exactly one document:
  `{"spec":{"template":{"metadata":{"annotations":{"cortexprime.io/restarted-by-action":"<action id>"}}}}}`
- [VERIFIED] The same action identity produces a byte-identical request.
- [VERIFIED] It **refuses to build anything** without the platform's action
  identity — an unattributable write is never constructed.
- [VERIFIED] The annotation key is CortexPrime's own, not `kubectl`'s, so an
  operator can attribute the change.

### D. THE BLOCKING FINDING — [BLOCKED]

- [VERIFIED] `AMBIENT` isolation is insufficient for an irreversible write.
- [VERIFIED] `CONTAINED` isolation is insufficient for an irreversible write.
- [VERIFIED] Only `SEALED` — *"full virtualization, no ambient credentials"* —
  is sufficient.
- [VERIFIED] The Kubernetes connector runs at `CONTAINED`, in-process (ADR-059's
  stated gap).
- [VERIFIED] **Gate 1 (registration)** refuses the capability outright:
  `isolation tier 'contained' is insufficient for a 'irreversible_write' capability`
  — `contexts/connectivity/domain/contract.py:206`.
- [VERIFIED] **Gate 2 (worker selection)** independently refuses:
  `WorkerImplementation.permits_side_effect` returns `False` —
  `worker_directory.py:514`.
- [VERIFIED] The two gates are independent; either alone stops the write.

**[BLOCKED] The real Kubernetes write.** Performing it would have required
declaring the in-process connector `SEALED`, asserting virtualization that does
not exist. The phase stopped instead. See ADR-086 §Decision 6.

This invariant had never been exercised before: no irreversible-write capability
has ever been registered in this repository.

### E. The governed read path is unaffected — [VERIFIED]

- [VERIFIED] A governed READ still succeeds against the real cluster through the
  one governed chain.
- [VERIFIED] It reported the deployment's real revision (`1`) from the live API.
- [VERIFIED] No CortexPrime restart annotation is present — nothing restarted
  anything.

### F. Two typed doors, one chain — [VERIFIED]

- [VERIFIED] `GovernedCapabilityReader.read()` refuses a mutating operation.
- [VERIFIED] `GovernedCapabilityWriter.write()` refuses a read — an approval is
  never attached to an action that changes nothing.
- [VERIFIED] Neither door will run an operation nobody declared.
- [VERIFIED] Both delegate to one `_perform()`. No second executor, gateway,
  scheduler, transport, approval system, autonomy system, audit system or World
  store was created.

### G. Autonomy — all ten gates — [VERIFIED]

- [VERIFIED] The **shipped default** (`max_level_high = A2_RECOMMEND`) refuses a
  HIGH-risk action entirely — *even with a valid approval*. Reaching A3 required
  an explicit, versioned deployment config (`phase96-autonomy/1`); the default
  was not changed, and a unit test proves the shipped default still refuses.
- [VERIFIED] A4 requested is never A4 effective for an irreversible action:
  `a4_autonomous → a3_approved_action → a3_approved_action`.
- [VERIFIED] The reversibility gate forces `HUMAN_APPROVAL_REQUIRED`:
  *"irreversible action: human approval required; no delegated autonomy."*
- [VERIFIED] `effective ≤ allowed ≤ requested`, always.
- [VERIFIED] Each of these independently refuses: emergency stop; circuit
  breaker; stale world evidence; conflicted world evidence; insufficient
  calibration; reliability below the required threshold; assurance coverage
  below the required threshold; calibration drift.

### H. Approval binding — five independent clauses — [VERIFIED]

- [VERIFIED] A matching approval covers the action.
- [VERIFIED] A **DENIED** approval authorizes nothing.
- [VERIFIED] An **EXPIRED** approval authorizes nothing.
- [VERIFIED] An approval for **another tenant** authorizes nothing.
- [VERIFIED] An approval for **another operation** authorizes nothing.
- [VERIFIED] An approval bound to **another digest** authorizes nothing.
- [VERIFIED] An approver of `"admin"` is **not** an authority. Authorization
  uses the existing identity reference mechanism.

### I. The decisive negative — [VERIFIED]

- [VERIFIED] **ZERO provider WRITES occurred in this entire run.**
- [VERIFIED] Every provider dial was a `GET` — `['GET']`.
- [VERIFIED] The live cluster carries **no** CortexPrime restart annotation.
- [VERIFIED] For every refusal, `provider_calls == 0`.

### J. Secrets, tenancy, audit — [VERIFIED]

- [VERIFIED] No token appears in any durable row of any table.
- [VERIFIED] No token appears in this report or the harness report.
- [VERIFIED] Cross-tenant world evidence is empty.
- [VERIFIED] The audit chain verifies (records=2).
- [VERIFIED] The Kubernetes connector reads no environment variable directly;
  credentials arrive through the existing credential mechanism. Phase 5.5's
  credential blocker remains untouched.

---

## Deferred

- [DEFERRED] Post-write independent readback against a real changed cluster.
- [DEFERRED] Prediction evaluation against a real remediation outcome.
- [DEFERRED] Assurance verdict on a real remediation.
- [DEFERRED] Rollback semantics — there are none to verify; the operation has no
  inverse and `rollback_available` is `False` by construction.

All four are deferred to **Phase 9.7**, which must first build a real SEALED
execution tier.

---

## Two defects found and fixed during verification

### 1. The write leaked into the read catalog

The rollout restart was initially added to `kubernetes_read_catalog()`, which
broke four existing assertions that the Kubernetes catalog is read-only. Those
assertions were correct and the code was wrong. The write now lives in a separate
`kubernetes_write_catalog()` that a caller must name deliberately; the read
catalog is unchanged and still read-only; and the real exposed operation set
excludes the write entirely. Verified: `kubernetes_read_catalog()` declares no
mutating operation, `kubernetes_write_catalog()` declares exactly one, and
`ROLLOUT_RESTART_OPERATION` is not in `KUBERNETES_REAL_READ_OPERATIONS`.

A related consequence: the investigator's `ToolRegistry` refusal is now proven
against a catalog that **does** declare the write, so the refusal demonstrably
comes from the side effect rather than from the operation being absent.

### 2. A refusal that would have raised `NameError`

`backend/api/capability_execution_composition.py` raised `ContractViolation`
without importing it — so the read door's refusal path would have raised
`NameError` instead of the intended refusal. The real-cluster harness caught it;
unit tests had asserted the refusal by reading source text, which a missing
import passes. Fixed, and `TestTheTwoDoorsAreTyped` now **executes** all three
refusals rather than reading source for them.

---

## Honest summary

Everything that could be proven without a real write is proven, against real
infrastructure. The one thing this phase existed to do was not done, because the
platform's own isolation invariant refused it and the only ways past that
refusal were lies. The refusal is the result.
