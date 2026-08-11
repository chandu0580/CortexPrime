# ADR-056 — Production Durable Audit and Retention

**Status:** Accepted
**Date:** 2026-08-10
**Phase:** 5.13
**Relates to:** ADR-055 (the fenced store this activates), ADR-054 (ownership), ADR-053 (retention semantics), ADR-050 (leadership), ADR-044 (durable state)
**Does not complete:** Phase 5.5, still blocked on `credential_unavailable`.

---

## What production composed before this phase

Verified, not assumed:

* The governed path's builder, `build_production_connectivity`, took
  `audit: Optional[Any] = None` — and **nothing in the repository supplied
  one**. A production assembly of the invocation gateway would have run
  unaudited by default.
* The only production JSONL audit was the legacy V1 facade
  (`enterprise_integrity_audit.integrity_audit`), used by the approval
  dispatcher — with a **silent in-memory fallback** when the file cannot open.
  It is not on the governed invocation path (verified structurally: nothing
  under `backend/contexts/` or `backend/api/` imports it).
* `main.py` composes neither durable persistence nor the governed gateway;
  the 5.x production line is assembled from `build_durable_persistence` and
  `build_production_connectivity`.

## The decision: the fenced chain is the production authority

Two composition changes, both structural rather than procedural:

**1. `DurablePersistence` owns THE audit.** Constructing the durable root now
constructs `audit_writer` (an `AuditWriterLeadership` over the *same*
`SqlLeadershipStore` every other singleton uses) and `audit` (an
`AuditRuntime` over `SqlAuditStore`, fenced by that same adapter — one object
answers the runtime's admission port and the store's fence, so the two can
never disagree about a handle). There is **no JSONL and no in-memory branch in
this constructor**: a process that cannot reach a migrated PostgreSQL never
obtains a `DurablePersistence`, and therefore never obtains a production audit
runtime at all. Fail-closed is a property of the object graph, not a check.

**2. `build_production_connectivity` refuses `audit=None`.** The governed
gateway cannot be assembled without its evidence sink. A production deployment
passes `persistence.audit`; there is nothing else to pass.

The builder also gained a `connectors` seam — additional providers register
through the exact seams the GitHub connector uses (directory registration,
adapter preflight, shared input validator). One path, more providers; it is how
the controlled provider stood in for GitHub in this phase's evidence without
touching the GitHub credential.

### Startup behaviour

`build_durable_persistence` → `build_durable_store` → `verify_durability`
refuses a blank or partial schema (`DurabilityUnavailable`), creates nothing
(`create_schema` is unexpressible in a production config — the constructor
refuses it), and has no fallback of any kind. Verified against a real blank
database: the boot refused and the database still contained zero tables.
Schema arrives by Alembic only (`0013` is head).

### Ownership and acquisition

`LeadershipRole.AUDIT_WRITER`, unchanged. The adapter is constructed
**unacquired**; taking the role is an explicit startup act
(`persistence.audit_writer.acquire()`), never a side effect of composing or of
appending. On a multi-process fleet exactly one process holds the role; the
others' observation attempts refuse (`AuditWriterNotOwned`) and are contained
by the gateway — including boot-time registration events on non-writer
processes, which therefore go unrecorded on those processes. That is the
ADR-054 single-writer model, stated rather than hidden.

### Audit failure semantics

Phase 5.8 preserved and re-verified in the production graph: with the audit
sink raising `StaleAuditWriter` mid-invocation, a cross-tenant call still
refused `tenant_mismatch`, no credential was minted, and no provider was
called. Audit remains best-effort observation; it grants nothing and denies
nothing.

### Refusal auditing

Every gateway refusal is recorded as `execution_refused` with its code.
Verified end-to-end on PostgreSQL: `tenant_mismatch`, `input_invalid`,
`binding_expired`, `operation_mismatch`, `lease_invalid` — five refusals, five
records, provider called zero times. An *undeclared* operation is refused one
layer earlier: worker selection cannot build a request for it, so the
dispatcher refuses before the gateway is reached.

### Unknown commit outcome

Not exactly-once, and not claimed. What holds, verified on the production
store:

* A writer whose commit outcome was unknown **cannot blindly duplicate**: its
  in-memory tail is stale, so a retry of the same record fails the chain-tail
  predicate and writes nothing. `event_id` is additionally unique in the
  store.
* The chain **reconciles from durable state**: a recovering runtime (restart,
  or a fresh `AuditRuntime` over the same store) finds the landed record at
  the tail and continues the chain from it.
* In-process automatic reconciliation is deliberately absent — after an
  unknown outcome the writer's next appends refuse until it re-reads the
  durable head. Detection is loud, resolution is recovery, duplication is
  impossible.

A real connection loss during COMMIT was **not** induced; the SQLSTATE
classification (`40003`, `08007` → `UnknownCommitOutcome`) and the
post-unknown-outcome states above are what was verified.

### Replay

Inert in the production graph: zero side effects, zero audit records, zero
leadership acquisitions (audit-writer and scheduler tokens compared before and
after).

### Multi-process evidence

Real OS processes, each booting through `build_durable_persistence` +
`build_production_connectivity` against `cortex_p513` (blank → Alembic 0013):
one writer admitted and writing; a second refused with zero records; a stale
ex-owner (belief frozen after supersession) refused **by the storage
transaction** (`StaleAuditWriter`, zero rows); crash leaves the claim held
until lease lapse; the successor then continues the same chain with no repair;
three-way contention admits exactly one. Concurrent load: one process
appending steadily while another exported (every export verified — reads are
coherent snapshots) and a third ran retention planning (every plan safe).

### JSONL disposition

Unchanged from ADR-055: development store, export format, offline archive —
single-writer admission only, never fenced, never the production authority.
The legacy `integrity_audit` facade remains a V1 approval-path subsystem, off
the governed path, with its in-memory fallback noted as a V1 limitation slated
for consolidation (PR-11 lineage), not silently promoted to authority.

## Retention: the explicit decision

**Retention remains PLAN-ONLY.** The options were evaluated against the real
chain:

* **A. Keep forever** — the default (`KeepForever`), and the operative policy.
* **B. Archive a contiguous prefix** — the architecture's sanctioned shape
  (ADR-053: archive-then-truncate from the front, never delete-in-place). The
  *non-destructive* half is verified working against PostgreSQL: a contiguous
  prefix exports with its manifest head, and the remainder verifies as a slice
  (`expect_origin=False`), its provenance being the archived manifest.
* **C. Delete a prefix with a continuation origin** — requires an apply path,
  approval gating, and a continuation-origin representation. No current policy
  demands deletion; building a deletion capability ahead of the policy that
  governs it fails §17's safety bar by construction.
* **D. A new archival chain** — rejected; nothing requires it.

Why plan-only is the *correct* result and not a deferral of convenience:

* `plan_retention` **refuses holes**: an age policy whose security floor
  retains refusals interleaved mid-chain yields `safe=False` ("would leave a
  hole… indistinguishable from tampering") rather than a plan. Verified on the
  real chain.
* The store has **no delete and no update to call**, and the retention module
  contains no apply function — the plan cannot be executed by accident.
* **Tenant retention is structurally forbidden**: the chain is process-level;
  a single tenant's records are non-contiguous in it, so per-tenant deletion
  would hole the global chain. Tenant data leaves through tenant-scoped
  export, which excludes other tenants and mutates nothing — verified.
* Export semantics are unchanged by planning: live head == exported head, row
  count unchanged, `verify_export` truthful.

When a compliance policy actually requires deletion, the apply path is its own
ADR: plan → approval evidence → archive with externally published head →
truncate → verify remainder as a slice. None of that was built here, on
purpose.

## Secret safety

Field-aware over SQL rows, full exports, refusal records, and retention plan
metadata: only references (`cred://…`), digests, effects, operation names, and
timestamps. No credential material, bearer token, API key, private key, or
Authorization value anywhere. `GITHUB_TOKEN` was neither read nor modified;
GitHub was never contacted.

## Guarantees

Everything ADR-055 guarantees, now composed by default in production: exactly
one authoritative audit sink; fail-closed startup; fenced appends; refusals
and successes audited; replay inert; no blind duplication after an unknown
commit; retention cannot execute and cannot hole the chain.

**Not guaranteed.** Exactly-once audit. Automatic in-process recovery after an
unknown commit outcome (restart-or-reread is the contract). Audit records from
non-writer processes in a fleet (single-writer observation, by design).
Fencing at wall-clock lease expiry (authority ends at supersession). The
legacy V1 approval facade's durability (its fallback is a stated V1
limitation). Behaviour under PostgreSQL replication failover.

## Phase 5.14 boundary

Candidates: consolidating the legacy `integrity_audit` facade onto the durable
authority (the PR-11 lineage); wiring `main.py`'s V1 application onto the 5.x
composition roots; an approval-gated retention apply path if and when a policy
requires deletion; and the standing Phase 5.5 blocker
(`credential_unavailable`), untouched by this phase.
