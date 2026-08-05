# ADR-013 — Approval Integrity Enforcement

- **Status:** Accepted
- **Date:** 2026-08-04
- **Phase:** 1 (PR-04) — the highest-priority security item in the Phase 1 review
- **Related:** ADR-007 (Approval Binding), ADR-010, ADR-011, ADR-012

## Context

The Phase 1 Architecture Compliance Report listed V1 as the only **P0**
security defect. In `enterprise_approval_action_dispatcher.py`:

```python
# before
self._pending[workflow_id] = {"action_type": action_type, "payload": payload}   # line 76
...
await handler(entry["payload"])                                                 # line 158
```

No digest existed anywhere in that path. The stashed payload lived in
`backend/data/pending_approval_actions.json`, and dispatch executed whatever it
read back. Anything able to write that file between approval-request and
approval-grant achieved **arbitrary approved execution** — with a genuine human
approval recorded against it.

This is precisely the bypass published penetration testing demonstrated against
a shipping agent product: what the human *saw* differed from what the system
*executed*. Constitution I2 exists because of it.

## Decision

Verify the stored record against its digest before every dispatch, and refuse
on any doubt.

### The digest is computed in the store, not by callers

Five executors call `pending_action_store.save()`. Every one is **unchanged**;
`save()` now builds a bound record internally.

This is the central design choice. A caller obliged to remember a security step
will eventually forget, and the failure is silent — the record simply carries no
digest and, before enforcement existed, dispatched anyway. Making the store the
only way to stash means the only stashable thing is a bound thing. Same
principle as `EventEnvelope.wrap()` computing its own digest in ADR-012.

### What the digest covers

Canonical form (ADR-011) of `record_version`, `workflow_id`, `action_type`, and
`payload`. Each closes a distinct attack:

| Field | Attack it closes |
|---|---|
| `payload` | Change a container name, branch, or provider |
| `action_type` | Re-label an approved benign payload onto a destructive handler |
| `workflow_id` | Move an approved record onto a different workflow's authority |
| `record_version` | Re-label v2 as v1 to trigger the unversioned legacy path |

`digest` and `created_at` are excluded. A field inside its own digest is
unverifiable, and a timestamp is not part of what was authorized.

### Order of operations at dispatch

Deliberate, and it must not be rearranged:

1. **Peek** — read without removing.
2. **Verify** — recompute and compare.
3. **Refuse and audit** on mismatch, leaving the record in place.
4. **Claim** the workflow in the consumed ledger.
5. **Remove**, audit the verified dispatch, then execute.

Verifying before removing means a refused record survives as evidence. Claiming
before executing means two concurrent resolutions cannot both dispatch.

### Fail closed, without exception

Nine refusal conditions: missing record, malformed record, legacy unversioned,
unsupported version, missing digest, malformed digest, digest mismatch, workflow
mismatch, already consumed. There is no branch in the module that executes on
uncertainty.

### Legacy records refuse

Records written before this change carry no digest, so their integrity cannot be
established, so they do not run. This is a **breaking behavior change**, made
deliberately: accepting them would leave the vulnerability open indefinitely
behind a flag nobody would ever turn off.

Refusals distinguish `LEGACY_UNVERSIONED` from `DIGEST_MISMATCH` via
`is_tamper_evidence`. Both refuse; only the latter should page anyone.

### Replay protection has two layers

Popping the record makes ordinary replay impossible. But an attacker who can
write the store can also *re-insert* a record that already executed — so a
`ConsumedLedger` makes a workflow id single-use, with an atomic
`mark_consumed()` so concurrent resolutions cannot both win.

The ledger is in-process. A restart clears it. Stated plainly rather than
hidden: durable replay protection arrives with PR-11, when the store moves to
the database.

### Every decision is audited

Refusals *and* verified dispatches, in a hash-chained append-only log using
ADR-010's `AuditEvent`. Recording successes matters: an auditor can then confirm
every executed action passed verification, not merely that failures were
noticed.

Captured per the requirement: timestamp, mission, approval (workflow), expected
digest, actual digest, reason, operator, execution-refused.

## Alternatives Considered

**Sign the record with an HMAC instead of hashing it.** Stronger — an attacker
who can write the store still cannot forge a valid tag without the key.
Rejected *for now*: it requires key management and rotation that do not exist
yet, and it solves a different problem than the one V1 describes. Worth
revisiting once secret brokering lands. The honest limitation is recorded below.

**Accept legacy records behind a compatibility flag.** Rejected: a flag
permitting unverified execution is the vulnerability with a switch on it, and
the switch would never be flipped off. The store was empty in practice, so the
migration cost is near zero.

**Verify inside each of the five executors.** Rejected: five places to get right
and five places to forget, and it would leave the store able to hold unbound
records.

**Delete the record on refusal.** Rejected: the tampered record is the only
copy of what was tampered with. Destroying it on detection would destroy the
evidence.

## Security Analysis

**Closed by this change**

| Attack | Result |
|---|---|
| Modify payload on disk after approval | Refused — digest mismatch |
| Modify a nested or deeply-nested field | Refused |
| Re-label `action_type` to a destructive handler | Refused |
| Move an approved record to another workflow | Refused — workflow mismatch |
| Strip the version to reach the legacy path | Refused — legacy unversioned |
| Re-insert an already-executed record | Refused — already consumed |
| Race two resolutions of one workflow | Exactly one dispatches |
| Reorder keys or round-trip JSON to shift bytes | No effect — canonicalized |
| Substitute `1` for `"1"` or `True` | Refused — types distinguished |

**Not closed, stated explicitly**

*A fully self-consistent forgery.* An attacker who can write the store can
change the payload **and** recompute a matching digest. The digest check then
passes by construction — there is a test asserting exactly this, so the
limitation is documented in the suite rather than assumed away.

What stops that today is that the attacker cannot also produce a human approval
against the forged content: the approval decision is recorded separately by the
Approval Center. The residual risk is that this binding is *implicit* — nothing
cryptographically ties the digest to the approval decision.

**PR-05 closes it** by having the Approval Center record the digest at
approval-grant time and having dispatch compare against *that* copy rather than
against the one stored alongside the payload. An attacker would then need to
write two independently-stored records.

Filesystem write access to `backend/data/` remains a privileged position. This
change turns it from "silently execute anything, approved" into "detected,
refused, and audited" — a large reduction, not elimination.

## Consequences

**Positive**

- The P0 defect is closed. No path dispatches without a verified digest.
- Five executors unchanged; binding cannot be forgotten.
- Every refusal is auditable and attributable.
- Concurrent double-dispatch is impossible.

**Negative**

- Legacy records stop dispatching (migration below; store was empty in practice).
- The consumed ledger does not survive restart.
- Audit persistence is in-process plus structured logs until PR-06.

## Migration Plan

1. **Before deploy:** run `python scripts/audit_pending_approvals.py`. It
   reports verified, legacy, and integrity-failing records, and exits non-zero
   if anything will refuse.
2. **If legacy records exist:** either let their approvals lapse and re-request,
   or run with `--purge` to clear them. Purge only removes records that cannot
   dispatch anyway; integrity failures are never purged, because they are
   evidence.
3. **Deploy.** New records are bound automatically from the first `save()`.
4. **After deploy:** confirm the audit log shows `EXECUTION_STARTED` entries for
   dispatches. Any `INTEGRITY_VIOLATION_DETECTED` entry warrants investigation.

Verified in this environment: the store is empty, so migration is a no-op here.

## Rollback Strategy

`git revert` restores the prior dispatcher. **Reverting reopens the
vulnerability** — prefer fixing forward.

Records written under PR-04 remain readable by the old code: it ignores
`record_version` and `digest` and reads `action_type` and `payload`, which are
unchanged in shape. So rollback is safe for data, unsafe for security.

If dispatch must be restored urgently without reverting, the correct action is
to re-request approval for the affected workflow. That produces a bound record
and dispatches normally.

## Compliance

- Invariant **I2** now has a live enforcement point and 80 adversarial tests.
- Invariant **I3** is partially satisfied: the audit chain is hash-linked and
  append-only, but durable storage awaits PR-06.
- Constitution S8 "fail closed, always" is satisfied for this path.
