"""Phase 7.2 (re-issue) — the evidence demands this spec adds beyond ingestion:

  * STEP 6  observation mutation is refused (positive test, not just "no method")
  * STEP 8  Observation -> serialize -> Observation preserves semantic equality
  * STEP 9  canonical digest: reordered keys => identical identity (tamper => not)

These are contract/serialization-level and need no database — the real-Postgres
round-trip (get_observation reconstructs an equal object from a fresh process)
is proven separately in scripts/phase72_observation_harness.py.
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timedelta, timezone

import pytest

from backend.contracts.evidence import SourceStatus
from backend.contracts.tenant import TenantRef
from backend.contracts.world import Observation, ObservationSourceKind
from backend.world.application import (
    ObservationIngestion,
    ReadObservation,
    observation_identity,
)

NOW = datetime(2026, 8, 11, 10, 5, tzinfo=timezone.utc)
OBSERVED = datetime(2026, 8, 11, 10, 0, tzinfo=timezone.utc)
RETRIEVED = datetime(2026, 8, 11, 10, 4, tzinfo=timezone.utc)
ACME = TenantRef(tenant_id="acme")


class MemRepo:
    def __init__(self):
        self.by_identity: dict = {}

    def record(self, observation, *, identity_digest):
        if identity_digest in self.by_identity:
            return False
        self.by_identity[identity_digest] = observation
        return True


def _observe(value):
    read = ReadObservation(
        source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:grafana",
        subject_ref="folder:p61", predicate="exists", value=value,
        status=SourceStatus.RETURNED_DATA, observed_at=OBSERVED, retrieved_at=RETRIEVED,
        produced_by="connector:grafana", execution_ref="ex-1", trace_ref="corr-1")
    obs, _ = ObservationIngestion(repository=MemRepo()).ingest(
        tenant=ACME, read=read, recorded_at=NOW)
    return obs


# ======================================================================
# STEP 8 — round-trip semantic equality (Observation -> dict -> Observation)
# ======================================================================

class TestRoundTrip:
    def test_serialize_reload_is_value_equal(self):
        obs = _observe({"uid": "p61", "title": "Phase 6.1"})
        reloaded = Observation.from_dict(obs.to_dict())
        assert reloaded == obs  # frozen dataclass equality is by value

    def test_provenance_survives(self):
        obs = _observe({"uid": "p61"})
        reloaded = Observation.from_dict(obs.to_dict())
        assert reloaded.provenance == obs.provenance
        assert reloaded.provenance.execution_ref == "ex-1"
        assert reloaded.provenance.trace_ref == "corr-1"
        assert reloaded.provenance.source_ref == "connector:grafana"

    def test_both_instants_and_recorded_at_survive(self):
        obs = _observe({"uid": "p61"})
        reloaded = Observation.from_dict(obs.to_dict())
        assert reloaded.instant.observed_at == OBSERVED
        assert reloaded.instant.retrieved_at == RETRIEVED
        assert reloaded.recorded_at == NOW
        # and they remain three distinct moments after the round-trip
        assert reloaded.instant.observed_at != reloaded.instant.retrieved_at
        assert reloaded.recorded_at != reloaded.instant.retrieved_at

    def test_source_status_and_value_survive(self):
        obs = _observe({"uid": "p61", "nested": {"k": [1, 2, 3]}})
        reloaded = Observation.from_dict(obs.to_dict())
        assert reloaded.source.kind is ObservationSourceKind.CONNECTOR
        assert reloaded.status is SourceStatus.RETURNED_DATA
        assert reloaded.value == {"uid": "p61", "nested": {"k": [1, 2, 3]}}

    def test_identity_survives_the_round_trip(self):
        obs = _observe({"uid": "p61"})
        reloaded = Observation.from_dict(obs.to_dict())
        assert observation_identity(reloaded) == observation_identity(obs)


# ======================================================================
# STEP 9 — canonicalisation: identity is key-order independent
# ======================================================================

class TestCanonicalIdentity:
    def test_reordered_payload_keys_yield_identical_identity(self):
        a = _observe({"alpha": 1, "beta": 2, "gamma": 3})
        b = _observe({"gamma": 3, "beta": 2, "alpha": 1})  # same value, keys reordered
        assert observation_identity(a) == observation_identity(b)

    def test_reordered_nested_keys_yield_identical_identity(self):
        a = _observe({"outer": {"x": 1, "y": 2}, "z": 3})
        b = _observe({"z": 3, "outer": {"y": 2, "x": 1}})
        assert observation_identity(a) == observation_identity(b)

    def test_a_changed_value_changes_identity(self):
        # Tamper detection: a genuinely different value is a different identity.
        a = _observe({"uid": "p61"})
        b = _observe({"uid": "p62"})
        assert observation_identity(a) != observation_identity(b)

    def test_identity_is_not_a_bare_payload_hash(self):
        # Same value under a different subject is a different observation.
        base = ReadObservation(
            source_kind=ObservationSourceKind.CONNECTOR, source_ref="connector:grafana",
            subject_ref="folder:A", predicate="exists", value={"uid": "x"},
            status=SourceStatus.RETURNED_DATA, observed_at=OBSERVED,
            retrieved_at=RETRIEVED, produced_by="connector:grafana")
        other = dataclasses.replace(base, subject_ref="folder:B")
        ing = ObservationIngestion(repository=MemRepo())
        oa, _ = ing.ingest(tenant=ACME, read=base, recorded_at=NOW)
        ob, _ = ing.ingest(tenant=ACME, read=other, recorded_at=NOW)
        assert observation_identity(oa) != observation_identity(ob)


# ======================================================================
# STEP 6 — an observation is immutable (mutation refused, not just absent)
# ======================================================================

class TestImmutability:
    def test_setting_a_field_is_refused(self):
        obs = _observe({"uid": "p61"})
        with pytest.raises(dataclasses.FrozenInstanceError):
            obs.value = {"uid": "tampered"}  # type: ignore[misc]

    def test_setting_a_nested_record_field_is_refused(self):
        obs = _observe({"uid": "p61"})
        with pytest.raises(dataclasses.FrozenInstanceError):
            obs.recorded_at = NOW + timedelta(days=1)  # type: ignore[misc]

    def test_provenance_is_itself_frozen(self):
        obs = _observe({"uid": "p61"})
        with pytest.raises(dataclasses.FrozenInstanceError):
            obs.provenance.produced_by = "someone-else"  # type: ignore[misc]
