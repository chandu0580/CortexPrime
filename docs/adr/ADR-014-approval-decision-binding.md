# ADR-014 — Approval Decision Binding

- **Status:** Accepted
- **Date:** 2026-08-04
- **Phase:** 1 (PR-05)
- **Closes:** the residual risk documented in ADR-013
- **Related:** ADR-011 (hashing), ADR-013 (approval integrity)

## Context

ADR-013 bound a stashed action to a digest stored **beside it** in
`pending_approval_actions.json`. That stops post-hoc payload edits, and it
recorded its own limit plainly:

> An attacker who can write the store can change the payload **and** recompute
> a matching digest. The digest check then passes by construction.

A test asserted exactly that, so the gap lived in the suite rather than in
someone's assumption. What stopped it in practice was that the attacker could
not also produce a human approval — but that binding was **implicit**. Nothing
tied the digest to the approval decision.

This ADR makes it explicit.

## Decision

Record what was approved **independently of what will execute**, and make the
approval record the authority.

### Two stores, two writes

| Store | Holds | Written |
|---|---|---|
| `pending_approval_actions.json` | The artifact that will execute | At stash |
| `approval_decisions.json` | The authoritative digest + approver identity | At stash, sealed at grant |

Dispatch recomputes the artifact digest and compares it against the **approval
record**, never against the digest stored beside the artifact. Forging now
requires writing two stores consistently.

The authoritative digest is written at *stash* time — before any human sees the
request — so the authority predates any opportunity to tamper.

### Signing is pluggable, and the honest default is stated

Two stores in one directory is a modest improvement on its own. The real
strength is the signature; separation is what makes a signature *checkable* —
there has to be something to compare against that the artifact's author did not
write.

`ApprovalSigner` is an interface. `HmacApprovalSigner` (HMAC-SHA256) activates
automatically when `APPROVAL_SIGNING_KEY` is set. Without a key the platform
runs unsigned, logs a warning at startup, and records
`signature_algorithm: "none"` on every record so an auditor can tell sealed
records from unsealed ones.

`APPROVAL_REQUIRE_SIGNATURE=true` refuses unsigned records outright.

Asymmetric signing, an HSM, or an external notary slot in behind the same
interface without touching the verification pipeline.

### What the signature covers

Canonical bytes of `record_version`, `approval_id`, `workflow_id`,
`action_type`, `artifact_digest`, `granted_at`, `approver_id`, `approver_kind`,
`expires_at`.

Deliberately excluded: `status` (changes legitimately from granted to consumed)
and `signature` (cannot cover itself).

Signing happens at **grant**, not request, because the signature covers *who
approved what* — not knowable until a human acts.

### Eight refusal conditions

`LEGACY_NO_APPROVAL_RECORD`, `APPROVAL_MALFORMED`, `APPROVAL_VERSION_MISMATCH`,
`APPROVAL_NOT_GRANTED`, `APPROVAL_EXPIRED`, `APPROVAL_REPLAY`,
`APPROVAL_IDENTITY_INVALID`, `APPROVAL_SIGNATURE_INVALID`,
`APPROVAL_UNSIGNED_REJECTED`, `ARTIFACT_MODIFIED`, `ACTION_TYPE_MISMATCH`.

`APPROVAL_IDENTITY_INVALID` fires when the approver is absent or not a human
principal — the Constitution's rule that the platform must never authorize
itself, enforced at the verification layer rather than trusted upstream.

### Defense in depth, not replacement

PR-04's `verify_record` still runs first. It is cheap and catches ordinary
corruption before the more expensive approval lookup. PR-05's check is
authoritative; PR-04's is a fast pre-filter. Both must pass.

## Alternatives Considered

**Store the approved digest in the Approval Center's own workflow record.**
Architecturally cleaner — one authority for approvals. Rejected for now:
`approval_center/workflows.py` holds workflows in memory with its own
persistence story, and threading a digest through it means changing a subsystem
five executors depend on. The separate store is a smaller, revertible change
that achieves the same separation. Consolidating is natural work for PR-11 when
both stores move to the database.

**Require a signing key unconditionally.** Rejected: it would break every
existing deployment on upgrade, and a hard failure at boot for a
defense-in-depth layer is disproportionate. `APPROVAL_REQUIRE_SIGNATURE` gives
operators the strict posture when they are ready; the warning makes the weaker
posture visible meanwhile.

**Asymmetric signatures now.** Better — the verifier would not hold signing
authority. Rejected as premature: no key distribution or rotation infrastructure
exists yet, and the interface accommodates it later without redesign.

**Delete the artifact on refusal.** Rejected for the same reason as ADR-013: a
forged artifact is the only copy of what was forged.

## Security Analysis

**Closed by this change**

| Attack | Before (PR-04) | After |
|---|---|---|
| Edit payload only | Refused | Refused |
| Edit payload + recompute local digest | **Passed** | Refused — `artifact_modified` |
| Edit both stores consistently | **Passed** | Refused — `approval_signature_invalid` (signed mode) |
| Strip signature to downgrade | n/a | Refused |
| Substitute another workflow's approval | n/a | Refused |
| Reuse a consumed approval | Refused (in-process) | Refused (persisted in the record) |
| Grant approval as the platform itself | n/a | Refused — `approval_identity_invalid` |
| Extend expiry or rewrite approver | n/a | Refused — signature covers both |

**Not closed, stated explicitly**

*Unsigned deployments remain vulnerable to a two-store forgery.* An attacker who
can write both files and is not facing an HMAC can forge consistently. There is
a test asserting this — `test_unsigned_deployment_cannot_stop_two_store_forgery`
— so the limitation is documented in the suite, not assumed away.

**Mitigation:** set `APPROVAL_SIGNING_KEY`. The startup warning names this.

*The verifier holds the signing key.* HMAC is symmetric, so an attacker with
code execution in the process can sign. This raises the bar from filesystem
write to code execution, which is a large jump, but not infinite. Asymmetric
signing closes it and the interface is ready.

*Key rotation invalidates existing approvals.* Tested and intended: silently
accepting records signed under a retired key would defeat rotation. Operators
must drain pending approvals before rotating.

## Migration Strategy

**Classification is explicit, never silent.** Three cases:

| Case | Classification | Behavior |
|---|---|---|
| Artifact + granted approval record | Current | Executes |
| Artifact, no approval record (PR-04 era) | `LEGACY_NO_APPROVAL_RECORD` | **Refuses**, audited, not flagged as tampering |
| Artifact + record under a retired key | `APPROVAL_SIGNATURE_INVALID` | **Refuses**, flagged as tampering |

Legacy artifacts never silently bypass verification — the requirement is met by
a distinct failure code that is audited and distinguishable from an attack.

**Steps**

1. Run `python scripts/audit_pending_approvals.py` (ADR-013 tooling) to find
   stashed artifacts.
2. Any artifact without an approval record must have its approval re-requested;
   the new stash writes both stores.
3. Set `APPROVAL_SIGNING_KEY` (32+ chars) before or during deploy. Records
   stashed before the key is set are unsigned and will fail once
   `APPROVAL_REQUIRE_SIGNATURE` is enabled — drain first, then enable strict
   mode.
4. Verified in this environment: both stores are empty, so migration is a no-op
   here.

## Rollback Strategy

`git revert` restores PR-04 behavior. **Reverting reopens the two-store forgery
gap** — prefer fixing forward.

Data is safe: `approval_decisions.json` is a new file the old code never reads,
and the pending-action record shape is unchanged. Reverting leaves an orphaned
decisions file, which is harmless and can be deleted.

To recover a stuck action without reverting, re-request approval — that writes
both stores and dispatches normally. Never hand-edit a store to force a
dispatch; that is the attack this exists to detect.

## Remaining Risks

1. **Unsigned deployments** — mitigated by setting a key; warned at startup.
2. **Symmetric key in-process** — asymmetric signing is the next step.
3. **Both stores are files** — PR-11 moves them to the database, which also
   makes replay protection survive a restart.
4. **Two stores, one directory** — separation is logical, not physical. A
   deployment wanting stronger separation can point the decision store at
   different storage; the path is injectable.

## Compliance

- Invariant **I2** now has two independent enforcement points.
- Constitution "the platform must never authorize itself" is enforced at
  verification, not merely at contract construction.
- Fail-closed holds across all eleven refusal conditions.
