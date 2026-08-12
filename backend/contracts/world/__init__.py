"""The World Plane epistemic contracts — Phase 7.1 (ADR-063).

This subpackage is the *vocabulary* of what CortexPrime knows about the
external world: observations, facts, beliefs, hypotheses, predictions,
outcomes, and verifications. It is contracts only — immutable value types
with validation, no persistence, no ingestion, no retrieval, no execution.

The four laws these contracts make structural (ADR-062):
  * MODEL OUTPUT never becomes a FACT. The model produces a ``ModelProposal``
    or a ``Hypothesis`` — distinct types with no conversion to ``Fact``. Only
    an ``Observation`` from an instrument (never a model) can ground a fact.
  * WORLD never executes. Nothing here imports a connector, the gateway, the
    execution plane, a credential, or a governance grant.
  * BELIEF ≠ FACT, HYPOTHESIS ≠ BELIEF, PREDICTION ≠ OUTCOME,
    MODEL VERDICT ≠ VERIFICATION — enforced as unconvertible types.
  * Every epistemic object is tenant-scoped and fails closed on ambiguity.

The World Plane describes reality. It does not act on reality.
"""

from backend.contracts.world.temporal import (
    ObservationInstant,
    ValidityInterval,
)
from backend.contracts.world.provenance import (
    ProvenanceRef,
    SecretInProvenance,
)
from backend.contracts.world.confidence import (
    CalibrationState,
    ClaimConfidence,
    ModelStatedConfidence,
    SourceAuthority,
)
from backend.contracts.world.epistemic import (
    Belief,
    EpistemicRecord,
    EpistemicStatus,
    Fact,
    Hypothesis,
    HypothesisStatus,
    ModelProposal,
    Observation,
    ObservationSource,
    ObservationSourceKind,
    Outcome,
    Prediction,
    WorldVerification,
)

__all__ = [
    # temporal
    "ObservationInstant",
    "ValidityInterval",
    # provenance
    "ProvenanceRef",
    "SecretInProvenance",
    # confidence
    "CalibrationState",
    "ClaimConfidence",
    "ModelStatedConfidence",
    "SourceAuthority",
    # epistemic spine + types
    "EpistemicRecord",
    "EpistemicStatus",
    "Observation",
    "ObservationSource",
    "ObservationSourceKind",
    "Fact",
    "Belief",
    "Hypothesis",
    "HypothesisStatus",
    "Prediction",
    "Outcome",
    "WorldVerification",
    "ModelProposal",
]
