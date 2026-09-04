# Phase 9.7 — Verification Report

**Phase:** SEALED execution tier
**Date:** 2026-09-04
**Branch:** `phase-1-foundation`
**ADR:** ADR-087
**Harness:** `scripts/phase97_sealed_execution_harness.py`
**Implementation map:** `docs/PHASE_9_7_IMPLEMENTATION_MAP.md`

---

## Definition of Done: **NOT MET**

Phase 9.7 required a real SEALED execution boundary. **It was not built, and no
production code was written.**

The security property SEALED requires — *full virtualization; explicitly excludes
shared-kernel containers* — does not exist on this machine and cannot be made to
exist on it. Per the phase's own honesty rule, the phase stopped. SEALED was not
claimed, `CONTAINED` was not renamed, `IRREVERSIBLE_WRITE` was not weakened, the
autonomy policy was not touched, and no intermediate tier was invented.

Decisive measurements, all negatives:

```
sealed_workers_built        = 0
provider_calls              = 0
production_modules_changed  = 0
```

---

## The unavailable property, stated exactly

**Hardware-enforced isolation (full virtualization).**

`IsolationTier.SEALED` is defined as *"Arbitrary commands or code. Full
virtualization, no ambient credentials,"* and the enum docstring states that
SEALED *"explicitly excludes shared-kernel containers."*

Executed against real Docker, in real containers — not asserted from source:

| Probe | Result |
|---|---|
| Container runtimes installed | `io.containerd.runc.v2`, `nvidia`, `runc` |
| gVisor (`runsc`) | **absent** |
| Kata | **absent** |
| Host kernel | `6.6.87.2-microsoft-standard-WSL2` |
| Kernel reported inside a container | `6.6.87.2-microsoft-standard-WSL2` — identical |
| `/dev/kvm` inside a container | **ABSENT** |
| `vmx` flags in `/proc/cpuinfo` | **0** |

A container here reports the host's kernel because it *is* the host's kernel.
Without `/dev/kvm` and without `vmx` exposure, Kata Containers and Firecracker
are impossible rather than merely uninstalled. gVisor is absent, and is a
user-space kernel rather than hardware-enforced isolation regardless.

Every container obtainable on this host is precisely the shared-kernel container
SEALED excludes. No configuration, installation or workaround changes that.

---

## Results

**Harness:** 30/30 checks passed, plus 1 claim labelled `[REASONED]` and
deliberately excluded from the count. **Exit code 2 (NOT VERIFIED) — by design.**
**Architecture gate:** PASS — 35 passed, 0 failed, 6 skipped, 1181 modules.
**Regression:** unchanged from Phase 9.6 (no production code was modified).

### A. The environment cannot provide SEALED — [BLOCKED]

- [VERIFIED] No gVisor runtime is installed.
- [VERIFIED] No Kata runtime is installed.
- [VERIFIED] A container reports the **host** kernel — one shared kernel, not
  virtualization.
- [VERIFIED] `/dev/kvm` is absent, so Kata and Firecracker cannot run here.
- [VERIFIED] The CPU exposes no `vmx` flags — no nested virtualization.

**[BLOCKED] A SEALED worker.** The property is unavailable and unobtainable.

### B. What the contract requires, and what it refuses — [VERIFIED]

- [VERIFIED] SEALED requires full virtualization.
- [VERIFIED] SEALED explicitly excludes shared-kernel containers.
- [VERIFIED] `AMBIENT` and `CONTAINED` are both insufficient for an irreversible
  write; only SEALED is sufficient.
- [VERIFIED] **Gate 1** — `CapabilityContract` refuses an irreversible write at
  CONTAINED: *"isolation tier 'contained' is insufficient for a
  'irreversible_write' capability."* Constructed and observed, not read.
- [VERIFIED] **Gate 2** — a CONTAINED worker refuses to perform an irreversible
  write, and still permits READ.
- [VERIFIED] A worker *declared* SEALED **would** pass gate 2. The gate trusts the
  declaration; only honesty upstream of it keeps the gate meaningful. This is
  precisely why the tier was not claimed.

### C. An out-of-process worker collides with `BND-PROCESS-SPAWN` — [VERIFIED]

- [VERIFIED] The spawn quarantine allows exactly **four** modules.
- [VERIFIED] A fifth spawn site is severity `ERROR`, not a warning.
- [VERIFIED] The rule passes today: **0 violations across 1181 modules.**
- [VERIFIED] All four allowlisted sites are legacy; none is a governed worker.
- [VERIFIED] The only existing sandbox (`ShellSandbox`, 22 allowed commands
  including `python3`, `git`, `env`) runs arbitrary shell. It is quarantined V1
  and is the opposite of this phase, not a foundation for it.

**Escapable** by operator pre-provisioning; recorded, not decisive.

### D. Bootstrap regress and privilege inversion — [VERIFIED] / [REASONED]

- [VERIFIED] `REVERSIBLE_WRITE` is the only class with a declared inverse.
- [VERIFIED] Creating a Pod — code that runs and terminates, with no inverse — is
  at least an `IRREVERSIBLE_WRITE`.
- [VERIFIED] **The regress:** creating a SEALED worker would itself require a
  SEALED worker.
- [REASONED — NOT VERIFIED] `create pods` is a strictly larger grant than
  `patch deployments`: it permits mounting any Secret in the namespace and
  assuming any ServiceAccount in it, so the bootstrap would grant CortexPrime
  more authority than the action the worker exists to contain. **Not executed** —
  proving it would mean granting that permission on a live cluster, which is the
  thing being argued against. Excluded from the pass count.

**Escapable** by operator pre-provisioning; recorded, not decisive.

### E. Nothing was built and nothing was weakened — [VERIFIED]

- [VERIFIED] The taxonomy still has exactly **three** tiers — no intermediate
  tier was invented.
- [VERIFIED] `CONTAINED` still permits exactly `READ` + `REVERSIBLE_WRITE`.
- [VERIFIED] SEALED remains the only tier sufficient for `DESTRUCTIVE` too.
- [VERIFIED] The Phase 9.6 write is still declared `IRREVERSIBLE_WRITE` — not
  softened to make it run.
- [VERIFIED] It is still absent from the real exposure — declared is not exposed.
- [VERIFIED] The Kubernetes read catalog still declares no mutation.
- [VERIFIED] Zero sealed workers were built.
- [VERIFIED] Zero provider calls were made; no cluster was contacted.

---

## Not verified / deferred

Every item below was to be proven *by* the sealed worker. With no worker, none
was attempted, and none is claimed:

- [BLOCKED] A. sealed worker creation — B. worker identity — C. capability
  binding — D. tenant binding — E. credential isolation — F. network restriction
  — G. filesystem isolation — H. process isolation — I. resource limits
- [BLOCKED] N. lease/fencing of a sealed worker — O. crash recovery (all 11
  scenarios) — P. credential failure modes — Q. cross-tenant isolation of worker
  state — W. worker termination — X. provider evidence from a sealed worker
- [DEFERRED] The Phase 9.6 rollout restart. Still declared, still honest, still
  unexposed, still never executed.
- [DEFERRED] A Kubernetes TokenRequest credential adapter. The broker is ready
  for one; building it without a worker to isolate would be building a component
  with no consumer.
- [NOT VERIFIED] k3s NetworkPolicy enforcement and Pod Security Admission
  `restricted` in k3d. Both are expected to work and neither was tested, because
  neither changes the outcome: they are properties of a boundary that cannot be
  SEALED regardless.

**No new architecture fitness rule was added.** A rule is justified only when an
invariant is otherwise unenforced; the invariants in question (`BND-PROCESS-SPAWN`,
the two isolation gates) are already enforced and already pass. Adding
`BND-SEALED-*` rules with no sealed worker to govern would be cosmetic.

---

## Honest summary

The whole phase reduces to one sentence: **CortexPrime cannot build the boundary
its own contract demands, because this machine has one kernel and no way to get a
second one.**

Everything downstream of that — the credential broker, the worker plug point, the
fencing, the audit chain — is already built and already correct, and would be
reused rather than rebuilt the moment a real boundary exists. The gap is not
software.

The one thing worth deliberating is in ADR-087 Decision 4: the tier taxonomy
demands the isolation appropriate to *arbitrary attacker-supplied code* in order
to perform a two-parameter typed `PATCH`. That may be the right rule. It may also
be the reason CortexPrime never writes anything. Resolving it is a ratification
decision, and it was deliberately not made here.
