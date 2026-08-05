"""Canonical serialization: one byte sequence per logical value.

Every guarantee built on hashing rests on these tests. If canonicalization is
not deterministic, Constitution I2 is unenforceable.
"""

from __future__ import annotations

import math

import pytest

from backend.platform.hashing import (
    CANONICAL_VERSION,
    CanonicalizationError,
    canonical_bytes,
    canonical_text,
)


class TestDeterminism:
    def test_key_order_does_not_affect_output(self) -> None:
        assert canonical_text({"b": 1, "a": 2}) == canonical_text({"a": 2, "b": 1})

    def test_keys_are_sorted(self) -> None:
        assert canonical_text({"z": 1, "a": 2, "m": 3}) == '{"a":2,"m":3,"z":1}'

    def test_nested_keys_are_sorted_recursively(self) -> None:
        left = {"outer": {"b": 1, "a": 2}}
        right = {"outer": {"a": 2, "b": 1}}
        assert canonical_text(left) == canonical_text(right)
        assert canonical_text(left) == '{"outer":{"a":2,"b":1}}'

    def test_repeated_calls_are_identical(self) -> None:
        value = {"a": [1, 2, {"c": None, "b": True}], "d": "text"}
        assert canonical_text(value) == canonical_text(value)

    def test_output_contains_no_insignificant_whitespace(self) -> None:
        text = canonical_text({"a": 1, "b": [1, 2]})
        assert " " not in text
        assert "\n" not in text

    def test_sequence_order_is_significant(self) -> None:
        assert canonical_text([1, 2]) != canonical_text([2, 1])

    def test_list_and_tuple_serialize_identically(self) -> None:
        """Contracts use tuples; JSON decoders produce lists. Both must agree."""
        assert canonical_text([1, 2, 3]) == canonical_text((1, 2, 3))


class TestPrimitives:
    @pytest.mark.parametrize(
        "value,expected",
        [
            (None, "null"),
            (True, "true"),
            (False, "false"),
            (0, "0"),
            (-17, "-17"),
            (2**70, str(2**70)),
            ("", '""'),
            ("plain", '"plain"'),
        ],
    )
    def test_primitive_encoding(self, value: object, expected: str) -> None:
        assert canonical_text(value) == expected

    def test_bool_is_not_encoded_as_int(self) -> None:
        """isinstance(True, int) is True in Python -- bool must be checked first."""
        assert canonical_text(True) == "true"
        assert canonical_text(1) == "1"
        assert canonical_text(True) != canonical_text(1)

    def test_float_and_int_do_not_collide(self) -> None:
        assert canonical_text(1.0) == "1.0"
        assert canonical_text(1) == "1"
        assert canonical_text(1.0) != canonical_text(1)

    def test_float_round_trips(self) -> None:
        assert canonical_text(0.1) == "0.1"
        assert canonical_text(-2.5) == "-2.5"

    @pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_floats_are_rejected(self, value: float) -> None:
        assert not math.isfinite(value)
        with pytest.raises(CanonicalizationError, match="NaN or Infinity"):
            canonical_text(value)


class TestStrings:
    @pytest.mark.parametrize(
        "value,expected",
        [
            ('quote"', '"quote\\""'),
            ("back\\slash", '"back\\\\slash"'),
            ("new\nline", '"new\\nline"'),
            ("tab\there", '"tab\\there"'),
            ("\r", '"\\r"'),
            ("\x08", '"\\b"'),
            ("\x0c", '"\\f"'),
            ("\x00", '"\\u0000"'),
            ("\x1f", '"\\u001f"'),
        ],
    )
    def test_escaping(self, value: str, expected: str) -> None:
        assert canonical_text(value) == expected

    def test_non_ascii_is_emitted_literally(self) -> None:
        assert canonical_text("café") == '"café"'
        assert canonical_text("日本") == '"日本"'

    def test_unicode_is_utf8_encoded(self) -> None:
        assert canonical_bytes("é") == '"é"'.encode("utf-8")

    def test_equal_strings_with_different_construction_agree(self) -> None:
        assert canonical_text("ab") == canonical_text("a" + "b")


class TestRejections:
    def test_non_string_key_is_rejected(self) -> None:
        with pytest.raises(CanonicalizationError, match="keys must be strings"):
            canonical_text({1: "value"})

    @pytest.mark.parametrize("value", [{1, 2}, object(), b"bytes", complex(1, 2)])
    def test_unsupported_types_are_rejected(self, value: object) -> None:
        with pytest.raises(CanonicalizationError, match="no canonical form|keys must be"):
            canonical_text(value)

    def test_excessive_nesting_is_rejected(self) -> None:
        deep: object = "leaf"
        for _ in range(100):
            deep = [deep]
        with pytest.raises(CanonicalizationError, match="maximum depth"):
            canonical_text(deep)

    def test_self_referencing_structure_raises_rather_than_hanging(self) -> None:
        cycle: list[object] = []
        cycle.append(cycle)
        with pytest.raises(CanonicalizationError, match="maximum depth"):
            canonical_text(cycle)


class TestVersioning:
    def test_canonical_version_is_declared(self) -> None:
        assert isinstance(CANONICAL_VERSION, int)
        assert CANONICAL_VERSION >= 1

    def test_canonical_bytes_is_utf8_of_canonical_text(self) -> None:
        value = {"a": "é", "b": [1, None, True]}
        assert canonical_bytes(value) == canonical_text(value).encode("utf-8")
