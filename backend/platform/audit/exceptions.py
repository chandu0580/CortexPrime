"""Audit runtime errors.

A small closed hierarchy, so a caller can catch :class:`AuditError` and be sure
it has caught everything this package raises.

Storage failures are *not* swallowed. Most subsystems degrade gracefully when
persistence fails; an audit runtime must not, because the failure mode is
silently losing the evidence that a control fired.
"""

from __future__ import annotations

from typing import Optional

__all__ = [
    "AuditError",
    "AuditStorageError",
    "AuditCorruptionError",
    "AuditChainError",
    "AuditRetentionError",
    "AuditWriterNotOwned",
    "StaleAuditWriter",
]


class AuditError(Exception):
    """Base for every error raised by the audit runtime."""


class AuditStorageError(AuditError):
    """A record could not be persisted or read.

    Deliberately fatal to the calling operation. A caller that continues after
    failing to write an audit record has performed an unaudited action.
    """


class AuditCorruptionError(AuditError):
    """Stored data could not be decoded as an audit record.

    Carries ``line_number`` where the backing store has one, so an operator can
    locate the damage rather than hunt for it.
    """

    def __init__(self, message: str, *, line_number: Optional[int] = None) -> None:
        super().__init__(message)
        self.line_number = line_number


class AuditWriterNotOwned(AuditError):
    """This runtime is not the admitted audit writer, so it did not append.

    Deliberately its own type, and deliberately **not** a subclass of anything
    that reads as an authorization outcome. An audit runtime that is not the
    writer has failed to *observe*; it has not decided anything about whether an
    operation was permitted, and a caller that conflated the two would turn an
    infrastructure ownership problem into a security refusal.
    """


class StaleAuditWriter(AuditWriterNotOwned):
    """This runtime *was* the admitted writer and has been superseded.

    Raised when a fenced append finds the leadership fencing token has moved
    past the one this writer holds: a successor acquired the role while this
    process was stalled, partitioned, or slow. The append was refused **by the
    storage transaction itself** -- the record was never durably written.

    A subclass of :class:`AuditWriterNotOwned` because the consequence is the
    same -- this runtime failed to *observe*, it decided nothing about whether
    an operation was permitted -- but kept distinct because the operator story
    differs: "never held the role" is a configuration question, "held it and
    lost it" is a lease-expiry or partition question.

    The caller must not retry, must not reacquire, and must not present a newer
    token: a stale writer that responded to this by taking the role back would
    be a second writer manufacturing its own authority.
    """


class AuditChainError(AuditError):
    """The hash chain is broken, incomplete, or out of order."""


class AuditRetentionError(AuditError):
    """A retention operation would violate append-only guarantees."""
