# ADR-055 — Fenced Audit Storage

**Status:** Accepted
**Date:** 2026-08-10
**Phase:** 5.12
**Relates to:** ADR-054 (the stated limitation this closes), ADR-053 (ownership and retention), ADR-052 (durable audit storage), ADR-050 (leadership and fencing), ADR-044 (durable state foundation), ADR-015 (audit runtime)
**Does not complete:** Phase 5.5, still blocked on `credential_unavailable`.

---

## The Phase 5.11 limitation, restated exactly

ADR-054 gave the audit writer *admission* through the existing leadership model
and refused to call it fencing:

> `fenced_where` works because the token check and the mutation are *one SQL
> statement* — there is no window between them. A filesystem append cannot join
> that predicate.

So a runtime that held `AUDIT_WRITER`, lost it (lease lapse, partition, stall),
and still appended got its write into the JSONL file. Phase 5.11 recorded that
as **NOT VERIFIED and not claimed**, and named the fix as a storage decision:
move the chain tail somewhere the fence can reach.

## Why JSONL cannot provide physical stale-writer fencing

The refusal has to live *inside* the write. For a file, the ownership check and
the `open(...).write(...)` are irreducibly two steps — the exact stale-check
race the SQL fence eliminates elsewhere. Every way to close it on a filesystem
is a second coordination system: `FileLock`, `fcntl`/`msvcrt`, `portalocker`, a
lock server. All were considered and rejected — OS file locks are advisory,
platform-divergent, and above all they would be a *second* election beside the
one the platform already trusts. PostgreSQL advisory locks fail the same test:
application-defined coordination, not an enforcement boundary.

## Storage options considered

| Option | Verdict |
|---|---|
| **A. JSONL + stale-writer safety** | Impossible without a second coordination system. Rejected. |
| **B. PostgreSQL through the existing `DurableStore`** | The fence, the transaction boundary, and the migration discipline already exist. **Chosen.** |
| **C. Another existing mechanism** | The only other durable stores are the same PostgreSQL behind other repositories. Nothing else qualifies. |
| **D. A new storage technology** | Forbidden by the phase directive and unnecessary. Rejected. |

## The decision

Two tables in the existing durable schema (migration `0013`, additive):

    cp_audit_chain      chain_id (PK) · next_sequence · head_digest
    cp_audit_record     chain_id + sequence (PK) · event_id (unique) ·
                        tenant_id · kind · recorded_at · subject_reference ·
                        correlation_id · actor_id · entry_digest ·
                        previous_digest · writer_token · document (JSONB)

and one store — `backend.database.durable.audit.SqlAuditStore` — implementing
the **existing** `AuditStore` protocol (append, read_all, query, last, count;
no update, no delete). `AuditRuntime` is unchanged: same digest computation,
same recovery, same ownership port. The composition root chooses the store; no
consumer knows which one is behind the port.

### Ownership model

Unchanged from ADR-054. `LeadershipRole.AUDIT_WRITER` on `SqlLeadershipStore`
designates the admitted writer; `AuditRuntime`'s ownership port refuses an
unadmitted runtime before any write. One adapter —
`AuditWriterLeadership` in the composition root, the same three-line shape as
`SchedulerLeadership` — answers both the runtime's admission port and the
store's fence, so both always speak of one handle. Ownership remains
process-level, never per-tenant.

### Fencing model and append atomicity

The append is one `DurableStore.atomic()` transaction, three statements, fixed
order:

    1. UPDATE cp_leadership SET heartbeat_at = :now
       WHERE <SqlLeadershipStore.fenced_where(handle)>
    2. UPDATE cp_audit_chain SET next_sequence = :seq + 1, head_digest = :digest
       WHERE chain_id = :chain AND next_sequence = :seq
         AND head_digest extends this record's previous_digest
    3. INSERT INTO cp_audit_record (...)

Statement 1 is the fence **as a mutation**, on the very row a successor's
acquisition mutates, carrying the token in its predicate. There is no
`SELECT`-compare-`INSERT`: if a successor holds token N+1, statement 1 matches
zero rows, `StaleAuditWriter` is raised, and the transaction — including the
INSERT that would have carried the record — rolls back. If acquisition and
append race, the database serializes them on the leadership row's lock: either
the append commits strictly before the acquisition, or the acquisition commits
first and the append's predicate re-evaluates against the new token and
matches nothing. "A wrote after B took the role" is not an ordering the
database will produce.

Statement 2 is a second, independent invariant: the tail advances only from the
exact sequence and head this record extends. Two writers cannot both advance
`next_sequence` past one value, so the chain physically cannot fork — the
Phase 5.10 corruption became an unwritable state. Zero rows anywhere is
refusal; nothing retries, reacquires, or advances a token.

`fenced_where` deliberately carries no expiry predicate (same as every fenced
write since ADR-050): authority ends at **supersession**, not at wall-clock
lease expiry. An expired-but-not-superseded writer can still append; until a
successor acquires, there is exactly one tail and no interleaving is possible.

### Chain schema, digests, sequence semantics

Digest computation did not move and was not duplicated: `AuditRuntime` computes
`entry_digest` over the canonical body exactly as before, and the store
persists the record it is given. The stored `document` is
`AuditEvent.to_dict()`; restoration is `AuditEvent.from_dict` with digests
**restored, never recomputed** — recomputation is what `verify_chain` does,
deliberately. JSONB physically reorders object keys (length-then-bytewise;
verified: neither insertion nor alphabetical order survives), and no digest
cares, because canonical hashing serializes with sorted keys before hashing.
Verified with non-ASCII text, floats, 2^63−1, nested objects: values
round-trip exactly and every digest recomputes.

`writer_token` on each record is evidence of which fence wrote it — evidence,
not enforcement; the enforcement is the transaction.

### Crash, stale writer, successor, concurrent writers — evidence

Real OS processes, real PostgreSQL 16, `cortex_p512` created blank and migrated
`0001 → 0013` by Alembic only. 84 checks, 0 failed, 0 skipped.

| Scenario | Result |
|---|---|
| First writer | acquires token N, writes 10; tail row advances in step |
| Second process while held | refused; wrote 0 |
| **Stale writer (§9)** | A held N, successor took N+1 while A's belief was frozen; A's append **raised `StaleAuditWriter` from the storage transaction; zero rows from A after N+1 exists** |
| **Race (§10)** | A's ownership check returned *true*, successor acquired, A appended on the checked handle without re-checking — still refused; the check-then-write gap cannot matter because the fence is in the write |
| Graceful handover | release → successor acquires, token advances, sequence contiguous, links verified, durable head equals verified head |
| Crash | claim survives (crash ≠ release); successor refused while the lease lives; after lapse, acquires and writes; chain verifies with no repair |
| Three-way race | exactly one admitted, exactly one wrote, refused wrote zero, chain verifies with no defects |

### Export, retention, tenant isolation

Export runs through the existing `export_chain`/`verify_export` over the
unchanged port — no second exporter. Verified: live head == recovered head ==
exported head; export mutates neither the count nor the tail; a tenant-scoped
export contains no other tenant's records. One process-level writer safely
recorded multiple tenants. Retention remains **plan-only** (ADR-053):
`plan_retention` reasons over the SQL store, `KeepForever` retires nothing, and
the store exposes no update or delete to implement anything more.

### Secret safety

Field-aware, over the full export including gateway invocation records: the
only sensitive-sounding fields are `authorization_digest`,
`authorization_effect`, `credential_ref` (`cred://…`, a reference),
`credential_type`, `credential_scope` (operation names), a hex
`credential_fingerprint`, and `credential_expires_at`. No credential material,
no `bearer `, no `ghp_`, no API key, no private key, no Authorization header
value anywhere.

### Failure semantics and replay

`StaleAuditWriter` subclasses `AuditWriterNotOwned`: an observation failure,
deliberately not an authorization type. Verified in the live gateway: with the
audit port raising `StaleAuditWriter` mid-invocation, a cross-tenant call still
refused with `tenant_mismatch`, no credential was minted, and the audit error
never became the outcome — Phase 5.8 semantics intact. Replay performed zero
side effects, wrote zero audit records, migrated no chain, and never acquired
`AUDIT_WRITER` (token compared before and after).

## JSONL disposition

`JsonlAuditStore` remains: development store, export format, offline archive.
Its guarantee is now documented in its own module, exactly: **single-writer
admission only** — never fenced, and never to be described as fenced.

## Guarantees

**Guaranteed.** A writer with fence token N cannot commit an audit record after
a successor holds N+1 — enforced by the storage transaction, not by a check.
The chain cannot fork or skip even under misconfigured leadership, because the
tail advance is conditional on sequence and head. One admitted writer at a
time; crash leaves the claim held until the lease lapses; a successor then
continues the same chain with no repair. Audit failure never changes a
governed outcome. Replay acquires nothing and writes nothing.

**Not guaranteed.** Exactly-once audit is neither introduced nor claimed — a
commit whose acknowledgement is lost (`UnknownCommitOutcome`) still requires
the caller to reconcile by reading the chain. Fencing at wall-clock lease
expiry (authority ends at supersession, as everywhere else). JSONL appends
remain unfenced. Power-loss durability beyond PostgreSQL's own WAL guarantees.
Behaviour under PostgreSQL replication failover was not tested.

## Phase 5.13 boundary

Applied retention (ADR-053 remains plan-only), wiring the production
composition (`main.py`) onto the fenced store as the default deployment, and
the Phase 5.5 blocker (`credential_unavailable`) — which this phase does not
touch — are the open candidates.
