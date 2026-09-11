"""Phase 11.3 (ADR-123): structured expectation matching is deterministic,
total, and never widens beyond what the test declared."""
from __future__ import annotations

from backend.intelligence.application.matching import describe_expectation, is_condition, matches


class TestExact:
    def test_plain_values_still_mean_equality(self):
        assert matches({"exitCode": 1, "reason": "Error"}, {"exitCode": 1, "reason": "Error"})
        assert not matches({"exitCode": 1}, {"exitCode": 137})
        assert matches("x", "x") and not matches("x", "y")

    def test_extra_observed_keys_are_ignored_but_missing_ones_never_match(self):
        assert matches({"phase": "Running"}, {"phase": "Running", "restartCount": 4})
        assert not matches({"phase": "Running", "waitingReason": None}, {"phase": "Running"})


class TestConditions:
    def test_in_and_not_in(self):
        assert matches({"exitCode": {"$in": [137, 139]}}, {"exitCode": 137})
        assert not matches({"exitCode": {"$in": [137]}}, {"exitCode": 1})
        assert matches({"reason": {"$not_in": ["OOMKilled"]}}, {"reason": "Error"})
        assert not matches({"reason": {"$not_in": ["OOMKilled"]}}, {})  # missing never matches

    def test_numeric_comparisons_refuse_non_numbers(self):
        assert matches({"restartCount": {"$gte": 3}}, {"restartCount": 3})
        assert not matches({"restartCount": {"$gte": 3}}, {"restartCount": 2})
        assert not matches({"restartCount": {"$gte": 3}}, {"restartCount": True})
        assert not matches({"restartCount": {"$gte": 3}}, {"restartCount": "3"})

    def test_contains_exists_and_any_of(self):
        assert matches({"pattern": {"$contains": "missing env"}}, {"pattern": "FATAL missing ENV X"})
        assert matches({"limit": {"$exists": False}}, {})
        assert not matches({"limit": {"$exists": False}}, {"limit": 1})
        assert matches({"$any_of": [{"exitCode": 137}, {"reason": "OOMKilled"}]}, {"exitCode": 1, "reason": "OOMKilled"})
        assert not matches({"$any_of": [{"exitCode": 137}, {"reason": "OOMKilled"}]}, {"exitCode": 1, "reason": "Error"})

    def test_an_unknown_operator_matches_nothing(self):
        assert not matches({"x": {"$regex": ".*"}}, {"x": "anything"})
        assert is_condition({"$in": [1]}) and not is_condition({"in": [1]})

    def test_describe_is_stable_text(self):
        text = describe_expectation({"exitCode": {"$not_in": [137]}, "reason": "Error"})
        assert "$not_in" in text and "Error" in text
