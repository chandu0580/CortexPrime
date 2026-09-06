# ADR-096 — Phase 10.3: human approval and governed remediation from the product

**Status:** Accepted (implemented)
**Date:** 2026-09-06
**Extends:** ADR-095 (workspace), ADR-094 (product API), ADR-090 (approval binds to the action), ADR-089 (contained execution), ADR-088 (execution trust model)
**Map:** `docs/PHASE_10_3_IMPLEMENTATION_MAP.md`
**Verification:** `docs/PHASE_10_3_VERIFICATION_REPORT.md`
**Harness:** `scripts/phase103_approval_remediation_harness.py` — 121/121

Labels: `[FACT]` verified from this repository or a live run, `[DECISION]`,
`[CONSEQUENCE]`.

## Context

Phase 10.2 gave a responder everything except a way to act. The question here is
whether a human can approve and initiate a real remediation through the product
without the frontend becoming a second governance authority.

The reason this needed a full negative matrix rather than a demo: Phase 9.9C
found a live hole where authorization downgraded REQUIRE_APPROVAL to ALLOW and
the gateway's action-digest comparison became unreachable, so an approval for
`billing-api` restarted `payments-api` `[FACT]`. A product API is a **new
caller** into that same path, and the way a new caller reintroduces such a defect
is by being trusted with a value it should have had to derive.

## Decision 1 — Implement the approval port durably; decide nothing `[DECISION]`

`[FACT]` CortexPrime has had an approval contract, an approval port and a
gateway check since Phase 9, and **nowhere to keep an approval**: the only
implementations were `NoApprovals` and an in-memory dict inside a harness. The
first governed write was authorized by an approval that lived in one process's
memory, bound by writing to a private attribute.

`cp_approval` and `SqlApprovalRepository` store approvals and run the
request/decide workflow. They hold no judgement: whether an approval covers an
action is still `ApprovalFacts.is_valid_for`; whether it covers *this* action is
still the gateway's digest comparison. `request()` takes the approval digest as
a **required argument** so nothing reaches into a private field again.

`[DECISION]` Installed through the declared seam —
`build_authorization(approvals=…)`, via a new `approvals_factory` parameter on
`build_governed_runtime` that defaults to `None`. `[CONSEQUENCE]` Existing
callers are unchanged and still fail closed.

## Decision 2 — The product API stops being read-only, in exactly three places `[DECISION]`

`[FACT]` Three POST routes exist and the harness asserts the application's
non-GET routes **equal** that enumerated set, so a fourth cannot appear
unnoticed. They live in one short file so the mutation surface can be read end
to end.

`[DECISION]` Every request model sets `extra="forbid"`. A body carrying
`tenant_id`, `action_digest`, `risk`, `autonomy_level`, `actor` or any other
authority field is **rejected 422**, not accepted-and-ignored. Ignoring is safe;
rejecting is honest — it makes an attempt to smuggle authority visible in a log
rather than invisible in a success.

## Decision 3 — Nothing a browser sends is authority `[DECISION]`

A client names an investigation and says why. Capability, provider, namespace,
workload, payload, environment, principal, side-effect class, code trust,
isolation tier, reversibility and **both digests** are reconstructed server-side
from the capability contract and the platform's own digest function.

`[FACT]` The harness recomputes the returned approval digest with
`canonical_approval_digest` and asserts equality, and asserts a different
workload yields a different digest.

`[DECISION]` The approver's identity is built from the verified session
(`human:<principal>`). There is no field on any model through which an actor
could be supplied, so `"admin"` in a body is not ignored — it is inexpressible.

## Decision 4 — The execution door is the existing one `[DECISION]`

`execute` calls `GovernedCapabilityWriter.write` with the payload **from the
stored approval row**. There is no second place a target can be supplied, so
there is no gap for the approved action and the performed action to differ.

`[FACT]` 121/121, `provider_writes = 1`, the approved target restarted, the
bystander untouched, identity/image/replicas unchanged, a new pod identity, and
zero mutations across 38 negative cases — measured by cluster generation, not by
return values.

## Decision 5 — A refusal is reported as a refusal `[DECISION]`

`[FACT]` Found by the negative matrix: the writer returns a governed refusal as
an *outcome* (`succeeded=False`), not an exception, and the endpoint initially
answered **HTTP 200** for a correctly-refused action. Zero cluster writes, and
still indistinguishable from success to any client trusting the status code.
The endpoint now inspects `succeeded` and answers 409.

## Decision 6 — `consumed_by_execution` records; it does not guard `[DECISION]`

`[FACT]` Two runs of this harness produced two different replay outcomes: one a
second cluster mutation, one a 409. Both are recorded.

`[DECISION]` The field makes a second use **visible to an auditor** and is
deliberately not a guard. A store inventing exactly-once would be overriding a
platform contract it does not own. **At-least-once remains the contract, and
exactly-once is never claimed.**

## Decision 7 — Two operations, kept separate `[DECISION]`

`[FACT]` `ApprovalFacts.is_valid_for` compares its `operation` against
`request.operation.value` — the **authorization verb** (`invoke`), not the
provider operation. Storing one value for both looked tidier and made every
legitimate approval invalid. The table now carries `operation` and
`authorization_operation` separately, and the check that stops an approval to
READ authorizing a DELETE works because it compares like with like.

## Decision 8 — One new fitness rule, because a real bypass was uncovered `[DECISION]`

`[FACT]` No existing rule names `backend/api/product`, which did not exist when
they were written. A product module could have imported the gateway, dispatcher,
an adapter, the transport broker or the credential broker and dispatched around
authorization while every rule passed.

`BND-PRODUCT-CANNOT-BYPASS-EXECUTION` forbids exactly that. `[FACT]`
Sensitivity-tested: injecting a transport-broker import into a product route
turned the gate FAIL; removing it returned PASS. The approval **store** is
deliberately not forbidden — storing approvals is not executing.

## What this ADR does NOT decide

- No autonomy control anywhere. No route, model, hook or component can set,
  promote or unlock a level.
- No second executor, approval authority, truth store or verification logic.
- No RAG. No exactly-once. No SLA. No accessibility certification.
- No new commissioned capability: the product proposes a remediation only where
  one already exists, and says so otherwise.

## Status of the invariants

`[FACT]` Architecture gate PASS (36 passed, 0 failed, 6 skipped, 1192 modules).
Regression 2974 passed, 0 failed. Frontend 79/79. Revocation VERIFIED against
real Redis, fail-closed. 38 negative cases, 0 cluster mutations. Exactly one
real provider write. No secret in the approval record. One new table, no
migration framework change, no new authority.
