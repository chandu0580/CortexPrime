# ADR-053 — Audit Writer Ownership and Retention/Export Boundaries

**Status:** Accepted, with one gap recorded as **DEFERRED**
**Date:** 2026-08-09
**Phase:** 5.10
**Relates to:** ADR-052 (durable audit), ADR-045 (leadership/fencing)
**Does not complete:** Phase 5.5, still blocked on `credential_unavailable`.

---

## Audit writer ownership — DEFERRED, and why

Phase 5.9 proved `JsonlAuditStore` is single-writer by behaviour with no
cross-process enforcement. Phase 5.10 asked the prior question: **who is
architecturally allowed to write the chain?**

The answer, derived rather than chosen: **nobody is designated.** Option D — the
architecture defines no audit-writer ownership model at all.

Evidence:

* `LeadershipRole` names `RECOVERY_SWEEP`, `OUTBOX_PUBLISHER` and `SCHEDULER`.
  **There is no audit role.**
* `JsonlAuditStore` has no cross-process lock (`fcntl`, `msvcrt`, `flock`,
  `portalocker` all absent) and no concept of owner, writer identity, lease or
  fence.
* `AuditRuntime.__init__` takes **no writer identity** — no `instance_id`, no
  `owner`.
* The runtime is constructed ad hoc wherever audit is needed, rather than owned
  by one component.

Re-demonstrated: two processes appended 20 records each, **both believed they
succeeded, neither was refused**, and the resulting chain carries
`broken_link`, `missing_record`, `orphan_origin` and `out_of_order` defects. The
damage is only visible afterwards, on verification.

### Why no lock was added

Closing this requires one of:

1. a new `LeadershipRole.AUDIT_WRITER` — a new coordination contract;
2. OS-level file locking — a new mechanism with its own crash semantics;
3. a PostgreSQL advisory lock — a real coordination decision with session or
   transaction scope, not an implementation detail;
4. routing all audit writes through an existing single-writer component — but
   none is designated, so this is also a new contract.

Every option is an architectural decision. This phase was explicitly forbidden
from inventing one silently, so the gap is **recorded, not closed**.

### Consequently unanswerable

Startup admission, second-writer refusal, graceful release, crash takeover and
stale-writer fencing are all **unanswerable today** — there is no ownership,
lease or fence for an audit writer to hold, lose or present. Reported as skips
rather than invented behaviour.

**Recommendation for the owner:** the closest existing fit is
`LeadershipRole.AUDIT_WRITER` over `SqlLeadershipStore`, which would inherit
fenced handover, crash expiry and successor acquisition already proven in
ADR-045 and ADR-050. That is a Phase 5.11 decision and needs its own ADR.

## Retention — VERIFIED

`plan_retention` **plans and does not mutate**: *"Producing a plan an operator
reviews before archiving is the difference between retention and data loss."*
There is no `apply_retention`, `delete_records` or `purge` anywhere in the
module — retention cannot destroy the chain because it never deletes.

Retirable records must form a **contiguous prefix**; otherwise archiving would
leave a hole and the chain could not be verified across the gap. The plan
reports `retain_from_sequence` — the explicit archive boundary — plus `safe` and
a `reason`.

`AgeBasedRetention` carries a separate `security_retain_days` floor (~7 years)
so security events cannot be aged out on an ordinary retention clock.
`KeepForever` is the conservative default.

Verified against a chain written by a process that then died: the recovered
chain verifies, `KeepForever` retires nothing, a 30-day policy retires nothing
from a chain written today, and planning as though 400 days later reports a
boundary **without applying it**. Nothing on disk changed, and the chain still
verifies afterwards.

## Export — VERIFIED

`export_chain` emits a manifest line followed by one line per record. The
manifest carries `record_count`, `first_sequence`, `last_sequence` and
`head_digest` — the value worth publishing where the platform cannot reach it.

Verified: the manifest head equals the live head; ordering is stable and
contiguous; `previous_digest` links survive; `verify_export` verifies the
exported chain independently; and **exporting does not mutate the live chain**.

### Export after recovery

Process A wrote 40 records and died. Process B recovered a head byte-identical
to A's, exported it, and the **exported head equals the recovered head**. The
export verifies, and the live chain was unchanged.

### Export tamper

Every mutation of an exported chain fails `verify_export`: altered payload,
altered `previous_digest`, altered `entry_digest`, altered `sequence`, reordered
records, deleted record. Nothing is repaired. The authoritative export still
verifies afterwards.

## Tenant isolation and secrets — VERIFIED

A scoped export contains only the selected tenant's records and the other
tenant's identifier does not appear anywhere in it. No credential value, no
`bearer `, no `ghp_`, no `CredentialMaterial`, no `"authorization":` header key,
no `x-api-key`, no `private_key`. The only sensitive-sounding fields are
`authorization_digest` and `authorization_effect` — a digest and a policy
effect, checked narrowly to avoid the Phase 5.8 false positive.

## Replay and audit failure semantics — unchanged

Replay wrote zero audit records and left every counter at zero. An audit
storage failure (`OSError`, "no space left on the audit volume") left a
cross-tenant refusal as `tenant_mismatch`, minted no credential, and never
leaked its own error out of the gate.

## Guarantees

**Guaranteed.** Retention plans and never deletes. An archive boundary is
explicit and contiguous. Exports are complete, ordered, independently
verifiable, tenant-scoped and secret-free. Export mutates nothing. Tampered
exports fail verification. Audit failure changes no governed outcome.

**Not guaranteed.** Single-writer enforcement — the store is single-writer by
behaviour with nothing preventing a second writer. Power-loss durability.
Exactly-once audit.

## What remains unverified

* **Real provider execution** — Phase 5.5, `credential_unavailable`.
* **Audit writer ownership** — DEFERRED, as above.
* **Retention actually applied.** No apply path exists, so archiving a prefix
  and verifying the remainder from a non-zero origin was not exercised
  end to end.
* **Power-loss durability.**
