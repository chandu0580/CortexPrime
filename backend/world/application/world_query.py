"""World Query — the read-only, deterministic, explainable view of world state.

The one place a consumer (a future LLM among them) asks the World Plane what it
knows, and receives a *structured* answer it does not have to reconstruct itself:

    WHAT / WHEN (valid) / AS-KNOWN (recorded) / WHY (authority) / SOURCE /
    FRESH? / CONFLICTED? / SUPPORTING EVIDENCE / TENANT

It composes three deterministic layers, each already built:
  * the Phase 7.3 bitemporal projection (``project_valid_at`` / ``history``) —
    the raw temporal truth, never regressed here;
  * an explicit ``FreshnessPolicy`` — is the evidence fresh, stale, or simply
    ungoverned (UNKNOWN)? STALE is never FALSE;
  * an explicit ``AuthorityPolicy`` — which source is authoritative, and why?
    Recency never overrides authority; equal-authority disagreement stays
    CONFLICTED with both evidence paths preserved.

It is READ-ONLY and pure of execution: it depends on two narrow *reader* ports
(fact versions, observations) and imports no connector, gateway, transport,
credential, scheduler, or execution — the World Plane describes reality, it never
acts. It contacts no provider; provider ingestion is a different boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional, Protocol

from backend.contracts.tenant import TenantRef
from backend.contracts.world import EpistemicStatus, Observation, SourceAuthority
from backend.world.application.authority import (
    AuthorityAlternative,
    AuthorityDecision,
    AuthorityPolicy,
    AuthorityStatus,
)
from backend.world.application.bitemporal import (
    FactStateView,
    FactVersion,
    HistoryEntry,
    history,
    knowledge_current,
    project_valid_at,
)
from backend.world.application.fact_derivation import fact_semantic_identity
from backend.world.application.freshness import (
    FreshnessPolicy,
    FreshnessResult,
    FreshnessState,
)

__all__ = [
    "FactVersionReader",
    "ObservationReader",
    "ObservationEvidence",
    "WorldQueryResult",
    "WorldQuery",
]


class FactVersionReader(Protocol):
    """The read-only fact source (a subset of the SQL repository). Tenant-scoped,
    fail-closed."""

    def versions_for(
        self, *, tenant_id: str, semantic_identity: str
    ) -> tuple[FactVersion, ...]:
        ...


class ObservationReader(Protocol):
    """The read-only observation source. Tenant-scoped, fail-closed."""

    def get_observation(
        self, *, tenant_id: str, observation_id: str
    ) -> Optional[Observation]:
        ...


@dataclass(frozen=True)
class ObservationEvidence:
    """One supporting observation behind a fact — source, times, value, tier."""

    observation_id: str
    source_kind: str
    source_ref: str
    observed_at: datetime
    retrieved_at: datetime
    status: str
    value: Any
    tier: SourceAuthority
    execution_ref: Optional[str] = None
    trace_ref: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "observation_id": self.observation_id,
            "source_kind": self.source_kind,
            "source_ref": self.source_ref,
            "observed_at": self.observed_at.isoformat(),
            "retrieved_at": self.retrieved_at.isoformat(),
            "status": self.status,
            "value": self.value,
            "authority_tier": self.tier.value,
            "execution_ref": self.execution_ref,
            "trace_ref": self.trace_ref,
        }


@dataclass(frozen=True)
class WorldQueryResult:
    """The explainable, typed answer to a world query.

    ``temporal`` is the raw Phase 7.3 projection (never regressed). ``authority``
    is the source-tier decision layered on top; ``freshness`` the freshness
    verdict; ``evidence`` the supporting observations. ``effective_value`` /
    ``effective_status`` are the answer a consumer should act on: the authority-
    resolved value when a policy governs, otherwise the temporal value."""

    tenant_id: str
    subject_ref: str
    predicate: str
    semantic_identity: str
    temporal: FactStateView
    freshness: FreshnessResult
    authority: AuthorityDecision
    evidence: tuple[ObservationEvidence, ...]
    queried_valid_at: Optional[datetime] = None
    as_known_at: Optional[datetime] = None

    @property
    def effective_status(self) -> EpistemicStatus:
        if self.authority.status is AuthorityStatus.RESOLVED:
            return EpistemicStatus.AFFIRMED
        if self.authority.status is AuthorityStatus.CONFLICTED:
            return EpistemicStatus.CONFLICTED
        if self.authority.status is AuthorityStatus.UNKNOWN:
            return EpistemicStatus.UNKNOWN
        # UNGOVERNED — defer to the raw temporal projection.
        return self.temporal.status

    @property
    def effective_value(self) -> Any:
        if self.authority.status is AuthorityStatus.RESOLVED:
            return self.authority.value
        if self.effective_status is EpistemicStatus.AFFIRMED:
            return self.temporal.value
        return None

    def to_dict(self) -> dict:
        """The structured, explainable result — the shape a future LLM consumes
        without reconstructing temporal truth itself."""
        return {
            "what": {"subject_ref": self.subject_ref, "predicate": self.predicate,
                     "value": self.effective_value},
            "status": self.effective_status.value,
            "when_valid": self.queried_valid_at.isoformat() if self.queried_valid_at else None,
            "as_known_at": self.as_known_at.isoformat() if self.as_known_at else None,
            "why": {
                "authority_status": self.authority.status.value,
                "reason": self.authority.reason,
                "source_kind": self.authority.source_kind,
                "source_ref": self.authority.source_ref,
                "tier": self.authority.tier.value if self.authority.tier else None,
                "alternatives": [
                    {"value": a.value, "source_ref": a.source_ref,
                     "tier": a.tier.value, "observation_ref": a.observation_ref}
                    for a in self.authority.alternatives
                ],
            },
            "fresh": {
                "state": self.freshness.state.value,
                "age_seconds": self.freshness.age_seconds,
                "horizon_seconds": self.freshness.horizon_seconds,
                "reason": self.freshness.reason,
            },
            "conflicted": self.effective_status is EpistemicStatus.CONFLICTED,
            "evidence": [e.to_dict() for e in self.evidence],
            "tenant": self.tenant_id,
        }


class WorldQuery:
    """Read-only world queries with freshness and authority overlays.

    Constructed with the two reader ports and (optionally) the freshness and
    authority policies. Every method is a pure read: it fetches tenant-scoped
    versions and their grounding observations and composes a deterministic
    result. It never writes, never contacts a provider, never executes."""

    def __init__(
        self,
        *,
        facts: FactVersionReader,
        observations: ObservationReader,
        freshness_policy: Optional[FreshnessPolicy] = None,
        authority_policy: Optional[AuthorityPolicy] = None,
    ) -> None:
        self._facts = facts
        self._observations = observations
        self._freshness = freshness_policy or FreshnessPolicy.none()
        self._authority = authority_policy or AuthorityPolicy.none()

    # -- public queries -----------------------------------------------------

    def current(
        self, *, tenant: TenantRef, subject_ref: str, predicate: str, now: datetime
    ) -> WorldQueryResult:
        """What the World Plane currently represents (latest knowledge, valid
        now)."""
        return self._answer(tenant=tenant, subject_ref=subject_ref, predicate=predicate,
                            at_valid=now, now=now, known_at=None, queried_valid_at=now)

    def as_of_valid(
        self, *, tenant: TenantRef, subject_ref: str, predicate: str,
        at_valid: datetime, now: datetime, known_at: Optional[datetime] = None,
    ) -> WorldQueryResult:
        """What was valid at world time ``at_valid`` (per latest knowledge, or per
        knowledge as of ``known_at``)."""
        return self._answer(tenant=tenant, subject_ref=subject_ref, predicate=predicate,
                            at_valid=at_valid, now=now, known_at=known_at,
                            queried_valid_at=at_valid)

    def as_known(
        self, *, tenant: TenantRef, subject_ref: str, predicate: str,
        known_at: datetime, now: Optional[datetime] = None,
    ) -> WorldQueryResult:
        """What CortexPrime had recorded by knowledge time ``known_at`` (projected
        to the world as it understood it then)."""
        return self._answer(tenant=tenant, subject_ref=subject_ref, predicate=predicate,
                            at_valid=known_at, now=now or known_at, known_at=known_at,
                            queried_valid_at=known_at, as_known_at=known_at)

    def history(
        self, *, tenant: TenantRef, subject_ref: str, predicate: str
    ) -> tuple[HistoryEntry, ...]:
        """The full append-only version history for a semantic identity."""
        sid = fact_semantic_identity(tenant, subject_ref, predicate)
        versions = self._facts.versions_for(
            tenant_id=tenant.tenant_id, semantic_identity=sid)
        return history(versions)

    def evidence_for(
        self, *, tenant: TenantRef, subject_ref: str, predicate: str
    ) -> tuple[ObservationEvidence, ...]:
        """Every supporting observation behind a semantic identity, with source
        and tier — the answer to 'which observations support this fact, and from
        which provider?'"""
        sid = fact_semantic_identity(tenant, subject_ref, predicate)
        versions = self._facts.versions_for(
            tenant_id=tenant.tenant_id, semantic_identity=sid)
        return self._evidence(tenant.tenant_id, versions)

    # -- internals ----------------------------------------------------------

    def _observation_of(self, tenant_id: str, version: FactVersion) -> Optional[Observation]:
        return self._observations.get_observation(
            tenant_id=tenant_id, observation_id=version.observation_ref)

    def _source_of(self, obs: Optional[Observation]) -> tuple[str, str]:
        if obs is None:
            return "unknown", "unknown"
        return obs.source.kind.value, obs.source.source_ref

    def _evidence(
        self, tenant_id: str, versions: tuple[FactVersion, ...]
    ) -> tuple[ObservationEvidence, ...]:
        seen: set[str] = set()
        out: list[ObservationEvidence] = []
        for v in versions:
            if v.observation_ref in seen:
                continue
            seen.add(v.observation_ref)
            obs = self._observations.get_observation(
                tenant_id=tenant_id, observation_id=v.observation_ref)
            if obs is None:
                continue
            kind, ref = obs.source.kind.value, obs.source.source_ref
            out.append(ObservationEvidence(
                observation_id=obs.record_id, source_kind=kind, source_ref=ref,
                observed_at=obs.instant.observed_at, retrieved_at=obs.instant.retrieved_at,
                status=obs.status.value, value=obs.value,
                tier=self._authority.authority_of(source_kind=kind, source_ref=ref),
                execution_ref=obs.provenance.execution_ref,
                trace_ref=obs.provenance.trace_ref))
        return tuple(out)

    def _answer(
        self, *, tenant: TenantRef, subject_ref: str, predicate: str,
        at_valid: datetime, now: datetime, known_at: Optional[datetime],
        queried_valid_at: Optional[datetime], as_known_at: Optional[datetime] = None,
    ) -> WorldQueryResult:
        if not isinstance(tenant, TenantRef):
            raise TypeError("tenant must be an explicit TenantRef (fail closed)")
        sid = fact_semantic_identity(tenant, subject_ref, predicate)
        all_versions = self._facts.versions_for(
            tenant_id=tenant.tenant_id, semantic_identity=sid)
        # Knowledge-time filter first (transaction time), then valid-time.
        visible = knowledge_current(all_versions, known_at)
        temporal = project_valid_at(visible, at_valid)

        # Source lookup for the versions that cover the queried instant.
        covering = tuple(v for v in visible if v.valid_from <= at_valid)
        src = {v.fact_id: self._source_of(self._observation_of(tenant.tenant_id, v))
               for v in covering}

        authority = self._resolve_authority(covering, at_valid, src)
        freshness = self._evaluate_freshness(
            covering, temporal, authority, src, now, predicate)
        evidence = self._evidence(tenant.tenant_id, covering)

        return WorldQueryResult(
            tenant_id=tenant.tenant_id, subject_ref=subject_ref, predicate=predicate,
            semantic_identity=sid, temporal=temporal, freshness=freshness,
            authority=authority, evidence=evidence,
            queried_valid_at=queried_valid_at, as_known_at=as_known_at)

    def _resolve_authority(
        self, covering: tuple[FactVersion, ...], at_valid: datetime,
        src: dict[str, tuple[str, str]],
    ) -> AuthorityDecision:
        if not covering:
            return AuthorityDecision(
                status=AuthorityStatus.UNKNOWN,
                reason="no evidence covers the queried time (UNKNOWN, not FALSE)")

        def _alt(v: FactVersion) -> AuthorityAlternative:
            kind, ref = src[v.fact_id]
            return AuthorityAlternative(
                value=v.value, source_kind=kind, source_ref=ref,
                tier=self._authority.authority_of(source_kind=kind, source_ref=ref),
                observation_ref=v.observation_ref)

        if not self._authority.governs:
            # No authority policy: the temporal projection stands unchanged.
            tv = project_valid_at(covering, at_valid)
            return AuthorityDecision(
                status=AuthorityStatus.UNGOVERNED,
                reason="no authority policy governs this fact; the temporal "
                       "projection stands",
                value=tv.value if tv.status is EpistemicStatus.AFFIRMED else None,
                alternatives=tuple(_alt(v) for v in covering))

        # Governed: the highest tier decides. Recency never crosses tiers.
        tiers = {v.fact_id: self._authority.authority_of(
            source_kind=src[v.fact_id][0], source_ref=src[v.fact_id][1])
            for v in covering}
        max_rank = max(t.rank for t in tiers.values())
        top = tuple(v for v in covering if tiers[v.fact_id].rank == max_rank)
        lower = tuple(v for v in covering if tiers[v.fact_id].rank < max_rank)

        # Within the authoritative tier, the ordinary temporal projection applies
        # (a single source changing over time). Recency is a tiebreak only here.
        top_view = project_valid_at(top, at_valid)
        if top_view.status is EpistemicStatus.AFFIRMED:
            winner = next(v for v in top if v.fact_id in top_view.fact_ids)
            kind, ref = src[winner.fact_id]
            tier = tiers[winner.fact_id]
            # Alternatives: every covering version whose value differs from the
            # chosen one (lower tiers AND same-tier earlier states).
            alts = tuple(_alt(v) for v in covering
                         if v.value_digest != winner.value_digest)
            return AuthorityDecision(
                status=AuthorityStatus.RESOLVED, value=winner.value,
                source_kind=kind, source_ref=ref, tier=tier,
                reason=(f"source {ref!r} is the highest authority ({tier.value}) "
                        f"governing this fact; lower-tier or older evidence does "
                        "not override it (recency is not authority)"),
                alternatives=alts)
        # The authoritative tier itself disagrees at this instant: no authority
        # to choose — CONFLICTED, both preserved.
        return AuthorityDecision(
            status=AuthorityStatus.CONFLICTED,
            reason="the highest-authority sources disagree at the same valid "
                   "instant; no authority to choose (both evidence paths kept)",
            alternatives=tuple(_alt(v) for v in top) + tuple(_alt(v) for v in lower))

    def _evaluate_freshness(
        self, covering: tuple[FactVersion, ...], temporal: FactStateView,
        authority: AuthorityDecision, src: dict[str, tuple[str, str]],
        now: datetime, predicate: str,
    ) -> FreshnessResult:
        # Freshness is evaluated against the evidence behind the *effective*
        # value: the authority winner if resolved, else the temporal winner. A
        # fact's valid_from is exactly its grounding observation's observed_at
        # (set at derivation), so it is the age input — no extra fetch needed.
        winner = self._effective_version(covering, temporal, authority)
        if winner is None:
            return FreshnessResult(
                state=FreshnessState.UNKNOWN, evaluated_at=now,
                policy_name=self._freshness.name,
                reason="no single effective value to age (conflicted or unknown)")
        kind = src.get(winner.fact_id, ("unknown", "unknown"))[0]
        return self._freshness.evaluate(
            observed_at=winner.valid_from, now=now, source_kind=kind,
            predicate=predicate)

    def _effective_version(
        self, covering: tuple[FactVersion, ...], temporal: FactStateView,
        authority: AuthorityDecision,
    ) -> Optional[FactVersion]:
        if authority.status is AuthorityStatus.RESOLVED:
            # The winning value's most-recent covering version (its own evidence).
            matches = [v for v in covering if v.value == authority.value]
            if matches:
                return max(matches, key=lambda v: (v.valid_from, v.recorded_at, v.fact_id))
            return None
        if temporal.status is EpistemicStatus.AFFIRMED:
            return next((v for v in covering if v.fact_id in temporal.fact_ids), None)
        return None
