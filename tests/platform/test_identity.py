"""Identifier generation: uniqueness, ordering, determinism, thread safety."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

import pytest

from backend.platform.identity import (
    CORTEXPRIME_NAMESPACE,
    CROCKFORD_ALPHABET,
    ULID_LENGTH,
    IdentityError,
    MonotonicUlidFactory,
    UlidError,
    deterministic_id,
    deterministic_uuid,
    is_ulid,
    is_uuid,
    monotonic_ulid,
    new_ulid,
    new_uuid,
    prefixed_id,
    timestamp_of,
    ulid_at,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


class TestUuidUniqueness:
    def test_generates_distinct_values(self) -> None:
        values = {new_uuid() for _ in range(10_000)}
        assert len(values) == 10_000

    def test_is_a_valid_uuid4(self) -> None:
        parsed = uuid.UUID(new_uuid())
        assert parsed.version == 4

    def test_is_lowercase_and_hyphenated(self) -> None:
        value = new_uuid()
        assert value == value.lower()
        assert len(value) == 36
        assert value.count("-") == 4

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("00000000-0000-4000-8000-000000000000", True),
            ("not-a-uuid", False),
            ("", False),
            (None, False),
            (12345, False),
        ],
    )
    def test_is_uuid_validation(self, value: object, expected: bool) -> None:
        assert is_uuid(value) is expected


class TestUlidFormat:
    def test_length_and_alphabet(self) -> None:
        value = new_ulid()
        assert len(value) == ULID_LENGTH
        assert all(character in CROCKFORD_ALPHABET for character in value)

    def test_excludes_ambiguous_characters(self) -> None:
        """Crockford omits I, L, O and U to prevent transcription errors."""
        for character in "ILOU":
            assert character not in CROCKFORD_ALPHABET

    def test_embedded_timestamp_is_recoverable(self) -> None:
        before = time.time_ns() // 1_000_000
        value = new_ulid()
        after = time.time_ns() // 1_000_000
        assert before <= timestamp_of(value) <= after

    def test_explicit_timestamp_round_trips(self) -> None:
        assert timestamp_of(ulid_at(1_700_000_000_000)) == 1_700_000_000_000

    def test_generates_distinct_values(self) -> None:
        assert len({new_ulid() for _ in range(10_000)}) == 10_000

    @pytest.mark.parametrize(
        "value,expected",
        [
            ("01ARZ3NDEKTSV4RRFFQ69G5FAV", True),
            ("01arz3ndektsv4rrffq69g5fav", True),  # case-insensitive decode
            ("TOO-SHORT", False),
            ("01ARZ3NDEKTSV4RRFFQ69G5FAI", False),  # I is not in the alphabet
            ("ZZZZZZZZZZZZZZZZZZZZZZZZZZ", False),  # overflows 128 bits
            ("", False),
            (None, False),
        ],
    )
    def test_is_ulid_validation(self, value: object, expected: bool) -> None:
        assert is_ulid(value) is expected

    def test_rejects_out_of_range_timestamp(self) -> None:
        with pytest.raises(UlidError, match="48-bit range"):
            ulid_at(2**48)
        with pytest.raises(UlidError, match="48-bit range"):
            ulid_at(-1)


class TestUlidOrdering:
    def test_later_timestamps_sort_after_earlier_ones(self) -> None:
        early = ulid_at(1_600_000_000_000)
        late = ulid_at(1_700_000_000_000)
        assert early < late

    def test_lexicographic_order_matches_chronological_order(self) -> None:
        timestamps = [1_600_000_000_000, 1_650_000_000_000, 1_700_000_000_000]
        values = [ulid_at(ms) for ms in timestamps]
        assert values == sorted(values)
        assert [timestamp_of(value) for value in sorted(values)] == timestamps

    def test_monotonic_factory_is_strictly_increasing(self) -> None:
        """The property audit chains depend on."""
        factory = MonotonicUlidFactory()
        values = [factory.new() for _ in range(5_000)]
        assert values == sorted(values)
        assert len(set(values)) == len(values)

    def test_module_level_monotonic_is_strictly_increasing(self) -> None:
        values = [monotonic_ulid() for _ in range(1_000)]
        assert values == sorted(values)

    def test_monotonic_survives_a_backwards_clock(self, monkeypatch) -> None:
        """NTP correction must not produce a value that sorts backwards."""
        factory = MonotonicUlidFactory()
        first = factory.new()

        frozen = [1_700_000_000_000 * 1_000_000]
        monkeypatch.setattr(time, "time_ns", lambda: frozen[0])
        second = factory.new()

        frozen[0] = 1_500_000_000_000 * 1_000_000  # clock jumps backwards
        third = factory.new()

        assert first < second < third


class TestUlidThreadSafety:
    def test_concurrent_generation_yields_no_duplicates(self) -> None:
        factory = MonotonicUlidFactory()
        results: list[list[str]] = []
        lock = threading.Lock()

        def worker() -> None:
            produced = [factory.new() for _ in range(500)]
            with lock:
                results.append(produced)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        flattened = [value for batch in results for value in batch]
        assert len(flattened) == 4_000
        assert len(set(flattened)) == 4_000, "concurrent generation produced a duplicate"

    def test_stateless_generation_is_concurrency_safe(self) -> None:
        results: list[str] = []
        lock = threading.Lock()

        def worker() -> None:
            produced = [new_ulid() for _ in range(500)]
            with lock:
                results.extend(produced)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert len(set(results)) == 4_000


class TestDeterministicIdentifiers:
    def test_same_inputs_yield_the_same_identifier(self) -> None:
        assert deterministic_id("execution", "docker.restart", "web-01") == deterministic_id(
            "execution", "docker.restart", "web-01"
        )

    def test_different_inputs_yield_different_identifiers(self) -> None:
        assert deterministic_id("execution", "docker.restart", "web-01") != deterministic_id(
            "execution", "docker.restart", "web-02"
        )

    def test_component_boundaries_are_unambiguous(self) -> None:
        """("a", "bc") and ("ab", "c") must not collide."""
        assert deterministic_id("a", "bc") != deterministic_id("ab", "c")

    def test_component_order_matters(self) -> None:
        assert deterministic_id("a", "b") != deterministic_id("b", "a")

    def test_is_stable_across_processes(self) -> None:
        """Idempotency keys must agree between a producer and a later consumer."""
        script = (
            "from backend.platform.identity import deterministic_id;"
            "print(deterministic_id('execution', 'docker.restart', 'web-01'))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == deterministic_id("execution", "docker.restart", "web-01")

    def test_pinned_value_does_not_drift(self) -> None:
        """Changing this breaks every stored idempotency key. Requires an ADR."""
        assert deterministic_id("execution", "docker.restart", "web-01") == (
            "02e8141f-94a2-5a2f-8ace-acc364290441"
        )

    def test_namespace_is_derived_reproducibly(self) -> None:
        assert CORTEXPRIME_NAMESPACE == uuid.uuid5(
            uuid.NAMESPACE_DNS, "cortexprime.platform.identity.v1"
        )

    def test_custom_namespace_produces_a_separate_identifier_space(self) -> None:
        other = uuid.uuid5(uuid.NAMESPACE_DNS, "tenant-alpha")
        assert deterministic_id("a", namespace=other) != deterministic_id("a")

    def test_result_is_a_valid_uuid5(self) -> None:
        assert deterministic_uuid("a", "b").version == 5

    @pytest.mark.parametrize(
        "parts,message",
        [
            ((), "at least one component"),
            (("",), "must not be empty"),
            (("a\x1fb",), "unit separator"),
        ],
    )
    def test_invalid_components_are_rejected(self, parts: tuple, message: str) -> None:
        with pytest.raises(IdentityError, match=message):
            deterministic_id(*parts)

    def test_non_string_component_is_rejected(self) -> None:
        with pytest.raises(IdentityError, match="must be strings"):
            deterministic_id("a", 1)  # type: ignore[arg-type]


class TestPrefixedIdentifiers:
    def test_format(self) -> None:
        value = prefixed_id("msn")
        prefix, _, suffix = value.partition("_")
        assert prefix == "msn"
        assert is_ulid(suffix)

    def test_lexicographic_order_never_contradicts_time_order(self) -> None:
        """Sorting by string gives non-decreasing timestamps.

        Note this is weaker than strict ordering: ``prefixed_id`` uses stateless
        ULIDs, so two identifiers minted in the same millisecond tie on timestamp
        and order arbitrarily by their random component. That is the documented
        ULID behavior. Where strict ordering is required -- audit chains --
        use :func:`monotonic_ulid`.
        """
        values = sorted(prefixed_id("msn") for _ in range(500))
        timestamps = [timestamp_of(value.split("_")[1]) for value in values]
        assert timestamps == sorted(timestamps)

    def test_identifiers_from_different_milliseconds_sort_correctly(self) -> None:
        first = prefixed_id("msn")
        time.sleep(0.002)
        second = prefixed_id("msn")
        assert first < second

    def test_generates_distinct_values(self) -> None:
        assert len({prefixed_id("exe") for _ in range(5_000)}) == 5_000

    @pytest.mark.parametrize(
        "prefix", ["", "a", "TOOLONGPREFIX", "1bad", "has_underscore", "UPPER", "has-dash", None, 5]
    )
    def test_invalid_prefixes_are_rejected(self, prefix: object) -> None:
        with pytest.raises(IdentityError, match="must be 2-8 lowercase"):
            prefixed_id(prefix)  # type: ignore[arg-type]

    @pytest.mark.parametrize("prefix", ["ms", "msn", "exec", "audit1", "abcdefgh"])
    def test_valid_prefixes_are_accepted(self, prefix: str) -> None:
        assert prefixed_id(prefix).startswith(f"{prefix}_")
