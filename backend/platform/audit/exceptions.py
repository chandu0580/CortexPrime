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


class AuditChainError(AuditError):
    """The hash chain is broken, incomplete, or out of order."""


class AuditRetentionError(AuditError):
    """A retention operation would violate append-only guarantees."""
