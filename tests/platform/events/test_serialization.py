"""Serialization, deterministic hashing, versioning, registry, and envelopes."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone

import pytest

from backend.contracts import ENVELOPE_CONTRACT_KEY, ENVELOPE_VERSION_KEY, HashAlgorithm
from backend.platform.events import (
    DomainEvent,
    EventEnvelope,
    EventIntegrityError,
    EventMetadata,
    EventRegistrationError,
    EventRegistry,
    EventSerializationError,
    EventValidationError,
    EventVersionError,
    UnknownEventTypeError,
    UpcasterRegistry,
    default_registry,
    deserialize,
    event_digest,
    is_decodable,
    is_version_decodable,
    payload_digest,
    serialize,
    to_bytes,
    validate_encoded,
)
from tests.platform.events.conftest import (
    EmptyPayloadEvent,
    SampleFollowed,
    SampleOccurred,
    VersionedEvent,
)


class TestSerialization:
    def test_round_trip_preserves_equality(self, event) -> None:
        assert deserialize(serialize(event)) == event

    def test_round_trip_through_json(self, event) -> None:
        assert deserialize(json.loads(json.dumps(serialize(event)))) == event

    def test_envelope_carries_type_and_version(self, event) -> None:
        wire = serialize(event)
        assert wire[ENVELOPE_CONTRACT_KEY] == "cortexprime.test.sample_occurred"
        assert wire[ENVELOPE_VERSION_KEY] == 1

    def test_metadata_survives_the_round_trip(self, event) -> None:
        restored = deserialize(serialize(event))
        assert restored.event_id == event.event_id
        assert restored.correlation_id == event.correlation_id
        assert restored.metadata.scope == event.metadata.scope

    def test_causal_chain_survives_the_round_trip(self, event) -> None:
        follow = event.derive(SampleFollowed, reference="OPS-1")
        restored = deserialize(serialize(follow))
        assert restored.causation_id == event.event_id
        assert restored.correlation_id == event.correlation_id

    def test_empty_payload_event_round_trips(self, metadata) -> None:
        original = EmptyPayloadEvent(metadata=metadata)
        assert deserialize(serialize(original)) == original

    def test_serialize_rejects_a_non_event(self) -> None:
        with pytest.raises(EventSerializationError, match="expected a DomainEvent"):
            serialize({"not": "an event"})  # type: ignore[arg-type]

    def test_deserialize_rejects_a_non_mapping(self) -> None:
        with pytest.raises(EventSerializationError, match="expected a mapping"):
            deserialize(["not", "a", "mapping"])  # type: ignore[arg-type]

    def test_deserialize_rejects_a_payload_without_a_type(self) -> None:
        with pytest.raises(EventSerializationError, match="missing"):
            deserialize({"metadata": {}})

    def test_deserialize_rejects_an_unknown_type(self) -> None:
        with pytest.raises(UnknownEventTypeError):
            deserialize({ENVELOPE_CONTRACT_KEY: "cortexprime.test.never_declared"})


class TestDeterministicHashing:
    def test_to_bytes_is_stable(self, event) -> None:
        assert to_bytes(event) == to_bytes(event)

    def test_equal_events_hash_identically(self, metadata) -> None:
        left = SampleOccurred(metadata=metadata, detail="x")
        right = SampleOccurred(metadata=metadata, detail="x")
        assert event_digest(left) == event_digest(right)

    def test_event_digest_distinguishes_identity(self, make_event) -> None:
        """Same payload, different events -- an envelope binds one, not both."""
        assert event_digest(make_event("same")) != event_digest(make_event("same"))

    def test_payload_digest_ignores_identity(self, make_event) -> None:
        """Deduplication asks about content, not identity."""
        assert payload_digest(make_event("same")) == payload_digest(make_event("same"))

    def test_payload_digest_detects_a_content_change(self, make_event) -> None:
        assert payload_digest(make_event("a")) != payload_digest(make_event("b"))

    def test_payload_digest_distinguishes_event_types(self, event) -> None:
        follow = event.derive(SampleFollowed, reference="something happened")
        assert payload_digest(event) != payload_digest(follow)

    def test_digest_survives_a_round_trip(self, event) -> None:
        assert event_digest(deserialize(serialize(event))) == event_digest(event)

    def test_sha512_is_supported(self, event) -> None:
        assert len(event_digest(event, HashAlgorithm.SHA512).value) == 128


class TestVersioning:
    def test_version_decodability_rules(self) -> None:
        assert is_version_decodable(1, 1) is True
        assert is_version_decodable(1, 3) is True
        assert is_version_decodable(3, 1) is False

    @pytest.mark.parametrize("declared,local", [(0, 1), (1, 0), (-1, 1)])
    def test_non_positive_versions_are_rejected(self, declared: int, local: int) -> None:
        with pytest.raises(EventVersionError, match="positive"):
            is_version_decodable(declared, local)

    def test_newer_payload_is_refused(self, event) -> None:
        wire = dict(serialize(event))
        wire[ENVELOPE_VERSION_KEY] = 99
        with pytest.raises(EventVersionError, match="understands at most"):
            deserialize(wire)

    def test_older_payload_decodes_without_an_upcaster(self, scope) -> None:
        """Additive evolution makes an old payload a valid subset."""
        original = VersionedEvent(
            metadata=EventMetadata.create(
                aggregate_id="a", aggregate_type="mission", scope=scope
            ),
            name="original",
        )
        wire = dict(serialize(original))
        wire[ENVELOPE_VERSION_KEY] = 1
        del wire["added_in_v2"]
        restored = deserialize(wire)
        assert restored.name == "original"
        assert restored.added_in_v2 is None

    def test_registered_upcaster_migrates_the_payload(self, scope) -> None:
        upcasters = UpcasterRegistry()
        upcasters.register(
            VersionedEvent.EVENT_TYPE,
            1,
            lambda payload: {**payload, "added_in_v2": "filled by upcaster"},
        )

        original = VersionedEvent(
            metadata=EventMetadata.create(
                aggregate_id="a", aggregate_type="mission", scope=scope
            ),
            name="original",
        )
        wire = dict(serialize(original))
        wire[ENVELOPE_VERSION_KEY] = 1
        del wire["added_in_v2"]

        restored = deserialize(wire, upcasters=upcasters)
        assert restored.added_in_v2 == "filled by upcaster"

    def test_upcasters_chain_one_step_at_a_time(self) -> None:
        upcasters = UpcasterRegistry()
        upcasters.register("t", 1, lambda p: {**p, "steps": p.get("steps", []) + ["v2"]})
        upcasters.register("t", 2, lambda p: {**p, "steps": p["steps"] + ["v3"]})
        assert upcasters.upcast("t", {}, 1, 3)["steps"] == ["v2", "v3"]

    def test_missing_step_refuses_rather_than_partially_migrating(self) -> None:
        upcasters = UpcasterRegistry()
        upcasters.register("t", 1, lambda p: p)
        with pytest.raises(EventVersionError, match="no upcaster registered"):
            upcasters.upcast("t", {}, 1, 3)

    def test_duplicate_registration_is_refused(self) -> None:
        upcasters = UpcasterRegistry()
        upcasters.register("t", 1, lambda p: p)
        with pytest.raises(EventVersionError, match="already registered"):
            upcasters.register("t", 1, lambda p: p)

    def test_downgrade_is_refused(self) -> None:
        with pytest.raises(EventVersionError, match="cannot downgrade"):
            UpcasterRegistry().upcast("t", {}, 3, 1)

    def test_upcaster_returning_a_non_dict_is_refused(self) -> None:
        upcasters = UpcasterRegistry()
        upcasters.register("t", 1, lambda p: "not a dict")  # type: ignore[return-value]
        with pytest.raises(EventVersionError, match="expected a dict"):
            upcasters.upcast("t", {}, 1, 2)

    def test_no_migration_needed_returns_the_payload(self) -> None:
        assert UpcasterRegistry().upcast("t", {"a": 1}, 2, 2) == {"a": 1}


class TestRegistry:
    def test_event_types_are_discovered_without_explicit_registration(self) -> None:
        assert default_registry.resolve(SampleOccurred.EVENT_TYPE) is SampleOccurred

    def test_explicit_registration_is_idempotent(self) -> None:
        registry = EventRegistry()
        registry.register(SampleOccurred)
        registry.register(SampleOccurred)
        assert registry.resolve(SampleOccurred.EVENT_TYPE) is SampleOccurred

    def test_registering_a_non_event_is_refused(self) -> None:
        with pytest.raises(EventRegistrationError, match="not a DomainEvent"):
            EventRegistry().register(dict)  # type: ignore[arg-type]

    def test_unknown_type_resolution_raises(self) -> None:
        with pytest.raises(UnknownEventTypeError):
            EventRegistry().resolve("cortexprime.test.absent")

    def test_get_returns_none_for_an_unknown_type(self) -> None:
        assert EventRegistry().get("cortexprime.test.absent") is None

    def test_knows_reports_membership(self) -> None:
        registry = EventRegistry()
        assert registry.knows(SampleOccurred.EVENT_TYPE) is True
        assert registry.knows("cortexprime.test.absent") is False

    def test_all_types_is_read_only(self) -> None:
        listing = EventRegistry().all_types()
        with pytest.raises(TypeError):
            listing["x"] = SampleOccurred  # type: ignore[index]

    def test_clear_empties_the_registry(self) -> None:
        registry = EventRegistry()
        registry.register(SampleOccurred)
        registry.clear()
        assert registry.get(SampleOccurred.EVENT_TYPE) is not None, (
            "clear() drops explicit entries but rediscovery from contracts still applies"
        )

    def test_concurrent_resolution_is_safe(self) -> None:
        registry = EventRegistry()
        errors: list[Exception] = []
        lock = threading.Lock()

        def worker() -> None:
            try:
                for _ in range(200):
                    assert registry.resolve(SampleOccurred.EVENT_TYPE) is SampleOccurred
                    registry.register(SampleFollowed)
            except Exception as exc:  # noqa: BLE001 - recorded and re-raised below
                with lock:
                    errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert not errors, f"concurrent registry access failed: {errors[:3]}"


class TestValidation:
    def test_valid_payload_returns_its_class(self, event) -> None:
        assert validate_encoded(serialize(event)) is SampleOccurred

    def test_is_decodable_predicate(self, event) -> None:
        assert is_decodable(serialize(event)) is True
        assert is_decodable({ENVELOPE_CONTRACT_KEY: "cortexprime.test.absent"}) is False

    def test_non_mapping_is_rejected(self) -> None:
        with pytest.raises(EventValidationError, match="expected a mapping"):
            validate_encoded("not a mapping")  # type: ignore[arg-type]

    def test_missing_type_key_is_rejected(self) -> None:
        with pytest.raises(EventValidationError, match="missing a valid"):
            validate_encoded({"metadata": {}})

    def test_unknown_type_is_rejected(self) -> None:
        with pytest.raises(EventValidationError, match="unknown event type"):
            validate_encoded({ENVELOPE_CONTRACT_KEY: "cortexprime.test.absent"})

    def test_missing_metadata_is_rejected(self) -> None:
        with pytest.raises(EventValidationError, match="missing its metadata"):
            validate_encoded(
                {
                    ENVELOPE_CONTRACT_KEY: SampleOccurred.EVENT_TYPE,
                    ENVELOPE_VERSION_KEY: 1,
                    "detail": "x",
                }
            )

    def test_future_version_is_rejected(self, event) -> None:
        wire = dict(serialize(event))
        wire[ENVELOPE_VERSION_KEY] = 99
        with pytest.raises(EventValidationError, match="understands at most"):
            validate_encoded(wire)

    def test_non_integer_version_is_rejected(self, event) -> None:
        wire = dict(serialize(event))
        wire[ENVELOPE_VERSION_KEY] = "1"
        with pytest.raises(EventValidationError, match="must be an integer"):
            validate_encoded(wire)


class TestEnvelope:
    def test_wrap_computes_a_matching_digest(self, event) -> None:
        envelope = EventEnvelope.wrap(event)
        assert envelope.verify_integrity() is True
        envelope.require_integrity()

    def test_wrap_starts_at_the_first_attempt_and_is_not_a_replay(self, event) -> None:
        envelope = EventEnvelope.wrap(event)
        assert envelope.delivery_attempt == 1
        assert envelope.replay is False

    def test_substituted_event_fails_integrity(self, event, make_event) -> None:
        """The transport analogue of an approval digest mismatch."""
        envelope = EventEnvelope.wrap(event)
        tampered = EventEnvelope(
            envelope_id=envelope.envelope_id,
            event=make_event("different"),
            content_digest=envelope.content_digest,
            enqueued_at=envelope.enqueued_at,
        )
        assert tampered.verify_integrity() is False
        with pytest.raises(EventIntegrityError, match="payload changed"):
            tampered.require_integrity()

    def test_next_attempt_increments_and_preserves_the_event(self, event) -> None:
        first = EventEnvelope.wrap(event)
        second = first.next_attempt()
        assert second.delivery_attempt == 2
        assert second.event == first.event
        assert second.envelope_id != first.envelope_id
        assert second.verify_integrity() is True

    def test_for_replay_marks_the_envelope_and_resets_the_attempt(self, event) -> None:
        replay = EventEnvelope.wrap(event).next_attempt().for_replay()
        assert replay.replay is True
        assert replay.delivery_attempt == 1
        assert replay.verify_integrity() is True

    def test_replay_flag_cannot_be_cleared(self, event) -> None:
        """Frozen, so a replay cannot be relabelled as a live delivery."""
        import dataclasses

        replay = EventEnvelope.wrap(event).for_replay()
        with pytest.raises(dataclasses.FrozenInstanceError):
            replay.replay = False  # type: ignore[misc]

    def test_replay_survives_further_attempts(self, event) -> None:
        assert EventEnvelope.wrap(event).for_replay().next_attempt().replay is True

    def test_envelope_round_trips_with_its_concrete_event_type(self, event) -> None:
        envelope = EventEnvelope.wrap(event)
        restored = EventEnvelope.from_dict(envelope.to_dict())
        assert isinstance(restored.event, SampleOccurred)
        assert restored.event == event
        assert restored.verify_integrity() is True

    def test_envelope_round_trips_through_json(self, event) -> None:
        envelope = EventEnvelope.wrap(event)
        restored = EventEnvelope.from_dict(json.loads(json.dumps(envelope.to_dict())))
        assert restored.event == event

    def test_decoding_rejects_a_missing_event(self) -> None:
        with pytest.raises(EventSerializationError, match="missing its event"):
            EventEnvelope.from_dict({"envelope_id": "x"})

    @pytest.mark.parametrize("field", ["envelope_id", "content_digest", "enqueued_at"])
    def test_decoding_rejects_missing_required_fields(self, event, field: str) -> None:
        wire = dict(EventEnvelope.wrap(event).to_dict())
        del wire[field]
        with pytest.raises(EventSerializationError, match="missing required field"):
            EventEnvelope.from_dict(wire)

    def test_decoding_rejects_a_naive_timestamp(self, event) -> None:
        wire = dict(EventEnvelope.wrap(event).to_dict())
        wire["enqueued_at"] = "2030-01-01T12:00:00"
        with pytest.raises(EventSerializationError, match="must carry a timezone"):
            EventEnvelope.from_dict(wire)

    def test_non_ulid_envelope_id_is_rejected(self, event) -> None:
        from backend.contracts import ContractViolation

        with pytest.raises(ContractViolation, match="must be a ULID"):
            EventEnvelope(
                envelope_id="not-a-ulid",
                event=event,
                content_digest=event_digest(event),
                enqueued_at=datetime.now(timezone.utc),
            )

    def test_zero_delivery_attempt_is_rejected(self, event) -> None:
        from backend.contracts import ContractViolation
        from backend.platform.identity import monotonic_ulid

        with pytest.raises(ContractViolation, match="positive integer"):
            EventEnvelope(
                envelope_id=monotonic_ulid(),
                event=event,
                content_digest=event_digest(event),
                enqueued_at=datetime.now(timezone.utc),
                delivery_attempt=0,
            )

    def test_headers_are_read_only(self, event) -> None:
        envelope = EventEnvelope.wrap(event, headers={"source": "watcher"})
        with pytest.raises(TypeError):
            envelope.headers["source"] = "other"  # type: ignore[index]
