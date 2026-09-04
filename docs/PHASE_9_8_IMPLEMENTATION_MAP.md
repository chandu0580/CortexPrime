# Phase 9.8 — Implementation Map

# NO IMPLEMENTATION IN 9.8

**No code was changed. No migration was created. No table was added. No connector
was built. No worker exists. Nothing was executed. The Constitution was not
modified.**

Phase 9.8 was an architecture-only reassessment. Its output is three documents
and a decision that has **not** been made — it awaits ratification.

---

## 1. What this phase produced

| Artifact | Purpose |
|---|---|
| `docs/PHASE_9_8_EXECUTION_TRUST_MODEL.md` | The full analysis: current semantics verified from source, threat model, capability matrix, Options A–D, Constitution review, Phase 9.6 reassessment |
| `docs/adr/ADR-088-execution-trust-model.md` | The proposed decision, **status PROPOSED, not applied** |
| `docs/PHASE_9_8_IMPLEMENTATION_MAP.md` | This file |

`git status` for this phase shows three added documents and **zero modified
files**.

---

## 2. What was read, and how

Discovery was source-verified, not recalled. Where a claim could be *executed*
rather than read, it was executed.

**Read from source:** `IsolationTier` and `_TIER_SUFFICIENCY`
(`backend/contracts/connector.py`); `SideEffectClass`, `EffectSemantics`,
`ExecutionEnvironment` (`backend/contracts/execution.py`); `RiskLevel`
(`backend/contracts/policy.py`); `CapabilityContract.__post_init__`
(`contexts/connectivity/domain/contract.py`); `WorkerImplementation` and
`permits_side_effect` (`contexts/execution/domain/worker_directory.py`);
`worker_selection.py`; `InvocationGateway.invoke`; `WorkerRuntime`;
`backend/platform/credentials/broker.py`; `backend/api/credential_composition.py`;
`backend/platform/transport/`; the architecture fitness rules;
`docs/CORTEXPRIME_INTELLIGENCE_CONSTITUTION.md` (L1–L12 verbatim, trust
boundary); ADR-086 and ADR-087.

**Executed rather than asserted:**

1. Imported every real connector catalog and enumerated declared effect classes
   → the four non-read operations in the repository.
2. Constructed a `CapabilityContract` for each of those at the tier its connector
   is actually composed with → three refusals, including
   `repository.create_issue_comment`.
3. Searched `backend/` for any SEALED declaration → one hit, a string comparison
   in a report.
4. Checked the three arbitrary-code V1 modules for `side_effect_class` and
   `IsolationTier` declarations → zero of each.
5. Searched `docs/adr/` for ADR-005 and `docs/` for any "S6" clause definition →
   neither exists.

---

## 3. The findings, in one place

1. `[FACT]` The taxonomy refuses `repository.create_issue_comment` — posting a
   GitHub comment requires full virtualization. Hardware-independent.
2. `[FACT]` The three modules that execute arbitrary code declare no effect class
   and no isolation tier. The coverage is inverted.
3. `[FACT]` Nothing has ever declared SEALED. The rule had never gated anything
   before Phase 9.6.
4. `[FACT]` "Constitution S6" and "ADR-005" — the cited authority for the rule —
   do not exist in this repository.
5. `[FACT]` Ratified law L10 already prices consequence in *authority, approval
   depth and verification strength*, with its mechanism named as policy ladder
   rules. It does not name isolation.

---

## 4. What is NOT implemented, and must not be until ratified

Everything below is described in ADR-088 as a proposal. **None of it exists.**

- No `CodeTrust` enum.
- No `SANDBOXED` tier. `IsolationTier` still has exactly three members.
- No change to `_TIER_SUFFICIENCY`.
- No `_MINIMUM_ISOLATION` matrix.
- No change to `SideEffectClass` or to any capability's reversibility class.
- No `CodeTrust` declaration on any capability or worker.
- No new architecture fitness rule. A rule is justified only where an invariant
  is otherwise unenforced; the invariants discussed are already enforced and
  already pass.
- No out-of-process worker.
- No Kubernetes credential adapter.
- No registration of `kubernetes.workload.rollout_restart`, which remains
  declared, honestly classified, unexposed and never executed.

---

## 5. Unchanged, and verified so

- `IsolationTier` — three tiers, definitions untouched, SEALED verbatim.
- `SideEffectClass` — four classes, untouched.
- Both isolation gates — registration and worker selection — still refuse exactly
  as they did in Phase 9.6.
- Authorization, capability binding, tenant binding, approval and its five
  voiding clauses, all ten autonomy gates, emergency stop, circuit breaker,
  fencing, replay inertness, audit chain, independent assurance.
- L1–L16.
- The Phase 5.5 credential blocker.
- Architecture gate: PASS, unchanged (no code was touched).

---

## 6. If ADR-088 is ratified — the shape of 9.9

Recorded for planning only. **Not started, not designed in detail, not approved.**

The proposed model returns **CONTAINED** for the rollout restart — and CONTAINED
means *"separate worker, per-execution credentials,"* which the in-process
Kubernetes connector does not provide (ADR-059's stated gap). So Phase 9.9 would
be **"make CONTAINED real"**, not "build a sealed worker":

1. Declare `CodeTrust` on existing capabilities (20 governed operations, all
   `FIXED`), and on the three V1 modules (which become *more* constrained).
2. An out-of-process worker for one capability, reached through the existing
   `WorkerRuntime.invoke` plug point — no second executor.
3. A Kubernetes credential adapter behind the **existing** broker — no competing
   credential authority.
4. Then, and only then, revisit the Phase 9.6 write.

Phase 9.7's discovery map already located everything that work would reuse: the
credential broker with its post-issuance verification, the
`GatewayAuthorityRevalidator`, the `WorkerRuntime.invoke` seam, and the existing
leases and fencing.

---

## 7. If ADR-088 is rejected

CortexPrime remains read-only against every provider, permanently and by
decision. That is a legitimate outcome and the analysis says so explicitly.

Findings 2, 3 and 4 survive rejection and still deserve separate attention: the
arbitrary-code paths would still declare no tier, SEALED would still be
unoccupied, and the isolation rule would still cite a document that does not
exist.

---

**Phase 9.8 stops here, at the decision.**
