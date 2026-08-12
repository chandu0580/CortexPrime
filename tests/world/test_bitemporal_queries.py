"""Phase 7.3 — bitemporal query semantics + the load-bearing example (STEP 6/16).

Pure projection over fact versions: current, as-of-valid time, as-known time, and
history — and the exact deployment-replicas scenario STEP 6 requires, proving the
World Plane answers "what was true in the world?" and "what did CortexPrime know?"
as two independent questions, with supersession that preserves history and never
overwrites.
"""

from __future__ import annotations

from datetime import datetime, timezone

from backend.contracts.evidence import SourceStatus
from backend.contracts.knowledge import KnowledgeAuthority
from backend.contracts.tenant import TenantRef
from backend.contracts.world import (
    EpistemicStatus,
    Observation,
    ObservationInstant,
    ObservationSource,
    ObservationSourceKind,
    ProvenanceRef,
)
from backend.world.application import (
    FactDerivation,
    FactVersion,
    as_known,
    as_of_valid,
    current_state,
    fact_semantic_identity,
    history,
    project_valid_at,
)


def _utc(h, m):
    return datetime(2026, 8, 12, h, m, tzinfo=timezone.utc)


ACME = TenantRef(tenant_id="acme")
SID = fact_semantic_identity(ACME, "deployment/payments", "spec.replicas")


def _fv(value, valid_from, recorded_at, *, status=EpistemicStatus.AFFIRMED, fid=None):
    vd = f"vd-{value}"
    return FactVersion(
        fact_id=fid or f"f-{value}-{valid_from.isoformat()}", semantic_identity=SID,
        tenant_id="acme", subject_ref="deployment/payments", predicate="spec.replicas",
        value=value, value_digest=vd, valid_from=valid_from, recorded_at=recorded_at,
        status=status, authority="advisory", observation_ref=f"o-{value}")


# ======================================================================
# Projection primitives
# ======================================================================

class TestProjection:
    def test_unknown_when_nothing_covers_the_instant(self):
        view = project_valid_at((), _utc(10, 0))
        assert view.status is EpistemicStatus.UNKNOWN
        assert view.value is None

    def test_latest_valid_from_wins_its_slot(self):
        versions = (_fv(5, _utc(10, 0), _utc(10, 4)),
                    _fv(3, _utc(10, 2), _utc(10, 10)))
        assert project_valid_at(versions, _utc(10, 1)).value == 5   # before the change
        assert project_valid_at(versions, _utc(10, 3)).value == 3   # after the change

    def test_derived_valid_to_bounds_the_earlier_interval(self):
        versions = (_fv(5, _utc(10, 0), _utc(10, 4)),
                    _fv(3, _utc(10, 2), _utc(10, 10)))
        early = project_valid_at(versions, _utc(10, 1))
        assert early.value == 5
        assert early.valid_from == _utc(10, 0)
        assert early.valid_to == _utc(10, 2)   # ends where 3 begins, derived not stored

    def test_same_valid_from_different_value_is_conflicted(self):
        versions = (_fv(5, _utc(10, 0), _utc(10, 4)),
                    _fv(3, _utc(10, 0), _utc(10, 10)))
        view = project_valid_at(versions, _utc(10, 5))
        assert view.status is EpistemicStatus.CONFLICTED
        assert view.value is None
        assert {c.value for c in view.conflicts} == {5, 3}   # both evidence paths

    def test_same_value_later_start_does_not_bound_interval(self):
        versions = (_fv(5, _utc(10, 0), _utc(10, 4)),
                    _fv(5, _utc(10, 5), _utc(10, 6)))
        view = project_valid_at(versions, _utc(10, 9))
        assert view.value == 5
        assert view.valid_to is None   # no CHANGE, interval stays open


# ======================================================================
# Knowledge-time axis
# ======================================================================

class TestKnowledgeTime:
    def test_as_known_hides_later_recordings(self):
        versions = (_fv(5, _utc(10, 0), _utc(10, 4)),)
        # recorded at 10:04 — not yet known at 10:00
        assert as_known(versions, _utc(10, 0)).status is EpistemicStatus.UNKNOWN
        # known by 10:05
        assert as_known(versions, _utc(10, 5)).value == 5

    def test_valid_and_knowledge_axes_are_independent(self):
        versions = (_fv(5, _utc(10, 0), _utc(10, 4)),
                    _fv(3, _utc(9, 58), _utc(10, 10)))
        # per latest knowledge, what was valid at 09:59 -> 3
        assert as_of_valid(versions, _utc(9, 59)).value == 3
        # but as known at 10:05 (before the 3 was recorded), 09:59 was UNKNOWN
        assert as_of_valid(versions, _utc(9, 59), known_at=_utc(10, 5)).status \
            is EpistemicStatus.UNKNOWN


# ======================================================================
# STEP 6 — the load-bearing example, end to end through the reconciler
# ======================================================================

class MemFactRepo:
    def __init__(self):
        self.by_version = {}

    def record(self, fact, *, version_digest, semantic_identity, value_digest):
        if version_digest in self.by_version:
            return False
        self.by_version[version_digest] = FactVersion(
            fact_id=fact.record_id, semantic_identity=semantic_identity,
            tenant_id=fact.tenant.tenant_id, subject_ref=fact.subject_ref,
            predicate=fact.predicate, value=fact.value, value_digest=value_digest,
            valid_from=fact.validity.valid_from, recorded_at=fact.recorded_at,
            status=fact.status, authority=fact.authority.value,
            observation_ref=fact.provenance.observation_ref,
            parent_claim_ref=fact.provenance.parent_claim_ref)
        return True

    def versions_for(self, *, tenant_id, semantic_identity):
        return tuple(v for v in self.by_version.values()
                     if v.tenant_id == tenant_id and v.semantic_identity == semantic_identity)


def _observation(value, observed_at, *, obs_id):
    return Observation(
        record_id=obs_id, tenant=ACME, recorded_at=observed_at,
        provenance=ProvenanceRef(produced_by="connector:kubernetes",
                                 execution_ref="ex-1", source_ref="connector:kubernetes"),
        source=ObservationSource(kind=ObservationSourceKind.CONNECTOR,
                                 source_ref="connector:kubernetes"),
        subject_ref="deployment/payments", predicate="spec.replicas", value=value,
        status=SourceStatus.RETURNED_DATA,
        instant=ObservationInstant(observed_at=observed_at, retrieved_at=observed_at))


class TestLoadBearingExample:
    """Observation at 10:04 says replicas=5, world-change established at 10:00.
    Later at 10:10 stronger evidence says replicas=3, became true at 09:58.
    The 5 must NOT be overwritten; both states remain queryable (STEP 6)."""

    def _versions(self):
        repo = MemFactRepo()
        deriver = FactDerivation(repository=repo)
        # first: replicas=5, valid_from 10:00, recorded 10:04
        deriver.derive(tenant=ACME, observation=_observation(5, _utc(10, 0), obs_id="o5"),
                       recorded_at=_utc(10, 4))
        # later: replicas=3, valid_from 09:58, recorded 10:10 (correction, earlier valid time)
        deriver.derive(tenant=ACME, observation=_observation(3, _utc(9, 58), obs_id="o3"),
                       recorded_at=_utc(10, 10))
        sid = fact_semantic_identity(ACME, "deployment/payments", "spec.replicas")
        return repo.versions_for(tenant_id="acme", semantic_identity=sid)

    def test_history_is_preserved_not_overwritten(self):
        versions = self._versions()
        assert len(versions) == 2                       # the 5 was not overwritten
        h = history(versions)
        assert [e.value for e in h] == [5, 3]           # recorded order preserved

    def test_what_was_true_at_0959(self):
        assert as_of_valid(self._versions(), _utc(9, 59)).value == 3

    def test_what_was_true_at_1002(self):
        assert as_of_valid(self._versions(), _utc(10, 2)).value == 5

    def test_what_cortexprime_knew_at_1000(self):
        # nothing was recorded until 10:04 -> UNKNOWN, not FALSE
        assert as_known(self._versions(), _utc(10, 0)).status is EpistemicStatus.UNKNOWN

    def test_what_cortexprime_knew_at_1005(self):
        # only the 5 (recorded 10:04) was known; the 3 (recorded 10:10) was not
        assert as_known(self._versions(), _utc(10, 5)).value == 5

    def test_what_the_world_plane_currently_represents(self):
        # per latest knowledge, at "now" the current value is 5 (valid from 10:00)
        assert current_state(self._versions(), _utc(10, 20)).value == 5
