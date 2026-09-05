# ADR-089 — CONTAINED is a real execution boundary, and the write it unblocks is blocked by something else

**Status:** Accepted (the boundary is built and verified; Phase 9.9B's Definition of Done is **NOT met** — see §Consequences)
**Date:** 2026-09-05
**Extends:** ADR-059 (in-process worker gap), ADR-086 (9.6 blocked write), ADR-087 (SEALED unavailable), ADR-088 (the execution trust model)
**Implementation map:** `docs/PHASE_9_9B_IMPLEMENTATION_MAP.md`
**Verification:** `docs/PHASE_9_9B_VERIFICATION_REPORT.md`

## Context

ADR-088 ratified that isolation answers to **code trust**, not consequence, and
that a `FIXED` capability performing an `IRREVERSIBLE_WRITE` requires
`CONTAINED` — *"a separate worker with per-execution credentials."* Part A then
made the three in-process connectors declare `AMBIENT`, which is what they are.

That left `CONTAINED` with **zero occupants**. Part B was to give it one.

## Decision 1 — The worker is operator-provisioned, never platform-created

Three ways to obtain a worker process; only one survives:

| Approach | Verdict |
|---|---|
| The platform spawns it | **Rejected.** `BND-PROCESS-SPAWN` confines process creation to four legacy modules and calls a fifth an ERROR. |
| The platform creates a Pod for it | **Rejected.** Creating a Pod is itself an irreversible write, so a CONTAINED worker would require a CONTAINED worker (ADR-087's regress). And `create pods` permits mounting any Secret and assuming any ServiceAccount in the namespace — strictly more authority than `patch deployments`. |
| **The operator pre-provisions it** | **Chosen.** The worker is deployment infrastructure, like PostgreSQL. No spawn, no regress, no privilege inversion. |

## Decision 2 — The worker runs standard library only

No pip, no requirements file, no Kubernetes SDK. `CodeTrust.FIXED` is a claim
that the worker cannot be made to do anything nobody declared, and a dependency
tree is precisely where undeclared behaviour hides. Every line that runs is
readable in one file.

## Decision 3 — The credential does not travel in the envelope

There is exactly **one** `reveal()` call site in this codebase
(`httpx_adapter.py`), where credential material becomes a transport
authorization header. This adapter deliberately does not add a second: the
envelope carries no secret at all, and the worker reads the credential from the
header the transport already sets.

Two consequences worth stating. The envelope is safe to digest, log and persist
because there is nothing in it to redact. And an envelope that carries a
`credential` field anyway is **refused** by the worker's unknown-field rule —
verified.

The worker's connection is HTTPS, refused at composition if plaintext. The
Kubernetes channel already refuses plaintext because *"a bearer token on
plaintext is exposed on every request"*, and the same reasoning applies here.

## Decision 4 — Binding is checked before the credential is touched

The worker verifies tenant, capability id, capability version, provider,
operation and implementation digest — in full, refusing on the first mismatch —
**before** reading the authorization header. A worker that authenticated and
then discovered the request was for another tenant would already have spent the
credential. Verified: a wrong-tenant envelope with no credential at all refuses
on the tenant, not on the missing credential.

## Decision 5 — The contained path is its own provider id

`kubernetes-contained`, not `kubernetes`. The in-process read connector reaches
the API server directly with a read-only ServiceAccount and declares `AMBIENT`;
the contained path is a different address, a different identity and a different
trust posture. One id for both would put two endpoints and two credentials
behind one name — the shadowing Phase 9.2 refused: *"one provider id, one
execution path, never a fallback."*

## Decision 6 — Part A's threading was incomplete, and the real chain found it

`code_trust` reached the contract, both gates and `BoundCapability` in Part A,
but never `CandidateSnapshot`, `CapabilityBinding` or `project_binding`. The
first real execution to resolve a binding raised `TypeError`. Unit tests did not
reach it because none of them resolved a binding end to end.

Now threaded, and fail-closed at the projection: a binding that does not declare
its code trust is refused rather than defaulted, for the same reason the effect
class beside it is.

Also corrected: the adapter declared `WorkerKind.KUBERNETES` while the runtime's
resolver answers `"connector"` for every governed capability, so worker selection
never matched it. Kubernetes-ness belongs in `supported_providers` and
`supported_operations`, which is where selection actually reads it.

## Decision 7 — What was proven, and what was refused

Measured from inside the container: non-root (uid 65532), PID 1 in its own
namespace, read-only root filesystem, no Docker socket, no repository, no
kubeconfig, and **no CortexPrime credential in its environment at all** — the
only `CORTEX_*` variables are bindings. Runtime-enforced:
`allowPrivilegeEscalation=false`, all capabilities dropped, `RuntimeDefault`
seccomp, memory and CPU limits.

**Honestly not claimed:** process-count limits (`RLIMIT_NPROC` is `[-1, -1]`;
k3d sets no `podPidsLimit`) and an egress firewall (no NetworkPolicy is
applied). Both are recorded `NOT VERIFIED` rather than asserted. This is
`CONTAINED`. It shares the host kernel, so it is **not** `SANDBOXED` and never
`SEALED`.

## The blocking finding — an approval-requiring capability cannot be dispatched

The gateway re-authorizes at dispatch, which is correct: an approval can be
revoked between authorization and dispatch. But the `AuthorizationRequest` that
`facts_for` builds to do that **carries no `approval_artifact_id`**, so the
`ApprovalLookup` is never given anything to look up, `approval_valid` can never
become true, and any capability whose policy answers `REQUIRE_APPROVAL` refuses
with `approval_required`.

Observed, not inferred: `dispatched=False invocation_refusal=approval_required`.

`AuthorityFacts` already *has* the field and the gateway already checks it — the
value is simply never fed on the re-authorization path. `InvocationRequest` has
no approval field either, so nothing on the dispatch path could carry it today.

**This has never been hit before.** Phase 9.6 was blocked by isolation before
dispatch, and every phase before it was read-only. No approval-requiring
capability has ever reached a real gateway in this repository. There is a
comment beside the defect recording an identical class of bug found the same
way: *"the gateway's re-authorization refused every invocation, which is only
visible once a real binding reaches a real gateway."*

**Identified fix, not applied:** carry the approval reference on the sealed
binding — exactly as `code_trust` now is — and pass it into `facts_for`'s
`AuthorizationRequest`. Additive and fail-closed (absent means no approval, which
is today's behaviour), and it makes the existing check work as designed rather
than changing any policy. It was not applied here because it changes how
approvals bind to executions, which is governance surface this phase was told not
to alter unilaterally.

## Consequences

- `CONTAINED` has its first genuine occupant, and the declaration is true rather
  than convenient. 61 of 62 checks pass against real infrastructure.
- **CortexPrime still has not performed a real write.** `provider_writes = 0`,
  and the target Deployment carries no CortexPrime annotation. Phase 9.9B's
  Definition of Done is **NOT met**.
- The obstacle has moved again, and this is the third time it has moved to
  somewhere more ordinary: hardware (9.7) → taxonomy (9.8) → an unfed field on
  one authorization request (9.9B). Each move was found by running the real
  chain against real infrastructure, and none was found by a unit test.
- Nothing was weakened. `SEALED` is unchanged, `IRREVERSIBLE_WRITE` is unchanged,
  the operation was not reclassified, no gate was bypassed, and no second
  executor, gateway, scheduler, credential authority, approval authority or
  audit path was created.
