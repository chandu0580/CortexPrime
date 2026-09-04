# ADR-087 — Phase 9.7: The SEALED execution tier cannot be built here

**Status:** Accepted (the phase's Definition of Done is **NOT met**; no code was written)
**Date:** 2026-09-04
**Extends:** ADR-059 (in-process worker isolation), ADR-086 (Phase 9.6 blocked write).
**Supersedes nothing. Weakens nothing.**

## Context

ADR-086 ended with a single next step: build a real SEALED execution tier, then
perform CortexPrime's first irreversible write. Phase 9.7 was that work.

Discovery — conducted before any implementation, per the phase brief — found that
the security property SEALED requires does not exist on this machine and cannot
be made to exist on it. This ADR records the finding, the two secondary
contradictions, the architectural observation underneath them, and the decision
to write no code at all.

## Decision 1 — Do not build. The required property is unavailable.

`IsolationTier.SEALED` (`backend/contracts/connector.py:56-68`) is defined as
*"Arbitrary commands or code. **Full virtualization**, no ambient credentials"*,
and its enum docstring states that SEALED *"explicitly excludes shared-kernel
containers: where untrusted or model-generated commands run, hardware-enforced
isolation is required."*

Executed against real Docker, in real containers:

| Probe | Result |
|---|---|
| Container runtimes installed | `io.containerd.runc.v2`, `nvidia`, `runc` |
| gVisor (`runsc`) | **absent** |
| Kata | **absent** |
| Host kernel | `6.6.87.2-microsoft-standard-WSL2` |
| Kernel reported *inside* a container | `6.6.87.2-microsoft-standard-WSL2` — **the same kernel** |
| `/dev/kvm` inside a container | **ABSENT** |
| `vmx` flags in `/proc/cpuinfo` | **0** |

A container on this host reports the host's kernel because it is the host's
kernel. With no `/dev/kvm` and no `vmx` exposure, Kata and Firecracker are not
uninstalled — they are impossible. gVisor is absent and would in any case be a
user-space kernel, not hardware-enforced isolation.

Every container obtainable here is exactly the shared-kernel container SEALED
excludes. Declaring one SEALED would assert virtualization that does not exist —
the same lie, on the same half of the same sentence, that ADR-086 refused to
tell. So nothing was built.

## Decision 2 — Do not invent an intermediate tier

The tempting move is a fourth tier between CONTAINED and SEALED: separate
process, no ambient credentials, capability-bound, network-restricted,
resource-limited — sufficient for `IRREVERSIBLE_WRITE` without virtualization.

Rejected. A new tier that permits irreversible writes on infrastructure SEALED
was written to exclude is the invariant-weakening this phase forbids, wearing a
new name. If the taxonomy should change, it should change deliberately and be
ratified (Decision 4), not arrive as a side effect of wanting a green result.

The taxonomy therefore still has exactly three tiers, and `CONTAINED` still
permits exactly `READ` and `REVERSIBLE_WRITE`. Verified: checks E1–E3.

## Decision 3 — Record the two secondary contradictions, and that they are escapable

**`BND-PROCESS-SPAWN`.** Process creation is confined to four named legacy
modules, and the rule states a fifth site "is an ERROR, not a review comment."
Verified executed: the allowlist has exactly four entries, its severity is
`ERROR`, all four are legacy, and it passes today with 0 violations across 1181
modules. A platform-spawned worker needs a fifth entry.

**Bootstrap regress.** Creating the sealed worker as a Pod runs code that
terminates with no inverse — an `IRREVERSIBLE_WRITE`. Creating a SEALED worker
would therefore require a SEALED worker. And `create pods` is a strictly larger
grant than `patch deployments`: it permits mounting any Secret in the namespace
and assuming any ServiceAccount in it, so the bootstrap would grant CortexPrime
more authority than the one action the worker exists to contain. (That last
clause is recorded as reasoned, not verified — proving it would mean granting the
permission on a live cluster.)

Both are **escapable** by operator pre-provisioning: a worker that is deployment
infrastructure, like PostgreSQL, is never spawned by the platform and never
created through a governed capability. Neither of these would have stopped the
phase on its own. They are recorded because the design that survives Decision 1
must still satisfy them.

## Decision 4 — Name the taxonomy problem, and leave it for ratification

`_TIER_SUFFICIENCY` routes `IRREVERSIBLE_WRITE` to SEALED, but SEALED is *defined*
in terms of arbitrary or model-generated code. The taxonomy has one axis where
the architecture has two:

- **Code trust** — can the worker be made to run something nobody declared?
- **Consequence** — what does it cost if the declared thing happens?

The rollout restart scores minimum on the first (one typed operation, two
validated parameters, one fixed document, one destination) and high on the
second. The platform currently demands the isolation appropriate to running
attacker-supplied code in order to perform a two-parameter typed `PATCH`.

Consequence is what governance is for, and 9.6 proved governance already contains
it: approval binding, autonomy ceiling A3, blast radius in the type, HIGH risk
derived by the platform, independent assurance. Isolation is what *code trust* is
for.

Separating these is a Constitution-level change (S6). **It is not made here.** It
is recorded so the block is understood correctly: this phase is stuck on a
taxonomy limit as much as on hardware, and only one of those can be fixed by
buying different infrastructure.

## Consequences

- CortexPrime remains **read-only against every real system**, now for a proven
  reason rather than an assumed one.
- Phases 9.1–9.5 are unaffected; the governed read path still works.
- Phase 9.6's code (operation spec, `ProviderBodyBuilder`, typed write door,
  remediation lifecycle) still ships, still unit-verified, still unreachable.
- Nothing was weakened: three tiers, `CONTAINED` unchanged, `IRREVERSIBLE_WRITE`
  unchanged, autonomy unchanged, gateway/authorization/approval/audit/tenant
  isolation untouched. Zero production modules changed in this phase.
- The write remains blocked. The next move is a decision, not a commit:
  1. Different infrastructure (KVM host, or a managed cluster with a gVisor/Kata
     `RuntimeClass`) — satisfies the contract as written, needs no ratification,
     needs hardware this project does not have.
  2. Ratify the axis split in Decision 4 — the only path that ends in a real
     write on the hardware that exists.
  3. Accept a read-only CortexPrime — defensible; an investigator that diagnoses
     correctly and refuses to act beats one that acts unsafely.

## What is verified

30/30 harness checks, executed: real Docker probes, real domain objects observing
real refusals, and the real `BND-PROCESS-SPAWN` rule run against the real module
graph. One claim (the `create pods` privilege comparison) is labelled
`[REASONED]` and deliberately excluded from the pass count.

The decisive measurements are negatives: `sealed_workers_built = 0`,
`provider_calls = 0`, `production_modules_changed = 0`.
