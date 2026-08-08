"""Commands and queries for the ContextBundle context.

Frozen values naming one intent each. Tuples-of-tuples for references and
dependencies rather than domain objects, so a command can be serialised, queued,
and replayed without dragging the domain across the wire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.contracts.errors import ContractViolation

__all__ = [
    "AssembleBundle", "RequestExpansion", "DecideExpansion", "ApplyExpansion",
    "ResolveBundle", "InvalidateBundle", "GetBundle", "ListBundles", "GetBoundarySignals",
]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractViolation(message)


@dataclass(frozen=True)
class AssembleBundle:
    work_id: str
    work_order_version: int
    base_commit: str
    blast_radius_allowed: tuple
    searchable: tuple
    blast_radius_forbidden: tuple = ()
    blast_radius_read_only: tuple = ()
    excluded_from_search: tuple = ()
    adr_references: tuple = ()
    superseded_adrs: tuple = ()
    dependencies: tuple = ()
    references: tuple = ()
    assembled_by: str = "orchestrator"

    def __post_init__(self) -> None:
        _require(bool(self.work_id), "work_id is required")
        _require(
            bool(self.base_commit and self.base_commit.strip()),
            "base_commit is required; a bundle describes a particular tree",
        )
        _require(self.work_order_version >= 1, "work_order_version starts at 1")
        _require(
            bool(self.blast_radius_allowed),
            "a blast radius that allows nothing authorises nothing",
        )
        _require(
            bool(self.searchable),
            "a bundle must be searchable somewhere; search is how a false premise is found",
        )


@dataclass(frozen=True)
class RequestExpansion:
    bundle_id: str
    requested_path: str
    question: str
    requested_by: str
    target_layer: str = "dependencies"

    def __post_init__(self) -> None:
        _require(bool(self.bundle_id), "bundle_id is required")
        _require(bool(self.requested_path), "requested_path is required")
        _require(
            bool(self.question and self.question.strip()),
            "a request must say what it answers; a request without one is browsing",
        )
        _require(bool(self.requested_by), "requested_by is required")


@dataclass(frozen=True)
class DecideExpansion:
    bundle_id: str
    request_id: str
    grant: bool
    decided_by: str
    reason: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.bundle_id), "bundle_id is required")
        _require(bool(self.request_id), "request_id is required")
        _require(bool(self.decided_by), "decided_by is required; a decision has an author")
        if not self.grant:
            _require(
                bool(self.reason and self.reason.strip()),
                "a denial must say why; one without a reason teaches nobody where the "
                "boundary actually is",
            )


@dataclass(frozen=True)
class ApplyExpansion:
    bundle_id: str
    request_id: str
    references: tuple = ()

    def __post_init__(self) -> None:
        _require(bool(self.bundle_id), "bundle_id is required")
        _require(bool(self.request_id), "request_id is required")


@dataclass(frozen=True)
class ResolveBundle:
    bundle_id: str
    resolved_for: str
    current_commit: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.bundle_id), "bundle_id is required")
        _require(
            bool(self.resolved_for and self.resolved_for.strip()),
            "resolved_for is required; a resolution records who received the context",
        )


@dataclass(frozen=True)
class InvalidateBundle:
    bundle_id: str
    reason: str
    current_commit: Optional[str] = None

    def __post_init__(self) -> None:
        _require(bool(self.bundle_id), "bundle_id is required")
        _require(
            bool(self.reason and self.reason.strip()),
            "invalidating a bundle must say why",
        )


@dataclass(frozen=True)
class GetBundle:
    bundle_id: str


@dataclass(frozen=True)
class ListBundles:
    work_id: Optional[str] = None
    active_only: bool = False


@dataclass(frozen=True)
class GetBoundarySignals:
    minimum_requests: int = 2
