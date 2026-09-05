# Phase 9.10 — Implementation Map (discovery output)

**Written before any production code changed.** Required by the phase brief.

9.9C performed the first real irreversible write and explicitly deferred four
things. This phase exists to close exactly those, and to prove the lifecycle
around the write rather than the write itself.

---

## 1. What 9.9C left open, and what closes each

| 9.9C deferral | Closed by | New code needed? |
|---|---|---|
| `ASSURANCE_SUPPORTED` — "needs a declared predicate and freshness horizon this phase did not add" | **Nothing new.** `deployed_revision` already exists with a 3600s horizon (`observability_freshness_policy`), and 9.6's `_seed_world` already ingests a deployment read as an Observation under it. | **No** |
| Replay inertness of a *completed* execution | `ExecutionReplayer` — *"Holds no repository, no worker pool, and no queue — by construction, not by discipline. There is nothing here to call."* | **No** |
| Emergency stop, breaker, ten autonomy gates | `AutonomyPolicy.evaluate`, unchanged since 9.6 | **No** |
| Fencing and crash semantics | `ExecutionLease` + queue claim + the 9.6 child-process crash harness | **No** |

**Discovery conclusion: this phase should add no production mechanism.** Every
requirement in Parts A–L is served by something that already exists. The work is
to *exercise* them against the real cluster and report honestly.

---

## 2. Mechanisms traced, and how each will be exercised

### Assurance (Part B) — reuse, do not duplicate

`AssuranceVerifier.verify(tenant=, procedure=, producer_reasoning_path=,
verified_at=, verifier=)` already returns every verdict the brief asks for, and
already refuses self-verification:

| Condition | Verdict, already implemented |
|---|---|
| world state UNKNOWN | `INSUFFICIENT_EVIDENCE` — *"nothing to verify against"* |
| evidence CONFLICTED | `INSUFFICIENT_EVIDENCE` — *"cannot adjudicate"* |
| evidence STALE | `INSUFFICIENT_EVIDENCE` — *"policy requires fresh evidence"* |
| no lineage independence | `INSUFFICIENT_EVIDENCE` |
| SUPPORTED with no citable evidence | downgraded to `INSUFFICIENT_EVIDENCE` |
| independent evidence matches | `SUPPORTED` |
| independent evidence contradicts | `UNSUPPORTED` |

`verifier.is_independent_of(producer_reasoning_path)` raises if the verifier
shares the producer's path (Constitution P5). The model cannot participate.

**Procedure for the restart:** `kind=COMPARE_WORLD_STATE`,
`subject_ref="kubernetes:deployment:<ns>/<workload>"`,
`predicate="deployed_revision"`, `expected={revision, image}` — the same
predicate 9.5 declared and 9.6 seeded. No new predicate, no new horizon.

### Replay (Part C) — structurally inert

`ExecutionReplayer.replay(events)` folds recorded events into a `ReplayedExecution`
projection. It holds nothing it could call. Replay will be proven two ways:
by construction (no repository/queue/pool attributes) and behaviourally (fed the
real completed execution's events, with a dial counter attached, and observing
zero provider writes and an unchanged cluster generation).

**Honest note carried forward:** 9.9C issued a *new governed request* and called
it replay; that produced a second write, correctly. This phase replays the
*recorded execution*, which is the thing the brief actually asks for. At-least-once
remains the contract; exactly-once is not claimed.

### Fencing (Part H) — reuse the lease, add no election

The dispatcher claims through `self._queue.claim(context, worker_id=...)` and the
execution aggregate's lease check decides. Fencing will be exercised by taking
the lease under one holder and attempting to proceed as a stale one — no second
lease system, no second election.

### Crash (Part G) — real process death, 9.6's pattern

9.6's harness spawns a child (`subprocess.Popen`) at a named crash point, kills
it, and reads a durable marker. The same pattern applies at the boundaries the
brief lists. **Honest limit stated up front:** the boundaries that matter are the
ones around the provider request; the platform's rule is that an interrupted
provider request is `UNKNOWN`, never SUCCESS and never FAILURE, and that is what
will be checked.

### Autonomy (Part F) — unchanged, re-run

`AutonomyPolicy.evaluate` with its ten gates was fully exercised in 9.6 against
the real cluster. This phase re-runs it against *this* write's actual risk class
and asserts `effective <= allowed <= requested` plus each refusing gate.

### RBAC (Part L) — already verified live

`phase99b_provision.sh` already runs eight `kubectl auth can-i` checks as the
worker's ServiceAccount against the live API server, and fails the provision if
any disagrees. Re-run and re-report; no change.

---

## 3. What this phase will NOT do

- No new provider, executor, gateway, approval system, verifier, lease or
  election mechanism.
- No new predicate or freshness horizon — the existing one fits.
- No World Plane redesign.
- **No new architecture fitness rule** unless an actual bypass is found, with
  `CURRENT = PASS` and `SYNTHETIC = FAIL` demonstrated. Part M says otherwise add
  nothing, and discovery found nothing unenforced.
- No weakening of the 9.9C security baseline. The `approval_required` fix and its
  two regression guards are the baseline and must stay green.

---

## 4. Expected honest limits

Recorded now so they are not discovered as excuses later:

- **Crash coverage will be partial by design.** Ten named boundaries, but several
  ("after Assurance", "before World observation") are in-process steps after the
  irreversible act; killing there proves durability of records, not write safety.
  Each will be labelled for what it actually shows.
- **Process-count and egress limits** remain `NOT VERIFIED` (ADR-089), unchanged.
- **`UNKNOWN` on an interrupted provider request** is the property to prove; the
  contained worker already returns `ambiguous=True` on transport failure and the
  adapter maps it to `UNKNOWN_OUTCOME`.

---

## 5. Stop rule

Any of the brief's stop conditions — replay repeating the action, a revoked or
cross-tenant or cross-workload approval dispatching, digest bypass, model or
worker influencing authority, assurance bypass, secrets in durable state, a stale
worker executing, or recovery fabricating success — stops the phase and is
reported, as 9.6, 9.7, 9.9B and 9.9C did.
