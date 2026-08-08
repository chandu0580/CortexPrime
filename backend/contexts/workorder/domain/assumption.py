"""Assumptions: what the Architect believes but did not verify.

The most important field in the WorkOrder specification, and the one that exists
because of a specific incident. A brief once required an invariant be promoted
from PARTIAL to ENFORCED; the promotion was impossible, because no model in the
schema carried the column the enforcement needed. The belief that it *was*
possible was never written down, so nothing forced anyone to check it.

An assumption converts such a belief from an unstated premise into an explicit
item the receiver must resolve before proceeding. Each one implies a rejection
ground, and that pairing is enforced in validation: an unverifiable belief with
no refusal path is precisely how a false premise reaches production.

Resolution is deliberately three-valued. ``UNVERIFIABLE`` is not a soft
``CONFIRMED`` -- it is its own outcome, it still requires evidence of the attempt,
and it is a blocking finding at approval time.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.workorder.domain.identifiers import AssumptionId, EvidenceRef

__all__ = ["AssumptionResolution", "Assumption"]


class AssumptionResolution(str, Enum):
    """What checking an assumption produced."""

    CONFIRMED = "confirmed"
    CONTRADICTED = "contradicted"
    UNVERIFIABLE = "unverifiable"

    @property
    def permits_progress(self) -> bool:
        """Whether work may continue past this resolution.

        Only ``CONFIRMED`` does. ``CONTRADICTED`` requires a ``PREMISE_FALSE``
        rejection. ``UNVERIFIABLE`` also blocks: proceeding on a belief nobody
        could check is the same risk as proceeding on one that was checked and
        found false, minus the knowledge that it was.
        """
        return self is AssumptionResolution.CONFIRMED


@dataclass(frozen=True)
class Assumption(Contract):
    """A belief the WorkOrder rests on, and how to check it."""

    CONTRACT_NAME = "cortexprime.engineering.assumption"

    assumption_id: AssumptionId
    statement: str
    verification_method: str
    resolution: Optional[AssumptionResolution] = None
    resolution_evidence: Optional[EvidenceRef] = None

    def __post_init__(self) -> None:
        if not isinstance(self.assumption_id, AssumptionId):
            raise ContractViolation("assumption_id must be an AssumptionId")

        for label, value in (
            ("statement", self.statement),
            ("verification_method", self.verification_method),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")
            if value != value.strip():
                raise ContractViolation(f"{label} must not have leading or trailing whitespace")

        if self.resolution is not None and not isinstance(self.resolution, AssumptionResolution):
            raise ContractViolation("resolution must be an AssumptionResolution")

        if self.resolution_evidence is not None and not isinstance(
            self.resolution_evidence, EvidenceRef
        ):
            raise ContractViolation("resolution_evidence must be an EvidenceRef")

        # Evidence is required for *every* resolution, including UNVERIFIABLE.
        # "I tried and could not determine" is itself a finding, and recording
        # it without saying what was tried makes it indistinguishable from not
        # having looked.
        if self.resolution is not None and self.resolution_evidence is None:
            raise ContractViolation(
                f"assumption resolved {self.resolution.value!r} without evidence; "
                "every resolution must cite what was checked"
            )
        if self.resolution is None and self.resolution_evidence is not None:
            raise ContractViolation(
                "resolution_evidence is present without a resolution; evidence of "
                "what?"
            )

    # ------------------------------------------------------------------

    @classmethod
    def create(cls, statement: str, verification_method: str) -> "Assumption":
        return cls(
            assumption_id=AssumptionId.new(),
            statement=statement,
            verification_method=verification_method,
        )

    @property
    def is_resolved(self) -> bool:
        return self.resolution is not None

    @property
    def permits_progress(self) -> bool:
        return self.resolution is not None and self.resolution.permits_progress

    def resolve(
        self, resolution: AssumptionResolution, evidence: EvidenceRef
    ) -> "Assumption":
        """Record the outcome of checking this assumption.

        Returns a new instance; assumptions are immutable like everything else
        in this context. Re-resolving is refused rather than overwriting -- a
        second answer to a settled question means one of them is wrong, and
        silently keeping the later one destroys the evidence of the first.
        """
        if self.is_resolved:
            raise ContractViolation(
                f"assumption {self.assumption_id} is already resolved "
                f"{self.resolution.value!r}; a second resolution would overwrite the first"
            )
        return replace(self, resolution=resolution, resolution_evidence=evidence)
