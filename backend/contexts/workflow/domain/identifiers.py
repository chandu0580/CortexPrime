"""Identifiers for the Workflow context.

``WorkflowId`` and ``GroupId`` are ULID-backed. **Node ids are readable strings**
for the reason Planner's task ids are: edges, conditions, branches, parallel
groups, compensations and resume points all name nodes, and a graph reading
``01KZD7... -> 01KZD8...`` is unreadable by whoever has to approve it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from backend.contracts.errors import ContractViolation
from backend.contexts.workflow.domain.errors import InvalidIdentifier
from backend.platform.identity import is_ulid, monotonic_ulid, timestamp_of

__all__ = ["WorkflowId", "GroupId", "normalise_node_id"]


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
class WorkflowId(_UlidIdentifier):
    KIND: ClassVar[str] = "WorkflowId"


@dataclass(frozen=True, order=True)
class GroupId(_UlidIdentifier):
    KIND: ClassVar[str] = "GroupId"


def normalise_node_id(value: str) -> str:
    """A node id a human can read in an edge list."""
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation("a node id must be non-blank text")
    if value != value.strip():
        raise ContractViolation(
            f"node id {value!r} has surrounding whitespace; two ids that differ only "
            "by spacing look identical in an edge list"
        )
    if any(character.isspace() and character != " " for character in value):
        raise ContractViolation(f"node id {value!r} contains a tab or newline")
    return value
