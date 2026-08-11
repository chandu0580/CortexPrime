# ADR-054 — Governed Audit Writer Ownership

**Status:** Accepted, with one limitation stated explicitly
**Date:** 2026-08-09
**Phase:** 5.11
**Relates to:** ADR-053 (the deferred gap), ADR-050 (leadership/fencing), ADR-052
**Does not complete:** Phase 5.5, still blocked on `credential_unavailable`.

---

## Why ownership was previously undefined

ADR-053 established that the architecture designated nobody as the audit writer:
`LeadershipRole` had no audit role, `JsonlAuditStore` had no owner or lease,
`AuditRuntime` took no writer identity, and the runtime was constructed ad hoc.
Two real processes appending concurrently produced a chain with `broken_link`,
`missing_record`, `orphan_origin` and `out_of_order` defects — and **neither was
refused**.

That gap is now closed for the ordinary case, using the mechanism the platform
already has.

## The decision: a role, not a new mechanism

`LeadershipRole.AUDIT_WRITER` joins the existing closed list. A hash chain has
exactly one tail, so appending is a genuine singleton responsibility — the same
argument that put `RECOVERY_SWEEP` and `OUTBOX_PUBLISHER` there.

**Nothing else was built.** No `FileLock`, no `fcntl`/`msvcrt`/`portalocker`, no
PostgreSQL advisory lock, no second election, no second lease table, no new
audit framework. `AuditRuntime` gained one optional `ownership` port, consulted
before every append; `None` means unowned, which is the single-writer deployment
and the pre-existing behaviour.

**No migration was required.** Leadership rows are created per role on demand,
so a new role needs no schema change. The database remains at `0012`.

### Identity, and where it may not come from

Ownership comes from `SqlLeadershipStore` — a durable row, an instance id and a
monotonic fencing token. The runtime never infers ownership from a process id, a
hostname, a timestamp, the existence of a file, an environment variable, or
"I started first". Verified structurally: no `getpid`, no `gethostname`, no
`os.path.exists` in the runtime.

### Failure semantics

`AuditWriterNotOwned` is its own exception type and deliberately **not** a
subclass of anything that reads as an authorization outcome. A runtime that is
not the writer has failed to *observe*; it has not decided that anything was
impermissible. Verified: with a sink raising `AuditWriterNotOwned`, a
cross-tenant invocation still refused with `tenant_mismatch`, no credential was
minted, and the ownership error never escaped the gate.

## Fencing strength — the limitation, stated plainly

**This is admission, not fencing.**

`fenced_where` works because the token check and the mutation are *one SQL
statement* — there is no window between them. A filesystem append cannot join
that predicate. The ownership check and the `open(...).write(...)` are therefore
two separate steps, which is precisely the stale-check race that the SQL fence
exists to eliminate.

Against the four outcomes the directive named for a stale writer:

* **not (A)** — nothing physically prevents a stale runtime's append;
* **not (B)** — an append that happens is in the file, not rejected afterwards;
* **not (C)** — a stale runtime still holds its store handle;
* **(D)** — the architecture cannot fence a filesystem append.

**What this closes:** a second process that never held the role is refused
before it touches the file. That is the case Phase 5.10 demonstrated corrupting
the chain, and it is now demonstrably prevented.

**What it does not close:** a runtime that held the role, lost it (lease lapse,
partition, stall) and still appends. Its write lands. This is recorded as
**NOT VERIFIED and not claimed** rather than glossed.

Closing it would need the audit tail in a fenceable store — the chain in
PostgreSQL under `fenced_where`, or a store whose append can carry the token.
That is a Phase 5.12 decision with its own ADR, not an improvisation here.

## Evidence

Real OS processes, real PostgreSQL 16 (`cortex_p511`, blank → Alembic `0012`).

| | Result |
|---|---|
| First process acquires and writes | 10 records, chain verifies |
| Second process while first holds | **refused; wrote 0** |
| Graceful release → successor | acquires, token advances, chain valid |
| Crash holding the role | claim survives; successor refused while lease is live |
| After lease lapse | successor acquires and writes; chain verifies |
| Three processes racing | **exactly one admitted, exactly one wrote, chain verifies with no defects** |

The last row is the Phase 5.10 gap closed: previously two processes each wrote
20 records and corrupted the chain; now the refused processes write zero.

## Tenant, secrets, replay, export, retention

Ownership is **process-level, not per-tenant** — one writer safely recorded
multiple tenants while reads stayed scoped, and a scoped export excludes the
other tenant. No new tenant model.

No credential value, `bearer `, `ghp_`, `CredentialMaterial`, `"authorization":`,
`x-api-key` or `private_key` in the export; only `authorization_digest` and
`authorization_effect`.

Replay performed zero side effects, wrote zero audit records, and **never
acquired the AUDIT_WRITER role** — verified by comparing the fencing token
before and after. Export head equals recovered head and mutates no live state.
Retention planning still reports correctly under ownership.

## Guarantees

**Guaranteed.** One admitted audit writer at a time, durably recorded, with a
monotonic token. A process that never held the role cannot append. Crash leaves
the claim held until the lease lapses; a successor then acquires without repair.
Ownership refusal never changes a governed outcome. Replay acquires nothing.

**Not guaranteed.** Fenced filesystem appends — a stale ex-owner can still
write. Power-loss durability. Exactly-once audit.

## Phase 5.12 boundary

The remaining audit gap is the stale ex-owner. Closing it means moving the chain
tail somewhere the fence can reach, which is a storage decision, not a locking
one. That, and applied retention (still plan-only), are the candidates.
