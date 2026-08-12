"""Investigation experience — projection & structured retrieval (Phase 8.6).

Experience is a deterministic PROJECTION over the existing durable ledgers, not new
state: an ``InvestigationEpisode`` is reconstructed from the investigation aggregate
(cw_investigation) plus, optionally, the assurance verdicts (cw_verification) linked
to it. Nothing is copied from the World Plane — the episode holds references and
categorical summaries only, and has no way to mint a Fact/Belief/Outcome/Verification
(the contract omits any such method).

Relevance is deterministic and EXPLAINABLE before any semantic similarity: episodes
match on categorical facets (service / environment / symptom class / resource types)
derived from the incident reference and the prior differential, and every match
carries the reasons it matched — never a fabricated similarity score.

This module imports the intelligence/epistemic contracts and reads investigations
through a narrow port (composition supplies the SQL repository). It imports no World
storage, no connector, no provider, and no V1 memory.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Optional, Protocol

from backend.contracts.tenant import TenantRef
from backend.contracts.world import HypothesisStatus
from backend.contracts.intelligence import (
    AssuranceStatus,
    EpisodeFacets,
    EpisodeHypothesis,
    ExperienceQuality,
    Investigation,
    InvestigationConclusion,
    InvestigationEpisode,
    is_terminal_status,
)

__all__ = [
    "EpisodeSourcePort",
    "EpisodeProjection",
    "ExperienceMatch",
    "ExperienceRetrievalPort",
    "StructuredExperienceRetrieval",
    "derive_facets",
]

# Verdict values (mirrored as strings to avoid importing the assurance package here).
_VERDICT_SUPPORTED = "supported"

# Known resource classes we recognise as facet dimensions (prefix before "/").
_KNOWN_ENVIRONMENTS = frozenset({"production", "prod", "staging", "stage", "dev",
                                 "development", "test", "sandbox"})


class EpisodeSourcePort(Protocol):
    """Read-only source of investigation snapshots (composition backs it with the
    SQL investigation repository). Tenant-scoped, fail-closed."""

    def list_terminal(self, *, tenant_id: str, limit: int = 200) -> tuple[dict, ...]:
        ...


def derive_facets(investigation: Investigation) -> EpisodeFacets:
    """Deterministically derive relevance facets from the incident reference and the
    prior differential (Part F). Explainable, no similarity. Convention-tolerant:
    ``incident:{environment}:{service}:{symptom}`` is parsed when present, otherwise
    the best-effort tokens are used; resource types come from the hypotheses'
    subject prefixes."""
    tokens = [t for t in investigation.incident_ref.replace("/", ":").split(":") if t.strip()]
    if tokens and tokens[0] == "incident":
        tokens = tokens[1:]
    environment, service, symptom = "unknown", "unknown", "unknown"
    lowered = [t.lower() for t in tokens]
    env_idx = next((i for i, t in enumerate(lowered) if t in _KNOWN_ENVIRONMENTS), None)
    if env_idx is not None:
        environment = lowered[env_idx]
        rest = tokens[:env_idx] + tokens[env_idx + 1:]
    else:
        rest = tokens
    if rest:
        service = rest[0]
        if len(rest) >= 2:
            symptom = rest[-1]
    resource_types = tuple(sorted({
        h.subject_ref.split("/", 1)[0] for h in investigation.differential
        if "/" in h.subject_ref}))
    return EpisodeFacets(service=service or "unknown", environment=environment or "unknown",
                         symptom_class=symptom or "unknown", resource_types=resource_types)


class EpisodeProjection:
    """Projects a TERMINAL investigation into an ``InvestigationEpisode`` (Part D/E).

    ``assurance_verdicts`` maps a linked verification_ref to its Verdict value (from
    cw_verification, supplied by composition). Absent verdicts, the episode is
    conservatively UNASSURED — experience never claims independent verification it
    cannot show."""

    def project(
        self, *, investigation: Investigation,
        assurance_verdicts: Optional[dict[str, str]] = None,
    ) -> Optional[InvestigationEpisode]:
        if not is_terminal_status(investigation.status):
            return None  # only completed investigations become reusable experience
        verdicts = assurance_verdicts or {}
        quality = _quality(investigation, verdicts)
        assurance = _assurance_status(investigation, verdicts)
        residual = _residual(investigation, assurance)
        hyps = tuple(
            EpisodeHypothesis(
                hypothesis_ref=h.hypothesis_ref, subject_ref=h.subject_ref,
                proposition=h.proposition, status=h.status.value,
                evidence_for=h.evidence_for, evidence_against=h.evidence_against)
            for h in investigation.differential)
        return InvestigationEpisode(
            episode_ref=investigation.investigation_ref, tenant=investigation.tenant,
            incident_ref=investigation.incident_ref, facets=derive_facets(investigation),
            status=investigation.status, conclusion=investigation.conclusion,
            quality=quality, assurance_status=assurance, residual_uncertainty=residual,
            incident_at=investigation.created_at, investigated_at=investigation.created_at,
            completed_at=investigation.updated_at, harness_version=investigation.harness_version,
            model_identity=investigation.provenance.produced_by, hypotheses=hyps,
            test_refs=investigation.test_refs, evidence_refs=investigation.evidence_refs,
            prediction_refs=investigation.prediction_refs,
            verification_refs=investigation.verification_refs)


def _supported(investigation) -> list:
    return [h for h in investigation.differential if h.status is HypothesisStatus.SUPPORTED]


def _open(investigation) -> list:
    return [h for h in investigation.differential
            if h.status in (HypothesisStatus.OPEN, HypothesisStatus.UNRESOLVED)]


def _has_supported_verification(investigation, verdicts) -> bool:
    return any(verdicts.get(ref) == _VERDICT_SUPPORTED for ref in investigation.verification_refs)


def _quality(investigation, verdicts) -> ExperienceQuality:
    c = investigation.conclusion
    if c is InvestigationConclusion.RESOLVED:
        if _has_supported_verification(investigation, verdicts):
            return ExperienceQuality.DIRECTLY_ASSURED
        return (ExperienceQuality.PARTIALLY_SUPPORTED if _open(investigation)
                else ExperienceQuality.SUPPORTED)
    if c is InvestigationConclusion.CONFLICTED:
        return ExperienceQuality.CONFLICTED
    if c is InvestigationConclusion.UNRESOLVED:
        return ExperienceQuality.UNRESOLVED
    # INSUFFICIENT_EVIDENCE / BLOCKED / FAILED / ESCALATED / None
    return ExperienceQuality.INSUFFICIENT_EVIDENCE


def _assurance_status(investigation, verdicts) -> AssuranceStatus:
    if investigation.conclusion is InvestigationConclusion.CONFLICTED:
        return AssuranceStatus.CONFLICTED
    if _has_supported_verification(investigation, verdicts):
        return AssuranceStatus.ASSURED
    if investigation.verification_refs:
        return AssuranceStatus.INSUFFICIENT_EVIDENCE  # verified, but not supported
    return AssuranceStatus.UNASSURED


def _residual(investigation, assurance) -> str:
    parts = []
    supported = [h.hypothesis_ref for h in _supported(investigation)]
    open_ = [h.hypothesis_ref for h in _open(investigation)]
    if supported:
        parts.append(f"supported under conditions at the time: {supported}")
    if open_:
        parts.append(f"alternatives not eliminated: {open_}")
    if assurance is not AssuranceStatus.ASSURED:
        parts.append(f"not independently verified ({assurance.value})")
    return "; ".join(parts) or "no residual recorded"


@dataclass(frozen=True)
class ExperienceMatch:
    """One relevant historical episode and WHY it matched — historical evidence, not
    a current answer (Part G). ``match_reasons`` are the explainable dimensions."""

    episode_ref: str
    match_reasons: tuple[str, ...]
    relevant_hypotheses: tuple[EpisodeHypothesis, ...]
    relevant_tests: tuple[str, ...]
    assurance_status: str
    quality: str
    residual_uncertainty: str
    episode_time: datetime
    episode: InvestigationEpisode

    def to_context_dict(self) -> dict:
        """The HISTORICAL_INVESTIGATION_EXPERIENCE section payload — explicitly
        labelled as history, never world truth."""
        return {
            "episode_ref": self.episode_ref, "kind": "HISTORICAL_INVESTIGATION_EXPERIENCE",
            "match_reasons": list(self.match_reasons),
            "relevant_hypotheses": [{"proposition": h.proposition, "status": h.status,
                                     "subject_ref": h.subject_ref}
                                    for h in self.relevant_hypotheses],
            "relevant_test_refs": list(self.relevant_tests),
            "assurance_status": self.assurance_status, "quality": self.quality,
            "residual_uncertainty": self.residual_uncertainty,
            "episode_time": self.episode_time.isoformat(),
            "caveat": "historical experience, not current world truth; acquire fresh evidence",
        }


class ExperienceRetrievalPort(Protocol):
    """The narrow seam the investigator uses to obtain relevant prior experience.
    Returns historical evidence — never 'the current answer'."""

    def find_relevant_episodes(
        self, *, tenant: TenantRef, facets: EpisodeFacets, now: datetime,
        exclude_ref: Optional[str] = None, as_known_at: Optional[datetime] = None,
        limit: int = 5,
    ) -> tuple[ExperienceMatch, ...]:
        ...


class StructuredExperienceRetrieval:
    """Deterministic, explainable, tenant-scoped experience retrieval (Part F/G/J/K).

    No embeddings, no vector store, no similarity score — a categorical facet match
    with reasons. Composition supplies the episode source (tenant-scoped SQL) and,
    optionally, a verdict source for assurance status."""

    def __init__(
        self, *, source: EpisodeSourcePort, projection: Optional[EpisodeProjection] = None,
        verdicts_for: Optional[Callable[[str, tuple[str, ...]], dict[str, str]]] = None,
    ) -> None:
        self._source = source
        self._projection = projection or EpisodeProjection()
        self._verdicts_for = verdicts_for

    def find_relevant_episodes(
        self, *, tenant: TenantRef, facets: EpisodeFacets, now: datetime,
        exclude_ref: Optional[str] = None, as_known_at: Optional[datetime] = None,
        limit: int = 5,
    ) -> tuple[ExperienceMatch, ...]:
        if not isinstance(tenant, TenantRef):
            raise TypeError("tenant must be an explicit TenantRef (fail closed)")
        states = self._source.list_terminal(tenant_id=tenant.tenant_id, limit=200)
        scored: list[tuple[int, datetime, str, ExperienceMatch]] = []
        for state in states:
            inv = Investigation.from_dict(state)
            if exclude_ref is not None and inv.investigation_ref == exclude_ref:
                continue
            verdicts = None
            if self._verdicts_for is not None and inv.verification_refs:
                verdicts = self._verdicts_for(tenant.tenant_id, inv.verification_refs)
            episode = self._projection.project(investigation=inv, assurance_verdicts=verdicts)
            if episode is None:
                continue
            # Temporal safety (Part K): an episode that completed AFTER the as-known
            # cutoff is future knowledge and is not visible.
            if as_known_at is not None and episode.completed_at > as_known_at:
                continue
            reasons, strength = _match(facets, episode.facets)
            if strength <= 0:
                continue
            match = ExperienceMatch(
                episode_ref=episode.episode_ref, match_reasons=reasons,
                relevant_hypotheses=episode.hypotheses, relevant_tests=episode.test_refs,
                assurance_status=episode.assurance_status.value, quality=episode.quality.value,
                residual_uncertainty=episode.residual_uncertainty,
                episode_time=episode.completed_at, episode=episode)
            scored.append((strength, episode.completed_at, episode.episode_ref, match))
        # Deterministic ranking: more matched dimensions first, then newer, then ref.
        scored.sort(key=lambda s: (s[0], s[1].isoformat(), s[2]), reverse=True)
        return tuple(m for _s, _t, _r, m in scored[:limit])


def _match(current: EpisodeFacets, past: EpisodeFacets) -> tuple[tuple[str, ...], int]:
    """Categorical facet match with explainable reasons. A 'strong' dimension
    (service or symptom_class) is required for any relevance; the strength is the
    COUNT of matched dimensions (an explainable count, NOT a similarity score)."""
    reasons: list[str] = []
    strong = 0
    if current.service == past.service and current.service != "unknown":
        reasons.append(f"service={past.service} matched")
        strong += 1
    if current.symptom_class == past.symptom_class and current.symptom_class != "unknown":
        reasons.append(f"symptom={past.symptom_class} matched")
        strong += 1
    if strong == 0:
        return (), 0
    extra = 0
    if current.environment == past.environment and current.environment != "unknown":
        reasons.append(f"environment={past.environment} matched")
        extra += 1
    overlap = sorted(set(current.resource_types) & set(past.resource_types))
    if overlap:
        reasons.append(f"resource types overlap: {overlap}")
        extra += 1
    return tuple(reasons), strong + extra
