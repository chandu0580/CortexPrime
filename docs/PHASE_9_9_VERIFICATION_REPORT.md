# Phase 9.9 Part A — Verification Report

**Phase:** Applying the ratified execution trust model
**Date:** 2026-09-04
**Branch:** `phase-1-foundation`
**ADR:** ADR-088 (ratified by the owner 2026-09-04, as written)

---

## Scope: Part A of two

ADR-088's implementation has two halves, and only the first is in this report.

| | Part | Status |
|---|---|---|
| **A** | The trust model in the contracts: `CodeTrust`, the `SANDBOXED` tier, the matrix, both gates, the digest, honest declarations | **COMPLETE — this report** |
| **B** | Making CONTAINED real: an out-of-process worker, a Kubernetes credential adapter behind the existing broker, then revisiting the 9.6 write | **NOT STARTED** |

**The Phase 9.6 write still does not execute, and Part A did not bring it
closer by a single gate.** What changed is that the obstacle is now the honest
one — see §4.

---

## 1. What was built

### 1.1 The `CodeTrust` axis — `backend/contracts/connector.py`

Five classes, ordered: `FIXED`, `PARAMETERIZED`, `THIRD_PARTY`,
`OPERATOR_SCRIPT`, `ARBITRARY`. Documented as a claim about **the code as
shipped**, true only while integrity is enforced — compromised fixed code is
arbitrary code.

### 1.2 The `SANDBOXED` tier

`IsolationTier` now has four ordered members with `rank` and `satisfies()`.
`SANDBOXED` is the kernel-hardened shared-kernel band. It is explicitly **not**
SEALED, and `SANDBOXED.satisfies(SEALED)` is `False` — verified.

**SEALED is unchanged, verbatim.** Its text still reads *"Arbitrary commands or
code. Full virtualization, no ambient credentials"* and *"explicitly excludes
shared-kernel containers."* Verified from source.

### 1.3 The matrix — `minimum_isolation(code_trust, side_effect)`

|  | READ | REVERSIBLE_WRITE | IRREVERSIBLE_WRITE | DESTRUCTIVE |
|---|---|---|---|---|
| FIXED | ambient | contained | contained | contained |
| PARAMETERIZED | ambient | contained | contained | sandboxed |
| THIRD_PARTY | contained | sandboxed | sandboxed | sealed |
| OPERATOR_SCRIPT | contained | sandboxed | sealed | sealed |
| ARBITRARY | **sealed** | **sealed** | **sealed** | **sealed** |

Exactly ADR-088 §4.3. The function refuses to answer if either argument is
absent: an unstated code trust is not "probably fine", and an unstated effect is
not "probably a read."

### 1.4 Both gates read the matrix

- **Gate 1** — `CapabilityContract.__post_init__`:
  `isolation_tier.satisfies(minimum_isolation(code_trust, side_effect_class))`.
- **Gate 2** — `WorkerImplementation.permits(code_trust, side_effect)`, consumed
  by `worker_selection.py` → `WorkerRefusal.ISOLATION_INSUFFICIENT`.
  `permits_side_effect()` is retained, narrowed to mean *"with FIXED code"*
  rather than left ambiguous.

### 1.5 `code_trust` is in the capability digest

The drift control, and the answer to the cost I raised before ratification. A
capability that quietly reclassifies produces a different digest, so it cannot
inherit approvals granted to the old classification. Verified: `FIXED` and
`PARAMETERIZED` contracts that are otherwise identical do not share a digest
payload, and a contract survives a dict round-trip.

### 1.6 Declaration is mandatory everywhere

`RegisterCapability.code_trust` is required with no default. The registration
API validates it against a pattern. Capability *discovery* refuses an
observation that omits it: *"whether this runs one declared operation or
arbitrary code is the question isolation answers to, and a tool description that
does not say is one nobody has classified."* `BoundCapability.code_trust` is
required, so worker selection can never be asked to guess.

---

## 2. The hazard the ratification created, and how it was closed

This is the most important item in Part A and it was **not** in ADR-088's plan.

Before ratification, SEALED blocked every irreversible write regardless of what
a connector declared about itself — so the GitHub, Grafana, Prometheus and
Kubernetes connectors declaring `CONTAINED` while running **in-process** cost
nothing. ADR-059 documented the gap and nothing depended on it.

After ratification, `FIXED × IRREVERSIBLE_WRITE` requires only CONTAINED.
**A false CONTAINED declaration became load-bearing.** The only remaining thing
stopping the 9.6 write was that the operation is absent from the real exposure —
the isolation gates themselves would have passed on a declaration that was not
true.

**Fix:** the three in-process connectors now declare `AMBIENT`, which is what
they are — in-process, process-level credentials. `CONTAINED` requires a
separate worker with per-execution credentials, and *a worker becomes CONTAINED
by being out-of-process, never by being declared so.*

Measured effect on the in-process Kubernetes worker:

```
FIXED x read                -> PERMITTED
FIXED x reversible_write    -> REFUSED
FIXED x irreversible_write  -> REFUSED
FIXED x destructive         -> REFUSED
```

Every governed read still works. Every write is refused — now for the honest
reason, and ADR-059's gap is enforced rather than merely documented.

One consequence, stated plainly: Grafana's `folder.create_folder`
(`REVERSIBLE_WRITE`) is also refused in-process. That is correct under the
ratified model and was previously permitted only because the tier claim was
generous.

---

## 3. Results

| Check | Result |
|---|---|
| Trust-model unit tests (`test_execution_trust_model.py`) | **34/34** |
| `tests/contexts` | **1720 passed** |
| Full suite (excl. load/benchmarks/production_validation) | **6770 passed, 58 failed — every failure pre-existing** |
| Architecture gate | **PASS** — 35 passed, 0 failed, 6 skipped, 1181 modules |
| Phase 9.7 harness re-run | **30/30, exit 2** — SEALED still unobtainable here |

### The 58 pre-existing failures, verified as such rather than assumed

The full suite has 58 failures. **None is attributable to Part A**, and this was
established by measurement, not by reading the names:

- Zero failures mention `code_trust`, `CodeTrust`, `minimum_isolation` or an
  isolation refusal.
- The causes are V1 quarantine refusals (`LegacyCredentialStoreRefused`,
  `LegacyExecutionRefused`, `UnsandboxedScriptExecutionRefused`), a missing V1
  attribute (`approval_center.workflows.approval_queue`), and live external APIs
  answering 401/403 with no keys configured (Azure, OpenAI, Tavily, LiveKit).
- The one failure that looked like it could be mine —
  `tests/platform/test_dependency_isolation.py` — is
  `credentials/inspection.py imports disallowed root(s): ['base64']`, in a file
  this phase never opened.
- **Baseline check:** the same four failing modules were run in a clean git
  worktree at `HEAD` (pre-Part-A) and again with Part A applied. Both produced
  **11 failed, 12 errors**. Identical.

### Verified behaviours

- [VERIFIED] Every matrix row matches ADR-088 §4.3, cell by cell.
- [VERIFIED] The matrix is monotonic in both directions — requirements never
  *fall* as code becomes less trusted or effects get worse.
- [VERIFIED] **The Phase 9.8 reductio is fixed:** a `FIXED × IRREVERSIBLE_WRITE`
  capability registers at CONTAINED. CortexPrime can, in principle, post a
  GitHub issue comment without a microVM.
- [VERIFIED] **Arbitrary code is refused below SEALED for every effect,
  including READ** — stricter than anything the platform declared before.
- [VERIFIED] `THIRD_PARTY × DESTRUCTIVE` (a `terraform destroy`) requires SEALED.
- [VERIFIED] A `FIXED × IRREVERSIBLE_WRITE` capability is still refused at
  AMBIENT: *"'contained' is the minimum."*
- [VERIFIED] `SANDBOXED` does not satisfy `SEALED`; `SEALED` satisfies
  `SANDBOXED`.
- [VERIFIED] `code_trust` is in the digest and reclassification changes it.
- [VERIFIED] A worker *declared* SEALED still passes gate 2 — the gate trusts the
  declaration. Recorded because it is the model's residual risk, not hidden.
- [VERIFIED] The 9.6 write is still `IRREVERSIBLE_WRITE` and still absent from
  `KUBERNETES_REAL_READ_OPERATIONS`. Ratification did not quietly expose it.

### Finding 2 from Phase 9.8, closed without a new rule

If any of the three V1 arbitrary-code modules ever entered the fabric, it would
now have to declare `code_trust` — the field is required — and `ARBITRARY`
requires SEALED for every effect class, `terraform destroy` included. The
inverted coverage is closed structurally.

**No architecture fitness rule was added.** By this project's own standard a rule
is justified only where an invariant is otherwise unenforced; these invariants
are enforced by the two gates and covered by unit tests. A `BND-SEALED-*` rule
would be cosmetic.

---

## 4. The 9.6 write, restated honestly

`kubernetes.workload.rollout_restart` is unchanged: `IRREVERSIBLE_WRITE`,
`NON_IDEMPOTENT_WRITE`, `reversible=False`, `INDEPENDENT_READBACK`, ceiling A3,
`RiskLevel.HIGH`. It was not executed and not reclassified.

| | Requirement | Obstacle |
|---|---|---|
| Before ADR-088 | SEALED — hardware virtualization | **Impossible** on this hardware (ADR-087) |
| After Part A | CONTAINED — a real out-of-process worker with per-execution credentials | **Buildable, and not yet built** |

The write is still refused, by the same two gates, for a different and truer
reason. **Part A moved the obstacle from physics to engineering.** That is all it
did, and that was the point.

---

## 5. What Part B must do

1. An out-of-process worker for one capability, reached through the existing
   `WorkerRuntime.invoke` seam — no second executor.
2. A Kubernetes credential adapter behind the **existing** broker — no competing
   credential authority, and per-execution credentials rather than the current
   long-lived ServiceAccount token.
3. That worker declares `CONTAINED` **because it is**, and the declaration is
   then true rather than convenient.
4. Only then, the Phase 9.6 write — with every governance gate that already
   passed in 9.6 re-run against a real cluster.

---

## 6. Honest limits

- [NOT VERIFIED] No out-of-process worker exists, so `CONTAINED` is currently a
  tier **nothing declares** — the same status SEALED had before Phase 9.6, and
  worth watching for the same reason: an unexercised tier is one nobody has had
  to defend.
- [NOT VERIFIED] `SANDBOXED` likewise has no occupants. It was added because the
  matrix needs it for `THIRD_PARTY` and `OPERATOR_SCRIPT` code, none of which is
  in the governed fabric yet.
- [UNCHANGED] Phase 5.5's credential blocker.
- [UNCHANGED] L1–L16, authorization, approval and its five voiding clauses, all
  ten autonomy gates, emergency stop, circuit breaker, fencing, replay
  inertness, audit, assurance, and `SideEffectClass` in full.
- **Residual risk, stated rather than buried:** the gates trust the
  declarations. `code_trust` in the digest catches *drift* in a declaration; it
  cannot catch a declaration that was wrong from the start. Code integrity —
  pinned versions and digests — is the precondition ADR-088 Decision 4 named,
  and it remains a precondition rather than a proof.
