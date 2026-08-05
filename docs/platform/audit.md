# Durable Audit Runtime

`backend.platform.audit` — compliance-grade evidence. **Not logging.**

> Constitution I3: append-only and independently verifiable.
> S8: designed for a hostile reader — it must survive a dispute without the
> reader trusting the running system.

---

## What belongs here, and what does not

| Belongs | Does not |
|---|---|
| Approvals, executions, policy decisions | Application logging |
| Verification results, integrity failures | Metrics, traces |
| Replay attempts, break-glass | Debug output |
| Configuration changes, identity events | Anything sampled or expired |
| Connector operations | Anything mutable |

Mixing observability into an evidence trail devalues both: the trail becomes too
noisy to audit and too expensive to retain.

---

## Usage

```python
from pathlib import Path
from backend.platform.audit import AuditRuntime, JsonlAuditStore, verify_chain
from backend.contracts import AuditEventKind

runtime = AuditRuntime(JsonlAuditStore(Path("backend/data/audit.jsonl")))

runtime.record(
    AuditEventKind.EXECUTION_REFUSED,
    scope,
    subject_reference=workflow_id,
    detail={"failure": "digest_mismatch"},
    correlation_id=incident_id,
    payload_digest=artifact_digest,
)

report = verify_chain(runtime)
assert report.ok, report.summary()
```

---

## Every record carries

`event_id` · `previous_digest` · `entry_digest` · `recorded_at` · `actor` ·
`scope` (tenant) · `correlation_id` · `causation_id` · `kind` ·
`payload_digest` · `schema_version`

**`payload_digest` vs `entry_digest`** — the first identifies the *subject* (the
approved artifact); the second covers the *audit entry itself*. Conflating them
would make it impossible to tie a record to the thing it describes without
trusting the detail bag.

---

## Three defect classes

| Defect | Meaning | Caught by |
|---|---|---|
| `TAMPERED` | A record was edited in place | Recomputed digest ≠ stored |
| `BROKEN_LINK` | Reordered or substituted | `previous_digest` ≠ predecessor |
| `MISSING_RECORD` | **A record was deleted** | Sequence numbers skip |

**The third is the one naive chain checks miss.** Deleting a record from the
middle leaves every surviving link intact — the sequence gap is the only trace.

Verification reports *every* defect, not just the first: an operator
investigating tampering needs the full extent of the damage.

---

## Storage is abstract

`AuditStore` is a Protocol with `append`, `read_all`, `query`, `last`, `count`.

**No `update`. No `delete`.** Not by convention — the operations do not exist to
call. A test asserts the Protocol exposes no mutation method.

| Implementation | Use |
|---|---|
| `InMemoryAuditStore` | Tests, ephemeral processes |
| `JsonlAuditStore` | Durable — one JSON object per line, fsynced per record |
| *PostgreSQL* | **PR-11**, behind this same interface |

### Why JSONL isn't the repo's JSON anti-pattern

The anti-pattern is *mutable* file state: every write rewrites the whole
document, a crash mid-write loses everything. That is what caused the event-loop
outage.

Append-only JSONL is a different shape — one record, one line, appended and
fsynced, never revisited. A torn write damages at most the final line, and
verification detects it. A test asserts the file only ever grows.

Still an interim. PostgreSQL gives transactional guarantees a file cannot.

---

## Recovery

Construction reads the chain head and continues from `last.sequence + 1`.

Starting fresh at zero would leave **two chains in one store** — verifiable as
neither — and quietly discard prior evidence. A corrupted store therefore raises
`AuditCorruptionError` naming the damaged line rather than starting over.

---

## Retention

Retention and tamper-evidence are in genuine tension. **Deleting from the middle
of a chain breaks it, and is indistinguishable from an attacker removing
evidence.**

So retention is *archive-then-truncate from the front*, never delete-in-place:

```python
from backend.platform.audit import plan_retention, AgeBasedRetention

decision = plan_retention(list(runtime.query()), AgeBasedRetention(retain_days=90))
if decision.safe:
    print(decision.reason)   # "archive sequences 0-412, then verify with expect_origin=False"
```

`plan_retention` **produces a plan, never a mutation** — an operator reviews it.
It refuses outright when retirable records are not a contiguous prefix:

> archiving them would leave a hole in the chain, which is indistinguishable
> from tampering

Security-relevant kinds get a longer minimum (default ~7 years). Default policy
is `KeepForever`; nothing is deleted automatically.

---

## Export

```python
exported = export_chain(runtime)          # manifest line + one record per line
report = verify_export(runtime, exported)
```

The manifest carries the **head digest**. Publishing it somewhere the platform
cannot reach — a ticket, an email, an external notary — converts "tamper-evident
to whoever holds the file" into "tamper-evident, full stop": a rewritten chain
cannot reproduce a head witnessed elsewhere.

`verify_export` checks the manifest against the records that follow, so an
export whose manifest was edited to hide a deletion is caught.

---

## Query

```python
from backend.platform.audit import AuditQuery

runtime.query(AuditQuery(security_relevant_only=True, limit=100))
runtime.query(AuditQuery(correlation_id="incident-1"))
runtime.query(AuditQuery(tenant_id="acme", since=yesterday))
```

Filtering happens in the store so a SQL implementation can push predicates down
rather than loading a chain into memory to discard most of it.

---

## Honest limitations

**Wholesale rewriting is not detected.** Chaining catches *edits*, not an
attacker who recomputes every digest. Mitigation: publish the head digest
externally. Supported by `export_chain`; the practice is operational.

**No transactionality.** A crash between an executed action and its audit write
leaves an unaudited action. A file cannot close this — PR-11 can.

**Single file, unbounded growth.** Retention *planning* exists; execution is
deliberately an operator action.

**`tenant_id="system"` placeholder** on legacy dispatch records, which have no
tenant context. Visible by design; PR-09 removes it.

---

## Migration from the PR-04 sink

`IntegrityAuditLog` keeps its full interface — all five call sites unchanged.
Behavioral differences are all improvements:

| Before | After |
|---|---|
| In-memory, capped at 1000 | Durable, uncapped |
| Lost on restart | Resumes the chain |
| Could not detect deletions | Detects deletions |
| `clear()` wiped the chain | Swaps to a fresh in-memory runtime; durable records never deleted |

If the durable store cannot be opened, the runtime falls back to in-memory and
**logs an error**. Refusing to boot over an audit path would take the platform
down; running silently unaudited would be worse.

---

## Tests

```bash
pytest tests/platform/test_audit_runtime.py --confcutdir=tests/platform
```

80 tests organized by defect class, because an auditor asks "what damage would
this catch?" — not "which method was called".
