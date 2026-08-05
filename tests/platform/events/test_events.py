"""Event creation, metadata integrity, causality, equality, and immutability."""

from __future__ import annotations

import dataclasses
import threading
from datetime import datetime, timedelta, timezone

import pytest

from backend.contracts import ContractViolation, TenantRef, TenantScope
from backend.platform.events import (
    DomainEvent,
    EventMetadata,
    EventRegistrationError,
    EventValidationError,
    new_correlation_id,
    require_causal_link,
    require_same_correlation,
    validate_chain,
)
from backend.platform.identity import is_ulid
from tests.platform.events.conftest import (
    NOW,
    EmptyPayloadEvent,
    SampleFollowed,
    SampleOccurred,
)


class TestEventCreation:
    def test_event_carries_its_declared_type_and_version(self, event) -> None:
        assert event.event_type == "cortexprime.test.sample_occurred"
        assert event.event_version == 1

    def test_event_type_and_contract_name_are_the_same_identity(self) -> None:
        """One declaration sets both, so they cannot drift apart."""
        assert SampleOccurred.EVENT_TYPE == SampleOccurred.CONTRACT_NAME
        assert SampleOccurred.EVENT_VERSION == SampleOccurred.CONTRACT_VERSION

    def test_payload_excludes_metadata_and_envelope_keys(self, event) -> None:
        assert event.payload() == {"detail": "something happened"}

    def test_event_with_no_payload_fields_is_valid(self, metadata) -> None:
        """The fact that it happened is the whole content."""
        assert EmptyPayloadEvent(metadata=metadata).payload() == {}

    def test_metadata_is_required(self) -> None:
        with pytest.raises(TypeError):
            SampleOccurred(detail="x")  # type: ignore[call-arg]

    def test_metadata_must_be_event_metadata(self) -> None:
        with pytest.raises(ContractViolation, match="must be an EventMetadata"):
            SampleOccurred(metadata={"event_id": "x"}, detail="y")  # type: ignore[arg-type]

    def test_accessors_delegate_to_metadata(self, event) -> None:
        assert event.event_id == event.metadata.event_id
        assert event.correlation_id == event.metadata.correlation_id
        assert event.causation_id == event.metadata.causation_id
        assert event.aggregate_id == event.metadata.aggregate_id
        assert event.aggregate_type == event.metadata.aggregate_type


class TestSubclassDeclaration:
    def test_blank_event_type_is_rejected(self) -> None:
        with pytest.raises(EventRegistrationError, match="non-empty string"):

            @dataclasses.dataclass(frozen=True)
            class Bad(DomainEvent):
                EVENT_TYPE = "   "

    def test_non_string_event_type_is_rejected(self) -> None:
        with pytest.raises(EventRegistrationError, match="non-empty string"):

            @dataclasses.dataclass(frozen=True)
            class Bad(DomainEvent):
                EVENT_TYPE = 123  # type: ignore[assignment]

    def test_non_positive_version_is_rejected(self) -> None:
        with pytest.raises(EventRegistrationError, match="positive integer"):

            @dataclasses.dataclass(frozen=True)
            class Bad(DomainEvent):
                EVENT_TYPE = "cortexprime.test.bad_version"
                EVENT_VERSION = 0

    def test_duplicate_event_type_is_rejected(self) -> None:
        """Two classes claiming one name would make decoding import-order dependent."""
        with pytest.raises(ContractViolation, match="duplicate CONTRACT_NAME"):

            @dataclasses.dataclass(frozen=True)
            class Duplicate(DomainEvent):
                EVENT_TYPE = "cortexprime.test.sample_occurred"


class TestMetadataIntegrity:
    def test_create_generates_a_ulid_event_id(self, scope) -> None:
        metadata = EventMetadata.create(
            aggregate_id="a", aggregate_type="mission", scope=scope
        )
        assert is_ulid(metadata.event_id)

    def test_create_generates_a_correlation_id_when_absent(self, scope) -> None:
        metadata = EventMetadata.create(
            aggregate_id="a", aggregate_type="mission", scope=scope
        )
        assert metadata.correlation_id
        assert metadata.is_chain_origin

    def test_create_joins_an_existing_chain_when_given_one(self, scope) -> None:
        correlation = new_correlation_id()
        metadata = EventMetadata.create(
            aggregate_id="a",
            aggregate_type="mission",
            scope=scope,
            correlation_id=correlation,
        )
        assert metadata.correlation_id == correlation

    def test_event_ids_are_unique_and_ordered(self, scope) -> None:
        ids = [
            EventMetadata.create(
                aggregate_id="a", aggregate_type="mission", scope=scope
            ).event_id
            for _ in range(500)
        ]
        assert len(set(ids)) == 500
        assert ids == sorted(ids), "event ids must be monotonic so events order by id"

    def test_non_ulid_event_id_is_rejected(self, scope) -> None:
        with pytest.raises(ContractViolation, match="must be a ULID"):
            EventMetadata(
                event_id="not-a-ulid",
                correlation_id="c",
                aggregate_id="a",
                aggregate_type="mission",
                occurred_at=NOW,
                scope=scope,
            )

    def test_naive_timestamp_is_rejected(self, scope) -> None:
        from backend.platform.identity import monotonic_ulid

        with pytest.raises(ContractViolation, match="timezone-aware"):
            EventMetadata(
                event_id=monotonic_ulid(),
                correlation_id="c",
                aggregate_id="a",
                aggregate_type="mission",
                occurred_at=datetime(2030, 1, 1, 12, 0),
                scope=scope,
            )

    def test_event_cannot_be_its_own_cause(self, scope) -> None:
        from backend.platform.identity import monotonic_ulid

        identifier = monotonic_ulid()
        with pytest.raises(ContractViolation, match="cannot be its own cause"):
            EventMetadata(
                event_id=identifier,
                correlation_id="c",
                aggregate_id="a",
                aggregate_type="mission",
                occurred_at=NOW,
                scope=scope,
                causation_id=identifier,
            )

    @pytest.mark.parametrize("field", ["correlation_id", "aggregate_id", "aggregate_type"])
    def test_blank_required_fields_are_rejected(self, scope, field: str) -> None:
        from backend.platform.identity import monotonic_ulid

        kwargs = {
            "event_id": monotonic_ulid(),
            "correlation_id": "c",
            "aggregate_id": "a",
            "aggregate_type": "mission",
            "occurred_at": NOW,
            "scope": scope,
            field: "   ",
        }
        with pytest.raises(ContractViolation, match="non-blank"):
            EventMetadata(**kwargs)

    def test_negative_sequence_is_rejected(self, scope) -> None:
        with pytest.raises(ContractViolation, match="non-negative"):
            EventMetadata.create(
                aggregate_id="a", aggregate_type="mission", scope=scope, sequence=-1
            )

    def test_tenant_scope_is_mandatory(self) -> None:
        """Constitution I6: every cross-context message carries tenant identity."""
        with pytest.raises(TypeError):
            EventMetadata.create(aggregate_id="a", aggregate_type="mission")  # type: ignore[call-arg]


class TestCausality:
    def test_derive_inherits_correlation_and_sets_causation(self, event) -> None:
        follow = event.derive(SampleFollowed, reference="OPS-1")
        assert follow.correlation_id == event.correlation_id
        assert follow.causation_id == event.event_id
        assert not follow.metadata.is_chain_origin

    def test_derive_inherits_aggregate_by_default(self, event) -> None:
        follow = event.derive(SampleFollowed, reference="OPS-1")
        assert follow.aggregate_id == event.aggregate_id
        assert follow.aggregate_type == event.aggregate_type

    def test_derive_accepts_an_explicit_aggregate(self, event) -> None:
        follow = event.derive(
            SampleFollowed, reference="OPS-1", aggregate_id="agg-2", aggregate_type="ticket"
        )
        assert follow.aggregate_id == "agg-2"
        assert follow.aggregate_type == "ticket"

    def test_caused_by_identifies_the_direct_cause(self, event) -> None:
        follow = event.derive(SampleFollowed, reference="OPS-1")
        assert follow.metadata.caused_by(event.metadata)
        assert not event.metadata.caused_by(follow.metadata)

    def test_a_chain_of_three_validates(self, event) -> None:
        second = event.derive(SampleFollowed, reference="a")
        third = second.derive(SampleFollowed, reference="b")
        validate_chain([event, second, third])

    def test_require_causal_link_rejects_a_wrong_cause(self, make_event) -> None:
        first = make_event("first")
        unrelated = make_event("unrelated")
        follow = first.derive(SampleFollowed, reference="x")
        with pytest.raises(EventValidationError, match="was caused by"):
            require_causal_link(follow, unrelated)

    def test_require_causal_link_rejects_an_origin(self, event, make_event) -> None:
        with pytest.raises(EventValidationError, match="no causation_id"):
            require_causal_link(event, make_event("other"))

    def test_matching_causation_with_mismatched_correlation_is_rejected(
        self, event, scope
    ) -> None:
        """Hand-built chains get this wrong; derive() cannot."""
        forged = SampleFollowed(
            metadata=EventMetadata.create(
                aggregate_id="agg-1",
                aggregate_type="mission",
                scope=scope,
                correlation_id=new_correlation_id(),
                causation_id=event.event_id,
            ),
            reference="x",
        )
        with pytest.raises(EventValidationError, match="not a correlation"):
            require_causal_link(forged, event)

    def test_chain_must_start_at_an_origin(self, event) -> None:
        second = event.derive(SampleFollowed, reference="a")
        third = second.derive(SampleFollowed, reference="b")
        with pytest.raises(EventValidationError, match="must have no causation_id"):
            validate_chain([second, third])

    def test_chain_requires_a_shared_correlation(self, make_event) -> None:
        with pytest.raises(EventValidationError, match="expected"):
            validate_chain([make_event("a"), make_event("b")])

    def test_empty_chain_is_valid(self) -> None:
        validate_chain([])

    def test_require_same_correlation_returns_the_shared_id(self, event) -> None:
        follow = event.derive(SampleFollowed, reference="x")
        assert require_same_correlation([event, follow]) == event.correlation_id

    def test_require_same_correlation_rejects_an_empty_sequence(self) -> None:
        with pytest.raises(EventValidationError, match="from no events"):
            require_same_correlation([])


class TestEqualityAndCloning:
    def test_events_are_equal_by_value_including_metadata(self, metadata) -> None:
        left = SampleOccurred(metadata=metadata, detail="x")
        right = SampleOccurred(metadata=metadata, detail="x")
        assert left == right
        assert hash(left) == hash(right)

    def test_distinct_events_with_identical_payloads_are_not_equal(self, make_event) -> None:
        """Different ids mean different events, even describing the same thing."""
        assert make_event("same") != make_event("same")

    def test_same_content_as_ignores_identity(self, make_event) -> None:
        assert make_event("same").same_content_as(make_event("same"))

    def test_same_content_as_detects_a_payload_difference(self, make_event) -> None:
        assert not make_event("a").same_content_as(make_event("b"))

    def test_same_content_as_distinguishes_event_types(self, event) -> None:
        follow = event.derive(SampleFollowed, reference="something happened")
        assert not event.same_content_as(follow)

    def test_same_content_as_rejects_a_non_event(self, event) -> None:
        assert not event.same_content_as({"detail": "something happened"})

    def test_with_metadata_replaces_metadata_and_keeps_payload(self, event, scope) -> None:
        replacement = EventMetadata.create(
            aggregate_id="agg-9", aggregate_type="mission", scope=scope
        )
        clone = event.with_metadata(replacement)
        assert clone.metadata is replacement
        assert clone.payload() == event.payload()
        assert clone.event_id != event.event_id

    def test_with_metadata_returns_a_new_instance(self, event, metadata) -> None:
        assert event.with_metadata(metadata) is not event


class TestImmutability:
    def test_events_are_frozen(self, event) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.detail = "changed"  # type: ignore[misc]

    def test_metadata_is_frozen(self, event) -> None:
        with pytest.raises(dataclasses.FrozenInstanceError):
            event.metadata.correlation_id = "changed"  # type: ignore[misc]

    def test_attributes_mapping_is_read_only(self, scope) -> None:
        metadata = EventMetadata.create(
            aggregate_id="a",
            aggregate_type="mission",
            scope=scope,
            attributes={"source": "watcher"},
        )
        with pytest.raises(TypeError):
            metadata.attributes["source"] = "other"  # type: ignore[index]

    def test_mutating_the_source_attributes_does_not_affect_the_event(self, scope) -> None:
        source = {"source": "watcher"}
        metadata = EventMetadata.create(
            aggregate_id="a", aggregate_type="mission", scope=scope, attributes=source
        )
        source["source"] = "tampered"
        assert metadata.attributes["source"] == "watcher"

    def test_events_are_hashable_and_usable_as_keys(self, event) -> None:
        assert {event: "seen"}[event] == "seen"


class TestThreadSafety:
    def test_concurrent_creation_produces_unique_ordered_ids(self, scope) -> None:
        results: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            produced = [
                SampleOccurred(
                    metadata=EventMetadata.create(
                        aggregate_id="a", aggregate_type="mission", scope=scope
                    ),
                    detail="d",
                ).event_id
                for _ in range(200)
            ]
            with lock:
                results.extend(produced)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(results) == 1600
        assert len(set(results)) == 1600, "concurrent creation produced a duplicate event id"

    def test_concurrent_derivation_preserves_every_causal_link(self, event) -> None:
        derived: list[DomainEvent] = []
        lock = threading.Lock()

        def worker() -> None:
            produced = [event.derive(SampleFollowed, reference=str(index)) for index in range(100)]
            with lock:
                derived.extend(produced)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(derived) == 400
        assert all(child.causation_id == event.event_id for child in derived)
        assert all(child.correlation_id == event.correlation_id for child in derived)
        assert len({child.event_id for child in derived}) == 400
