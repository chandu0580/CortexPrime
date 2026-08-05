"""Constitutional invariants I1-I8 as executable fitness functions.

The Constitution says: *"Violation of any invariant is a defect, regardless of
tests passing."* That is only meaningful if violating one makes something fail.

Each invariant here is an **active probe**, not an assertion about the code's
shape. A probe constructs a state that violates the invariant and asserts the
system refuses it. That matters: a structural check confirms a guard is
*present*; a probe confirms it *works*. If someone deletes the digest comparison
in the dispatcher, a structural check still sees the module and passes. The
probe does not.

Honest status reporting
-----------------------
Not every invariant is enforced yet. Each check declares its
:class:`InvariantStatus`, and an unenforced invariant reports as **skipped, not
passed** -- because a skip recorded as a pass is exactly how an unenforced
invariant comes to look enforced.

The CI gate blocks only on an ``ENFORCED`` invariant failing. Unenforced ones
appear in the report with their tracking PR, so the gap is visible without being
permanently red.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Mapping, Optional

from backend.platform.architecture.rules import (
    ModuleGraph,
    RuleResult,
    Severity,
    Violation,
)

__all__ = [
    "InvariantStatus",
    "InvariantCheck",
    "constitutional_invariants",
]


class InvariantStatus(str, Enum):
    """How completely an invariant is enforced today."""

    ENFORCED = "enforced"
    """A probe exists and the invariant holds. Failure blocks a merge."""

    PARTIAL = "partial"
    """Enforced at one layer but not end to end. Failure blocks a merge."""

    NOT_ENFORCED = "not_enforced"
    """No enforcement point exists yet. Reported, never blocking."""

    @property
    def is_gated(self) -> bool:
        return self in {InvariantStatus.ENFORCED, InvariantStatus.PARTIAL}


@dataclass(frozen=True)
class InvariantCheck:
    """One constitutional invariant, with a probe that proves it holds.

    ``probe`` returns ``None`` when the invariant holds, or a string explaining
    the breach. It is given the module graph so structural invariants can use
    it; behavioural probes ignore it.
    """

    invariant_id: str
    statement: str
    status: InvariantStatus
    probe: Optional[Callable[[ModuleGraph], Optional[str]]] = None
    tracking: Optional[str] = None
    """Where enforcement is being built, for NOT_ENFORCED invariants."""

    @property
    def rule_id(self) -> str:
        return f"INV-{self.invariant_id}"

    @property
    def description(self) -> str:
        return self.statement

    def evaluate(self, graph: ModuleGraph) -> RuleResult:
        if self.status is InvariantStatus.NOT_ENFORCED or self.probe is None:
            return RuleResult(
                rule_id=self.rule_id,
                description=self.statement,
                skipped=True,
                skip_reason=(
                    f"no enforcement point exists yet"
                    + (f"; tracked by {self.tracking}" if self.tracking else "")
                ),
            )

        try:
            breach = self.probe(graph)
        except Exception as exc:  # noqa: BLE001 - a probe that crashes is a failure
            return RuleResult(
                rule_id=self.rule_id,
                description=self.statement,
                violations=(
                    Violation(
                        rule_id=self.rule_id,
                        severity=Severity.ERROR,
                        module=self.invariant_id,
                        detail=f"probe raised {type(exc).__name__}: {exc}",
                    ),
                ),
                modules_checked=1,
            )

        if breach is None:
            return RuleResult(
                rule_id=self.rule_id, description=self.statement, modules_checked=1
            )
        return RuleResult(
            rule_id=self.rule_id,
            description=self.statement,
            violations=(
                Violation(
                    rule_id=self.rule_id,
                    severity=Severity.ERROR,
                    module=self.invariant_id,
                    detail=breach,
                ),
            ),
            modules_checked=1,
        )


# ======================================================================
# Probes
# ======================================================================


def _probe_i3_audit_append_only(_: ModuleGraph) -> Optional[str]:
    """I3 -- the audit trail is append-only and independently verifiable.

    Probes all three defect classes, including deletion, which a naive link
    check cannot see.
    """
    import dataclasses

    from backend.contracts import AuditEventKind, TenantRef, TenantScope
    from backend.platform.audit import (
        AuditRuntime,
        AuditStore,
        InMemoryAuditStore,
        verify_chain,
    )

    for forbidden in ("update", "delete", "remove", "replace"):
        if hasattr(AuditStore, forbidden):
            return f"AuditStore exposes {forbidden!r}; the trail is mutable"

    scope = TenantScope(tenant=TenantRef(tenant_id="invariant-probe"))
    runtime = AuditRuntime(InMemoryAuditStore())
    for index in range(6):
        runtime.record(
            AuditEventKind.EXECUTION_REFUSED, scope, subject_reference=f"probe-{index}"
        )

    if not verify_chain(runtime).ok:
        return "a clean chain failed verification (false positive)"

    records = list(runtime.query())

    edited = list(records)
    edited[2] = dataclasses.replace(edited[2], detail={"tampered": True})
    if verify_chain(runtime, edited).ok:
        return "an edited audit record passed chain verification"

    deleted = [record for index, record in enumerate(records) if index != 3]
    if verify_chain(runtime, deleted).ok:
        return "a deleted audit record was not detected (sequence gap missed)"

    reordered = list(records)
    reordered[1], reordered[2] = reordered[2], reordered[1]
    if verify_chain(runtime, reordered).ok:
        return "reordered audit records passed chain verification"

    return None


def _probe_i6_tenant_identity(_: ModuleGraph) -> Optional[str]:
    """I6 -- tenant identity travels with every scoped record.

    Enforced at the contract layer: metadata and audit records cannot be
    constructed without a tenant scope. Storage-layer enforcement is partial
    until PR-09, which is why this invariant is PARTIAL.
    """
    from backend.contracts import ContractViolation, TenantRef, TenantScope
    from backend.platform.events import EventMetadata

    try:
        EventMetadata.create(aggregate_id="a", aggregate_type="mission")  # type: ignore[call-arg]
    except TypeError:
        pass
    else:
        return "event metadata was constructed without a tenant scope"

    try:
        TenantRef(tenant_id="   ")
    except ContractViolation:
        pass
    else:
        return "a blank tenant id was accepted"

    scope = TenantScope(tenant=TenantRef(tenant_id="probe"))
    metadata = EventMetadata.create(
        aggregate_id="a", aggregate_type="mission", scope=scope
    )
    if metadata.scope.tenant.tenant_id != "probe":
        return "tenant identity did not survive metadata construction"
    return None


def _probe_i7_memory_may_not_authorize(_: ModuleGraph) -> Optional[str]:
    """I7 -- experiential memory may propose; it may never authorize."""
    from backend.contracts import (
        ContractViolation,
        KnowledgeAuthority,
        KnowledgeItem,
        KnowledgeKind,
    )
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    try:
        KnowledgeItem(
            item_id="probe",
            kind=KnowledgeKind.EXPERIENTIAL,
            authority=KnowledgeAuthority.AUTHORITATIVE,
            content="it worked last time",
            recorded_at=now,
        )
    except ContractViolation:
        pass
    else:
        return "experiential knowledge was accepted as authoritative"

    try:
        KnowledgeItem(
            item_id="probe",
            kind=KnowledgeKind.EVIDENCE_DERIVED,
            authority=KnowledgeAuthority.AUTHORITATIVE,
            content="a prior conclusion",
            recorded_at=now,
        )
    except ContractViolation:
        pass
    else:
        return "a prior conclusion was accepted as authoritative"

    advisory = KnowledgeItem(
        item_id="probe",
        kind=KnowledgeKind.EXPERIENTIAL,
        authority=KnowledgeAuthority.ADVISORY,
        content="it worked last time",
        recorded_at=now,
        confidence=0.5,
    )
    if advisory.authority is not KnowledgeAuthority.ADVISORY:
        return "advisory experiential knowledge was rejected (false positive)"
    return None


def _probe_platform_never_authorizes(_: ModuleGraph) -> Optional[str]:
    """The Constitution's second catastrophic failure mode.

    Not numbered as an invariant, but named in the Constitution as one of the
    two properties every failure runs through: the system must never authorize
    itself.
    """
    from datetime import datetime, timezone

    from backend.contracts import (
        ApprovalDecision,
        ApprovalOutcome,
        ContractViolation,
        PrincipalKind,
        PrincipalRef,
    )

    platform = PrincipalRef(principal_id="cortexprime", kind=PrincipalKind.PLATFORM)
    if platform.can_approve:
        return "a platform principal reports that it can approve"

    try:
        ApprovalDecision(
            request_id="probe",
            artifact_id="probe",
            outcome=ApprovalOutcome.GRANTED,
            decided_at=datetime.now(timezone.utc),
            decided_by=platform,
        )
    except ContractViolation:
        return None
    return "the platform granted its own approval"


def _probe_contracts_immutable(graph: ModuleGraph) -> Optional[str]:
    """Contracts are frozen. Mutable shared vocabulary is a data race."""
    import dataclasses

    from backend.contracts import contract_registry

    for name, contract_type in contract_registry().items():
        if not dataclasses.is_dataclass(contract_type):
            return f"{name} is not a dataclass"
        if not contract_type.__dataclass_params__.frozen:
            return f"{name} is not frozen; contracts must be immutable"
    return None


# ======================================================================
# Registry
# ======================================================================


def constitutional_invariants(
    probes: Optional[Mapping[str, Callable[[ModuleGraph], Optional[str]]]] = None,
) -> tuple[InvariantCheck, ...]:
    """Every invariant from the Phase 0 Constitution, with current status.

    ``probes`` supplies implementations this package cannot own. I2's
    enforcement lives in ``backend.services``, and Constitution S10 forbids
    ``platform/`` from importing a bounded context or service — so the probe for
    it is registered by the layer that may import those, rather than exempting
    this module from the rule it enforces.

    An invariant whose probe is not supplied reports as skipped, naming what is
    missing, so an unregistered probe cannot be mistaken for a pass.
    """
    supplied = dict(probes or {})

    def _probe_for(invariant_id: str) -> Optional[Callable]:
        return supplied.get(invariant_id)

    i2_probe = _probe_for("I2")

    return (
        InvariantCheck(
            invariant_id="I1",
            statement="No execution occurs without a policy decision recorded before it",
            status=InvariantStatus.NOT_ENFORCED,
            tracking="PR-29/PR-30 (policy interface and pre-execution persistence)",
        ),
        InvariantCheck(
            invariant_id="I2",
            statement=(
                "No approved action executes with a payload whose hash differs "
                "from the approved one"
            ),
            status=(
                InvariantStatus.ENFORCED if i2_probe else InvariantStatus.NOT_ENFORCED
            ),
            probe=i2_probe,
            tracking=(
                None
                if i2_probe
                else "probe not registered; supply it via constitutional_invariants(probes=...)"
            ),
        ),
        InvariantCheck(
            invariant_id="I3",
            statement="The audit record is append-only and independently verifiable",
            status=InvariantStatus.ENFORCED,
            probe=_probe_i3_audit_append_only,
        ),
        InvariantCheck(
            invariant_id="I4",
            statement="Every finding references at least one retrievable evidence item",
            status=InvariantStatus.NOT_ENFORCED,
            tracking="PR-31+ (no finding-producing context exists yet)",
        ),
        InvariantCheck(
            invariant_id="I5",
            statement="No credential outlives the execution it was minted for",
            status=InvariantStatus.NOT_ENFORCED,
            tracking="credential brokering is unbuilt; see ADR-011 follow-ups",
        ),
        InvariantCheck(
            invariant_id="I6",
            statement=(
                "Every tenant-scoped read and write carries tenant identity to "
                "the storage layer"
            ),
            status=InvariantStatus.PARTIAL,
            probe=_probe_i6_tenant_identity,
            tracking="PR-09 threads identity through storage; contracts enforce it today",
        ),
        InvariantCheck(
            invariant_id="I7",
            statement="Experiential memory may propose; it may never authorize",
            status=InvariantStatus.ENFORCED,
            probe=_probe_i7_memory_may_not_authorize,
        ),
        InvariantCheck(
            invariant_id="I8",
            statement=(
                "No component holds authoritative state that another component "
                "also holds"
            ),
            status=InvariantStatus.NOT_ENFORCED,
            tracking="PR-31 (mission consolidation); 12 modules currently define Mission",
        ),
        InvariantCheck(
            invariant_id="SELF-AUTH",
            statement="The platform never authorizes itself",
            status=InvariantStatus.ENFORCED,
            probe=_probe_platform_never_authorizes,
        ),
        InvariantCheck(
            invariant_id="IMMUTABLE",
            statement="Every contract is an immutable frozen dataclass",
            status=InvariantStatus.ENFORCED,
            probe=_probe_contracts_immutable,
        ),
    )
