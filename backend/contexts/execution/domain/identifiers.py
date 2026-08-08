"""Identifiers for the Execution Runtime.

ULID-backed for everything the runtime creates. **Node ids stay readable
strings** for the reason they do in Planner and Workflow: they arrive from the
compiled workflow, and the whole point of the projection is that a human reading
an execution's record recognises the graph it came from.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from backend.contracts.errors import ContractViolation
from backend.contexts.execution.domain.errors import InvalidIdentifier
from backend.platform.identity import is_ulid, monotonic_ulid, timestamp_of

__all__ = [
    "ExecutionId",
    "AttemptId",
    "LeaseId",
    "CheckpointId",
    "WorkerId",
    "normalise_node_id",
]


@dataclass(frozen=True, order=True)
class _UlidIdentifier:
    KIND: ClassVar[str] = "identifier"

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise InvalidIdentifier(
                type(self).KIND,
                self.value,
                f"expected a string, got {type(self.value).__name__}",
            )
        if not is_ulid(self.value):
            raise InvalidIdentifier(type(self).KIND, self.value, "not a valid ULID")

    @classmethod
    def new(cls):
        return cls(monotonic_ulid())

    @property
    def created_at_ms(self) -> int:
        return timestamp_of(self.value)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, order=True)
class ExecutionId(_UlidIdentifier):
    KIND: ClassVar[str] = "ExecutionId"


@dataclass(frozen=True, order=True)
class AttemptId(_UlidIdentifier):
    KIND: ClassVar[str] = "AttemptId"


@dataclass(frozen=True, order=True)
class LeaseId(_UlidIdentifier):
    KIND: ClassVar[str] = "LeaseId"


@dataclass(frozen=True, order=True)
class CheckpointId(_UlidIdentifier):
    KIND: ClassVar[str] = "CheckpointId"


def normalise_node_id(value: str) -> str:
    """A node id as the compiled workflow wrote it."""
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation("a node id must be non-blank text")
    if value != value.strip():
        raise ContractViolation(
            f"node id {value!r} has surrounding whitespace; it would no longer match "
            "the workflow it came from"
        )
    return value


def normalise_worker_id(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation("a worker id must be non-blank text")
    return value.strip()


#: Workers are named by whoever registers them, not minted here. A worker that
#: reconnects after a restart must be able to present the same id, or every
#: restart would orphan the leases it still legitimately holds.
WorkerId = str
