# ADR-099 — Phase 10.6: separation of duties, requester ≠ approver

**Status:** Accepted (implemented)
**Date:** 2026-09-06
**Extends:** ADR-098 (approver authority), ADR-097 (approval queue), ADR-096 (human approval and remediation), ADR-090 (approval binds to the action)
**Map:** `docs/PHASE_10_6_IMPLEMENTATION_MAP.md`
**Verification:** `docs/PHASE_10_6_VERIFICATION_REPORT.md`
**Harness:** `scripts/phase106_separation_of_duties_harness.py` — 123/123

Labels: `[FACT]` verified from this repository or a live run, `[DECISION]`,
`[CONSEQUENCE]`.

## Context

Phase 10.5 made approving an irreversible action require an explicit grant, and
reported honestly that the requester could hold that grant — so one person could
still raise and approve an irreversible remediation alone. It deferred changing
that, because adding the constraint silently would have been inventing
governance. This ADR adds it deliberately.

## Decision 1 — Reuse the primitive, not the predicate `[DECISION]`

`[FACT]` Separation of duties already exists here and is enforced — for a
different pair: a capability owner may not be the one who makes it live. But
that check reasons about a capability lifecycle operation and an owner; it has
no approval, no decision and no deciding actor. Calling it for this question is
impossible, and extending it to take them would change its semantics rather than
preserve them.

`[DECISION]` What is reused is the outcome vocabulary.
`separation_denial_reason()` returns the platform's own
`DenialReason.SEPARATION_OF_DUTIES`, so a refusal here and a refusal in the
capability policy are the same named thing and a reviewer grepping for it finds
both. The predicate is one identity comparison; there is no engine to duplicate.

## Decision 2 — Compare the two stored, server-minted references `[DECISION]`

`[FACT]` `requested_by` and `decided_by` are both written by the **same helper**
from the verified session, so the comparison is between two canonical
`human:<subject>` references — never display names, browser-supplied usernames
or free text — and no parameter exists through which a caller could supply
either side.

`[DECISION]` Normalised on whitespace and case only, because the same person
must not become two people through a capitalisation difference. `[DECISION]` An
absent or unreadable requester **denies**: an approval whose requester cannot be
established is exactly the one where nobody can say the decision was
independent.

`[FACT]` The requester is already inside `canonical_approval_digest`. The policy
reads that identity and never rewrites it — asserted byte-for-byte on the
approve path, the reject path, and after a refused self-decision.

## Decision 3 — It applies to BOTH decisions `[DECISION]`

`[DECISION]` The requester may neither approve nor reject. A rule that stopped
approval but allowed rejection would leave them able to bury their own request —
the same authority wearing a different hat. `[FACT]` Both are refused 403 with
`separation_of_duties`, and the approval stays **pending** with no decider.

## Decision 4 — Precedence is inherited, not chosen `[DECISION]`

`[FACT]` `CapabilityPolicy.evaluate` checks authorization first, separation of
duties second, and state concerns after. The new check sits in the same
position: after approver authority, before expiry.

`[CONSEQUENCE]` An approval that is both expired *and* self-decided answers
`SEPARATION_OF_DUTIES`, while an independent approver on that same approval gets
the expiry. `[FACT]` That is what Part N's own worked example expects — reached
by inheriting the order rather than picking one.

## Decision 5 — The requester must not win a race `[DECISION]`

`[FACT]` With the requester and an approver deciding simultaneously, the
requester is refused 403 and the approver succeeds, and the single stored
decision is the approver's. The refusal happens on its own merits before the
request reaches the conditional update, so there is no window in which it could
win. `[DECISION]` **No distributed lock** — the existing optimistic concurrency
is untouched.

## Decision 6 — Say why, and do not hide the row `[DECISION]`

`[DECISION]` Telling a requester "you lack authority" would be **false** — they
have it. The screen distinguishes four reasons as four sentences: nobody may
decide this any more; you may not and neither may most people here; you may in
general and not this one because you asked for it; and you may decide it.

`[DECISION]` The row is **not hidden** from the requester. Hiding it would leave
them unable to tell "somebody must act on what I raised" from "nothing is
there".

`[FACT]` The flag is computed server-side; a frontend test asserts the component
contains no `requested_by ===` comparison and no `currentUser`. A client-side
comparison would put the security control in the one place that cannot be
trusted.

## Decision 7 — No new fitness rule `[DECISION]`

`[FACT]` The policy lives in `backend/auth/approver.py`, which
`BND-AUTH-CANNOT-EXECUTE` already covers — proven by injecting
`from backend.contexts.execution.domain import invocation` into that module and
watching the gate FAIL naming it. A second rule would be cosmetic.

## What this ADR does NOT decide

- **Requester and proposer are the same person** in this model. If a proposer
  role is ever introduced, this policy must be revisited rather than assumed to
  cover it.
- **The identity reference is not tenant-qualified.** Safe today because the
  approval is tenant-scoped and never visible across the boundary; changing the
  format would change what existing stored references mean.
- **Execution authority is still not narrowed.** A requester who cannot approve
  their own action can still execute one an independent approver approved —
  arguably correct, since the judgement was independent, but named rather than
  implied covered.
- No new capability, no new table, no new authority, no RAG, no exactly-once.

## Status of the invariants

`[FACT]` 123/123 on the first run. 37 negative cases, **0 provider writes**,
refusals attributed across six layers, and the approval all of them targeted
still pending. One real provider write on the positive path, the
already-commissioned `kubernetes.workload.rollout_restart`. Both digests
byte-identical across approve, reject and refusal. Architecture gate PASS
(37 passed, 0 failed, 6 skipped, 1194 modules). Frontend 113/113.
