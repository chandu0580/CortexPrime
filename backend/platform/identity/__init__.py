"""Identifier generation.

The single source of truth for identifiers across CortexPrime.

    from backend.platform.identity import new_uuid, deterministic_id, prefixed_id

    mission_id = prefixed_id("msn")                              # msn_01J8XK...
    execution_key = deterministic_id("execution", "docker.restart", "web-01")

Choosing a kind
---------------
======================  ==================================================
:func:`new_uuid`        Identity is not derivable from content.
:func:`deterministic_id`  Two callers must independently agree on the same
                        identifier -- execution keys, idempotency keys.
:func:`prefixed_id`     Humans will read it: time-sortable, type-tagged.
:func:`monotonic_ulid`  Ordering is load-bearing -- audit chains.
======================  ==================================================

See ``docs/adr/ADR-011-canonical-hashing.md``.
"""

from __future__ import annotations

from backend.platform.identity.generators import (
    CORTEXPRIME_NAMESPACE,
    IdentityError,
    deterministic_id,
    deterministic_uuid,
    is_uuid,
    new_uuid,
    prefixed_id,
)
from backend.platform.identity.ulid import (
    CROCKFORD_ALPHABET,
    ULID_LENGTH,
    MonotonicUlidFactory,
    UlidError,
    is_ulid,
    monotonic_ulid,
    new_ulid,
    timestamp_of,
    ulid_at,
)

__all__ = [
    # uuid + deterministic
    "CORTEXPRIME_NAMESPACE",
    "IdentityError",
    "new_uuid",
    "is_uuid",
    "deterministic_uuid",
    "deterministic_id",
    "prefixed_id",
    # ulid
    "ULID_LENGTH",
    "CROCKFORD_ALPHABET",
    "UlidError",
    "new_ulid",
    "ulid_at",
    "timestamp_of",
    "is_ulid",
    "MonotonicUlidFactory",
    "monotonic_ulid",
]
