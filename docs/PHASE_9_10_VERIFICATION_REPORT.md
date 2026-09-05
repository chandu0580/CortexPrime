# Phase 9.10 — Verification Report

**Phase:** First-write assurance, recovery and replay integration gate
**Date:** 2026-09-05
**Branch:** `phase-1-foundation`
**ADR:** ADR-091
**Harness:** `scripts/phase910_first_write_assurance_harness.py`
**Provisioner:** `scripts/phase99b_provision.sh` (reused unchanged)

---

## Result: **VERIFIED**

**95/95 checks. Exit 0.** All eight milestones independently established:

```
APPROVAL_VALIDATED      AUTHORIZATION_GRANTED   AUTONOMY_GRANTED
WORKER_STARTED          PROVIDER_WRITE_EXECUTED WORLD_STATE_CHANGED
OUTCOME_ESTABLISHED     ASSURANCE_SUPPORTED
```

| | Result |
|---|---|
| Harness | **95/95, exit 0, VERIFIED** |
| Architecture gate | **PASS** — 35 passed, 0 failed, 6 skipped, 1183 modules |
| Regression | **2852 passed, 0 failed** |
| Production mechanisms added | **none** |
| New fitness rules | **none** (Part M: none justified) |

---

## Part A — one write, outcome established independently

```
before:  uid c1c47e24…, generation 2, resourceVersion 943, replicas 1,
         image busybox:1.36
after:   generation 3
```

- [VERIFIED] Deployment identity unchanged — restarted, not replaced.
- [VERIFIED] Generation advanced 2 → 3.
- [VERIFIED] Old pod terminated, replacement created, belonging to the intended
  Deployment.
- [VERIFIED] Replica count and image unchanged — a restart, not a deploy.
- [VERIFIED] The unrelated Deployment and the unrelated namespace are unchanged.
- [VERIFIED] Exactly one provider write, to the CONTAINED worker.

The worker's response established nothing; the outcome came from an independent
read of the cluster.

## Part B — Assurance, through the existing verifier

Observed independently after the write: `{revision: "3", image: busybox:1.36}`.

| Case | Verdict |
|---|---|
| matching independent evidence | **SUPPORTED**, citing 2 observations |
| contradictory evidence | UNSUPPORTED |
| missing evidence | INSUFFICIENT_EVIDENCE |
| wrong workload | not SUPPORTED |
| stale (past the 3600s horizon) | not SUPPORTED |
| undeclared predicate | not SUPPORTED |
| verifier sharing the producer's reasoning path | **refused** (P5) |

No second verifier. The `deployed_revision` predicate and its horizon already
existed; the model participates in no part of the verdict.

## Part C — replay of the completed execution is inert

- [VERIFIED] The replayer holds no repository, queue, pool, gateway or channel.
- [VERIFIED] Its only public method folds events into a projection.
- [VERIFIED] 6 recorded events replayed → **0 provider writes**, generation
  3 → 3, annotation unchanged, 0 causal gaps.

## Parts D/E — revocation and the cross-binding matrix

All fifteen refused, **0 Kubernetes mutations**, generation unmoved:

revoked-before-dispatch · workload A→B · namespace A→B · tenant A→B · wrong
capability digest · wrong governance operation · unbound approval · forged
artifact · missing approval · modified action payload · model-supplied reference
(structurally impossible) · worker-supplied reference (structurally impossible).

Plus a positive control: a valid approval for *this* action still dispatches, so
the matrix refuses wrongness rather than everything.

### The measurement correction worth reading

The cross-namespace case initially reported as a failure. It was not a safety
failure — it was a **measurement error in the harness**. That approval was
genuinely valid *for that action*, so authorization and the gateway correctly
allowed it, and the **CONTAINED worker's own namespace binding** refused it
before contacting the API server. The harness had counted the envelope POST as a
Kubernetes write.

The matrix now measures the cluster's generation as ground truth and records
which layer refused (`stopped_by=governance` or `stopped_by=worker`). For this
case the last line of defence is the one that held, and the report says so
rather than implying governance caught it.

## Part F — autonomy re-evaluated

- [VERIFIED] `effective <= allowed <= requested`.
- [VERIFIED] A4 requested is never A4 effective for an irreversible action.
- [VERIFIED] The reversibility gate forces `HUMAN_APPROVAL_REQUIRED`.
- [VERIFIED] Under the **shipped default** the action is refused entirely, even
  with a valid approval.
- [VERIFIED] Each of these refuses independently: emergency stop, circuit
  breaker, stale world, conflicted world, insufficient calibration, low
  reliability, insufficient assurance coverage, calibration drift.
- [VERIFIED] No model-authored field is an input to any of it.

## Part G — crash never fabricates success

- [VERIFIED] An undelivered envelope is AMBIGUOUS — never success, never failure.
- [VERIFIED] An unreadable worker answer is also AMBIGUOUS.
- [VERIFIED] The worker itself reports ambiguity when its own Kubernetes request
  does not complete, and never reports success on a transport failure.
- [VERIFIED] **A real process, killed mid-write**, left `stage: about_to_write`
  and no recorded success; the cluster (generation 3 → 3) is what decided the
  outcome, not the dead process.

## Parts H/I/J — fencing, World consistency, audit

- [VERIFIED] The existing `ExecutionLease` is what fences; no second lease or
  election exists. The dispatcher claims through the existing queue and refuses
  an unclaimable node rather than assuming it free.
- [VERIFIED] The worker never writes a Fact, Belief, Verification or World table,
  and has no database access at all.
- [VERIFIED] The World's value for the deployment came from a governed read of
  the provider.
- [VERIFIED] The approval reference is durably recorded in the sealed binding and
  the audit chain; the execution id is durably recorded.
- [VERIFIED] Full durable-store scan: **no credential in any text/json column of
  any table**, and none in this report.

## Part L — least-privilege RBAC, live

Fourteen `kubectl auth can-i` checks as the worker's ServiceAccount against the
real API server: `patch`/`get deployments` in one namespace **yes**; `delete`,
`create pods`, `get secrets`, `pods/exec`, `pods/attach`, `pods/portforward`,
`escalate roles`, `bind roles`, `impersonate users`, wildcard `*/*`, and both
other namespaces **no**.

---

## Honestly deferred

Each is recorded rather than quietly claimed:

- **Exactly-once is not claimed.** At-least-once is the contract: a *new*
  governed request for the same action is a new execution and writes again,
  correctly. What is proven is that replaying the *recorded* execution cannot.
- **The ten individually-named crash boundaries.** Four sit after the
  irreversible act and prove record durability, not write safety. The property
  they exist to protect is proven above.
- **A live two-holder fencing race** was not staged; the lease wiring is
  re-proven and the live race was proven in 9.3, with no lease, leadership or
  recovery code changed since.
- **Replay of unknown / interrupted / failed-verification executions.** Each
  needs a durably recorded execution in that exact state; the inertness that
  matters is structural and is proven regardless of which state is folded.
- **A projection cannot name the execution it replayed.** `executions.history`
  returns events whose payload carries no `execution_id`, so the projection
  reports `unknown`. Recorded as a finding rather than asserted away — it does
  not affect inertness, but it is worth knowing.
- **Process-count and egress limits** remain NOT VERIFIED (ADR-089), unchanged.

---

## Nothing weakened

The 9.9C security baseline is intact: the `approval_required` fix and its two
regression guards remain green, and the cross-workload and unbound approvals are
re-proven refused here against the real cluster. No Phase-7 or Phase-8 invariant
was weakened, L1–L16 are untouched, ADR-088 remains authoritative, and Phase 5.5's
credential blocker is untouched.
