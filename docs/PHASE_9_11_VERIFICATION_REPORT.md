# Phase 9.11 — Verification Report (Phase 9 Final Gate)

**Phase:** DevOps capability hardening and Phase 9 closure
**Date:** 2026-09-05
**Branch:** `phase-1-foundation`
**ADR:** ADR-092
**Harness:** `scripts/phase911_final_gate_harness.py`

---

## Result: **VERIFIED**

| | Result |
|---|---|
| 9.11 harness | **92/92, exit 0, VERIFIED** |
| 9.10 harness (re-run against the hardened worker) | **95/95, exit 0** |
| Architecture gate | **PASS** — 35 passed, 0 failed, 6 skipped, 1183 modules, **0 blocking violations** |
| Regression | **2852 passed, 0 failed** |
| New capabilities commissioned | **none** (Part B) |
| New fitness rules | **none** (Part L — no bypass found) |
| Production infrastructure touched | **none** (Part N) |

Milestones, each emitted only when independently established:
`APPROVAL_VALIDATED`, `AUTHORIZATION_GRANTED`, `WORKER_STARTED`,
`PROVIDER_WRITE_EXECUTED`, `WORLD_STATE_CHANGED`, `OUTCOME_ESTABLISHED`,
`ASSURANCE_SUPPORTED`.

---

## VERIFIED

**Part I — V1 strangler audit (a stop condition).** Probed by *calling* each
surface: legacy execution disabled, **zero ungated surfaces**, the execution
guard refuses, the V1 `ScriptSandbox` refuses to execute Python, the V1
credential store refuses to construct. `BND-PROCESS-SPAWN`, `BND-DIRECT-HTTP`,
`BND-PROVIDER-SDK`, `BND-AMBIENT-CREDENTIALS`, `BND-EFFECT-GATE` all pass. **No
bypass found.**

**Part F — both ADR-089 limits now enforced, by runtime probe.**
- Process count: **9/9 pod cgroups at `pids.max=128`**.
- Egress: allow-list of exactly two destinations (`172.29.0.3/32` API endpoint,
  `10.43.0.10/32` DNS), `policyTypes: [Egress]` so everything else is denied.
- Enforcement proven on a disposable pod: deny-all → API **BLOCKED**; the
  worker's exact shape → API **REACHABLE**, internet **BLOCKED**, unrelated
  cluster service **BLOCKED**.
- The worker still writes with egress restricted — the 9.10 harness scores 95/95
  against this same hardened worker.

**Part E — fencing, a real two-holder race.** A takes token 1; B (a *different*
instance) is refused while A is live; A goes stale; B takes token 2; **A's token
carried into a leader-only `UPDATE` matches 0 rows** and B's matches 1. The
advisory check also refuses A. No second lease or election mechanism, and no new
`LeadershipRole`.

**Part D — replay matrix.** Replaying the COMPLETED irreversible execution and a
REFUSED execution performed **zero provider writes**; an unknown execution id
**refuses** rather than returning an empty run; the cluster did not move.

**Part C — crash.** An interrupted provider request, an unreadable response and a
failed worker→Kubernetes request are all AMBIGUOUS, never success. A real process
killed after the request recorded **no fabricated success**, and the cluster
decided the outcome.

**Part J — the 9.9C security regression, green.** approval-for-A→action-B,
unbound, cross-tenant, wrong digest, wrong operation, revoked, modified payload
and missing approval all refuse at **zero Kubernetes mutations**.

**Part K — RBAC.** Fourteen live `can-i` checks: `patch`/`get deployments` in one
namespace **yes**; `delete`, `create pods`, `get secrets`, `pods/exec`,
`pods/attach`, `pods/portforward`, `escalate roles`, `bind roles`,
`impersonate users`, wildcard `*/*`, and both other namespaces **no**.
Namespace-scoped Role + RoleBinding.

**Part G — execution history.** A replayed projection can now name its execution.
The id is a **hint, never an override**; the fold is untouched and the replayer
still holds nothing it could call.

**Part M — final end-to-end.** One provider mutation, no bystander mutation, no
cross-namespace mutation, no secret persisted, Assurance SUPPORTED.

---

## NOT VERIFIED

- **Four post-write crash boundaries** (observation / outcome / verification /
  audit persistence). They sit after the irreversible act; killing there tests
  record durability, not write safety.
- **Production capability.** Never attempted; disposable k3d only.
- **Real LLM.** Phase 5.5 credential blocker, untouched. The model proposer
  remains scripted.

## DEFERRED

- **Replay of `INTERRUPTED` and `FAILED_VERIFICATION`** — each needs a ledger
  durably in that state, and this phase declined to manufacture one by corrupting
  it. Replay inertness is structural and state-independent.
- **Three declared-but-not-commissioned writes**: `github.repository.create_issue`,
  `github.repository.create_issue_comment`, `grafana.folder.create_folder`. No
  credential adapter, no worker, never executed.

## NEVER CLAIMED

**Exactly-once.** At-least-once is the contract. A *new* governed request for the
same action is a new execution and writes again, correctly.

## BLOCKED

Nothing.

---

## Remaining Phase 9 capabilities

| Capability | Status |
|---|---|
| Kubernetes read / watch / observability corroboration / read-only investigation | **VERIFIED** (9.1–9.5) |
| `kubernetes.workload.rollout_restart` | **VERIFIED, commissioned, hardened** |
| `github.repository.create_issue` | NOT COMMISSIONED |
| `github.repository.create_issue_comment` | NOT COMMISSIONED |
| `grafana.folder.create_folder` | NOT COMMISSIONED |
| Everything else (AWS, Azure, GCP, Terraform write, DNS, shell, arbitrary K8s) | **DOES NOT EXIST** |

One execution authority. One gateway. One approval system. One credential broker.
One audit chain. One World Plane. One Assurance Plane.

---

## Recommendation on Phase 10

**Phase 10 may begin.** Every stop condition was checked and none tripped: no
replay repeats an irreversible action, no stale worker can act, no revoked,
cross-tenant or cross-workload approval dispatches, digest binding holds, neither
model nor worker can authorize, autonomy cannot self-promote, Assurance cannot be
bypassed, no V1 bypass can execute externally, no secret reaches durable state,
audit retains the approval reference, and crash recovery fabricates nothing.

Three conditions I would attach, as the engineer who built this:

1. **Do not commission a second write capability without repeating 9.9B–9.10 for
   it.** The rollout restart is proven; nothing else is. Each of the three
   declared writes needs its own worker binding, credential adapter, approval
   digest and independent observation.
2. **The `CONTAINED` declaration is honest today because one worker is genuinely
   out-of-process.** Any new worker that declares CONTAINED while running
   in-process re-opens exactly what ADR-088/089 closed.
3. **Exactly-once will keep being asked for.** It is not the contract and should
   not become one by implication.

Phase 9's obstacle moved five times — hardware, taxonomy, a missing field, a
dead-code check, and a measurement error — and every one was found by running the
real chain against real infrastructure rather than by reasoning about it. That is
the practice worth carrying into Phase 10.
