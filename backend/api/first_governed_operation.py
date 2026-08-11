"""The first concrete provider operation, declared and commissioned.

What this module is, and what it deliberately is not
------------------------------------------------------
It is **not an execution path.** There is exactly one of those —
``SecureCapabilityInvocationGateway.invoke`` — and adding a second, however
convenient, would mean two places that decide whether a provider call may
happen. Nothing here calls an adapter, a channel or a transport.

What it is: the declaration of *which* operation is the first one this platform
will really perform, the check that the operation is what it is claimed to be,
and the governed commissioning of the worker that performs it.

    declare      one operation, named, with the reason it is this one
    verify       the catalog agrees: same method, same effect class
    commission   REGISTERED → VALIDATED → ENABLED, trust established separately
    execute      through the existing gateway. Not from here.

Why ``repository.get_repository``
-----------------------------------
Every property that makes an operation safe to be first, this one has:

* **READ.** It creates nothing, changes nothing, and a duplicate delivery caused
  by an unknown outcome is another read.
* **Sufficient isolation.** ``ConnectorAdapter`` runs in-process, which ADR-005
  calls ``AMBIENT`` — "read-only calls to declared APIs with process-level
  scoped credentials". ``AMBIENT`` is sufficient for ``READ`` and for nothing
  else, so this operation is permitted *by the existing rule*, not by an
  exception carved for it.
* **Declared, not assembled.** The URL comes from the catalog's path template
  with validated parameters. There is no argument that reaches a URL.
* **Small, bounded response.** One repository object against a declared byte
  ceiling.

The two ``IRREVERSIBLE_WRITE`` operations in the same catalog —
``create_issue`` and ``create_issue_comment`` — remain **refused** by worker
selection with ``isolation_insufficient``, and this module does not touch that.
That refusal is correct: an in-process adapter genuinely does not provide the
containment an irreversible write into somebody's repository requires. Making
the first governed operation a read is what lets the refusal stay in place
rather than becoming the thing standing between the platform and a demo.

``assert_write_refusal_intact`` exists so that stays true. It is a check, not a
comment: if a future change gives the connector an isolation tier that would
permit the writes, this raises at commissioning time and names what changed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

from backend.contracts.connector import IsolationTier
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import SideEffectClass
from backend.contracts.identity import PrincipalRef
from backend.contexts.execution.application.worker_commissioning import (
    CommissioningReport,
    WorkerCommissioning,
)
from backend.contexts.execution.domain.worker_directory import WorkerTrust

__all__ = [
    "GovernedOperationDeclaration",
    "FIRST_GOVERNED_OPERATION",
    "OperationVerification",
    "verify_declared_operation",
    "assert_write_refusal_intact",
    "commission_first_operation",
]

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class GovernedOperationDeclaration:
    """One provider operation this platform is prepared to perform.

    A declaration, not a permission: a capability still has to be registered, a
    binding still has to resolve to it, and authorization still has to say yes.
    What this pins is the *shape* — so that "the first governed operation" means
    something specific enough to check rather than a name in a document.
    """

    provider_id: str
    worker_id: str
    operation: str
    method: str
    side_effect: SideEffectClass
    minimum_isolation: IsolationTier
    rationale: str

    def to_dict(self) -> dict:
        return {
            "provider_id": self.provider_id,
            "worker_id": self.worker_id,
            "operation": self.operation,
            "method": self.method,
            "side_effect": self.side_effect.value,
            "minimum_isolation": self.minimum_isolation.value,
            "rationale": self.rationale,
        }


FIRST_GOVERNED_OPERATION = GovernedOperationDeclaration(
    provider_id="github",
    worker_id="github-connector",
    operation="repository.get_repository",
    method="GET",
    side_effect=SideEffectClass.READ,
    minimum_isolation=IsolationTier.AMBIENT,
    rationale=(
        "A read against a declared path template, with a bounded response and "
        "no state change. AMBIENT isolation is sufficient for READ under "
        "ADR-005, so this is permitted by the existing rule rather than by an "
        "exception; the catalog's two irreversible writes stay refused."
    ),
)


@dataclass(frozen=True)
class OperationVerification:
    """Whether the catalog agrees with the declaration. Facts, and the mismatch."""

    operation: str
    matches: bool
    problems: tuple = ()
    declared_digest: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "operation": self.operation,
            "matches": self.matches,
            "problems": list(self.problems),
            "declared_digest": self.declared_digest,
        }


def verify_declared_operation(
    catalog: Any, declaration: GovernedOperationDeclaration = FIRST_GOVERNED_OPERATION
) -> OperationVerification:
    """Check the catalog against the declaration. Two sources, one answer.

    The catalog is what the adapter actually executes; the declaration is what
    governance signed off. Comparing them is the point — a catalog edited to
    make ``get_repository`` a POST, or to relax its effect class, would silently
    change what was approved, and this is where that becomes visible.
    """
    problems: list = []
    try:
        spec = catalog.require(declaration.operation)
    except Exception as exc:  # noqa: BLE001 - an absent operation is a mismatch
        return OperationVerification(
            operation=declaration.operation,
            matches=False,
            problems=(f"the catalog has no operation {declaration.operation!r}: {exc}",),
        )

    if spec.method != declaration.method:
        problems.append(
            f"method is {spec.method!r}; the declaration says {declaration.method!r}"
        )
    if spec.side_effect_class is not declaration.side_effect:
        problems.append(
            f"side effect is {spec.side_effect_class.value!r}; the declaration "
            f"says {declaration.side_effect.value!r}"
        )
    if "{" not in (spec.path_template or ""):
        # A path with no parameters is either wrong for this operation or a sign
        # the template was replaced with a literal URL, which is the thing the
        # catalog exists to prevent.
        problems.append(
            "the path is not a template; a literal path means the URL stopped "
            "being derived from validated parameters"
        )
    return OperationVerification(
        operation=declaration.operation,
        matches=not problems,
        problems=tuple(problems),
        declared_digest=spec.digest,
    )


def assert_write_refusal_intact(
    catalog: Any, entry: Any, *, declaration: GovernedOperationDeclaration = FIRST_GOVERNED_OPERATION
) -> tuple:
    """Confirm the irreversible writes are still refused. Returns their names.

    This is the check that stops "make the first operation work" from quietly
    becoming "make every operation work". It reads the worker's actual isolation
    tier and asks the domain whether that tier permits each operation's effect
    class; if a write has become permitted, it raises and says which.

    Deliberately consults ``WorkerImplementation.permits_side_effect`` rather
    than re-implementing the comparison: there is one rule about which tier
    permits which effect, it lives in the domain, and a second copy here would
    be a second rule to keep in step.
    """
    implementation = getattr(entry, "implementation", entry)
    refused: list = []
    permitted_writes: list = []
    for name in catalog.operations:
        spec = catalog.require(name)
        if spec.side_effect_class is declaration.side_effect:
            continue
        if implementation.permits_side_effect(spec.side_effect_class):
            permitted_writes.append((name, spec.side_effect_class.value))
        else:
            refused.append(name)

    if permitted_writes:
        raise ContractViolation(
            "the connector's isolation tier now permits "
            + ", ".join(f"{n} ({e})" for n, e in permitted_writes)
            + ". These were refused with isolation_insufficient, and an "
            "in-process adapter does not provide the containment an "
            "irreversible write into somebody else's repository requires. If "
            "the adapter genuinely runs contained now, say so deliberately -- "
            "this check exists so it cannot happen as a side effect."
        )
    return tuple(sorted(refused))


def commission_first_operation(
    connectivity: Any,
    context: Any,
    *,
    tenant_id: str,
    by: PrincipalRef,
    reason: str,
    trust: WorkerTrust = WorkerTrust.VERIFIED,
    declaration: GovernedOperationDeclaration = FIRST_GOVERNED_OPERATION,
    available: bool = True,
    expected_digest: Optional[str] = None,
) -> dict:
    """Verify, guard, then commission. Returns what was checked and what moved.

    Order matters and is the whole design: the catalog is verified **before**
    anything is enabled, and the write refusal is confirmed **before** the
    worker becomes selectable. Commissioning first and checking afterwards would
    mean a window in which a worker that should not have been enabled was.

    Nothing here contacts GitHub. A commissioned worker is one the platform is
    willing to select; whether GitHub answers is availability, and availability
    is observed, not asserted.
    """
    catalog = connectivity.catalogs.get(declaration.provider_id)
    if catalog is None:
        raise ContractViolation(
            f"no {declaration.provider_id} catalog is wired; the first governed "
            "operation cannot be commissioned against a provider this process "
            "does not have"
        )

    verification = verify_declared_operation(catalog, declaration)
    if not verification.matches:
        raise ContractViolation(
            f"the catalog does not match the declared operation: "
            + "; ".join(verification.problems)
        )

    entry = connectivity.directory.entry(
        context, worker_id=declaration.worker_id, tenant_id=tenant_id
    )
    if entry is None:
        raise ContractViolation(
            f"worker {declaration.worker_id} is not registered for {tenant_id}"
        )
    still_refused = assert_write_refusal_intact(catalog, entry, declaration=declaration)

    if not entry.implementation.permits_side_effect(declaration.side_effect):
        raise ContractViolation(
            f"the connector's isolation tier does not permit "
            f"{declaration.side_effect.value}; the first governed operation "
            "cannot be commissioned against a worker that may not perform it"
        )

    commissioning = WorkerCommissioning(
        directory=connectivity.directory, metrics=connectivity.metrics
    )
    report: CommissioningReport = commissioning.commission(
        context,
        worker_id=declaration.worker_id,
        tenant_id=tenant_id,
        trust=trust,
        by=by,
        reason=reason,
        available=available,
        expected_digest=expected_digest,
    )

    log.info(
        "first governed operation commissioned: %s via %s (%d write operation(s) "
        "still refused by isolation)",
        declaration.operation,
        declaration.worker_id,
        len(still_refused),
    )
    return {
        "declaration": declaration.to_dict(),
        "verification": verification.to_dict(),
        "still_refused_by_isolation": list(still_refused),
        "commissioning": report.to_dict(),
        "execution_path": (
            "SecureCapabilityInvocationGateway.invoke -- the only one. This "
            "module commissions and verifies; it never invokes."
        ),
    }
