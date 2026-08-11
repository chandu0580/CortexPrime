# ADR-052 — Durable Audit Storage and Crash Recovery

**Status:** Accepted
**Date:** 2026-08-09
**Phase:** 5.9
**Relates to:** ADR-051 (audit integration), ADR-049/050
**Does not complete:** Phase 5.5, still blocked on `credential_unavailable`.

---

## Why this phase exists

ADR-051 wired the existing audit seam and named three things it had not reached:
durable audit storage, chain recovery after a crash, and long-run continuity.
Phase 5.9 closes those three. **Nothing was implemented** — the subsystem
already existed and this phase established which of its claims are true.

## Audit ownership and storage

`JsonlAuditStore` **is** the intended durable implementation. Its own docstring
says so, and the code backs it: every `append` opens in append mode, writes one
line, `flush()`es and **`os.fsync()`**es before returning. It refuses a record
containing a newline, so one record can never become two lines.

`AuditRuntime._recover` resumes an existing chain — it reads the last record,
adopts its digest as the head and its sequence plus one. A corrupted store
**raises rather than starting a fresh chain**, because beginning again at zero
would leave two chains in one store that can be verified as neither.

## Durability semantics — stated precisely

**Proven: process-crash durability.** A process wrote 25 records and died via
`os._exit(9)` — no finalisers, no flush on exit. A separate process reopened the
file, found **all 25 records**, recovered a head byte-identical to the one the
dead process held, and verified the chain end to end.

**Not proven, and not claimed:** power-loss or hardware durability. `fsync`
makes that plausible and is the right call, but this phase tested a killed
*process*, not a killed *machine*, and those are different guarantees.

**Storage boundary.** PostgreSQL remains the durable system of record for
execution state. The audit chain is a **file-backed durable observation store**,
deliberately separate. Audit was not moved into PostgreSQL; the existing
architecture already made this choice and Phase 5.9 respects it.

## Chain recovery and continuity

Reopening after a crash, appending one record, and re-verifying showed:
the new record's `previous_digest` equals the recovered head, the head advanced,
the sequence continued rather than restarting, and the extended chain verifies as
**one chain, not two**.

A **1200-event** chain across three tenants and four event kinds — 1.24 MB on
disk — was written, closed, reopened in a fresh process and verified end to end,
with the reopened head matching the writer's.

## Canonicalisation and ordering

Recomputing a record's digest reproduces it exactly. Reserialising a record with
its keys in reverse order and recomputing yields the **same** digest — key order
cannot change what was attested. Ordering comes from an explicit contiguous
`sequence`, not a wall-clock tie-break, and every timestamp is timezone-aware.

## Tamper detection

Mutations were applied to **throwaway copies**; the authoritative chain was
verified untouched afterwards. Every case is detected as a named defect:

| mutation | defects reported |
|---|---|
| altered payload | `tampered_record` |
| altered `previous_digest` | `tampered_record`, `broken_link` |
| altered `entry_digest` | `tampered_record`, `broken_link` |
| deleted middle event | `missing_record`, `broken_link` |
| reordered events | `missing_record`, `broken_link`, `out_of_order` (×2 each) |

Nothing is repaired, no hash is regenerated, no new head is accepted.

**A defect in my own testing, worth recording:** the first run reported these as
"detected" on the strength of an `AttributeError` — which came from my
*formatting* of the report, not from verification. An exception while rendering a
result is not detection. The checks now assert a real defect list and explicitly
require that nothing crashed. The subsystem was always correct; my evidence for
it was not.

## Corruption behaviour

A truncated final record and a malformed final line are both **refused at open**
with `AuditCorruptionError` naming the line number. Neither is skipped, repaired
or truncated — the file on disk is byte-identical after the refusal. A duplicated
final record is detected as a chain defect.

## Multi-process semantics — a real limitation

`JsonlAuditStore` synchronises **within** a process with `threading.RLock` and
declares **no cross-process lock** (no `fcntl`, no `msvcrt`, no advisory
locking).

Two processes appending concurrently to one file produced a chain with
`broken_link`, `missing_record`, `orphan_origin` and `out_of_order` defects. Both
processes believed they wrote 20 records each.

**The store is single-writer.** That is now demonstrated rather than assumed. A
deployment running two writers against one audit file will corrupt the chain.
No lock was added — inventing a cross-process synchronisation scheme is exactly
the architectural change this phase forbids, and the correct fix is a decision
about audit ownership (one writer per file, or a store that supports many).

## Tenant isolation and secret safety

Records carry an explicit scope; `AuditQuery` filters at the read boundary, and
filtering a multi-tenant chain returns only the selected tenant's records.

No credential value, no `bearer `, no `ghp_`, no `CredentialMaterial`, no
`"authorization":` header key, no `x-api-key`, no `private_key`. The only
sensitive-sounding fields are `authorization_digest` and `authorization_effect` —
a digest and a policy effect, which are precisely the evidence an audit should
carry. This check was written narrowly on purpose, to avoid repeating the
Phase 5.8 false positive.

## Audit failure semantics — unchanged

Re-verified with two failing sinks: an unavailable store (`OSError`) and a
serialisation failure (`TypeError`). In both cases a cross-tenant invocation
still refused with `tenant_mismatch`, the sink's own error never escaped the
gate, and no credential was minted. Audit remains **best-effort observation**.

## Relationship to the outbox

Kept separate and verified separate: the outbox writes no audit records, so
there is no audit → outbox → audit recursion, and enabling durable audit created
no duplicate events. Replay wrote **zero** audit records and left every counter
at zero.

## Guarantees

**Guaranteed.** Records survive abrupt process termination. A fresh process
recovers the head and continues the same chain. Key order cannot change a
digest. Every tested tamper is detected as a named defect and nothing is
repaired. Corruption is refused at open. Audit failure cannot change a governed
outcome. No credential material in serialised records.

**Not guaranteed.** Power-loss durability. Multi-process writing — the store is
single-writer and concurrent writers corrupt the chain. Exactly-once audit.

## What remains unverified

* **Real provider execution** — Phase 5.5, `credential_unavailable`.
* **Power-loss / hardware durability.**
* **A defined single-writer enforcement.** The limitation is proven; nothing in
  the architecture currently *prevents* a second writer.
* **Retention interaction.** `RetentionPolicy`, `plan_retention` and
  `export_chain` exist and were not exercised against a recovered chain.
