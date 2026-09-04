# ADR-086 — Phase 9.6: The first governed Kubernetes write, and why it did not happen

**Status:** Accepted (the phase's Definition of Done is **NOT met**; see §7)
**Date:** 2026-09-04
**Extends:** ADR-059 (in-process worker isolation), ADR-071 (intelligence boundary),
ADR-072–079 (Phase 8 autonomy), ADR-081–085 (Phase 9 read path).

## Context

Every governed action CortexPrime has ever performed against a real external
system has been a **read**. Phases 9.1–9.5 built a real Kubernetes read adapter,
a continuous watch, a second corroborating observability source, and a read-only
incident investigator that can reach a supported conclusion about a real
CrashLoopBackOff.

Phase 9.6 was to close the loop: perform one real, verifiable, minimal write —
a single-workload rollout restart — but only after the platform had *earned* the
authority to do it, and only through the one governed execution chain.

The write did not happen. Not because the code is unfinished, and not because
the cluster was unavailable, but because **the platform refused itself.** This
ADR records the operation as built, the refusal, and why the refusal is the
correct outcome rather than a defect to be patched around.

## Decision 1 — Classify the rollout restart honestly: IRREVERSIBLE_WRITE

A rollout restart is universally described as safe, routine and reversible. It
is none of those things in the sense this platform's autonomy model uses the
word.

`kubectl rollout restart` works by writing an annotation into a Deployment's pod
template. That mutates the pod template, which creates a **new ReplicaSet
revision**, which terminates every running pod of that workload and starts
replacements. There is **no inverse operation**:

- Removing the annotation does not restore the pods that were killed; it
  produces yet another revision and yet another termination.
- `rollout undo` is not an inverse either — it is a further forward mutation to
  a *previous spec*, which does not exist as a distinct spec here because the
  restart changed no spec the operator cares about.
- The terminated pods are gone. Their local state, their in-flight requests and
  their process identity are not recoverable by any subsequent call.

We therefore declare:

| Property | Value |
|---|---|
| `side_effect_class` | `IRREVERSIBLE_WRITE` |
| `effect_semantics` | `NON_IDEMPOTENT_WRITE` |
| `reversible` | `False` |
| verification | `INDEPENDENT_READBACK` |
| autonomy ceiling | `A3_APPROVED_ACTION` (never A4) |
| derived risk | `HIGH` |

The brief permitted classifying it as reversible if a true inverse existed. It
does not, so we did not. `reversible=False` is not pessimism; it is the fact.

## Decision 2 — Blast radius lives in the type, not in a runtime check

`RemediationTarget` (`backend/api/remediation.py`) accepts exactly one namespace
and one deployment name, and **refuses at construction** any value containing
`*`, `,`, ` `, `/`, `=` or a newline. There is no selector field, no list field
and no "all" mode to disable. The provider operation itself declares only two
parameters (`namespace`, `name`), so a fan-out has nowhere to be expressed even
if a caller wanted one.

## Decision 3 — A fourth narrow provider port: `ProviderBodyBuilder`

Phases 9.2–9.3 added `ProviderBodyNormalizer` and `ProviderBodyDecoder` to the
generic `ConnectorAdapter` as the established way to extend it without a second
adapter. A write needs the mirror of a decoder: something that produces the
request document. `ProviderBodyBuilder` (port 4) runs **after** parameter
validation and replaces `plan.body`.

`KubernetesRestartBodyBuilder` produces exactly one document and nothing else:

```json
{"spec": {"template": {"metadata": {"annotations": {
    "cortexprime.io/restarted-by-action": "<action id>"}}}}}
```

The annotation is CortexPrime's own key, not `kubectl.kubernetes.io/restartedAt`
— an operator reading the cluster must be able to tell which system touched the
workload. The value is the platform's action identity, so the same action
produces a byte-identical request (verified) and a *different* action cannot be
mistaken for a retry of it. The builder **raises without an action identity**: an
unattributable write is not one this platform will construct.

## Decision 3b — A write does not live in a function named `read`

The restart was first added to `kubernetes_read_catalog()`, which broke four
existing assertions that the Kubernetes catalog is read-only. Those assertions
were right and the code was wrong: every existing caller — the read harnesses,
the investigator's `ToolRegistry`, the provider factory — asks for the read
catalog and must keep getting exactly reads, so that a write can never reach one
of them by having been quietly added to a set it already trusts.

`kubernetes_read_catalog()` is therefore unchanged and still read-only.
`kubernetes_write_catalog()` is a separate function a caller must name
deliberately. And `KUBERNETES_REAL_READ_OPERATIONS` — the *exposed* set the
composed connector serves — deliberately excludes the write: offering an
operation the CONTAINED worker must refuse is worse than not offering it.

**Declared is not exposed.** That gap is the point of declaring a contract ahead
of exposing it, and here it is load-bearing.

## Decision 4 — Two typed doors into one chain

`GovernedCapabilityReader.read()` and `GovernedCapabilityWriter.write()` both
delegate to one private `_perform()`. There is no second executor, gateway,
scheduler or transport. The doors differ only in what they refuse:

- `read()` refuses any operation whose `side_effect_class.mutates`.
- `write()` refuses any operation that does **not** mutate — attaching an
  approval to an action that changes nothing would make approvals meaningless.
- `write()` carries `approval_artifact_id` into the `AuthorizationRequest`;
  `read()` cannot supply one.

## Decision 5 — Authorization is an identity reference, never a name

An approval whose approver is the string `"admin"` is not an authority and is
refused. Five clauses are each independently sufficient to void an approval:
DENIED status, expiry, another tenant, another operation, another digest.

## Decision 6 — The blocking finding: the platform refuses to write what it cannot isolate

This is the finding the phase turned on, and it was **not** known before
implementation.

`IsolationTier` assigns sufficiency by consequence:

| Tier | Sufficient for |
|---|---|
| `AMBIENT` | `READ` |
| `CONTAINED` | `READ`, `REVERSIBLE_WRITE` |
| `SEALED` | everything, including `IRREVERSIBLE_WRITE` |

`SEALED` is documented as *"arbitrary commands or code; full virtualization, no
ambient credentials."*

The Kubernetes connector is declared `CONTAINED` and runs **in-process**
(the gap ADR-059 states openly). So an honestly-classified rollout restart hits
two independent refusals, each sufficient on its own:

- **Gate 1 — registration.** `CapabilityContract.__post_init__`
  (`contexts/connectivity/domain/contract.py:206`) refuses the capability at
  registration: *"isolation tier 'contained' is insufficient for a
  'irreversible_write' capability."* The capability cannot exist.
- **Gate 2 — selection.** `WorkerImplementation.permits_side_effect`
  (`worker_directory.py:514`) returns `False`, so even a registered capability
  could not be dispatched to this worker.

No irreversible-write capability has ever been registered in this repository.
GitHub's connector declares some, but was never commissioned (Phase 5.5's
credential blocker). **This invariant had never been exercised until now.**

There were exactly three ways forward:

1. Declare the restart `REVERSIBLE_WRITE`. Rejected — it is a lie about the
   operation (Decision 1), and the brief forbids it explicitly.
2. Declare the in-process connector `SEALED`. Rejected — it asserts full
   virtualization and the absence of ambient credentials, neither of which
   exists. This is the one thing the project must never do: weaken a safety
   declaration to obtain a green result.
3. Stop, and report BLOCKED.

**We chose 3.** The autonomy and isolation policies are unchanged. No tier was
widened, no classification softened, no gate bypassed.

## Consequences

- CortexPrime still has **zero** write capability against any real system, and
  the reason is now documented and machine-verified rather than incidental.
- The read path is untouched and still works against the real cluster.
- The 9.6 code (operation spec, body-builder port, typed write door, remediation
  lifecycle, pre-action gate) ships and is unit-verified, but is unreachable in
  production until a SEALED execution tier exists.
- **Phase 9.7 is now defined by this finding:** build a real SEALED execution
  tier — an out-of-process, credential-brokered, virtualized worker — and only
  then perform the first irreversible write. Phase 9.6's Definition of Done
  moves to 9.7 unchanged.

## §7 — What is and is not verified

Verified against the real k3d cluster and real PostgreSQL (53/53 harness checks,
46/46 unit tests): the honest declaration, the blast-radius refusals, both
isolation gates, the body builder's determinism and its refusal without an
action identity, all ten autonomy gates (including that the *shipped default*
caps HIGH risk at A2 and refuses even with a valid approval), the five approval
clauses, secret containment, tenant isolation, and audit-chain verification.

**Not verified — BLOCKED:** the real Kubernetes write, the post-write readback,
the prediction evaluation against a real outcome, and the assurance verdict on a
real remediation. The decisive measurement of this phase is a negative:
`provider_writes == 0`, every provider dial a `GET`, and the cluster carries no
CortexPrime restart annotation.
