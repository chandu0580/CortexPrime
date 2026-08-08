"""ImplementationRecord lifecycle events.

Namespaced ``engineering.implementation.*``. ``CONTRACT_NAME`` is globally unique
and a clash raises at import time, and PR-E2's runtime already owns
``engineering.runtime.implementation_started``.

The two are different facts and both are worth having. The runtime's says *the
orchestrator handed work to an implementer*; this one says *the Implementation
context opened a record*. They coincide today and will not once dispatch is
queued -- and the gap between them is where a dropped handoff would hide.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.errors import ContractViolation
from backend.platform.events import DomainEvent

__all__ = [
    "AGGREGATE_TYPE", "ImplementationStarted", "ImplementationUpdated",
    "ImplementationCompleted", "ClaimAdded", "RiskDeclared", "AssumptionResolved",
    "DigestComputed", "ImplementationSuperseded", "IMPLEMENTATION_EVENT_TYPES",
]

AGGREGATE_TYPE = "implementation_record"


def _require_text(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")


@dataclass(frozen=True)
class ImplementationStarted(DomainEvent):
    """A record was opened for one round against one context bundle."""

    EVENT_TYPE = "engineering.implementation.started"

    implementation_id: str = ""
    work_id: str = ""
    round: int = 1
    context_bundle_id: str = ""
    context_bundle_version: int = 1
    revision: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("implementation_id", self.implementation_id)
        _require_text("work_id", self.work_id)
        _require_text("context_bundle_id", self.context_bundle_id)
        _require_text("revision", self.revision)


@dataclass(frozen=True)
class ImplementationUpdated(DomainEvent):
    """Something was recorded against an open implementation.

    ``what`` names the kind of change rather than the change itself. A consumer
    tailing this stream wants to know that work is progressing; one that needs the
    detail reads the record.
    """

    EVENT_TYPE = "engineering.implementation.updated"

    implementation_id: str = ""
    work_id: str = ""
    what: str = ""
    detail: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("implementation_id", self.implementation_id)
        _require_text("what", self.what)


@dataclass(frozen=True)
class ImplementationCompleted(DomainEvent):
    """Sealed and submittable. Review and Verification may consume it."""

    EVENT_TYPE = "engineering.implementation.completed"

    implementation_id: str = ""
    work_id: str = ""
    round: int = 1
    digest: str = ""
    claim_count: int = 0
    files_changed: int = 0
    revision: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("implementation_id", self.implementation_id)
        _require_text("work_id", self.work_id)
        _require_text("digest", self.digest)
        if self.claim_count < 1:
            raise ContractViolation(
                "a completed implementation carries at least one claim; a verification "
                "with nothing to verify reports complete having established nothing"
            )
        if self.files_changed < 1:
            raise ContractViolation(
                "a completed implementation changed at least one file; work that left "
                "no trace cannot be reviewed"
            )


@dataclass(frozen=True)
class ClaimAdded(DomainEvent):
    """An assertion was made, with the evidence offered for it."""

    EVENT_TYPE = "engineering.implementation.claim_added"

    implementation_id: str = ""
    work_id: str = ""
    claim_id: str = ""
    claim_type: str = ""
    statement: str = ""
    evidence_count: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("implementation_id", self.implementation_id)
        _require_text("claim_id", self.claim_id)
        _require_text("claim_type", self.claim_type)
        _require_text("statement", self.statement)
        if self.evidence_count < 1:
            raise ContractViolation(
                "a claim cites at least one evidence reference; one a verifier cannot "
                "attack can only be taken on trust"
            )


@dataclass(frozen=True)
class RiskDeclared(DomainEvent):
    """The implementer surfaced something it knows could go wrong."""

    EVENT_TYPE = "engineering.implementation.risk_declared"

    implementation_id: str = ""
    work_id: str = ""
    risk_id: str = ""
    level: str = ""
    statement: str = ""
    mitigated: bool = False

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("implementation_id", self.implementation_id)
        _require_text("risk_id", self.risk_id)
        _require_text("level", self.level)
        _require_text("statement", self.statement)
        if not isinstance(self.mitigated, bool):
            raise ContractViolation("mitigated must be a bool")


@dataclass(frozen=True)
class AssumptionResolved(DomainEvent):
    """A WorkOrder assumption was checked.

    The most consequential event here. A ``contradicted`` outcome means the
    WorkOrder's premise was false, which is the failure the whole model exists to
    catch before code is written -- and catching it after is still better than
    not catching it.
    """

    EVENT_TYPE = "engineering.implementation.assumption_resolved"

    implementation_id: str = ""
    work_id: str = ""
    assumption_id: str = ""
    outcome: str = ""
    evidence_count: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("implementation_id", self.implementation_id)
        _require_text("assumption_id", self.assumption_id)
        _require_text("outcome", self.outcome)
        if self.evidence_count < 1:
            raise ContractViolation(
                "every resolution cites what was checked, including 'unverifiable'"
            )


@dataclass(frozen=True)
class DigestComputed(DomainEvent):
    """The record was sealed. What follows is bound to this hash."""

    EVENT_TYPE = "engineering.implementation.digest_computed"

    implementation_id: str = ""
    work_id: str = ""
    digest: str = ""
    algorithm: str = ""
    canonical_form: int = 1

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("implementation_id", self.implementation_id)
        _require_text("digest", self.digest)


@dataclass(frozen=True)
class ImplementationSuperseded(DomainEvent):
    EVENT_TYPE = "engineering.implementation.superseded"

    implementation_id: str = ""
    work_id: str = ""
    superseded_by: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("implementation_id", self.implementation_id)
        _require_text("superseded_by", self.superseded_by)
        if self.implementation_id == self.superseded_by:
            raise ContractViolation("an implementation cannot supersede itself")


IMPLEMENTATION_EVENT_TYPES = (
    ImplementationStarted, ImplementationUpdated, ImplementationCompleted,
    ClaimAdded, RiskDeclared, AssumptionResolved, DigestComputed,
    ImplementationSuperseded,
)
