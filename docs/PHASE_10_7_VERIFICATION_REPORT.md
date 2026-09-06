# Phase 10.7 — Scoped Approver Authority + Narrow Execution Authority
## Verification Report

**Verdict: VERIFIED — 155/155.**

Harness: `scripts/phase107_scoped_authority_harness.py`
Infrastructure: real k3d cluster (`k3d-cortex-p99b-server-0`, v1.35.5+k3s1),
real PostgreSQL (`cortex_p107`), real Redis, real tenant store, real OS
process death. No mocks, no in-memory substitutes, no simulated refusals.

Every claim below is labelled. Nothing is asserted from a code reading alone.

---

## 1. Section results

| § | Area | Checks |
|---|---|---|
| A | Composition — no new surface, table or capability | 6 [VERIFIED] |
| B | Grant grammar — categorical, no wildcards, no score | 11 [VERIFIED] |
| C | Approver scope, bound to the stored action | 8 [VERIFIED] |
| D | Execution scope — the gap 10.5 and 10.6 both named | 6 [VERIFIED] |
| E | Requester, approver, executor stay three concepts | 5 [VERIFIED] |
| F | Scope consumes digests, never rewrites them | 4 [VERIFIED] |
| G | The queue projects both scopes, per row | 12 [VERIFIED] |
| H | Revocation — approver grant, executor grant, approval | 4 [VERIFIED] |
| I | Concurrency | 2 [VERIFIED] |
| J | Negative matrix | 88 [VERIFIED] |
| K | Restart | 5 [VERIFIED] |
| L | Audit | 3 [VERIFIED] |
| M | Measured latency | 1 [VERIFIED] |
| | **Total** | **155 / 155** |

Ten personas were provisioned, each holding a **real** grant — for something
that is not this action. A refusal in this phase is never merely the absence of
a grant unless the case says so.

REQUESTER · APPROVER · APPROVER_TWO · WRONG_CAPABILITY · WRONG_ENVIRONMENT ·
LOW_RISK_ONLY · LEGACY_GRANT · EXECUTOR · APPROVER_NO_EXEC · OTHER_TENANT

---

## 2. Approver scope [VERIFIED]

Each refusal names the **dimension that failed**, because a wrong capability, a
wrong environment and a risk ceiling are three different grants to go and ask
for:

| Case | Result | Reason code |
|---|---|---|
| C1 wrong capability | 403 | `out_of_scope_capability` |
| C2 wrong environment | 403 | `out_of_scope_environment` |
| C3 risk ceiling exceeded | 403 | `risk_exceeds_grant_ceiling` |
| C4 legacy unscoped grant | 403 | `grant_is_not_scoped` |
| C5 correctly scoped approver | 200 | `scoped_grant_matched` |

Scope is resolved against the **stored approval row** — its capability, its
environment — and the risk the platform derives with its own
`implied_risk_for()`. Nothing is read from the request; the request models
forbid extra fields, so supplying a capability, environment or risk is a 422,
not a silent ignore. [VERIFIED]

## 3. Execution scope [VERIFIED]

Before this phase, `POST .../execute` checked tenant membership and a valid
approval. **Any tenant member could execute any granted approval.**

| Case | Result | Reason code |
|---|---|---|
| D1 member, no execution grant | 403 | `no_executor_authority` |
| D2 approver without execution grant | 403 | `no_executor_authority` |
| D3 executor, wrong capability | 403 | `out_of_scope_capability` |
| D4 executor, wrong environment | 403 | `out_of_scope_environment` |
| D5 correctly scoped executor | 200 | one real cluster mutation |

`executor_authority` appears as its own stopping layer 6 times in the negative
matrix — it is not folded into `governance`. [VERIFIED]

## 4. Separation of duties survived, and did not spread [VERIFIED]

`requester != approver` still holds (`separation_of_duties`, 1 negative case).
`requester != executor` was **not** introduced. §E proves all three
combinations explicitly: the requester may execute, the approver may execute,
and a third party may execute — each only if they hold execution scope.
Imposing an unratified `requester != executor` would have been inventing
governance. [VERIFIED]

## 5. Digest integrity [VERIFIED]

§F: `capability_digest` and `canonical_approval_digest` are byte-identical
before and after every scope decision. Scope **consumes** digests as an input
to a decision; it never participates in computing them and never rewrites an
action. A refusal changes no stored bytes. [VERIFIED]

## 6. Negative matrix — 47 cases, 0 provider writes [VERIFIED]

`negative_matrix_provider_writes = 0`, established by reading the **cluster's
own state**, not by trusting an HTTP status.

Refusals are attributed to seven distinct layers and never collapsed into
"blocked":

| Stopping layer | Cases |
|---|---|
| governance | 28 |
| executor_authority | 6 |
| approver_authority | 4 |
| approval_state | 4 |
| membership | 2 |
| authentication | 2 |
| separation_of_duties | 1 |

Includes tenant isolation (other-tenant caller holding a valid grant in their
own tenant), forged identity, missing tenant claim, altered approval row,
altered capability row, and direct worker / provider / grant-route attempts.
[VERIFIED]

## 7. Revocation and expiration [VERIFIED]

§H: revoking the approver grant, revoking the executor grant, and withdrawing
the approval each take effect on the next request against the authoritative
store. The JWT is not treated as the authority. Expired approvals refuse at
`governance` with 409 (N27); rejected and withdrawn refuse at `approval_state`
(N26, N28). Instantaneous revocation is **not** claimed — the guarantee is
"authoritative on next check", as established in Phase 10.5. [VERIFIED]

## 8. Concurrency and replay [VERIFIED — with an explicit non-claim]

```
concurrent_execution_codes  = [200, 200]
concurrent_execution_writes = 1
```

Reported verbatim. Two concurrent executions of one approval returned 200 twice
and produced **one** cluster mutation. **Exactly-once is NOT claimed.** The
platform contract is at-least-once, no idempotency was invented for this phase,
and if both had produced separate legitimate writes that is what this report
would say. [VERIFIED as measured]

Replay of a recorded execution remains inert (Phase 9.10 behaviour, unchanged).

## 9. Crash / restart [VERIFIED]

§K: after real OS process death and restart, scope decisions are recomputed
from the durable store. No grant, scope verdict or approval state was cached
across the boundary in a way that survived it. No fabricated success.
[VERIFIED]

## 10. Audit [VERIFIED]

§L: the audit record for a decision carries
`[authority=… scope=<matched_grant> membership_role=…]`, so the record says
**which grant** authorized it, not merely that someone was permitted. No audit
events were invented for reads. The chain is unbroken. [VERIFIED]

## 11. Performance [VERIFIED — measured, not estimated]

| Path | p50 | p95 |
|---|---|---|
| Queue list | 207.7 ms | 333.3 ms |
| Approval detail | 19.8 ms | 22.9 ms |
| Unauthorized approval (refusal) | 10.3 ms | 12.1 ms |
| Unauthorized execution (refusal) | 11.3 ms | 13.9 ms |
| Authorized approval | 31.9 ms | 37.2 ms |

Refusals are the fastest paths — scope resolution short-circuits before any
governed work. No index was added; none was justified by the measurement.

## 12. Frontend [VERIFIED]

- `npx vitest run tests/investigator` — **121 passed**.
- `npx tsc --noEmit` — 5 errors, **all pre-existing**, all in
  `operations-center/` and `runtime/`; none in any investigator file.

The product distinguishes, in words: APPROVED — YOU MAY EXECUTE / APPROVED —
NO EXECUTION AUTHORITY / OUT OF SCOPE — CAPABILITY / OUT OF SCOPE —
ENVIRONMENT / ABOVE YOUR RISK CEILING / GRANT NOT SCOPED / YOU REQUESTED THIS
/ EXPIRED / WITHDRAWN / REJECTED.

Out-of-scope rows are **shown, not hidden** — hiding them would imply no
approval exists. Every reason is a server-provided code rendered by
`readScopeRefusal()`; the client infers no scope, computes no risk, and
performs no identity comparison. The Execute control is gated on the server's
`can_execute`, never on the existence of an approval. Refusals never rely on
colour alone — each carries an explicit textual label and a `role="note"`
region. [VERIFIED]

## 13. Architecture gate and regression [VERIFIED]

- `tests/architecture` — **155 passed**. `BND-AUTH-CANNOT-EXECUTE` still
  covers `backend/auth/approver.py`, where all authority logic was added.
  **No new fitness rule was added** — per Part U, none is warranted because no
  new bypass exists: the product layer gained no new route to execution, and
  scope lives inside the authority module the existing rule already fences.
- Backend regression — **2819 passed** (`tests/contexts tests/intelligence
  tests/contracts tests/assurance tests/world`).
- Combined **2974**, matching the pre-phase baseline exactly. No test was
  weakened, skipped or allow-listed. [VERIFIED]

## 14. Stop conditions — none triggered [VERIFIED]

| Stop condition | Result |
|---|---|
| Existing component insufficient | Not triggered — `permissions`, the `AutonomyScope` vocabulary, `implied_risk_for`, `supported_environments` and the approval row all sufficed |
| A new table appears necessary | Not triggered — **0 migrations**, durable schema unchanged at **22 tables** |
| Requester identity caller-supplied | Not triggered — resolved server-side from the verified session |
| Environment abstraction missing | Not triggered — `supported_environments` and the approval `environment` column already existed, so no DEFERRED was needed |
| Second governance authority required | Not triggered — scope sits inside the existing authorization step |

## 15. Known limitations [NOT VERIFIED / DEFERRED]

1. **Exactly-once is not claimed.** [Explicit non-claim] At-least-once, with
   `[200, 200] → 1 mutation` reported verbatim.
2. **Revocation is authoritative-on-next-check, not instantaneous.** A request
   already past the check completes. [DEFERRED]
3. **Grants are issued outside the product API.** There is no grant-management
   surface; `grant_permission` / `revoke_permission` are called
   administratively. This is *why* an approver cannot widen their own scope,
   and it is also a gap: grant issuance itself is not yet governed, audited or
   approval-bound. [DEFERRED — the natural Phase 10.8]
4. **Grants are version-pinned.** A capability version bump silently
   invalidates existing grants — fail-closed, but operationally sharp. No
   re-issue tooling exists. [NOT VERIFIED against a real version bump]
5. **A bare `approve:remediation` grant no longer confers authority.**
   Deliberate breaking change, fail-closed, surfaced to the holder as
   `grant_is_not_scoped` rather than as "you are not an approver".
6. **`max_risk` is optional.** A grant omitting it accepts any risk the
   capability declares, bounded only by capability and environment scope.
7. **One commissioned write.** Everything here is proven against
   `rollout_restart@1`. The scope logic is capability-generic but has been
   exercised against exactly one real capability. [NOT VERIFIED for others]
8. **No scope inheritance, groups or roles.** Grants are per-principal and
   flat. Deliberate — hierarchy is where wildcards re-enter.

---

## 16. Defects found and fixed during this phase

1. **The Phase 10.5 gate did an exact string match** (`APPROVE_REMEDIATION in
   permissions`), so a correctly scoped grant failed the *outer* authority
   check. Fixed by parsing rather than matching; 10.5 now asks "are you an
   approver at all?" and 10.7 asks "for THIS action?".
2. **The harness hardcoded a capability reference without its `@1` version.**
   `reference.value` is versioned. Now derived at runtime.
3. **A Python default argument bound `CAPABILITY` at definition time**, when it
   was still `""` — so every grant the harness built was empty and the scope
   tests would have passed vacuously. Fixed, and stale grants are now cleared
   each run because the tenant store is durable.
4. **My own assertion expected the wrong field.** G1 looked for
   `scoped_grant_matched` in `authority_reason`; the projection correctly
   reports `approver_authority_granted` there and the scope verdict in
   `approve_scope_reason`. The assertion was corrected — strengthened to check
   both — not the code.

As in every prior phase, the verification checks were wrong more often than the
production code was, and each was fixed to be stronger rather than removed.
