# ADR-095 — Phase 10.2: the read-only incident investigator workspace

**Status:** Accepted (implemented)
**Date:** 2026-09-05
**Extends:** ADR-094 (product API boundary), ADR-093 (Phase 10), ADR-085 (read-only investigator), ADR-088–092 (Phase 9)
**Map:** `docs/PHASE_10_2_IMPLEMENTATION_MAP.md`
**Verification:** `docs/PHASE_10_2_VERIFICATION_REPORT.md`
**Harness:** `scripts/phase102_workspace_harness.py` — 67/67

Labels: `[FACT]` verified from this repository or a live run, `[DECISION]`,
`[CONSEQUENCE]`.

## Context

ADR-094 gave the verified engine a governed API and nothing that consumed it.
Phase 10.0 chose the first vertical: a **read-only AI incident investigator**.
The question this phase had to answer is whether an SRE can actually investigate
through that surface without the UI inventing truth or routing around
governance.

## Decision 1 — The missing wire is in the backend, and it fails closed `[DECISION]`

Discovery found a blocker before any UI existed: **login minted tokens with no
tenant claim** (`auth_routes.py:192`) `[FACT]`, and the Product API correctly
refuses such a token with 403 `[FACT]`. No browser session could reach a single
endpoint.

The frontend must not fix this — a client-supplied tenant is a stop condition.
So login and refresh now resolve membership from the **existing**
`TenantManager` and pass it to the **existing** `create_access_token`, which
already accepted `tenant_id`, `tenant_slug` and `user_role` `[FACT]`.

`[FACT]` No membership, an inactive membership, an inactive tenant, or a store
failure yields **no claims at all** — exactly the pre-change behaviour, so the
API keeps answering 403. Refresh **re-resolves** rather than copying, so a
revoked membership stops being honoured at the next rotation.

`[CONSEQUENCE]` Authentication is still a single env-configured user with a
file-backed membership store. This wires tenancy into the session; it does not
make CortexPrime multi-user. That remains Phase 10.9.

## Decision 2 — Four read methods, no new store `[DECISION]`

Part R required proving the workspace needs a gap closed before closing it.

| Added | Why it was needed | What it is |
|---|---|---|
| `list_active` | An investigator that can only list *finished* investigations is a report archive; the one a responder needs is the one still running | The existing `list_terminal` query with the status filter inverted |
| `list_events` | A timeline | A read of the append-only ledger, ordered by `seq` |
| Evidence resolution | 10.1 returned bare observation ids; a responder cannot check a claim they cannot see | The existing `get_observation`, per reference |
| `BeliefFormation` on the engine | CORRELATED vs INDEPENDENT | The existing belief path, with the **same** query and the **same** policies |

`[DECISION]` No `Incident` aggregate, no new table, no migration, no new
repository. Residual uncertainty and evidence gaps come from `settle()` and
`analyze_gaps()` — the platform's own deterministic functions of persisted state.
**This module may call the engine's reasoning and may never contain any.**

## Decision 3 — The UI has one route out of the browser, enforced `[DECISION]`

`lib/product-api.ts` exposes `productGet` and nothing else: there is no
post/put/delete to call. `[FACT]` Sensitivity-tested — injecting an `axios`
import and a `fetch(..., {method:"POST"})` into a workspace component failed 5
assertions in `frontend/tests/investigator/boundary.test.ts`.

`[DECISION]` **No Python architecture fitness rule was added.** The gate scans
Python and cannot see TypeScript; a `BND-PRODUCT-UI-*` rule there would restate
rules that already hold and still not cover the code it names. Part X forbids
cosmetic rules, so the boundary is enforced where it lives.

## Decision 4 — Same-origin, rather than a wider CSP `[DECISION]`

`[FACT]` `next.config.ts` sets `connect-src 'self' https:`, which **blocks** a
direct call to `http://localhost:8110`.

The response was not to widen the policy. The workspace reaches the Product API
through a same-origin rewrite. The CSP is satisfied untouched, no credentialed
cross-origin request is made, and the browser needs no CORS allowance at all.

## Decision 5 — A separate epistemic vocabulary, not the existing StatusPill `[DECISION]`

`[FACT]` `components/ui/StatusPill.tsx` offers `success | warning | error | info`.
Rendering STALE as *warning* and CONFLICTED as *error* is the collapse Parts G
and M forbid: a stale observation is not a malfunction and a conflict is not an
error.

So `EpistemicBadge` and `lib/investigator/epistemic.ts` define their own tones —
established / absent / aged / disputed / insufficient / excluded / open /
neutral. `[FACT]` The tone set contains no `success`, `warning` or `error`
member, and a test asserts it. The rest of the design system — tokens, layout,
auth guard, query provider — is reused unchanged.

`[DECISION]` **The state name is always rendered as words**, so it survives
greyscale, colour blindness and a screen reader. Colour is emphasis on top of a
label that already says the whole thing.

## Decision 6 — CORRELATED says, in words, that it is not independent `[DECISION]`

The label is literally **"CORRELATED — NOT INDEPENDENT"**.

`[FACT]` Proven against real data: `connector:kubernetes` and
`prometheus:kube-state-metrics` both reporting `restartCount: 7` came back as
`correlated`, with **two sources and exactly one distinct origin**, and the
reason *"2 sources agree but share lineage origin 'kubernetes-cluster' —
correlated, not independent"*.

## Decision 7 — Two clocks, never one `[DECISION]`

`TemporalStamp` has no unlabelled mode. `observed_at` (the world),
`retrieved_at` (when CortexPrime learned), `recorded_at` (a ledger commit) and
`read_at` (when this answer was computed) each render under their own name, in
explicit UTC. `[FACT]` A missing time renders as "not recorded", never as a
blank that reads like zero.

## Decision 8 — Historical experience is a filter, not a retrieval system `[DECISION]`

Prior investigations of the same subject are shown in a panel headed
**HISTORICAL EXPERIENCE** with an explicit statement that they do not establish
current truth. It filters the already-exposed completed list by subject. **No
embeddings, no vector search, no similarity score** (Part Q) `[FACT]`.

## Three defects in the Phase 10.1 projection, corrected `[FACT]`

Found while mapping, all of the same kind — reading attributes the contracts do
not have, which fails silently as an empty field rather than loudly as an error:

1. `conclusion.residual_uncertainty` on a `str` Enum — **residual uncertainty
   was always empty**. Now from `settle()`.
2. A conclusion *kind* projected into a field named `diagnosis`.
3. `record.procedure` and `record.predicate` on a `WorldVerification`, which has
   `procedure_ref` and a `VerifierIdentity` — so **who verified was never
   shown**, and independence could not be checked.

## What this ADR does NOT decide

- No mutation, approval, execution or autonomy control. Autonomy is displayed as
  a platform-set fact with no input that could change it `[FACT]`.
- No live updates, no websocket, no streaming.
- No incident aggregate, no RAG, no notifications, no RBAC.
- No SLA. The measured latencies are in-process, single-client, local database.

## Status of the invariants

`[FACT]` Architecture gate PASS (35 passed, 0 failed, 6 skipped, 1189 modules).
Regression 2974 passed, 0 failed. The Phase 10.1 harness passes against this code
(44/44). Provider calls during the whole run: **0**. Five full workspace loads
changed no row in any ledger. No migration, no new table, no new execution or
governance authority, no new credential path.
