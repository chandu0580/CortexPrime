"""Event schema evolution.

Events outlive the code that emits them. A replay in 2030 must be able to read
an event written in 2026, so version compatibility is a foundation concern
rather than something each event type solves for itself.

The rules, identical in spirit to ADR-010's contract rules:

======================================  =======================================
Add an optional field with a default    Not breaking. Keep the version.
Add a new event type                    Not breaking.
Remove or rename a field                Breaking. Increment ``EVENT_VERSION``.
Make an optional field required         Breaking.
Narrow a field's type                   Breaking.
Change a field's meaning                Breaking -- and easy to miss, because
                                        nothing about the shape changes.
======================================  =======================================

Decoding
--------
* Older payload, no upcaster -> accepted as-is. Additive evolution makes an old
  payload a valid subset of the current shape.
* Older payload with upcasters registered -> migrated forward, one step at a
  time, so a v1 payload reaches v3 through v2 rather than by a bespoke jump.
* Newer payload -> refused. Silently dropping fields we do not understand would
  let a consumer act on a partial view of a fact.

Upcasters operate on payload dictionaries, never on constructed events. A v1
event class may no longer exist; its serialized form always does.
"""

from __future__ import annotations

import threading
from typing import Any, Callable, Mapping

from backend.platform.events.exceptions import EventVersionError

__all__ = [
    "Upcaster",
    "UpcasterRegistry",
    "default_upcasters",
    "is_version_decodable",
]

Upcaster = Callable[[Mapping[str, Any]], dict[str, Any]]
"""Migrates a payload dict from version N to version N+1."""


def is_version_decodable(declared: int, local: int) -> bool:
    """Whether a payload at ``declared`` version can be read by ``local`` code.

    Equal or older is decodable. Newer is not -- see the module docstring.
    """
    if not isinstance(declared, int) or not isinstance(local, int):
        raise EventVersionError("versions must be integers")
    if declared < 1 or local < 1:
        raise EventVersionError("versions must be positive")
    return declared <= local


class UpcasterRegistry:
    """Thread-safe registry of payload migrations, keyed by event type.

    Migrations are registered per single version step. Chaining is handled here
    so that registering a v2 to v3 step does not require anyone to also update a
    v1 to v3 path.
    """

    __slots__ = ("_lock", "_steps")

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._steps: dict[tuple[str, int], Upcaster] = {}

    def register(self, event_type: str, from_version: int, upcaster: Upcaster) -> None:
        """Register a migration from ``from_version`` to ``from_version + 1``."""
        if not isinstance(event_type, str) or not event_type.strip():
            raise EventVersionError("event_type must be a non-blank string")
        if not isinstance(from_version, int) or from_version < 1:
            raise EventVersionError("from_version must be a positive integer")
        if not callable(upcaster):
            raise EventVersionError("upcaster must be callable")

        key = (event_type, from_version)
        with self._lock:
            if key in self._steps:
                raise EventVersionError(
                    f"an upcaster for {event_type} v{from_version} is already registered; "
                    "replacing it would silently change how historical events decode"
                )
            self._steps[key] = upcaster

    def has_step(self, event_type: str, from_version: int) -> bool:
        with self._lock:
            return (event_type, from_version) in self._steps

    def upcast(
        self, event_type: str, payload: Mapping[str, Any], from_version: int, to_version: int
    ) -> dict[str, Any]:
        """Migrate ``payload`` forward one version at a time.

        Returns the payload unchanged when no migration is needed. Raises if a
        step is missing, because a partially-migrated payload is worse than a
        refusal -- it looks valid.
        """
        if from_version > to_version:
            raise EventVersionError(
                f"cannot downgrade {event_type} from v{from_version} to v{to_version}"
            )

        current = dict(payload)
        version = from_version
        while version < to_version:
            with self._lock:
                step = self._steps.get((event_type, version))
            if step is None:
                raise EventVersionError(
                    f"no upcaster registered for {event_type} v{version} -> v{version + 1}; "
                    f"cannot migrate a v{from_version} payload to v{to_version}"
                )
            migrated = step(current)
            if not isinstance(migrated, dict):
                raise EventVersionError(
                    f"upcaster for {event_type} v{version} returned "
                    f"{type(migrated).__name__}; expected a dict"
                )
            current = migrated
            version += 1
        return current

    def clear(self) -> None:
        """Remove every registration. Intended for test isolation."""
        with self._lock:
            self._steps.clear()


default_upcasters = UpcasterRegistry()
"""Process-wide upcaster registry used by the serializer unless one is passed."""
