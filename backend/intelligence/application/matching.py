"""Structured expectation matching — Phase 11.3 (ADR-123).

The engine compares an OBSERVED world value to a test's structured expectation
(``supports_value`` / ``contradicts_value``). Until this phase the comparison was
digest equality, which can only express "the value is exactly this". A real
investigation needs to express "the exit code is one of these", "memory is at or
above the limit", "the log carries a config-shaped error", "the rollout happened
inside the window" — all still deterministic, still platform-evaluated, still
explainable, and never a model verdict.

An expectation is either a plain value (exact match, as before) or a mapping in
which any value may be a *condition*: a mapping whose keys all start with ``$``.

Conditions::

    {"$in": [...]}            observed is one of the listed values
    {"$not_in": [...]}        observed is none of the listed values
    {"$gt": n} {"$gte": n}    numeric comparison (bool is not a number)
    {"$lt": n} {"$lte": n}
    {"$contains": "text"}     observed string contains the text (case-insensitive)
    {"$exists": true|false}   the key is present / absent on the observed mapping
    {"$any_of": [e1, e2]}     any of the sub-expectations matches the observed value

A mapping expectation matches a mapping observation when EVERY declared key
matches; keys the expectation does not name are ignored (the test declares what
it discriminates on, the observation may carry more). A missing observed key
never matches anything except ``{"$exists": false}``.

Pure, total, deterministic. Nothing here reads the world or the ledger.
"""

from __future__ import annotations

from typing import Any, Mapping

from backend.platform.hashing import compute_digest

__all__ = ["matches", "is_condition", "describe_expectation"]

_OPERATORS = ("$in", "$not_in", "$gt", "$gte", "$lt", "$lte", "$contains",
              "$exists", "$any_of")


def is_condition(value: Any) -> bool:
    return (isinstance(value, Mapping) and bool(value)
            and all(isinstance(k, str) and k.startswith("$") for k in value))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _digest_equal(a: Any, b: Any) -> bool:
    try:
        return compute_digest(a).value == compute_digest(b).value
    except Exception:  # noqa: BLE001 - an undigestable value equals nothing
        return False


def _condition_matches(condition: Mapping[str, Any], observed: Any, *, present: bool) -> bool:
    for operator, operand in condition.items():
        if operator == "$exists":
            if bool(operand) != present:
                return False
            continue
        if not present:
            return False
        if operator == "$in":
            if not isinstance(operand, (list, tuple)) or not any(
                    _digest_equal(observed, item) for item in operand):
                return False
        elif operator == "$not_in":
            if not isinstance(operand, (list, tuple)) or any(
                    _digest_equal(observed, item) for item in operand):
                return False
        elif operator in ("$gt", "$gte", "$lt", "$lte"):
            if not (_is_number(observed) and _is_number(operand)):
                return False
            if operator == "$gt" and not observed > operand:
                return False
            if operator == "$gte" and not observed >= operand:
                return False
            if operator == "$lt" and not observed < operand:
                return False
            if operator == "$lte" and not observed <= operand:
                return False
        elif operator == "$contains":
            if not (isinstance(observed, str) and isinstance(operand, str)):
                return False
            if operand.lower() not in observed.lower():
                return False
        elif operator == "$any_of":
            if not isinstance(operand, (list, tuple)) or not any(
                    matches(item, observed) for item in operand):
                return False
        else:
            # An operator this module does not know is a condition nobody
            # evaluated; refusing to match is the only honest answer.
            return False
    return True


def matches(expected: Any, observed: Any) -> bool:
    """Does the OBSERVED value satisfy the EXPECTED expectation?"""
    if is_condition(expected):
        return _condition_matches(expected, observed, present=True)
    if isinstance(expected, Mapping):
        if not isinstance(observed, Mapping):
            return False
        for key, sub in expected.items():
            present = key in observed
            value = observed.get(key) if present else None
            if is_condition(sub):
                if not _condition_matches(sub, value, present=present):
                    return False
            elif isinstance(sub, Mapping):
                if not present or not matches(sub, value):
                    return False
            else:
                if not present or not _digest_equal(value, sub):
                    return False
        return True
    return _digest_equal(expected, observed)


def describe_expectation(expected: Any) -> str:
    """A short, deterministic, human-readable rendering for reports."""
    if is_condition(expected):
        return " and ".join(f"{op} {val!r}" for op, val in expected.items())
    if isinstance(expected, Mapping):
        return "{" + ", ".join(f"{k}: {describe_expectation(v)}" for k, v in expected.items()) + "}"
    return repr(expected)
