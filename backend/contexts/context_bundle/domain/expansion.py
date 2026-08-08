"""Context expansion: the only way a bundle may grow.

The rule this context exists to enforce. A bundle that can widen without a
recorded request is a bundle whose contents nobody can account for.

Auto-grant is deterministic, not permissive
--------------------------------------------
Three categories are granted without a human: ADRs, the contracts vocabulary, and
a declared dependency's interface. Each is already *conceptually* inside the
bundle -- an agent given ADR-018's identifier in its index and refused its text is
being told about a decision it may not read.

Auto-granting is still an **expansion**, recorded exactly like any other. The
difference is who decided, not whether it happened. A category that were merely
"allowed" rather than granted-and-recorded would be implicit expansion with extra
steps, and the log would understate what agents actually saw.

A denial is information, not an error
--------------------------------------
Denied requests stay in the record. Repeated requests for the same out-of-scope
path across independent bundles are the highest-value signal this context
produces: they mean the architectural boundary is drawn in the wrong place.
Discarding denials would discard exactly that.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, Sequence

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.context_bundle.domain.errors import ExpansionAlreadyDecided
from backend.contexts.context_bundle.domain.identifiers import ExpansionRequestId
from backend.contexts.context_bundle.domain.layers import ContextLayer

__all__ = [
    "Disposition",
    "ExpansionRequest",
    "AUTO_GRANT_PREFIXES",
    "auto_grant_reason",
]


#: Paths granted without escalation, and why each is already conceptually inside
#: the bundle. Read-only in every case -- auto-grant never confers write access.
AUTO_GRANT_PREFIXES = {
    "docs/adr/": "an ADR the bundle's index already names",
    "backend/contracts/": "the dependency-free vocabulary every context shares",
}


class Disposition(str, Enum):
    PENDING = "pending"
    AUTO_GRANTED = "auto_granted"
    GRANTED = "granted"
    DENIED = "denied"

    @property
    def is_decided(self) -> bool:
        return self is not Disposition.PENDING

    @property
    def widens_bundle(self) -> bool:
        return self in {Disposition.AUTO_GRANTED, Disposition.GRANTED}


def auto_grant_reason(path: str, *, dependency_interfaces: Sequence[str] = ()) -> Optional[str]:
    """Why ``path`` may be granted without escalation, or ``None``.

    Returns the reason rather than a boolean so the record says *why* something
    was auto-granted. A log of bare "auto_granted" values cannot be reviewed for
    whether the categories are still the right ones.
    """
    normalised = path.strip().replace("\\", "/")
    for prefix, reason in AUTO_GRANT_PREFIXES.items():
        if normalised.startswith(prefix):
            return reason
    for interface in dependency_interfaces:
        # A declared dependency's interface was already promised to this bundle;
        # refusing it would mean declaring a dependency and withholding it.
        if normalised == interface or normalised.startswith(interface.rstrip("*").rstrip("/") + "/"):
            return f"the declared interface of dependency {interface!r}"
    return None


@dataclass(frozen=True)
class ExpansionRequest(Contract):
    """One request to widen a bundle, and what was decided.

    ``question`` is mandatory. A request without one is browsing, and browsing
    produces an expansion log nobody can learn from -- the entries would record
    that a path was wanted without recording what it was wanted *for*.
    """

    CONTRACT_NAME = "cortexprime.engineering.context_expansion_request"

    request_id: ExpansionRequestId
    requested_path: str
    question: str
    requested_by: str
    target_layer: ContextLayer = ContextLayer.DEPENDENCIES
    disposition: Disposition = Disposition.PENDING
    decided_by: Optional[str] = None
    decision_reason: Optional[str] = None
    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    decided_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not isinstance(self.request_id, ExpansionRequestId):
            raise ContractViolation("request_id must be an ExpansionRequestId")
        for label, value in (
            ("requested_path", self.requested_path),
            ("question", self.question),
            ("requested_by", self.requested_by),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")

        normalised = self.requested_path.strip().replace("\\", "/")
        if normalised.startswith("/"):
            raise ContractViolation("requested_path must be repository-relative")
        if ".." in normalised.split("/"):
            raise ContractViolation("requested_path must not traverse upward with '..'")
        object.__setattr__(self, "requested_path", normalised)
        object.__setattr__(self, "question", self.question.strip())
        object.__setattr__(self, "requested_by", self.requested_by.strip())

        if not isinstance(self.target_layer, ContextLayer):
            raise ContractViolation("target_layer must be a ContextLayer")
        if self.target_layer is ContextLayer.OWNED:
            raise ContractViolation(
                "expansion never grants write access; widening the writable set is a "
                "blast-radius change, which is the Architect's decision and produces a "
                "new WorkOrder version"
            )

        if not isinstance(self.disposition, Disposition):
            raise ContractViolation("disposition must be a Disposition")

        if self.disposition.is_decided:
            if not self.decided_by or not self.decided_by.strip():
                raise ContractViolation(
                    f"a {self.disposition.value} request must record who decided it"
                )
            if self.decided_at is None:
                raise ContractViolation("a decided request must record when")
            if self.disposition is Disposition.DENIED and not (
                self.decision_reason and self.decision_reason.strip()
            ):
                raise ContractViolation(
                    "a denial must say why; a denied request with no reason teaches "
                    "nobody where the boundary actually is"
                )
        else:
            if self.decided_by or self.decided_at or self.decision_reason:
                raise ContractViolation(
                    "a pending request carries no decision"
                )

        for label, value in (("requested_at", self.requested_at), ("decided_at", self.decided_at)):
            if value is not None and value.tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        requested_path: str,
        question: str,
        requested_by: str,
        *,
        target_layer: ContextLayer = ContextLayer.DEPENDENCIES,
    ) -> "ExpansionRequest":
        return cls(
            request_id=ExpansionRequestId.new(),
            requested_path=requested_path,
            question=question,
            requested_by=requested_by,
            target_layer=target_layer,
        )

    def _require_pending(self) -> None:
        if self.disposition.is_decided:
            raise ExpansionAlreadyDecided(
                request_id=str(self.request_id), disposition=self.disposition.value
            )

    def auto_grant(self, reason: str) -> "ExpansionRequest":
        """Grant deterministically. Still recorded as an expansion."""
        self._require_pending()
        return replace(
            self,
            disposition=Disposition.AUTO_GRANTED,
            decided_by="orchestrator",
            decision_reason=reason,
            decided_at=datetime.now(timezone.utc),
        )

    def grant(self, decided_by: str, reason: Optional[str] = None) -> "ExpansionRequest":
        self._require_pending()
        if not decided_by or not decided_by.strip():
            raise ContractViolation("a grant must record who decided it")
        return replace(
            self,
            disposition=Disposition.GRANTED,
            decided_by=decided_by.strip(),
            decision_reason=reason,
            decided_at=datetime.now(timezone.utc),
        )

    def deny(self, decided_by: str, reason: str) -> "ExpansionRequest":
        self._require_pending()
        if not reason or not reason.strip():
            raise ContractViolation(
                "a denial must say why; a denied request with no reason teaches nobody "
                "where the boundary actually is"
            )
        return replace(
            self,
            disposition=Disposition.DENIED,
            decided_by=(decided_by or "architect").strip(),
            decision_reason=reason.strip(),
            decided_at=datetime.now(timezone.utc),
        )

    @property
    def widens_bundle(self) -> bool:
        return self.disposition.widens_bundle

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.requested_path} [{self.disposition.value}]"
