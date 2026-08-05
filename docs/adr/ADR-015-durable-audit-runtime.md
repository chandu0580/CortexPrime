# ADR-015 — Durable Audit Runtime

- **Status:** Accepted
- **Date:** 2026-08-04
- **Phase:** 1 (PR-06)
- **Related:** ADR-010 (contracts), ADR-011 (hashing), ADR-013/014 (approval integrity)

## Context

PR-04 introduced an audit trail for approval-integrity decisions and recorded
its own limits: entries lived in an in-process ring capped at 1000, durability
depended on the log aggregator, and a restart lost the chain. PR-05 added more
decisions to record without changing that.

The trail had become the weakest link in an otherwise strong chain. An attacker
who could no longer forge an approval could still lose the record of having
tried — and the PR-04 chain check could not detect a *deleted* entry at all,
because deleting one leaves the survivors internally consistent.

Compliance evidence has to survive the process that produced it.

## Decision

Build `backend/platform/audit` as the single source of truth for
security-critical decisions, and migrate the existing sink onto it.

### Storage is abstract, deliberately

`AuditStore` is a Protocol with five operations: `append`, `read_all`, `query`,
`last`, `count`. There is **no update and no delete** — not as a convention but
because the operations do not exist to call. A store that cannot express
mutation cannot be mutated by mistake.

Two implementations ship: `InMemoryAuditStore` for tests, `JsonlAuditStore` for
durability. PostgreSQL arrives in PR-11 behind the same interface, which is the
entire reason the interface exists.

### JSONL, and why it is not the repository's JSON anti-pattern

The Phase 1 review names file-based state as an anti-pattern — correctly, for
*mutable* state, where every write rewrites the whole document and a crash
mid-write loses everything. That is the shape that caused the event-loop
outage.

Append-only JSONL is a different shape. One record is one line, appended and
fsynced, never revisited. A torn write damages at most the final line, and chain
verification detects that rather than silently accepting it. A test asserts the
file only ever grows: `test_file_is_append_only_on_disk`.

It is still an interim. PostgreSQL gives transactional guarantees a file does
not.

### Three defect classes, because they are genuinely different

| Defect | Meaning | Detected by |
|---|---|---|
| **Tampered** | A record was edited in place | Recomputed digest ≠ stored digest |
| **Broken link** | Records reordered or substituted | `previous_digest` ≠ predecessor's digest |
| **Missing** | A record was deleted | Sequence numbers skip |

The third is the one PR-04 could not see. Deleting a record from the middle
leaves every surviving link intact; the gap in sequence numbers is the only
trace. `verify_chain` checks sequence contiguity for exactly this reason.

Verification continues past the first defect rather than stopping, because an
operator investigating tampering needs the full extent of the damage.

### Recovery resumes rather than restarts

On construction the runtime reads the chain head from the store and continues
from `last.sequence + 1`. Starting a fresh chain at zero would leave two chains
in one store — verifiable as neither — and quietly discard prior evidence.

A corrupted store raises `AuditCorruptionError` at construction, naming the
damaged line, rather than starting over.

### Retention is archive-then-truncate, never delete-in-place

Retention and tamper-evidence are in genuine tension. Deleting from the middle
of a chain breaks it, and is indistinguishable to a verifier from an attacker
removing evidence — which is the whole point of chaining.

So `plan_retention` produces a **plan an operator reviews**, never a mutation,
and refuses outright when the retirable records are not a contiguous prefix:

> archiving them would leave a hole in the chain, which is indistinguishable
> from tampering

A truncated *prefix* still verifies when the verifier is told it is a slice
(`expect_origin=False`). Security-relevant kinds get a longer minimum retention
(default ~7 years), because they are exactly the records a dispute turns on.

The default policy is `KeepForever`. Nothing is ever deleted automatically.

### Export carries a manifest

`export_chain` emits the chain preceded by a manifest with the head digest,
record count, and sequence range. Publishing the head digest somewhere the
platform cannot reach — a ticket, an email, an external notary — converts
"tamper-evident to whoever holds the file" into "tamper-evident, full stop",
because a rewritten chain can no longer reproduce a head witnessed elsewhere.

`verify_export` checks the manifest against the records that follow, so an
export whose manifest was edited to hide a deletion is caught.

### Contracts extended, not duplicated

`AuditEvent` already carried 8 of the 11 required fields. Rather than create a
second record type, three optional fields were added: `correlation_id`,
`causation_id`, `payload_digest`. Four enum members were added for the newly
required categories.

Both are additive and non-breaking per ADR-010, so no version bump. A test
asserts PR-05-era entries still decode.

`payload_digest` is distinct from `entry_digest`: the former identifies the
*subject* (the approved artifact), the latter covers the *audit entry itself*.
Conflating them would make it impossible to tie a record to the thing it
describes without trusting the detail bag.

## Alternatives Considered

**Write directly to PostgreSQL now.** The eventual target. Rejected for this PR:
the pending-action and decision stores are still files, so an audit table alone
would leave the security-critical state split across two persistence models
mid-migration. PR-11 moves all three together, and the interface makes that a
substitution.

**Keep the in-memory ring and rely on log aggregation.** Rejected: log
durability is an operational property of someone else's system, aggregators
sample and expire, and a chain reassembled from log lines cannot be verified
because ordering is not guaranteed.

**Delete `IntegrityAuditLog` and update the five call sites.** Rejected per the
standing instruction to prefer incremental migration. Keeping it as a thin
façade makes this a substitution reviewable in isolation. New code uses
`AuditRuntime` directly.

**Sign each record as well as chaining it.** Stronger — chaining detects
editing, signing detects wholesale rewriting. Deferred: it needs the key
management ADR-014 also deferred, and the exported head digest achieves much of
the same at zero key-management cost.

## Security Analysis

**Closed**

- Records survive process restart, and the chain continues rather than forking.
- Deleted records are now detectable (sequence gaps).
- The 1000-entry silent truncation is gone; `entries()` reads durable storage.
- Corruption fails loudly at a named line rather than silently starting over.
- Retention cannot create an unverifiable hole.
- Export is independently verifiable, manifest included.

**Not closed, stated explicitly**

*Wholesale chain rewriting.* An attacker with write access to the file and the
ability to recompute every digest can produce a valid-looking chain. Chaining
detects *edits*, not rewriting. Mitigation is publishing the head digest
externally — supported by `export_chain`, but an operational practice this PR
cannot enforce.

*No transactional guarantee.* A crash between the executed action and its audit
write leaves an unaudited action. A file cannot close this; PR-11 can.

*The system tenant placeholder remains.* Records from the legacy dispatch path
carry `tenant_id="system"` because that path has no tenant context. Visible by
design; PR-09 threads real identity through.

## Migration Strategy

**Backward compatible.** `IntegrityAuditLog` keeps its full interface —
`record_refusal`, `record_verified_dispatch`, `entries`, `verify_chain`,
`clear`. All five dispatcher call sites are unchanged.

Behavioral differences, all improvements:

| Before | After |
|---|---|
| In-memory, capped at 1000 | Durable, uncapped |
| Lost on restart | Resumes the chain |
| Could not detect deletions | Detects deletions |
| `clear()` wiped the chain | `clear()` swaps to a fresh in-memory runtime; durable records are never deleted |

No data migration is needed: there was no durable prior state. The first write
creates `backend/data/integrity_audit.jsonl` at sequence 0.

If the durable store cannot be opened, the runtime falls back to in-memory and
**logs an error**. Refusing to boot over an audit path would take the platform
down; running silently unaudited would be worse. A visible degraded mode is the
least-bad third option.

## Rollback Strategy

`git revert` restores the in-process ring. The durable file is left behind,
harmless and still verifiable with the exported tooling.

Reverting loses durability but no evidence already written — the JSONL file
remains readable and chain-verifiable by any build containing this code.

## Remaining Risks

1. **Wholesale rewriting** — mitigated by publishing the head digest externally.
2. **No transactionality** — PR-11.
3. **fsync per record** costs latency on the audit path. Correct trade: an audit
   record lost in a crash was never written.
4. **Single file, unbounded growth** — retention planning exists; execution is
   an operator action, deliberately.

## Compliance

Invariant **I3** — append-only and independently verifiable — is now satisfied
for the integrity trail: durable, chained, gap-detecting, exportable. The
invariant test can move from `xfail` to live in PR-08.
