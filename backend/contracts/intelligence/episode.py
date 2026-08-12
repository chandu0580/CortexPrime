"""Investigation experience — the episode contract (Phase 8.6, ADR-077).

An ``InvestigationEpisode`` is the retained EXPERIENCE of a completed investigation:
what was investigated, what was hypothesised and tested, what disposition it
reached, and how assured that disposition was — all as REFERENCES to the
authoritative World/Assurance/Investigation objects, never copies of them.

The load-bearing invariant (Part C): experience is not truth. An episode carries
references and categorical summaries; it has deliberately NO ``to_fact`` /
``to_belief`` / ``to_outcome`` / ``to_verification`` method. A future investigator
may read "episode E123 found H4 supported under those conditions" — that is
history, not a current fact. The barrier is the missing conversion, enforced here
by the type system (an episode holds only strings/enums/reference summaries) and,
at the import level, by ``BND-MODEL-CANNOT-CREATE-FACT`` (the intelligence plane
may not import the World grounded constructors at all).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.tenant import TenantRef
from backend.contracts.intelligence.investigation import (
    InvestigationConclusion,
    InvestigationStatus,
)

__all__ = [
    "ExperienceQuality",
    "AssuranceStatus",
    "EpisodeFacets",
    "EpisodeHypothesis",
    "InvestigationEpisode",
]


def _req_str(value: Any, label: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} is required")


def _req_ref_tuple(value: Any, label: str) -> None:
    if not isinstance(value, tuple) or not all(
        isinstance(r, str) and r.strip() for r in value
    ):
        raise ContractViolation(f"{label} must be a tuple of reference strings")


def _req_aware(value: datetime, label: str) -> None:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ContractViolation(f"{label} must be a timezone-aware datetime")


class ExperienceQuality(str, Enum):
    """A categorical quality of the retained experience — NOT a numeric confidence
    (Part M). It summarises how strongly the prior investigation settled, mapping
    onto the existing ``InvestigationConclusion`` / ``Verdict`` / ``HypothesisStatus``
    vocabularies; it never invents a new epistemic axis."""

    DIRECTLY_ASSURED = "directly_assured"
    """RESOLVED and independently Assurance-verified (a Verdict.SUPPORTED)."""
    SUPPORTED = "supported"
    """A hypothesis was supported by world evidence, but not independently verified."""
    PARTIALLY_SUPPORTED = "partially_supported"
    """Supported with un-eliminated alternatives / residual uncertainty."""
    UNRESOLVED = "unresolved"
    CONFLICTED = "conflicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"


class AssuranceStatus(str, Enum):
    """Whether the episode's disposition was independently verified (Part L). A
    historically supported hypothesis is not automatically trustworthy — this
    distinguishes 'historically supported' from 'independently verified'."""

    ASSURED = "assured"
    """An independent Assurance verification SUPPORTED the disposition."""
    UNASSURED = "unassured"
    """No independent verification was recorded for the disposition."""
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTED = "conflicted"


@dataclass(frozen=True)
class EpisodeFacets:
    """The deterministic, explainable dimensions used for relevance (Part F) — all
    categorical references, no similarity score."""

    service: str
    environment: str
    symptom_class: str
    resource_types: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("service", "environment", "symptom_class"):
            _req_str(getattr(self, name), name)
        _req_ref_tuple(self.resource_types, "resource_types")

    def to_dict(self) -> dict:
        return {"service": self.service, "environment": self.environment,
                "symptom_class": self.symptom_class, "resource_types": list(self.resource_types)}


@dataclass(frozen=True)
class EpisodeHypothesis:
    """A reference SUMMARY of a hypothesis from the prior differential — a proposition
    string and its final epistemic status value, plus references. It is not a live
    ``DifferentialHypothesis`` and carries no evidence objects, only refs."""

    hypothesis_ref: str
    subject_ref: str
    proposition: str
    status: str                 # HypothesisStatus value (a string, not a live object)
    evidence_for: tuple[str, ...] = ()
    evidence_against: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("hypothesis_ref", "subject_ref", "proposition", "status"):
            _req_str(getattr(self, name), name)
        for name in ("evidence_for", "evidence_against"):
            _req_ref_tuple(getattr(self, name), name)

    def to_dict(self) -> dict:
        return {"hypothesis_ref": self.hypothesis_ref, "subject_ref": self.subject_ref,
                "proposition": self.proposition, "status": self.status,
                "evidence_for": list(self.evidence_for), "evidence_against": list(self.evidence_against)}


@dataclass(frozen=True)
class InvestigationEpisode(Contract):
    """The retained experience of one completed investigation — references only.

    Deliberately absent: any ``to_fact`` / ``to_belief`` / ``to_outcome`` /
    ``to_verification`` method. Experience references authoritative objects; it can
    never mint one. A future investigator consumes this as HISTORICAL context and
    must acquire its own current evidence (ADR-077, Part C)."""

    CONTRACT_NAME = "cortexprime.intelligence.investigation_episode"

    episode_ref: str            # == the investigation_ref it summarises
    tenant: TenantRef
    incident_ref: str
    facets: EpisodeFacets
    status: InvestigationStatus
    quality: ExperienceQuality
    assurance_status: AssuranceStatus
    residual_uncertainty: str
    incident_at: datetime       # when the incident occurred (T1)
    investigated_at: datetime   # when the investigation started
    completed_at: datetime      # when it reached its terminal disposition (T2)
    harness_version: str
    model_identity: str
    conclusion: Optional[InvestigationConclusion] = None
    hypotheses: tuple[EpisodeHypothesis, ...] = ()
    test_refs: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()
    prediction_refs: tuple[str, ...] = ()
    verification_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in ("episode_ref", "incident_ref", "residual_uncertainty",
                     "harness_version", "model_identity"):
            _req_str(getattr(self, name), name)
        if not isinstance(self.tenant, TenantRef):
            raise ContractViolation("tenant must be a TenantRef; experience is tenant-scoped")
        if not isinstance(self.facets, EpisodeFacets):
            raise ContractViolation("facets must be EpisodeFacets")
        if not isinstance(self.status, InvestigationStatus):
            raise ContractViolation("status must be an InvestigationStatus")
        if not isinstance(self.quality, ExperienceQuality):
            raise ContractViolation("quality must be an ExperienceQuality (no numeric confidence)")
        if not isinstance(self.assurance_status, AssuranceStatus):
            raise ContractViolation("assurance_status must be an AssuranceStatus")
        if self.conclusion is not None and not isinstance(self.conclusion, InvestigationConclusion):
            raise ContractViolation("conclusion must be an InvestigationConclusion or None")
        if not isinstance(self.hypotheses, tuple) or not all(
            isinstance(h, EpisodeHypothesis) for h in self.hypotheses
        ):
            raise ContractViolation("hypotheses must be a tuple of EpisodeHypothesis (references only)")
        for name in ("test_refs", "evidence_refs", "prediction_refs", "verification_refs"):
            _req_ref_tuple(getattr(self, name), name)
        for name in ("incident_at", "investigated_at", "completed_at"):
            _req_aware(getattr(self, name), name)

    def to_dict(self) -> dict:
        return {
            "episode_ref": self.episode_ref, "tenant": self.tenant.tenant_id,
            "incident_ref": self.incident_ref, "facets": self.facets.to_dict(),
            "status": self.status.value,
            "conclusion": self.conclusion.value if self.conclusion else None,
            "quality": self.quality.value, "assurance_status": self.assurance_status.value,
            "residual_uncertainty": self.residual_uncertainty,
            "incident_at": self.incident_at.isoformat(),
            "investigated_at": self.investigated_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "harness_version": self.harness_version, "model_identity": self.model_identity,
            "hypotheses": [h.to_dict() for h in self.hypotheses],
            "test_refs": list(self.test_refs), "evidence_refs": list(self.evidence_refs),
            "prediction_refs": list(self.prediction_refs),
            "verification_refs": list(self.verification_refs),
        }

    # NOTE, loudly: there is NO to_fact()/to_belief()/to_outcome()/to_verification()
    # here. That absence is the experience-is-not-truth firewall (Part C). Adding one
    # would let history mint World truth and breaches ADR-062/077.
