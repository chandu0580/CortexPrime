"""Identifier generation: random, deterministic, and prefixed.

Three kinds, each for a distinct purpose:

**Random** (:func:`new_uuid`) -- no meaning, no collisions in practice. Use for
anything whose identity is not derivable from its content.

**Deterministic** (:func:`deterministic_uuid`, :func:`deterministic_id`) -- the
same inputs always yield the same identifier, on any machine, in any process.
This is what makes idempotency work: two attempts to restart the same container
for the same incident produce the same execution key, so the second one is
recognizably a repeat rather than a new action. Constitution S6 requires
executions to be idempotent by execution key; this is how that key is built.

**Prefixed** (:func:`prefixed_id`) -- a short type tag plus a ULID, e.g.
``msn_01J8XK...``. Readable in a log line, sortable by time, and immediately
identifiable when someone pastes one into a ticket.

Determinism guarantee
---------------------
:func:`deterministic_uuid` is UUIDv5 (SHA-1 based, RFC 4122) over a fixed
namespace and a canonically-encoded name. It contains no clock and no
randomness, so its output is stable across processes, machines, and releases.

SHA-1 appears here because RFC 4122 specifies it for UUIDv5. It is used as a
*name-to-identifier* mapping, never as a security primitive -- collision
resistance is not a property we depend on. Content integrity uses SHA-256 via
``backend.platform.hashing`` and is a separate concern.
"""

from __future__ import annotations

import re
import uuid
from typing import Final

from backend.platform.identity.ulid import new_ulid

__all__ = [
    "CORTEXPRIME_NAMESPACE",
    "IdentityError",
    "new_uuid",
    "deterministic_uuid",
    "deterministic_id",
    "prefixed_id",
    "is_uuid",
]

CORTEXPRIME_NAMESPACE: Final[uuid.UUID] = uuid.uuid5(
    uuid.NAMESPACE_DNS, "cortexprime.platform.identity.v1"
)
"""Root namespace for every deterministic identifier.

Derived from a fixed DNS-namespace name rather than hard-coded, so the
derivation is auditable. The trailing ``v1`` means a future change to the
scheme yields a different namespace and therefore different identifiers --
visible rather than silent."""

_SEPARATOR: Final[str] = "\x1f"
"""ASCII Unit Separator. Joins name components so that ``("a", "bc")`` and
``("ab", "c")`` cannot produce the same identifier -- the separator cannot
appear in a component (enforced below)."""

_PREFIX_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[a-z][a-z0-9]{1,7}$")


class IdentityError(ValueError):
    """An identifier could not be generated from the supplied inputs."""


def new_uuid() -> str:
    """Return a random UUIDv4 as a lowercase hyphenated string."""
    return str(uuid.uuid4())


def is_uuid(value: object) -> bool:
    """Return whether ``value`` parses as a UUID in any standard form."""
    if not isinstance(value, str):
        return False
    try:
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return True


def _join(parts: tuple[str, ...]) -> str:
    if not parts:
        raise IdentityError(
            "a deterministic identifier needs at least one component; deriving one "
            "from nothing would give every caller the same value"
        )
    for part in parts:
        if not isinstance(part, str):
            raise IdentityError(
                f"components must be strings; received {type(part).__name__}. "
                "Convert deliberately -- an implicit str() would make the identifier "
                "depend on a repr that may change between releases."
            )
        if not part:
            raise IdentityError("components must not be empty")
        if _SEPARATOR in part:
            raise IdentityError(
                "components must not contain the unit separator (U+001F); it delimits "
                "components and allowing it would let two different inputs collide"
            )
    return _SEPARATOR.join(parts)


def deterministic_uuid(*parts: str, namespace: uuid.UUID = CORTEXPRIME_NAMESPACE) -> uuid.UUID:
    """Return the UUIDv5 derived from ``parts`` within ``namespace``.

    Stable across processes, machines, and releases::

        deterministic_uuid("execution", "docker.restart", "web-01")

    always returns the same UUID. Callers needing separate identifier spaces
    (per tenant, say) should pass their own namespace, itself derived with this
    function.
    """
    return uuid.uuid5(namespace, _join(parts))


def deterministic_id(*parts: str, namespace: uuid.UUID = CORTEXPRIME_NAMESPACE) -> str:
    """String form of :func:`deterministic_uuid`.

    The usual way to build an execution key::

        key = deterministic_id("execution", tenant_id, action_type, resource_id)
    """
    return str(deterministic_uuid(*parts, namespace=namespace))


def prefixed_id(prefix: str) -> str:
    """Return a time-sortable identifier tagged with a short type prefix.

    ``prefixed_id("msn")`` yields something like ``msn_01J8XK3M9QP7VWZC4H2NRTB5FD``.

    Sorting these strings yields non-decreasing creation times. Ordering is
    *not* strict: this uses a stateless ULID, so two identifiers minted in the
    same millisecond tie on timestamp and order arbitrarily by their random
    component. That is deliberate -- independent randomness is preferable for
    identifiers that may be exposed. Where strict ordering is load-bearing,
    such as an audit chain, use :func:`~backend.platform.identity.monotonic_ulid`.

    The prefix must be 2-8 lowercase alphanumeric characters starting with a
    letter. Constraining it keeps identifiers scannable and prevents the tag
    from growing into a description.
    """
    if not isinstance(prefix, str) or not _PREFIX_PATTERN.match(prefix):
        raise IdentityError(
            f"prefix {prefix!r} must be 2-8 lowercase alphanumeric characters "
            "beginning with a letter"
        )
    return f"{prefix}_{new_ulid()}"
