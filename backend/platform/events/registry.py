"""Event type registry: name on the wire to class in this process.

Deserialization needs to turn ``"cortexprime.mission.concluded"`` back into a
class. That mapping lives here.

Discovery rather than bookkeeping
---------------------------------
Because :class:`DomainEvent` extends ``Contract``, every event subclass already
registers itself in the contract registry at import time. This registry derives
its index from there instead of asking authors to remember a second
registration step. A registration you can forget is a registration that will be
forgotten, and the failure surfaces only when something tries to decode.

Explicit :meth:`EventRegistry.register` remains available for tests and for
types declared somewhere the import graph does not reach.

Thread safety
-------------
Guarded by a re-entrant lock. Registration typically happens during import on a
single thread, but resolution happens on request threads, and refresh mutates
the index -- so both are locked.
"""

from __future__ import annotations

import threading
from typing import Mapping, Optional

from backend.contracts import contract_registry
from backend.platform.events.base import DomainEvent
from backend.platform.events.exceptions import (
    EventRegistrationError,
    UnknownEventTypeError,
)

__all__ = ["EventRegistry", "default_registry"]


class EventRegistry:
    """Maps event type names to their classes."""

    __slots__ = ("_lock", "_types", "_synced_contract_count")

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._types: dict[str, type[DomainEvent]] = {}
        self._synced_contract_count = -1

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, event_class: type[DomainEvent]) -> type[DomainEvent]:
        """Register ``event_class``. Usable as a decorator.

        Re-registering the identical class is a no-op, so a module imported
        twice does not fail. Registering a *different* class under an existing
        name raises -- that is a genuine collision and silently preferring one
        would make decoding depend on import order.
        """
        if not isinstance(event_class, type) or not issubclass(event_class, DomainEvent):
            raise EventRegistrationError(
                f"{event_class!r} is not a DomainEvent subclass"
            )
        event_type = getattr(event_class, "EVENT_TYPE", None)
        if not isinstance(event_type, str) or not event_type.strip():
            raise EventRegistrationError(
                f"{event_class.__name__} must declare a non-empty EVENT_TYPE"
            )

        with self._lock:
            existing = self._types.get(event_type)
            if existing is not None and existing is not event_class:
                raise EventRegistrationError(
                    f"event type {event_type!r} is already registered to "
                    f"{existing.__name__}; {event_class.__name__} cannot claim it"
                )
            self._types[event_type] = event_class
        return event_class

    def _refresh_locked(self) -> None:
        """Pull DomainEvent subclasses out of the contract registry."""
        contracts = contract_registry()
        if len(contracts) == self._synced_contract_count:
            return
        for name, contract_type in contracts.items():
            if isinstance(contract_type, type) and issubclass(contract_type, DomainEvent):
                existing = self._types.get(name)
                if existing is None:
                    self._types[name] = contract_type
                elif existing is not contract_type:
                    raise EventRegistrationError(
                        f"event type {name!r} maps to both {existing.__name__} and "
                        f"{contract_type.__name__}"
                    )
        self._synced_contract_count = len(contracts)

    def refresh(self) -> None:
        """Re-scan the contract registry for newly imported event types."""
        with self._lock:
            self._synced_contract_count = -1
            self._refresh_locked()

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def resolve(self, event_type: str) -> type[DomainEvent]:
        """Return the class for ``event_type``.

        Raises :class:`UnknownEventTypeError` if nothing matches, which usually
        means a peer is emitting a type this build does not have.
        """
        if not isinstance(event_type, str):
            raise UnknownEventTypeError(str(event_type))
        with self._lock:
            found = self._types.get(event_type)
            if found is None:
                # A type may have been imported since the last scan.
                self._refresh_locked()
                found = self._types.get(event_type)
        if found is None:
            raise UnknownEventTypeError(event_type)
        return found

    def get(self, event_type: str) -> Optional[type[DomainEvent]]:
        """Return the class for ``event_type``, or ``None``."""
        try:
            return self.resolve(event_type)
        except UnknownEventTypeError:
            return None

    def knows(self, event_type: str) -> bool:
        return self.get(event_type) is not None

    def all_types(self) -> Mapping[str, type[DomainEvent]]:
        """Read-only view of every known event type."""
        import types as _types

        with self._lock:
            self._refresh_locked()
            return _types.MappingProxyType(dict(self._types))

    def clear(self) -> None:
        """Drop every registration. Intended for test isolation."""
        with self._lock:
            self._types.clear()
            self._synced_contract_count = -1


default_registry = EventRegistry()
"""Process-wide registry used by the serializer unless one is passed."""
