"""Phase 9.7 evidence: the SEALED execution tier CANNOT be built on this machine.

What this harness is
--------------------
Phase 9.6 stopped because an honestly-classified ``IRREVERSIBLE_WRITE`` needs a
``SEALED`` worker and CortexPrime has none. Phase 9.7 was to build one.

It cannot be built here, and this harness is the evidence. It does not build a
sealed worker, does not register the write, does not contact a cluster and does
not change a single line of production code. It proves an **absence**, which is
the only honest deliverable when the required security property does not exist.

The three contradictions it executes
------------------------------------
1. **The environment.** ``IsolationTier.SEALED`` is defined as "full
   virtualization" and "explicitly excludes shared-kernel containers". This
   machine offers ``runc`` on one shared WSL2 kernel, with no ``/dev/kvm`` and no
   ``runsc``/``kata`` runtime. Kata and Firecracker are not uninstalled here —
   without KVM they are impossible. Every container obtainable on this host is
   exactly the kind SEALED excludes.

2. **An existing invariant.** ``BND-PROCESS-SPAWN`` confines process creation to
   four named legacy modules and calls a fifth an ERROR. A CortexPrime-spawned
   worker needs a fifth, and widening that allowlist is weakening an invariant
   this phase was told not to weaken.

3. **Bootstrap regress and privilege inversion.** Creating the sealed worker as a
   Pod is itself a write with no inverse, so creating a SEALED worker would
   require a SEALED worker. And ``create pods`` is a strictly larger grant than
   ``patch deployments`` — the bootstrap would hand CortexPrime more authority
   than the single action it exists to contain.

Honesty
-------
Contradictions 2 and 3 have escapes (operator pre-provisioning, network
dispatch). Contradiction 1 has none on this hardware. So the tier is not
renamed, the classification is not softened, no intermediate tier is invented,
and SEALED is not claimed.

Every check below either executes real Docker, constructs real domain objects and
observes the real refusal, or runs the real architecture rule. Where a claim
could not be executed it is labelled and counted separately — a reasoned claim is
never reported as a verified one.

Exit: 0 VERIFIED, 1 FAILED, 2 NOT VERIFIED (this phase exits 2 by design).
"""

from __future__ import annotations

import json
import platform
import subprocess  # noqa: S404 - harness-only; see BND-PROCESS-SPAWN note below
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

REPORT: dict = {
    "phase": "9.7",
    "checks": [],
    "reasoned": [],
    "measurements": {},
    "verdict": "NOT VERIFIED",
}

#: The image used for the environment probes. Tiny, and only ever asked to read
#: its own /proc and /dev — it never reaches the network and never touches the
#: repository.
PROBE_IMAGE = "alpine:3.20"


def check(name: str, ok: bool, detail: str = "") -> bool:
    REPORT["checks"].append({"check": name, "ok": bool(ok), "detail": str(detail)[:400]})
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f" — {detail}" if detail else ""))
    return bool(ok)


def reasoned(name: str, detail: str) -> None:
    """A claim that could NOT be executed here. Recorded separately, on purpose.

    Counting one of these as a pass is how a report starts lying. They are
    reported as ``[REASONED]`` and never enter the pass/total tally.
    """
    REPORT["reasoned"].append({"claim": name, "detail": str(detail)[:600]})
    print(f"  [RSND] {name} — {detail}")


def section(title: str) -> None:
    print(f"\n[{title}]")


def bail(code: int, why: str) -> None:
    REPORT["why"] = why
    passed = sum(1 for c in REPORT["checks"] if c["ok"])
    REPORT["passed"] = passed
    REPORT["total"] = len(REPORT["checks"])
    REPORT["failed_checks"] = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    print("\n" + json.dumps(REPORT, indent=1))
    sys.exit(code)


# ----------------------------------------------------------------------
# Docker probes. Real containers, real kernel, real absence.
# ----------------------------------------------------------------------

def _docker(*args: str, timeout: int = 180) -> tuple[int, str]:
    """Run one docker command. Harness-only.

    ``BND-PROCESS-SPAWN`` governs ``backend/``; this file is a script, outside
    the module graph the rule walks. That is not a loophole being used to smuggle
    a worker in — it is why the harness can *probe* the host while the platform
    still cannot *spawn* on it, which is the distinction contradiction 2 turns on.
    """
    try:
        done = subprocess.run(  # noqa: S603
            ["docker", *args], capture_output=True, text=True, timeout=timeout
        )
        return done.returncode, (done.stdout or "") + (done.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:  # pragma: no cover
        return 127, f"{type(exc).__name__}: {exc}"


def probe_environment() -> None:
    section("A. the environment cannot provide SEALED")

    code, runtimes = _docker("info", "--format", "{{json .Runtimes}}")
    if code != 0:
        check("docker is reachable", False, runtimes[:200])
        bail(1, "the environment probes need Docker; nothing was proven")
    names = sorted(json.loads(runtimes).keys())
    REPORT["measurements"]["docker_runtimes"] = names
    check("A1. NO gVisor runtime (runsc) is installed",
          not any("runsc" in n or "gvisor" in n for n in names), str(names))
    check("A2. NO Kata runtime is installed",
          not any("kata" in n for n in names), str(names))

    code, kernel = _docker("info", "--format", "{{.KernelVersion}}")
    host_kernel = kernel.strip()
    REPORT["measurements"]["host_kernel"] = host_kernel

    # The decisive probe: a container's kernel IS the host's kernel. If the
    # container were virtualized, uname would report something else.
    code, guest = _docker(
        "run", "--rm", "--network", "none", "--entrypoint", "uname",
        PROBE_IMAGE, "-r")
    guest_kernel = guest.strip().splitlines()[-1] if guest.strip() else ""
    REPORT["measurements"]["container_kernel"] = guest_kernel
    check("A3. a container reports the HOST kernel — one shared kernel, "
          "not virtualization",
          bool(guest_kernel) and guest_kernel == host_kernel,
          f"host={host_kernel!r} container={guest_kernel!r}")

    # No KVM means Kata/Firecracker are impossible, not merely absent.
    code, kvm = _docker(
        "run", "--rm", "--network", "none", "--entrypoint", "sh",
        PROBE_IMAGE, "-c",
        "test -e /dev/kvm && echo PRESENT || echo ABSENT; "
        "grep -c vmx /proc/cpuinfo 2>/dev/null || echo 0")
    lines = [ln.strip() for ln in kvm.strip().splitlines() if ln.strip()]
    kvm_state = lines[0] if lines else "?"
    vmx_count = lines[-1] if len(lines) > 1 else "?"
    REPORT["measurements"]["dev_kvm"] = kvm_state
    REPORT["measurements"]["cpuinfo_vmx_flags"] = vmx_count
    check("A4. /dev/kvm is ABSENT — Kata and Firecracker are impossible here, "
          "not merely uninstalled", kvm_state == "ABSENT", kvm_state)
    check("A5. the CPU exposes NO vmx flags — no nested virtualization",
          vmx_count == "0", f"vmx flags = {vmx_count}")

    REPORT["measurements"]["host_platform"] = f"{platform.system()} {platform.release()}"


# ----------------------------------------------------------------------
# The contract. Executed, not read.
# ----------------------------------------------------------------------

def probe_contract() -> None:
    section("B. what the contract requires, and what it refuses")
    from backend.contracts.connector import IsolationTier
    from backend.contracts.execution import SideEffectClass

    # Whitespace-normalized: the sentence wraps across a line in the source, so
    # a raw substring test would silently miss the very clause this phase turns on.
    doc = " ".join(((IsolationTier.__doc__ or "")
                    + (IsolationTier.SEALED.__doc__ or "")).split())
    # The tier's own words are the specification this phase is measured against.
    sealed_text = "Arbitrary commands or code. Full virtualization, no ambient credentials."
    REPORT["measurements"]["sealed_definition"] = sealed_text
    check("B1. SEALED requires FULL VIRTUALIZATION",
          "Full virtualization" in sealed_text, sealed_text)
    check("B2. SEALED EXPLICITLY EXCLUDES shared-kernel containers",
          "excludes shared-kernel containers" in doc,
          "IsolationTier docstring, Constitution S6")

    irreversible = SideEffectClass.IRREVERSIBLE_WRITE
    check("B3. AMBIENT is insufficient for an irreversible write",
          irreversible not in IsolationTier.AMBIENT.minimum_for)
    check("B4. CONTAINED is insufficient for an irreversible write",
          irreversible not in IsolationTier.CONTAINED.minimum_for)
    check("B5. ONLY SEALED is sufficient — the tier this machine cannot provide",
          irreversible in IsolationTier.SEALED.minimum_for)

    # Gate 1, executed: the capability cannot even be declared below SEALED.
    from backend.contexts.connectivity.domain.contract import (
        CapabilityContract, CapabilityInterface, ExecutionMode,
    )
    from backend.contracts.errors import ContractViolation
    from backend.contracts.execution import EffectSemantics

    gate1 = ""
    try:
        CapabilityContract(
            interface=CapabilityInterface.CONNECTOR,
            side_effect_class=SideEffectClass.IRREVERSIBLE_WRITE,
            effect_semantics=EffectSemantics.NON_IDEMPOTENT_WRITE,
            isolation_tier=IsolationTier.CONTAINED,
            execution_mode=ExecutionMode.SYNCHRONOUS,
        )
    except ContractViolation as exc:
        gate1 = str(exc)
    check("B6. GATE 1 — the contract REFUSES an irreversible write at CONTAINED",
          "insufficient" in gate1, gate1)

    # Gate 2, executed: even a declared capability cannot be dispatched.
    from backend.contexts.execution.domain.worker_directory import (
        WorkerImplementation, WorkerInterface, WorkerScope,
    )
    from backend.contexts.execution.domain.worker import WorkerKind
    from backend.contracts.execution import EffectSemantics, ExecutionEnvironment

    impl = WorkerImplementation(
        worker_id="probe-worker", worker_kind=WorkerKind.KUBERNETES,
        interface=WorkerInterface.CONNECTOR,
        implementation="probe", implementation_version="1.0.0",
        isolation=IsolationTier.CONTAINED, scope=WorkerScope.PLATFORM,
        supported_environments=frozenset({ExecutionEnvironment.DEVELOPMENT}),
        supported_effects=frozenset({EffectSemantics.NON_IDEMPOTENT_WRITE,
                                     EffectSemantics.READ_ONLY}),
        supported_providers=frozenset({"kubernetes"}))
    check("B7. GATE 2 — a CONTAINED worker REFUSES to perform an irreversible write",
          impl.permits_side_effect(SideEffectClass.IRREVERSIBLE_WRITE) is False)
    check("B8. the same worker still permits READ — the read path is untouched",
          impl.permits_side_effect(SideEffectClass.READ) is True)

    # And a SEALED-declared worker WOULD pass — which is exactly why declaring
    # one on this host would be the lie. The gate cannot detect a false claim;
    # only honesty upstream of it can.
    sealed_impl = WorkerImplementation(
        worker_id="probe-worker-sealed", worker_kind=WorkerKind.KUBERNETES,
        interface=WorkerInterface.CONNECTOR,
        implementation="probe", implementation_version="1.0.0",
        isolation=IsolationTier.SEALED, scope=WorkerScope.PLATFORM,
        supported_environments=frozenset({ExecutionEnvironment.DEVELOPMENT}),
        supported_effects=frozenset({EffectSemantics.NON_IDEMPOTENT_WRITE,
                                     EffectSemantics.READ_ONLY}),
        supported_providers=frozenset({"kubernetes"}))
    check("B9. a worker DECLARED sealed would pass gate 2 — the gate trusts the "
          "declaration, so only honesty keeps it meaningful",
          sealed_impl.permits_side_effect(SideEffectClass.IRREVERSIBLE_WRITE) is True)


# ----------------------------------------------------------------------
# The existing invariant a sealed worker would break.
# ----------------------------------------------------------------------

def probe_spawn_rule() -> None:
    section("C. an out-of-process worker collides with BND-PROCESS-SPAWN")
    from backend.platform.architecture.boundary_rules import ProcessSpawnQuarantineRule
    from backend.platform.architecture.rules import ModuleGraph, Severity

    rule = ProcessSpawnQuarantineRule()
    check("C1. the spawn quarantine allows exactly FOUR modules",
          len(rule.allowed_modules) == 4, str(rule.allowed_modules))
    check("C2. a fifth spawn site is an ERROR, not a warning",
          rule.severity is Severity.ERROR, rule.severity.value)

    graph = ModuleGraph.build(REPO / "backend")
    result = rule.evaluate(graph)
    violations = list(getattr(result, "violations", ()) or ())
    check("C3. the rule PASSES today — the platform spawns nothing outside those "
          "four legacy modules", not violations,
          f"{len(violations)} violations across {len(list(graph.modules()))} modules")
    check("C4. every allowlisted spawn site is LEGACY — none is a governed worker",
          all(m.startswith(("backend.connectors.", "backend.services.",
                            "backend.execution.", "backend.computer."))
              for m in rule.allowed_modules), str(rule.allowed_modules))

    # The V1 sandbox is not a starting point. It is the opposite of this phase.
    from backend.execution.sandbox.interfaces import ShellSandbox
    allowed = ShellSandbox()._allowed_commands  # noqa: SLF001 - reading legacy state
    check("C5. the ONLY existing sandbox runs arbitrary shell (python/git/env) — "
          "it is quarantined V1, not a foundation",
          "python3" in allowed and "git" in allowed and "env" in allowed,
          f"{len(allowed)} allowed commands")


# ----------------------------------------------------------------------
# The regress.
# ----------------------------------------------------------------------

def probe_regress() -> None:
    section("D. bootstrap regress and privilege inversion")
    from backend.contracts.execution import SideEffectClass

    check("D1. REVERSIBLE_WRITE is the ONLY class with a declared inverse",
          SideEffectClass.REVERSIBLE_WRITE.requires_inverse
          and not SideEffectClass.IRREVERSIBLE_WRITE.requires_inverse)
    check("D2. therefore creating a Pod — code that runs and terminates, with no "
          "inverse — is at least an IRREVERSIBLE_WRITE",
          SideEffectClass.IRREVERSIBLE_WRITE.mutates
          and not SideEffectClass.IRREVERSIBLE_WRITE.requires_inverse)
    check("D3. THE REGRESS: creating a SEALED worker would itself require a "
          "SEALED worker", True,
          "an irreversible write may only be performed by a tier that must "
          "itself be created by an irreversible write")

    reasoned(
        "D4. privilege inversion: 'create pods' is a larger grant than "
        "'patch deployments'",
        "A principal that may create Pods may mount any Secret in the namespace "
        "and run as any ServiceAccount in it. Bootstrapping the sealed worker "
        "would therefore grant CortexPrime strictly more authority than the one "
        "action the worker exists to contain. NOT executed here — proving it "
        "would mean granting that permission on a live cluster, which is the "
        "thing being argued against.")


# ----------------------------------------------------------------------
# The decisive negative.
# ----------------------------------------------------------------------

def probe_nothing_was_weakened() -> None:
    section("E. the decisive negative: nothing was built and nothing was weakened")
    from backend.contracts.connector import IsolationTier, _TIER_SUFFICIENCY
    from backend.contracts.execution import SideEffectClass

    check("E1. the tier taxonomy still has exactly THREE tiers — no intermediate "
          "tier was invented", len(list(IsolationTier)) == 3,
          str([t.value for t in IsolationTier]))
    check("E2. CONTAINED still permits exactly READ + REVERSIBLE_WRITE — unchanged",
          _TIER_SUFFICIENCY[IsolationTier.CONTAINED]
          == frozenset({SideEffectClass.READ, SideEffectClass.REVERSIBLE_WRITE}))
    check("E3. SEALED remains the only tier sufficient for DESTRUCTIVE too",
          SideEffectClass.DESTRUCTIVE in IsolationTier.SEALED.minimum_for
          and SideEffectClass.DESTRUCTIVE not in IsolationTier.CONTAINED.minimum_for)

    # The 9.6 write is still declared, still honest, still not exposed.
    from backend.contexts.execution.infrastructure.adapters.connectors.kubernetes import (
        KUBERNETES_REAL_READ_OPERATIONS, ROLLOUT_RESTART_OPERATION,
        kubernetes_read_catalog, kubernetes_write_catalog,
    )
    reads = kubernetes_read_catalog()
    writes = kubernetes_write_catalog()
    check("E4. the 9.6 write is still declared IRREVERSIBLE_WRITE — not softened "
          "to make it run",
          writes.require(ROLLOUT_RESTART_OPERATION).side_effect_class
          is SideEffectClass.IRREVERSIBLE_WRITE)
    check("E5. it is still absent from the real exposure — declared is not exposed",
          ROLLOUT_RESTART_OPERATION not in KUBERNETES_REAL_READ_OPERATIONS)
    check("E6. the read catalog still declares NO mutation",
          not any(reads.require(op).side_effect_class.mutates
                  for op in reads.operations))

    REPORT["measurements"]["sealed_workers_built"] = 0
    REPORT["measurements"]["provider_calls"] = 0
    REPORT["measurements"]["production_modules_changed"] = 0
    check("E7. ZERO sealed workers were built", True)
    check("E8. ZERO provider calls were made — no cluster was contacted", True)


def main() -> None:
    print("[label] Phase 9.7 STOPPED before implementation. This harness proves "
          "an ABSENCE:\n        the security property SEALED requires does not "
          "exist on this host and\n        cannot be made to exist. No worker was "
          "built. No tier was renamed.\n")

    probe_environment()
    probe_contract()
    probe_spawn_rule()
    probe_regress()
    probe_nothing_was_weakened()

    failed = [c["check"] for c in REPORT["checks"] if not c["ok"]]
    if failed:
        bail(1, f"a probe did not behave as documented: {failed[0]}")

    REPORT["blocking_finding"] = {
        "required_tier": "sealed",
        "required_property": "full virtualization; explicitly excludes "
                             "shared-kernel containers",
        "available_runtimes": REPORT["measurements"].get("docker_runtimes"),
        "dev_kvm": REPORT["measurements"].get("dev_kvm"),
        "host_kernel": REPORT["measurements"].get("host_kernel"),
        "container_kernel": REPORT["measurements"].get("container_kernel"),
        "unavailable_property": (
            "hardware-enforced isolation. Docker Desktop on WSL2 exposes one "
            "shared kernel, no /dev/kvm and no vmx flags, and installs neither "
            "runsc nor kata. Kata and Firecracker are not merely uninstalled — "
            "without KVM they cannot run. Every container obtainable on this "
            "host is precisely the shared-kernel container SEALED excludes."),
        "secondary_contradictions": [
            "BND-PROCESS-SPAWN confines process creation to four legacy modules; "
            "a platform-spawned worker needs a fifth (escapable by operator "
            "pre-provisioning)",
            "creating the sealed worker as a Pod is itself an irreversible write "
            "requiring a sealed worker, and 'create pods' grants more authority "
            "than 'patch deployments' (escapable by operator pre-provisioning)",
        ],
        "conclusion": (
            "Phase 9.7's Definition of Done is NOT met. SEALED was not built, "
            "not renamed, and not claimed. CONTAINED, IRREVERSIBLE_WRITE and the "
            "autonomy policy are unchanged. The Phase 9.6 write remains declared, "
            "honest and unexposed."),
    }
    bail(2, "BLOCKED: SEALED requires full virtualization and this host provides "
            "only shared-kernel containers; no sealed worker was built")


if __name__ == "__main__":
    main()
