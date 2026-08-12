"""World Plane confidence — Phase 7.1 (Part O).

The Phase 7.0 research is unanimous: verbalized LLM confidence is systematically
overconfident and must never be treated as calibrated truth. So this module
refuses to reduce uncertainty to a single ``confidence: float`` and instead
keeps three concepts distinct and unconvertible:

  * SOURCE AUTHORITY — how much a *source* is trusted, as a tier, not a number
    a model can invent. Deterministic and provenance-derived (a later phase
    computes it; here it is the vocabulary).
  * CLAIM CONFIDENCE — how strongly a *claim* is held. Carries a calibration
    STATE: it is ``UNCALIBRATED`` until enough logged prediction-vs-outcome
    history exists to fit a calibration; a numeric value is permitted only
    once ``CALIBRATED``. There is no default 0.5 and no default 1.0.
  * MODEL-STATED CONFIDENCE — what a model *said* ("I'm 95% sure"). A separate
    type with no conversion to ``ClaimConfidence``. It is metadata, evidence of
    what the model claimed, never an input to a decision.

The type barrier is the point: you cannot pass a ``ModelStatedConfidence`` where
a ``ClaimConfidence`` is required, so a model's stated number can never silently
become the platform's calibrated confidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = [
    "SourceAuthority",
    "CalibrationState",
    "ClaimConfidence",
    "ModelStatedConfidence",
]


class SourceAuthority(str, Enum):
    """How much a source system is trusted — a tier, not a probability.

    A tier so a model cannot mint a number; the ordering is a provenance/
    corroboration judgement a later phase derives deterministically. Ordered
    weakest-first.
    """

    UNVERIFIED = "unverified"
    """A source whose reliability is unknown or untrusted (e.g. untrusted
    external input). Cannot alone ground an authoritative fact."""

    SINGLE_SOURCE = "single_source"
    """One configured instrument reporting; believable but uncorroborated."""

    CORROBORATED = "corroborated"
    """Multiple independent sources agree."""

    AUTHORITATIVE = "authoritative"
    """The system of record for this claim (e.g. the cluster's own API for its
    own pod count)."""

    @property
    def rank(self) -> int:
        return {
            SourceAuthority.UNVERIFIED: 0,
            SourceAuthority.SINGLE_SOURCE: 1,
            SourceAuthority.CORROBORATED: 2,
            SourceAuthority.AUTHORITATIVE: 3,
        }[self]

    def at_least(self, floor: "SourceAuthority") -> bool:
        return self.rank >= floor.rank


class CalibrationState(str, Enum):
    """Whether a claim confidence is backed by measured calibration."""

    UNCALIBRATED = "uncalibrated"
    """No outcome history has calibrated this claim class yet. The honest
    default — a confidence that has never been measured against reality."""

    CALIBRATED = "calibrated"
    """A numeric confidence fitted from logged prediction-vs-outcome (a later
    phase; here only the state and the invariant it implies)."""


@dataclass(frozen=True)
class ClaimConfidence(Contract):
    """How strongly a claim is held, with its calibration state (Part O, K).

    Invariant: a value may exist **only** when ``CALIBRATED``. An
    ``UNCALIBRATED`` confidence has no number — because a number nobody
    measured against outcomes is decoration, and decoration is exactly what the
    research says to reject. Construct with :meth:`uncalibrated` (the default
    for anything not yet measured) or :meth:`calibrated`.
    """

    CONTRACT_NAME = "cortexprime.world.claim_confidence"

    state: CalibrationState
    value: Optional[float] = None

    def __post_init__(self) -> None:
        if not isinstance(self.state, CalibrationState):
            raise ContractViolation("state must be a CalibrationState")
        if self.state is CalibrationState.UNCALIBRATED:
            if self.value is not None:
                raise ContractViolation(
                    "an UNCALIBRATED confidence must carry no value; a number "
                    "with no measured calibration is not confidence"
                )
        else:  # CALIBRATED
            if not isinstance(self.value, (int, float)) or isinstance(self.value, bool):
                raise ContractViolation(
                    "a CALIBRATED confidence must carry a numeric value")
            if not (0.0 <= float(self.value) <= 1.0):
                raise ContractViolation("a calibrated confidence must be in [0, 1]")

    @classmethod
    def uncalibrated(cls) -> "ClaimConfidence":
        return cls(state=CalibrationState.UNCALIBRATED, value=None)

    @classmethod
    def calibrated(cls, value: float) -> "ClaimConfidence":
        return cls(state=CalibrationState.CALIBRATED, value=float(value))

    @property
    def is_calibrated(self) -> bool:
        return self.state is CalibrationState.CALIBRATED


@dataclass(frozen=True)
class ModelStatedConfidence(Contract):
    """What a model *said* about its own confidence. Metadata, never a control
    input (Part O).

    Deliberately a separate type with no conversion to :class:`ClaimConfidence`.
    A model saying "95%" produces a ``ModelStatedConfidence(0.95)`` that records
    the claim for attribution — it can never be used where a calibrated claim
    confidence is required, so verbalized overconfidence cannot leak into a
    decision.
    """

    CONTRACT_NAME = "cortexprime.world.model_stated_confidence"

    stated_value: float
    stated_by: str

    def __post_init__(self) -> None:
        if not isinstance(self.stated_value, (int, float)) or isinstance(self.stated_value, bool):
            raise ContractViolation("stated_value must be numeric")
        if not (0.0 <= float(self.stated_value) <= 1.0):
            raise ContractViolation("stated_value must be in [0, 1]")
        if not isinstance(self.stated_by, str) or not self.stated_by.strip():
            raise ContractViolation("stated_by must name the model that stated it")
