"""ContextBundle lifecycle events.

Namespaced ``engineering.context.*``. ``CONTRACT_NAME`` is globally unique and a
clash raises at import time, so the namespace is load-bearing rather than
decorative.

``ContextExpanded`` and ``ContextVersioned`` are separate events for one
underlying change, and that is deliberate. A consumer tracking *what an agent can
now see* wants the expansion; a consumer tracking *which bundle is current* wants
the version. Collapsing them would force everyone to read a field to find out
which kind of change happened.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.errors import ContractViolation
from backend.platform.events import DomainEvent

__all__ = [
    "AGGREGATE_TYPE",
    "ContextBundleCreated",
    "ContextExpanded",
    "ContextResolved",
    "ContextInvalidated",
    "ContextVersioned",
    "ContextSuperseded",
    "CONTEXT_EVENT_TYPES",
]

AGGREGATE_TYPE = "context_bundle"


def _require_text(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")


@dataclass(frozen=True)
class ContextBundleCreated(DomainEvent):
    """A bundle was assembled and sealed."""

    EVENT_TYPE = "engineering.context.bundle_created"

    bundle_id: str = ""
    work_id: str = ""
    work_order_version: int = 1
    version: int = 1
    base_commit: str = ""
    manifest_digest: str = ""
    reference_count: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("bundle_id", self.bundle_id)
        _require_text("work_id", self.work_id)
        _require_text("base_commit", self.base_commit)
        _require_text("manifest_digest", self.manifest_digest)


@dataclass(frozen=True)
class ContextExpanded(DomainEvent):
    """A bundle grew under a granted request.

    Carries the question the request asked, because the expansion log is only
    useful if it records what each path was wanted *for*. A log of paths tells
    you the boundary was crossed; a log of questions tells you why.
    """

    EVENT_TYPE = "engineering.context.expanded"

    bundle_id: str = ""
    work_id: str = ""
    request_id: str = ""
    requested_path: str = ""
    question: str = ""
    disposition: str = ""
    decided_by: str = ""
    paths_added: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("bundle_id", self.bundle_id)
        _require_text("request_id", self.request_id)
        _require_text("requested_path", self.requested_path)
        _require_text("question", self.question)
        _require_text("decided_by", self.decided_by)
        if self.disposition not in {"granted", "auto_granted"}:
            raise ContractViolation(
                f"a bundle cannot expand under a {self.disposition!r} request; only a "
                "granted or auto-granted one widens anything"
            )


@dataclass(frozen=True)
class ContextResolved(DomainEvent):
    """A bundle was handed to an agent.

    The event that answers "what did it see, and when?". Emitted at resolution
    rather than at assembly, because a bundle assembled and never resolved was
    never seen by anyone.
    """

    EVENT_TYPE = "engineering.context.resolved"

    bundle_id: str = ""
    work_id: str = ""
    version: int = 1
    manifest_digest: str = ""
    readable_paths: int = 0
    writable_paths: int = 0
    resolved_for: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("bundle_id", self.bundle_id)
        _require_text("manifest_digest", self.manifest_digest)
        _require_text("resolved_for", self.resolved_for)


@dataclass(frozen=True)
class ContextInvalidated(DomainEvent):
    """The bundle no longer describes the tree being worked on."""

    EVENT_TYPE = "engineering.context.invalidated"

    bundle_id: str = ""
    work_id: str = ""
    version: int = 1
    reason: str = ""
    current_commit: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("bundle_id", self.bundle_id)
        _require_text("reason", self.reason)


@dataclass(frozen=True)
class ContextVersioned(DomainEvent):
    """A new version exists, with a new manifest digest."""

    EVENT_TYPE = "engineering.context.versioned"

    bundle_id: str = ""
    work_id: str = ""
    from_version: int = 1
    to_version: int = 2
    manifest_digest: str = ""
    predecessor: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("bundle_id", self.bundle_id)
        _require_text("manifest_digest", self.manifest_digest)
        if self.to_version <= self.from_version:
            raise ContractViolation("a new version must increment")


@dataclass(frozen=True)
class ContextSuperseded(DomainEvent):
    EVENT_TYPE = "engineering.context.superseded"

    bundle_id: str = ""
    work_id: str = ""
    superseded_by: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("bundle_id", self.bundle_id)
        _require_text("superseded_by", self.superseded_by)
        if self.bundle_id == self.superseded_by:
            raise ContractViolation("a bundle cannot supersede itself")


CONTEXT_EVENT_TYPES = (
    ContextBundleCreated,
    ContextExpanded,
    ContextResolved,
    ContextInvalidated,
    ContextVersioned,
    ContextSuperseded,
)
