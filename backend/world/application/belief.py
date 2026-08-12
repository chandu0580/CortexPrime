"""Belief formation — FACTS + EVIDENCE -> CORROBORATION -> BELIEF.

A Belief is CortexPrime's held position on a proposition, derived
deterministically from structured evidence — never from model text. This module
is the bridge the Intelligence Plane consumes:

    Facts (bitemporal projection, Phase 7.3)
      + Authority decision   (Phase 7.4)
      + Freshness verdict     (Phase 7.4)
      + Corroboration         (Phase 7.5, here)
        -> Belief (contract) + a structured, queryable evidence graph

It is a **derived projection**, not a durable ledger (ADR-067): a belief is a
pure function of the durable facts/observations and the explicit policies, so it
reconstructs identically after a crash without any belief table. No belief
database, no migration, no mutable truth.

The invariants (L1-L16; ADR-062/063/066):
  * A Belief is derived only from real Facts/Observations. Raw text and model
    output cannot become a Belief; there is no ``to_belief`` and the belief
    formation input is structured evidence, not a string.
  * **Authority is not replaced by corroboration** (Part E). The effective value
    is the authority decision's when a policy governs; corroboration only
    resolves an *ungoverned* proposition, and only when its sources agree.
  * **Corroboration is independence, not counting** (Part D). Multiple
    observations from the same source are correlated — one independent source,
    not many. Distinct sources agreeing are independent corroboration.
  * **Conflict is preserved** (Part G). Equal-authority disagreement, or
    ungoverned disagreement, stays CONFLICTED; contradictory evidence is never
    erased.
  * **STALE / UNKNOWN are never FALSE** (Part F/H). Stale evidence yields a STALE
    belief with its value intact; absence yields UNKNOWN.
  * **Confidence stays UNCALIBRATED** (Part I). No number is invented; a Belief's
    confidence is ``ClaimConfidence.uncalibrated()`` until measured calibration
    exists (a later phase).

It imports the epistemic contracts, the Phase 7.3/7.4 read layers, and stdlib —
no connector, gateway, transport, credential, scheduler, or execution. A belief
never executes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional, Protocol

from backend.contracts.tenant import TenantRef
from backend.contracts.world import (
    Belief,
    ClaimConfidence,
    EpistemicStatus,
    Observation,
    ProvenanceRef,
    SourceAuthority,
)
from backend.platform.hashing import compute_digest
from backend.platform.identity.generators import prefixed_id
from backend.world.application.authority import AuthorityPolicy, AuthorityStatus
from backend.world.application.freshness import FreshnessResult, FreshnessState
from backend.world.application.world_query import ObservationEvidence, WorldQuery

__all__ = [
    "CorroborationLevel",
    "CorroborationAssessment",
    "BeliefView",
    "BeliefFormation",
    "ObservationCorroborationReader",
]


class CorroborationLevel(str, Enum):
    """How the evidence corroborates the effective value — independence, not a
    count, and never a probability."""

    INDEPENDENT = "independent"
    """Two or more *distinct* sources agree on the value."""
    SINGLE = "single"
    """Exactly one source supports the value (one or more correlated
    observations from it — correlated evidence is not independent corroboration)."""
    CONTRADICTED = "contradicted"
    """Sources disagree; there is no single corroborated value."""
    INSUFFICIENT = "insufficient"
    """No evidence covers the queried instant."""


class ObservationCorroborationReader(Protocol):
    """The read-only observation source for corroboration (a subset of the SQL
    repository). Tenant-scoped, fail-closed."""

    def list_for_subject(
        self, *, tenant_id: str, subject_ref: str, predicate: str
    ) -> tuple[Observation, ...]:
        ...


@dataclass(frozen=True)
class CorroborationAssessment:
    """The deterministic corroboration verdict for one proposition."""

    level: CorroborationLevel
    independent_sources: tuple[str, ...]          # distinct source_refs that agree
    supporting: tuple[ObservationEvidence, ...]    # evidence for the effective value
    contradicting: tuple[ObservationEvidence, ...]  # evidence for a different value
    correlated_count: int                          # supporting obs beyond the source count
    reason: str

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "independent_sources": list(self.independent_sources),
            "correlated_count": self.correlated_count,
            "supporting": [e.to_dict() for e in self.supporting],
            "contradicting": [e.to_dict() for e in self.contradicting],
            "reason": self.reason,
        }


@dataclass(frozen=True)
class BeliefView:
    """The structured, explainable belief and its evidence graph (Part L).

    ``belief`` is the typed :class:`Belief` contract the Intelligence Plane
    consumes (``None`` when UNKNOWN — nothing grounds a belief). The rest is the
    evidence graph a future LLM may verbalize but never has to reconstruct."""

    tenant_id: str
    subject_ref: str
    predicate: str
    status: EpistemicStatus
    value: Any
    confidence: ClaimConfidence
    belief: Optional[Belief]
    corroboration: CorroborationAssessment
    authority: Any                 # AuthorityDecision (Phase 7.4)
    freshness: FreshnessResult
    queried_valid_at: Optional[datetime] = None
    as_known_at: Optional[datetime] = None

    def to_dict(self) -> dict:
        """WHY do we believe this — the structured evidence graph."""
        return {
            "what": {"subject_ref": self.subject_ref, "predicate": self.predicate,
                     "value": self.value},
            "status": self.status.value,
            "confidence": {"state": self.confidence.state.value,
                           "value": self.confidence.value},  # UNCALIBRATED -> None
            "when_valid": self.queried_valid_at.isoformat() if self.queried_valid_at else None,
            "as_known_at": self.as_known_at.isoformat() if self.as_known_at else None,
            "authority": {
                "status": self.authority.status.value,
                "reason": self.authority.reason,
                "source_ref": self.authority.source_ref,
                "tier": self.authority.tier.value if self.authority.tier else None,
            },
            "freshness": {"state": self.freshness.state.value,
                          "age_seconds": self.freshness.age_seconds,
                          "reason": self.freshness.reason},
            "corroboration": self.corroboration.to_dict(),
            "conflicted": self.status is EpistemicStatus.CONFLICTED,
            "tenant": self.tenant_id,
        }


class BeliefFormation:
    """Forms a Belief from the World Plane's evidence — deterministically.

    Constructed with a :class:`WorldQuery` (for the temporal/authority/freshness
    projection) and an observation reader (for corroboration, which must see
    every observation, not only the ones that became fact versions). The
    ``authority_policy`` is used only to tier the corroboration evidence for
    display; the *decision* comes from the WorldQuery. No provider, no clock of
    its own (the caller supplies ``now``), no execution."""

    def __init__(
        self,
        *,
        query: WorldQuery,
        observations: ObservationCorroborationReader,
        authority_policy: Optional[AuthorityPolicy] = None,
        produced_by: str = "belief:world-beliefs/1",
    ) -> None:
        self._query = query
        self._observations = observations
        self._authority_policy = authority_policy or AuthorityPolicy.none()
        self._produced_by = produced_by

    # -- public forms -------------------------------------------------------

    def form_current(
        self, *, tenant: TenantRef, subject_ref: str, predicate: str, now: datetime,
        recorded_at: Optional[datetime] = None,
    ) -> BeliefView:
        wqr = self._query.current(tenant=tenant, subject_ref=subject_ref,
                                  predicate=predicate, now=now)
        return self._form(tenant, subject_ref, predicate, at_valid=now, now=now,
                          known_at=None, wqr=wqr, recorded_at=recorded_at or now,
                          queried_valid_at=now, as_known_at=None)

    def form_as_of_valid(
        self, *, tenant: TenantRef, subject_ref: str, predicate: str,
        at_valid: datetime, now: datetime, known_at: Optional[datetime] = None,
        recorded_at: Optional[datetime] = None,
    ) -> BeliefView:
        wqr = self._query.as_of_valid(tenant=tenant, subject_ref=subject_ref,
                                      predicate=predicate, at_valid=at_valid, now=now,
                                      known_at=known_at)
        return self._form(tenant, subject_ref, predicate, at_valid=at_valid, now=now,
                          known_at=known_at, wqr=wqr, recorded_at=recorded_at or now,
                          queried_valid_at=at_valid, as_known_at=known_at)

    def form_as_known(
        self, *, tenant: TenantRef, subject_ref: str, predicate: str,
        known_at: datetime, now: Optional[datetime] = None,
        recorded_at: Optional[datetime] = None,
    ) -> BeliefView:
        wqr = self._query.as_known(tenant=tenant, subject_ref=subject_ref,
                                   predicate=predicate, known_at=known_at, now=now)
        moment = now or known_at
        return self._form(tenant, subject_ref, predicate, at_valid=known_at, now=moment,
                          known_at=known_at, wqr=wqr, recorded_at=recorded_at or moment,
                          queried_valid_at=known_at, as_known_at=known_at)

    # -- internals ----------------------------------------------------------

    def _latest_per_source(
        self, tenant_id: str, subject_ref: str, predicate: str,
        at_valid: datetime, known_at: Optional[datetime],
    ) -> dict[str, Observation]:
        """The most recent informative observation from each source, honoring
        both temporal axes: observed_at <= at_valid AND recorded_at <= known_at.
        Same-source duplicates collapse to one — correlated, not independent."""
        latest: dict[str, Observation] = {}
        for obs in self._observations.list_for_subject(
                tenant_id=tenant_id, subject_ref=subject_ref, predicate=predicate):
            if obs.value is None:
                continue
            if obs.instant.observed_at > at_valid:
                continue
            if known_at is not None and obs.recorded_at > known_at:
                continue
            ref = obs.source.source_ref
            current = latest.get(ref)
            if current is None or (
                (obs.instant.observed_at, obs.recorded_at)
                > (current.instant.observed_at, current.recorded_at)
            ):
                latest[ref] = obs
        return latest

    def _evidence_of(self, obs: Observation) -> ObservationEvidence:
        kind, ref = obs.source.kind.value, obs.source.source_ref
        return ObservationEvidence(
            observation_id=obs.record_id, source_kind=kind, source_ref=ref,
            observed_at=obs.instant.observed_at, retrieved_at=obs.instant.retrieved_at,
            status=obs.status.value, value=obs.value,
            tier=self._authority_policy.authority_of(source_kind=kind, source_ref=ref),
            execution_ref=obs.provenance.execution_ref,
            trace_ref=obs.provenance.trace_ref)

    def _form(
        self, tenant: TenantRef, subject_ref: str, predicate: str, *,
        at_valid: datetime, now: datetime, known_at: Optional[datetime], wqr,
        recorded_at: datetime, queried_valid_at: Optional[datetime],
        as_known_at: Optional[datetime],
    ) -> BeliefView:
        if not isinstance(tenant, TenantRef):
            raise TypeError("tenant must be an explicit TenantRef (fail closed)")

        latest = self._latest_per_source(
            tenant.tenant_id, subject_ref, predicate, at_valid, known_at)
        all_obs = tuple(latest.values())
        # count total supporting observations (for correlated_count) across ALL
        # observations from supporting sources, not just the latest.
        source_obs_counts = self._source_obs_counts(
            tenant.tenant_id, subject_ref, predicate, at_valid, known_at)

        # 1) The effective value + base status. Authority is primary; corroboration
        #    resolves only an ungoverned proposition, and only when sources agree.
        value, base_status = self._decide(wqr, latest)

        # 2) Corroboration relative to the effective value.
        eff_digest = compute_digest(value).value if value is not None else None
        corroboration = self._corroborate(
            latest, source_obs_counts, eff_digest, base_status)

        # 3) Freshness overlay: a supported-but-stale belief is STALE, not FALSE.
        status = base_status
        if base_status is EpistemicStatus.AFFIRMED and wqr.freshness.state is FreshnessState.STALE:
            status = EpistemicStatus.STALE

        # 4) Build the grounded Belief contract (None when UNKNOWN).
        belief = self._build_belief(
            tenant, subject_ref, predicate, value, status, corroboration,
            recorded_at) if status is not EpistemicStatus.UNKNOWN else None

        return BeliefView(
            tenant_id=tenant.tenant_id, subject_ref=subject_ref, predicate=predicate,
            status=status, value=value, confidence=ClaimConfidence.uncalibrated(),
            belief=belief, corroboration=corroboration, authority=wqr.authority,
            freshness=wqr.freshness, queried_valid_at=queried_valid_at,
            as_known_at=as_known_at)

    def _source_obs_counts(
        self, tenant_id, subject_ref, predicate, at_valid, known_at,
    ) -> dict[str, int]:
        counts: dict[str, int] = {}
        for obs in self._observations.list_for_subject(
                tenant_id=tenant_id, subject_ref=subject_ref, predicate=predicate):
            if obs.value is None or obs.instant.observed_at > at_valid:
                continue
            if known_at is not None and obs.recorded_at > known_at:
                continue
            counts[obs.source.source_ref] = counts.get(obs.source.source_ref, 0) + 1
        return counts

    def _decide(self, wqr, latest: dict[str, Observation]):
        """Effective (value, base status). Authority governs; corroboration only
        resolves the ungoverned case, and never silently resolves disagreement."""
        a = wqr.authority
        if a.status is AuthorityStatus.RESOLVED:
            return a.value, EpistemicStatus.AFFIRMED
        if a.status is AuthorityStatus.CONFLICTED:
            return None, EpistemicStatus.CONFLICTED
        if a.status is AuthorityStatus.UNKNOWN or not latest:
            return None, EpistemicStatus.UNKNOWN
        # UNGOVERNED: let the sources speak, but never silently resolve a
        # disagreement (Part G).
        digests = {compute_digest(o.value).value for o in latest.values()}
        if len(digests) > 1:
            return None, EpistemicStatus.CONFLICTED
        # a single agreed value across one or more sources
        return next(iter(latest.values())).value, EpistemicStatus.AFFIRMED

    def _corroborate(
        self, latest: dict[str, Observation], source_counts: dict[str, int],
        eff_digest: Optional[str], base_status: EpistemicStatus,
    ) -> CorroborationAssessment:
        if not latest:
            return CorroborationAssessment(
                level=CorroborationLevel.INSUFFICIENT, independent_sources=(),
                supporting=(), contradicting=(), correlated_count=0,
                reason="no evidence covers the queried instant (INSUFFICIENT, "
                       "not FALSE)")
        supporting: list[ObservationEvidence] = []
        contradicting: list[ObservationEvidence] = []
        support_sources: list[str] = []
        for ref, obs in sorted(latest.items()):
            ev = self._evidence_of(obs)
            if eff_digest is not None and compute_digest(obs.value).value == eff_digest:
                supporting.append(ev)
                support_sources.append(ref)
            else:
                contradicting.append(ev)
        correlated = sum(max(0, source_counts.get(r, 1) - 1) for r in support_sources)

        if base_status is EpistemicStatus.CONFLICTED or eff_digest is None:
            level = CorroborationLevel.CONTRADICTED
            reason = ("sources disagree and no authority resolves it; both "
                      "evidence paths preserved")
        elif len(support_sources) >= 2:
            level = CorroborationLevel.INDEPENDENT
            reason = (f"{len(support_sources)} independent sources agree "
                      f"({', '.join(support_sources)})")
        elif len(support_sources) == 1:
            level = CorroborationLevel.SINGLE
            reason = (f"one source supports the value ({support_sources[0]}); "
                      f"{correlated} correlated observation(s) add no independence")
        else:
            level = CorroborationLevel.CONTRADICTED
            reason = "the effective value has no supporting source"
        return CorroborationAssessment(
            level=level, independent_sources=tuple(support_sources),
            supporting=tuple(supporting), contradicting=tuple(contradicting),
            correlated_count=correlated, reason=reason)

    def _build_belief(
        self, tenant: TenantRef, subject_ref: str, predicate: str, value: Any,
        status: EpistemicStatus, corroboration: CorroborationAssessment,
        recorded_at: datetime,
    ) -> Optional[Belief]:
        refs = tuple(sorted({e.observation_id
                             for e in corroboration.supporting + corroboration.contradicting}))
        if not refs:
            return None
        primary = corroboration.supporting[0] if corroboration.supporting \
            else corroboration.contradicting[0]
        provenance = ProvenanceRef(
            produced_by=self._produced_by, observation_ref=primary.observation_id,
            execution_ref=primary.execution_ref, trace_ref=primary.trace_ref)
        return Belief(
            record_id=prefixed_id("wbelief"), tenant=tenant, recorded_at=recorded_at,
            provenance=provenance, subject_ref=subject_ref, predicate=predicate,
            value=value, confidence=ClaimConfidence.uncalibrated(), status=status,
            basis=refs)
