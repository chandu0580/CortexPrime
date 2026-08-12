"""The Intelligence Plane contracts — Phase 8.1 (ADR-072).

Typed, immutable value contracts for representing an investigation as a durable,
crash-safe, replay-safe state machine — WITHOUT letting the model create truth or
execute actions. Contracts only: no persistence, no I/O, no model call, no
execution.

The laws these contracts make structural (ADR-071/072):
  * The model PROPOSES; the platform DECIDES. A question, hypothesis, test, or
    prediction proposed by a model is a reasoning artifact tagged with its
    producer — never world truth.
  * Differential diagnosis, not premature selection: an investigation owns a SET
    of hypotheses with explicit evidence for/against/missing/contradicting and an
    epistemic status — never a numeric confidence.
  * Autonomy is platform policy, never a model claim. ``AutonomyLevel`` is set by
    the platform; nothing a model outputs can promote it.
  * Evidence is referenced, never duplicated: the investigation points at World
    observations/facts/beliefs/verifications by reference.
  * Tenant-scoped and provenance-bearing on every contract; fail closed.
"""

from backend.contracts.intelligence.investigation import (
    AutonomyLevel,
    DifferentialHypothesis,
    HumanEvent,
    HumanEventKind,
    Investigation,
    InvestigationConclusion,
    InvestigationEventKind,
    InvestigationQuestion,
    InvestigationStatus,
    InvestigationTest,
    TemporalFit,
    is_legal_transition,
    is_terminal_status,
    legal_transitions_from,
)
from backend.contracts.intelligence.episode import (
    AssuranceStatus,
    EpisodeFacets,
    EpisodeHypothesis,
    ExperienceQuality,
    InvestigationEpisode,
)

__all__ = [
    "AutonomyLevel",
    "InvestigationStatus",
    "InvestigationConclusion",
    "InvestigationEventKind",
    "TemporalFit",
    "HumanEventKind",
    "Investigation",
    "DifferentialHypothesis",
    "InvestigationQuestion",
    "InvestigationTest",
    "HumanEvent",
    "is_legal_transition",
    "is_terminal_status",
    "legal_transitions_from",
    # 8.6 investigation experience
    "InvestigationEpisode",
    "EpisodeFacets",
    "EpisodeHypothesis",
    "ExperienceQuality",
    "AssuranceStatus",
]
