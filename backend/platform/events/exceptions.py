"""Event-layer errors.

A small, closed hierarchy. Every failure in this package raises one of these, so
a consumer can catch :class:`EventError` and be certain it has caught everything
the event foundation can throw.

These are infrastructure errors. They never carry domain meaning -- "this event
is malformed" is an event-layer concern; "this deployment should not have
happened" is not.
"""

from __future__ import annotations

__all__ = [
    "EventError",
    "EventValidationError",
    "EventRegistrationError",
    "UnknownEventTypeError",
    "EventVersionError",
    "EventSerializationError",
    "EventIntegrityError",
]


class EventError(Exception):
    """Base for every error raised by the event foundation."""


class EventValidationError(EventError, ValueError):
    """An event or envelope failed structural validation.

    Inherits ValueError so that callers already handling malformed input in the
    conventional way keep working.
    """


class EventRegistrationError(EventError):
    """An event type could not be registered.

    Raised on a duplicate ``EVENT_TYPE`` or a malformed declaration. Always a
    programming error, surfaced at import time rather than at first publish.
    """


class UnknownEventTypeError(EventError, KeyError):
    """A serialized event names a type this build does not know.

    Distinct from a version mismatch: the type itself is unrecognized, which
    usually means a peer is running code this process does not have.
    """

    def __init__(self, event_type: str) -> None:
        super().__init__(event_type)
        self.event_type = event_type

    def __str__(self) -> str:
        return f"unknown event type: {self.event_type!r}"


class EventVersionError(EventError):
    """An event version cannot be decoded by this build.

    Raised when a payload declares a version newer than the local class
    understands and no upcaster bridges the gap.
    """


class EventSerializationError(EventError):
    """An event could not be encoded or decoded."""


class EventIntegrityError(EventError):
    """An envelope's content digest does not match its event.

    The event-layer analogue of an approval digest mismatch: the payload has
    changed since the digest was taken, so it must not be trusted.
    """
