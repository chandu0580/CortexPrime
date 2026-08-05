# Approval Integrity

**The approved artifact is the executed artifact.** Constitution I2.

> Before PR-04, the dispatcher executed whatever it read back from
> `pending_approval_actions.json`. Anything able to write that file between
> approval-request and approval-grant achieved arbitrary **approved** execution.
> This document describes the control that closed it.

---

## The pipeline

```
Executor blocks pending approval
        │
        ▼
pending_action_store.save()  ──►  canonical serialization  ──►  SHA-256 digest
        │                                                            │
        ▼                                                            ▼
                    record persisted with its digest
        │
        ▼
   Human approves  ──►  EventBus  ──►  handle_approval_event()
                                              │
                                              ▼
                                  peek (do not remove)
                                              │
                                              ▼
                                    recompute digest
                                              │
                                     ┌────────┴────────┐
                                  match            mismatch
                                     │                 │
                             claim ledger        AUDIT + REFUSE
                                     │           (record retained
                                  dispatch         as evidence)
```

---

## What the digest covers

Canonical form of four fields together. Each closes a distinct attack:

| Field | Attack closed |
|---|---|
| `payload` | Change a container name, branch, provider |
| `action_type` | Re-label a benign payload onto a destructive handler |
| `workflow_id` | Move an approved record onto another workflow's authority |
| `record_version` | Re-label v2 as v1 to reach the legacy path |

**Excluded:** `digest` itself (a field inside its own digest is unverifiable)
and `created_at` (not part of what was authorized).

---

## The binding cannot be forgotten

All five fix executors call `pending_action_store.save()` **unchanged**. The
digest is computed inside `save()`.

A caller obliged to remember a security step will eventually forget, and the
failure is silent. Making the store the only way to stash means the only
stashable thing is a bound thing.

---

## Fail closed — nine refusal conditions

| Failure | Meaning | Tamper evidence? |
|---|---|---|
| `MISSING_RECORD` | Nothing stored for this workflow | No |
| `MALFORMED_RECORD` | Not a mapping, or missing required fields | No |
| `LEGACY_UNVERSIONED` | Predates PR-04; no digest exists | **No** |
| `UNSUPPORTED_VERSION` | Version this build does not know | No |
| `MISSING_DIGEST` | Versioned record with no digest | Yes |
| `MALFORMED_DIGEST` | Digest unparsable or wrong length | **Yes** |
| `DIGEST_MISMATCH` | Content changed after approval | **Yes** |
| `WORKFLOW_MISMATCH` | Record bound to a different workflow | **Yes** |
| `ALREADY_CONSUMED` | This workflow already dispatched | **Yes** |

All nine refuse. `is_tamper_evidence` separates deliberate modification from a
record that merely predates the check — both refuse, only the former should page
anyone.

---

## Order of operations

Deliberate. Do not rearrange.

1. **Peek**, don't pop — a refused record must survive as evidence.
2. **Verify** — recompute and compare in constant time.
3. **Refuse and audit** on mismatch, leaving the record in place.
4. **Claim** the workflow atomically in the consumed ledger.
5. **Remove**, audit the dispatch, execute.

Claiming before executing means two concurrent resolutions cannot both dispatch.
Verified by a 32-thread test asserting exactly one winner.

---

## Replay protection, two layers

1. Popping the record — ordinary replay impossible.
2. `ConsumedLedger` — a workflow id is single-use, closing the re-insertion
   attack an attacker with store write access would otherwise have.

**Limitation:** the ledger is in-process and a restart clears it. Durable replay
protection arrives with PR-11, when the store moves to the database.

---

## Audit

Every refusal **and** every verified dispatch is recorded in a hash-chained,
append-only log.

Recording successes matters as much as failures: an auditor can then confirm
that every executed action passed verification, not merely that failures were
noticed.

Each entry captures: timestamp · mission · workflow · expected digest · actual
digest · reason · operator · execution-refused.

`verify_chain()` walks the chain and reports the first break, so a deleted entry
is detectable.

**Limitation:** entries are in-process plus structured logs at ERROR/INFO. The
log is the durable copy today. PR-06 replaces the sink with the hash-chained
database table behind the same interface.

---

## Known residual risk

**A fully self-consistent forgery is not detected by the digest check alone.**

An attacker who can write the store can change the payload *and* recompute a
matching digest. The check then passes by construction — there is a test
asserting exactly this, so the limitation lives in the suite rather than in
someone's assumption.

What stops it today: the attacker cannot also produce a human approval against
the forged content, because the approval decision is recorded separately by the
Approval Center. The residual risk is that this binding is **implicit** —
nothing cryptographically ties the digest to the approval decision.

**PR-05 closes it** by recording the digest at approval-grant time and comparing
against that copy, so an attacker would need to write two independently-stored
records.

---

## Operating it

**Before deploying:**

```bash
python scripts/audit_pending_approvals.py           # report
python scripts/audit_pending_approvals.py --purge   # clear legacy records
```

Exit 0 = all verified. Exit 1 = something will refuse. Purge only removes
records that cannot dispatch anyway; integrity failures are never purged.

**A refusal appears in the logs as:**

```
APPROVAL INTEGRITY REFUSAL {"workflow_id": "...", "failure": "digest_mismatch",
  "expected_digest": "...", "actual_digest": "...", "execution_refused": true,
  "tamper_evidence": true, ...}
```

Any entry with `tamper_evidence: true` warrants investigation. A
`legacy_unversioned` refusal is expected during migration and means only that
the approval must be re-requested.

**To recover a stuck action:** re-request approval. That produces a bound record
which dispatches normally. Never hand-edit the store to make something dispatch
— that is the attack this control exists to detect.

---

## Tests

```bash
pytest tests/test_approval_integrity.py
```

Organized by attack rather than by function, so coverage can be checked against
a threat model. The load-bearing assertion throughout is that **nothing reached
a dispatch handler** — a refusal that still executes is not a refusal.
