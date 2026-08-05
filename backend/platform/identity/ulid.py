"""ULID generation and parsing.

A ULID is a 128-bit identifier that sorts lexicographically by creation time:

* 48 bits -- milliseconds since the Unix epoch
* 80 bits -- randomness
* rendered as 26 characters of Crockford Base32

This matters for CortexPrime because audit entries, mission transitions, and
execution records are all read in time order. A UUIDv4 primary key forces an
index on a separate timestamp column and scatters inserts across the B-tree; a
ULID sorts correctly as a string and inserts sequentially.

Implemented here rather than taken as a dependency: the specification is small
and fully described above, ``python-ulid`` is not currently installed, and
Constitution S11 requires a stated reason for every dependency. Sixty lines of
well-tested code is the cheaper side of that trade.

Monotonicity
------------
:func:`new_ulid` is stateless and safe to call from any thread, but two calls in
the same millisecond have no guaranteed order relative to each other.

:class:`MonotonicUlidFactory` guarantees strictly increasing values by
incrementing the random component within a millisecond. It holds a lock and is
safe to share across threads. Use it wherever ordering is load-bearing --
audit chains in particular.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Final

__all__ = [
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

CROCKFORD_ALPHABET: Final[str] = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
"""Crockford Base32. Excludes I, L, O and U to avoid transcription errors and
accidental profanity."""

_DECODE: Final[dict[str, int]] = {char: index for index, char in enumerate(CROCKFORD_ALPHABET)}

ULID_LENGTH: Final[int] = 26
_TIMESTAMP_BITS: Final[int] = 48
_RANDOM_BITS: Final[int] = 80
_MAX_TIMESTAMP: Final[int] = (1 << _TIMESTAMP_BITS) - 1
_MAX_RANDOM: Final[int] = (1 << _RANDOM_BITS) - 1


class UlidError(ValueError):
    """A ULID could not be generated or parsed."""


def _encode(value: int) -> str:
    """Render a 128-bit integer as 26 Crockford Base32 characters.

    26 characters carry 130 bits, so the leading character encodes only the top
    two bits and is always in the range 0-7.
    """
    if not 0 <= value < (1 << 128):
        raise UlidError("value does not fit in 128 bits")
    chars = [""] * ULID_LENGTH
    for position in range(ULID_LENGTH - 1, -1, -1):
        chars[position] = CROCKFORD_ALPHABET[value & 0x1F]
        value >>= 5
    return "".join(chars)


def _decode(text: str) -> int:
    if len(text) != ULID_LENGTH:
        raise UlidError(f"a ULID is {ULID_LENGTH} characters; received {len(text)}")
    value = 0
    for character in text.upper():
        digit = _DECODE.get(character)
        if digit is None:
            raise UlidError(f"{character!r} is not a Crockford Base32 character")
        value = (value << 5) | digit
    if value >= (1 << 128):
        raise UlidError("value overflows 128 bits; the leading character must be 0-7")
    return value


def _compose(timestamp_ms: int, randomness: int) -> str:
    if not 0 <= timestamp_ms <= _MAX_TIMESTAMP:
        raise UlidError(f"timestamp {timestamp_ms} is outside the 48-bit range")
    if not 0 <= randomness <= _MAX_RANDOM:
        raise UlidError("randomness is outside the 80-bit range")
    return _encode((timestamp_ms << _RANDOM_BITS) | randomness)


def new_ulid() -> str:
    """Return a new ULID for the current instant.

    Stateless and thread-safe. Ordering between two ULIDs created in the same
    millisecond is unspecified -- use :class:`MonotonicUlidFactory` when that
    matters.
    """
    return _compose(time.time_ns() // 1_000_000, int.from_bytes(os.urandom(10), "big"))


def ulid_at(timestamp_ms: int) -> str:
    """Return a ULID carrying an explicit timestamp.

    Provided for tests and for backfilling historical records. Production code
    should call :func:`new_ulid` so that the embedded time is real.
    """
    return _compose(timestamp_ms, int.from_bytes(os.urandom(10), "big"))


def timestamp_of(value: str) -> int:
    """Extract the embedded creation time, in milliseconds since the epoch."""
    return _decode(value) >> _RANDOM_BITS


def is_ulid(value: object) -> bool:
    """Return whether ``value`` is a syntactically valid ULID."""
    if not isinstance(value, str):
        return False
    try:
        _decode(value)
    except UlidError:
        return False
    return True


class MonotonicUlidFactory:
    """Generates strictly increasing ULIDs, safely across threads.

    Within a single millisecond the random component is incremented rather than
    redrawn, which guarantees that successive values compare greater. Across
    milliseconds the timestamp advances and ordering follows from that.

    A clock that moves backwards (NTP correction, container migration) would
    otherwise produce a value that sorts before its predecessor. That is
    detectable corruption in an audit chain, so this factory pins to the last
    observed millisecond instead and keeps incrementing -- ordering is
    preserved, and the embedded timestamp is at worst slightly stale.
    """

    __slots__ = ("_lock", "_last_ms", "_last_random")

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._last_ms = -1
        self._last_random = 0

    def new(self) -> str:
        """Return the next ULID. Strictly greater than every prior result."""
        with self._lock:
            now_ms = time.time_ns() // 1_000_000

            if now_ms > self._last_ms:
                self._last_ms = now_ms
                self._last_random = int.from_bytes(os.urandom(10), "big")
            else:
                # Same millisecond, or the clock went backwards.
                if self._last_random >= _MAX_RANDOM:
                    raise UlidError(
                        "exhausted the 80-bit random space within a single millisecond; "
                        "this implies over 1.2e24 identifiers in one millisecond and is "
                        "almost certainly a bug in the caller"
                    )
                self._last_random += 1

            return _compose(self._last_ms, self._last_random)


_default_factory: Final[MonotonicUlidFactory] = MonotonicUlidFactory()


def monotonic_ulid() -> str:
    """Return a strictly increasing ULID from the process-wide factory.

    Convenience over constructing a factory. Ordering is guaranteed within this
    process only; across processes, rely on the embedded timestamp.
    """
    return _default_factory.new()
