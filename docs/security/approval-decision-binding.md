# Approval Decision Binding

**The approval is the authority — not the payload.** ADR-014.

> PR-04 bound an artifact to a digest stored *beside it*. This closes the gap
> PR-04 documented: an attacker who could write that one file could rewrite the
> payload **and** its digest together, producing a self-consistent forgery.

---

## The trust chain

```
Executor stashes action
        │
        ├──────────────────────────────┐
        ▼                              ▼
 pending_approval_actions.json   approval_decisions.json
   (the artifact)                  (the AUTHORITY)
        │                              │
        │                       status: pending
        │                              │
        │                     Human grants approval
        │                              │
        │                       status: granted
        │                       + approver identity
        │                       + HMAC signature ◄── seals it
        │                              │
        └──────────► DISPATCH ◄────────┘
                        │
              recompute artifact digest
                        │
              compare against APPROVAL RECORD
                   (never the local digest)
                        │
              ┌─────────┴─────────┐
            match             mismatch
              │                   │
        consume approval    AUDIT + REFUSE
        dispatch            (both stores retained)
```

**Forging now requires writing two stores consistently** — and, with a signing
key configured, producing an HMAC the attacker does not hold.

---

## Why two stores

Two files in one directory is a modest improvement on its own. The real strength
is the signature; **separation is what makes a signature checkable** — there has
to be something to compare against that the artifact's author did not write.

The authoritative digest is written at *stash* time, before any human sees the
request, so the authority predates any opportunity to tamper.

---

## Configure signing

```bash
export APPROVAL_SIGNING_KEY="$(openssl rand -hex 32)"   # 32+ chars
export APPROVAL_REQUIRE_SIGNATURE=true                  # refuse unsigned records
export APPROVAL_DECISION_TTL_MINUTES=60                 # 0 = no expiry (default)
```

| Mode | Single-store forgery | Two-store forgery |
|---|---|---|
| Unsigned (default) | ✅ Refused | ❌ **Not detected** |
| HMAC signed | ✅ Refused | ✅ Refused |
| HMAC + strict | ✅ Refused | ✅ Refused, and unsigned records refuse too |

Running unsigned logs a warning at startup and stamps
`signature_algorithm: "none"` on every record, so an auditor can tell sealed
records from unsealed ones rather than a missing signature being ambiguous.

---

## Refusal conditions

| Failure | Meaning | Tamper evidence? |
|---|---|---|
| `LEGACY_NO_APPROVAL_RECORD` | Artifact predates decision binding | No |
| `APPROVAL_MALFORMED` | Record unusable | No |
| `APPROVAL_VERSION_MISMATCH` | Unknown record version | No |
| `APPROVAL_NOT_GRANTED` | Still pending, or revoked | No |
| `APPROVAL_EXPIRED` | Past its TTL | No |
| `APPROVAL_UNSIGNED_REJECTED` | Strict mode, unsigned record | No |
| `ARTIFACT_MODIFIED` | **The artifact is not what was approved** | **Yes** |
| `ACTION_TYPE_MISMATCH` | Approval authorized a different action | **Yes** |
| `APPROVAL_REPLAY` | This approval already executed | **Yes** |
| `APPROVAL_IDENTITY_INVALID` | Approver missing or not human | **Yes** |
| `APPROVAL_SIGNATURE_INVALID` | Record altered after sealing | **Yes** |

All refuse. `is_tamper_evidence` separates deliberate modification from drift —
only the former should page anyone.

---

## What the signature covers

`record_version` · `approval_id` · `workflow_id` · `action_type` ·
`artifact_digest` · `granted_at` · `approver_id` · `approver_kind` ·
`expires_at`

**Excluded:** `status` (legitimately changes granted → consumed) and `signature`
(cannot cover itself).

Signing happens at **grant**, not request — the signature covers *who approved
what*, which is not known until a human acts.

---

## Honest limitations

**Unsigned deployments cannot stop a two-store forgery.** There is a test
asserting this (`test_unsigned_deployment_cannot_stop_two_store_forgery`), so
the limit lives in the suite rather than in an assumption. Fix: set
`APPROVAL_SIGNING_KEY`.

**HMAC is symmetric** — the verifier holds the signing key, so code execution in
the process still permits forgery. This raises the bar from filesystem write to
code execution. Asymmetric signing closes it; `ApprovalSigner` is an interface
precisely so that drops in without touching the pipeline.

**Key rotation invalidates existing approvals** — tested and intended. Silently
accepting records signed under a retired key would defeat rotation. Drain
pending approvals before rotating.

**Both stores are still files.** PR-11 moves them to the database, which also
makes replay protection survive a restart.

---

## Migration

Three cases, classified explicitly — legacy artifacts **never** silently bypass
verification:

| Case | Result |
|---|---|
| Artifact + granted record | Executes |
| Artifact, no record (PR-04 era) | Refuses as `LEGACY_NO_APPROVAL_RECORD`, audited, **not** flagged as attack |
| Record under a retired key | Refuses as `APPROVAL_SIGNATURE_INVALID`, flagged as tampering |

```bash
python scripts/audit_pending_approvals.py    # find stashed artifacts
```

Any artifact without an approval record needs its approval re-requested — the
new stash writes both stores. Set the signing key before enabling strict mode,
and drain first.

Verified in this environment: both stores are empty, so migration is a no-op.

---

## Recovery

**To recover a stuck action:** re-request approval. That writes both stores and
dispatches normally.

**Never hand-edit a store to force a dispatch.** That is precisely the attack
this control exists to detect, and it will be refused and audited as tampering.
