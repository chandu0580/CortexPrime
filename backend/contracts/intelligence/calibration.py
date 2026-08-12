"""Empirical calibration & reliability contracts — Phase 8.7 (ADR-078).

Calibration is empirical evidence ABOUT system behaviour, derived from REAL
historical prediction outcomes — never from model-stated confidence. Because
CortexPrime deliberately emits NO model probability (no numeric confidence exists
anywhere in the epistemic path), there is no probability-vs-frequency curve to fit;
the honest, correct quantity is the **empirical reliability of a prediction class**:
"across the historical predictions of this class, how often did the predicted
relationship actually hold, under what conditions, with what evidence quality, and
how independently was it verified?"

These are reference-only value contracts: a calibration result carries counts, an
interval around the estimate, and an explicit status — it never authorizes an
action, promotes autonomy, writes World truth, or asserts a point estimate as
truth. A numeric ``ClaimConfidence`` value is produced ONLY when the sample
supports it (fulfilling the Phase 7.1 ``CalibrationState`` contract); otherwise the
result is INSUFFICIENT_DATA and the confidence stays UNCALIBRATED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

# NOTE: contracts are level-0 value types and must not compute hashes here (no
# platform/stdlib-hash dependency). Digests (policy/dataset/result identities) are
# computed deterministically in the application layer (calibration.py) via the
# platform canonical hash and passed in as fields — keeping these contracts pure.

__all__ = [
    "PredictionClass",
    "CalibrationEligibility",
    "OutcomeLabel",
    "AssuranceTier",
    "CalibrationStatus",
    "DriftStatus",
    "ReliabilityInterval",
    "CalibrationSample",
    "CalibrationPolicy",
    "CalibrationDataset",
    "ReliabilityEstimate",
]


def _req_str(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} is required")


class CalibrationEligibility(str, Enum):
    """Whether a prediction is eligible to enter the calibration estimate. Incomplete
    cases are preserved (censored), never silently discarded (Part D)."""

    ELIGIBLE = "eligible"
    INELIGIBLE = "ineligible"
    PENDING_OUTCOME = "pending_outcome"
    PENDING_ASSURANCE = "pending_assurance"
    CONFLICTED = "conflicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class OutcomeLabel(str, Enum):
    """The outcome of a prediction — SUPPORTED/UNSUPPORTED are DECIDED; the others
    are censored and are NEVER forced into failure (Part E)."""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTED = "conflicted"
    PENDING = "pending"


class AssuranceTier(str, Enum):
    """The evidence-quality population a sample belongs to (Part F). Kept visible so
    high- and low-quality examples are never silently mixed."""

    ASSURED_OUTCOME = "assured_outcome"          # independent verification SUPPORTED
    SUPPORTED_OUTCOME = "supported_outcome"        # verified but the verdict differed
    UNASSURED_OUTCOME = "unassured_outcome"        # evaluated, no independent verification
    INSUFFICIENT_OUTCOME = "insufficient_outcome"  # censored / no decided outcome


class CalibrationStatus(str, Enum):
    """The status of a reliability estimate. INSUFFICIENT_DATA is a valid, preferred
    outcome — never fake precision (Part I/J)."""

    CALIBRATED = "calibrated"
    CALIBRATED_WITH_LIMITATIONS = "calibrated_with_limitations"
    INSUFFICIENT_DATA = "insufficient_data"
    STALE = "stale"
    INVALIDATED = "invalidated"


class DriftStatus(str, Enum):
    NO_DRIFT = "no_drift"
    DRIFT_DETECTED = "drift_detected"
    UNKNOWN_DRIFT_STATUS = "unknown_drift_status"


@dataclass(frozen=True)
class PredictionClass:
    """The typed calibration unit (Part C). A minimal useful stratification; broader
    fallbacks drop dimensions EXPLICITLY (Part K). Model/harness are always tracked
    so an estimate never silently spans incompatible runtime versions (Part L)."""

    subject_type: str            # e.g. "dependency", "deployment" (resource class)
    predicate: str
    environment: str
    model_identity: str
    harness_version: str

    def __post_init__(self) -> None:
        for name in ("subject_type", "predicate", "environment", "model_identity",
                     "harness_version"):
            _req_str(getattr(self, name), name)

    def broaden(self) -> Optional["PredictionClass"]:
        """The next broader class for explicit fallback: drop the most specific
        dimension (environment) first, then predicate — never dropping model/harness
        (versions must never be silently merged). Returns None when no safe broader
        class remains."""
        if self.environment != "*":
            return PredictionClass(self.subject_type, self.predicate, "*",
                                   self.model_identity, self.harness_version)
        if self.predicate != "*":
            return PredictionClass(self.subject_type, "*", "*",
                                   self.model_identity, self.harness_version)
        return None

    def to_dict(self) -> dict:
        return {"subject_type": self.subject_type, "predicate": self.predicate,
                "environment": self.environment, "model_identity": self.model_identity,
                "harness_version": self.harness_version}


@dataclass(frozen=True)
class ReliabilityInterval:
    """An interval around the estimate — communicates uncertainty about the estimate
    itself (Part J). Never a bare point estimate presented as truth."""

    method: str          # "wilson"
    level: float         # e.g. 0.95
    lower: float
    upper: float

    def to_dict(self) -> dict:
        return {"method": self.method, "level": self.level,
                "lower": self.lower, "upper": self.upper}


@dataclass(frozen=True)
class CalibrationSample(Contract):
    """One prediction's calibration record — references and categorical labels only.
    Model-stated confidence is deliberately absent; if retained anywhere it is
    UNTRUSTED_METADATA and never enters here (Part B)."""

    CONTRACT_NAME = "cortexprime.intelligence.calibration_sample"

    prediction_ref: str
    prediction_class: PredictionClass
    eligibility: CalibrationEligibility
    outcome_label: OutcomeLabel
    assurance_tier: AssuranceTier
    matched: Optional[bool]
    within_horizon: Optional[bool]
    subject_ref: str
    predicate: str
    model_identity: str
    harness_version: str
    recorded_at: datetime
    execution_ref: Optional[str] = None
    verification_ref: Optional[str] = None
    uses_experience: bool = False
    human_adjudicated: bool = False

    def __post_init__(self) -> None:
        _req_str(self.prediction_ref, "prediction_ref")
        if not isinstance(self.prediction_class, PredictionClass):
            raise ContractViolation("prediction_class must be a PredictionClass")
        for name, enum in (("eligibility", CalibrationEligibility),
                           ("outcome_label", OutcomeLabel), ("assurance_tier", AssuranceTier)):
            if not isinstance(getattr(self, name), enum):
                raise ContractViolation(f"{name} must be a {enum.__name__}")

    @property
    def is_decided(self) -> bool:
        return (self.eligibility is CalibrationEligibility.ELIGIBLE
                and self.outcome_label in (OutcomeLabel.SUPPORTED, OutcomeLabel.UNSUPPORTED))

    def to_dict(self) -> dict:
        return {
            "prediction_ref": self.prediction_ref, "prediction_class": self.prediction_class.to_dict(),
            "eligibility": self.eligibility.value, "outcome_label": self.outcome_label.value,
            "assurance_tier": self.assurance_tier.value, "matched": self.matched,
            "within_horizon": self.within_horizon, "subject_ref": self.subject_ref,
            "predicate": self.predicate, "model_identity": self.model_identity,
            "harness_version": self.harness_version, "recorded_at": self.recorded_at.isoformat(),
            "execution_ref": self.execution_ref, "verification_ref": self.verification_ref,
            "uses_experience": self.uses_experience, "human_adjudicated": self.human_adjudicated,
        }


@dataclass(frozen=True)
class CalibrationPolicy:
    """The deterministic inclusion/exclusion + estimation policy. Its digest is part
    of every dataset/result so runs are reproducible (Part H/U)."""

    min_decided_samples: int = 8
    min_assurance_coverage: float = 0.5      # fraction of decided that are assured
    interval_level: float = 0.95
    interval_method: str = "wilson"
    algorithm_version: str = "empirical-reliability/1"
    require_within_horizon: bool = True

    def to_dict(self) -> dict:
        return {
            "min_decided_samples": self.min_decided_samples,
            "min_assurance_coverage": self.min_assurance_coverage,
            "interval_level": self.interval_level, "interval_method": self.interval_method,
            "algorithm_version": self.algorithm_version,
            "require_within_horizon": self.require_within_horizon,
        }


@dataclass(frozen=True)
class CalibrationDataset(Contract):
    """A reproducible, versioned snapshot of calibration samples (Part H). Same
    ledgers + same policy + same known_at ⇒ same ``dataset_digest``."""

    CONTRACT_NAME = "cortexprime.intelligence.calibration_dataset"

    tenant_id: str
    policy_digest: str
    generated_at: datetime
    samples: tuple[CalibrationSample, ...]
    time_from: Optional[datetime] = None
    time_to: Optional[datetime] = None
    known_at: Optional[datetime] = None       # None = FINAL-EVALUATED; set = AS-KNOWN-AT-TIME
    model_identities: tuple[str, ...] = ()
    harness_versions: tuple[str, ...] = ()
    algorithm_version: str = "empirical-reliability/1"
    provider_label: str = "scripted"          # Part Y: scripted vs real-model evidence, never mixed

    def __post_init__(self) -> None:
        _req_str(self.tenant_id, "tenant_id")
        if not isinstance(self.samples, tuple) or not all(
            isinstance(s, CalibrationSample) for s in self.samples
        ):
            raise ContractViolation("samples must be a tuple of CalibrationSample")

    def digest_payload(self) -> dict:
        """The canonical, order-independent payload the application hashes into the
        reproducible ``dataset_digest`` (the hash itself is computed in the
        application layer, keeping this contract free of a hashing dependency)."""
        return {
            "tenant": self.tenant_id, "policy": self.policy_digest,
            "known_at": self.known_at.isoformat() if self.known_at else None,
            "provider": self.provider_label,
            # order-independent: sort by the unique prediction_ref so the digest does
            # not depend on sample iteration order.
            "samples": [s.to_dict() for s in
                        sorted(self.samples, key=lambda s: s.prediction_ref)],
        }


@dataclass(frozen=True)
class ReliabilityEstimate(Contract):
    """The empirical reliability of a prediction class — counts, an interval, an
    explicit status, and (only when the data supports it) a calibrated
    ``ClaimConfidence``. Never a point estimate presented as truth; never an
    authorization (Part J/R)."""

    CONTRACT_NAME = "cortexprime.intelligence.reliability_estimate"

    prediction_class: PredictionClass
    status: CalibrationStatus
    sample_count: int
    decided_count: int
    supported_count: int
    unsupported_count: int
    insufficient_count: int
    conflicted_count: int
    pending_count: int
    assured_count: int
    dataset_digest: str
    policy_digest: str
    confidence: Any                             # ClaimConfidence (calibrated only if enough)
    generated_at: datetime
    support_rate: Optional[float] = None        # empirical rate among DECIDED; None if insufficient
    interval: Optional[ReliabilityInterval] = None
    assurance_coverage: Optional[float] = None
    fallback_applied: bool = False
    fallback_from: Optional[dict] = None
    reliability_note: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.prediction_class, PredictionClass):
            raise ContractViolation("prediction_class must be a PredictionClass")
        if not isinstance(self.status, CalibrationStatus):
            raise ContractViolation("status must be a CalibrationStatus")
        # No fake precision: a numeric rate exists only for a genuinely calibrated status.
        if self.support_rate is not None and self.status in (
            CalibrationStatus.INSUFFICIENT_DATA,
        ):
            raise ContractViolation(
                "INSUFFICIENT_DATA must carry no support_rate (no fake precision)")

    def to_dict(self) -> dict:
        conf = self.confidence
        return {
            "prediction_class": self.prediction_class.to_dict(), "status": self.status.value,
            "sample_count": self.sample_count, "decided_count": self.decided_count,
            "supported_count": self.supported_count, "unsupported_count": self.unsupported_count,
            "insufficient_count": self.insufficient_count, "conflicted_count": self.conflicted_count,
            "pending_count": self.pending_count, "assured_count": self.assured_count,
            "support_rate": self.support_rate,
            "interval": self.interval.to_dict() if self.interval else None,
            "assurance_coverage": self.assurance_coverage,
            "confidence": {"state": getattr(conf, "state", None) and conf.state.value,
                           "value": getattr(conf, "value", None)},
            "fallback_applied": self.fallback_applied, "fallback_from": self.fallback_from,
            "dataset_digest": self.dataset_digest, "policy_digest": self.policy_digest,
            "reliability_note": self.reliability_note,
            "generated_at": self.generated_at.isoformat(),
        }
