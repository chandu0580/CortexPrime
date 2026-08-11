"""Worker fabric events. Namespaced ``execution.worker.*``.

Only genuinely new facts
--------------------------
The execution lifecycle events (``execution.runtime.*``) describe a *run*. These
describe the *fabric that runs it*: which implementations exist, what the
platform vouches for them, and which one was chosen for a binding. Neither set
substitutes for the other, and no event here restates one there.

There is no ``worker_rebound`` and no ``worker_selection_updated``. A selection
is immutable; if the selected worker becomes invalid, execution refuses and
recovery starts a new governed flow. An event saying a selection changed would
be a record of something that structurally cannot happen.

Digest-aware, tenant-attributable, replay-safe
------------------------------------------------
Every event carries the implementation digest, so replay can say *which build*
was registered or selected rather than only which id. Tenancy and actor ride on
``EventMetadata`` like every other event in the codebase. None of them carries a
credential, a token, or a provider payload -- these reach audit.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.errors import ContractViolation
from backend.platform.events import DomainEvent

__all__ = [
    "WORKER_AGGREGATE_TYPE",
    "WorkerRegistered",
    "WorkerValidated",
    "WorkerEnabled",
    "WorkerDisabled",
    "WorkerRevoked",
    "WorkerTrustChanged",
    "WorkerSelected",
    "WORKER_EVENT_TYPES",
]

WORKER_AGGREGATE_TYPE = "execution_worker"


def _require_text(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")


@dataclass(frozen=True)
class _WorkerEvent(DomainEvent):
    """Shared shape: which worker, which build, which kind."""

    worker_id: str = ""
    worker_kind: str = ""
    worker_version: str = ""
    worker_digest: str = ""
    scope: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("worker_id", self.worker_id)
        _require_text("worker_kind", self.worker_kind)
        _require_text("worker_version", self.worker_version)
        _require_text("worker_digest", self.worker_digest)


@dataclass(frozen=True)
class WorkerRegistered(_WorkerEvent):
    """An implementation was recorded. Not validated, not trusted, not usable."""

    EVENT_TYPE = "execution.worker.registered"

    interface: str = ""
    implementation: str = ""
    isolation: str = ""
    protocol_version: str = ""
    environments: tuple = ()
    providers: tuple = ()


@dataclass(frozen=True)
class WorkerValidated(_WorkerEvent):
    """The declaration was checked against the adapter. Still switched off."""

    EVENT_TYPE = "execution.worker.validated"

    note: str = ""


@dataclass(frozen=True)
class WorkerEnabled(_WorkerEvent):
    """Eligible for selection, subject to trust and availability."""

    EVENT_TYPE = "execution.worker.enabled"

    trust: str = ""
    availability: str = ""
    executable: bool = False
    """Whether it can actually be selected now. Enabling something unverified or
    unreachable is legal and leaves this false -- which is the fact worth
    recording, because 'I enabled it and nothing ran' is otherwise a mystery."""


@dataclass(frozen=True)
class WorkerDisabled(_WorkerEvent):
    """Switched off, reversibly."""

    EVENT_TYPE = "execution.worker.disabled"

    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("reason", self.reason)


@dataclass(frozen=True)
class WorkerRevoked(_WorkerEvent):
    """Withdrawn permanently. Terminal."""

    EVENT_TYPE = "execution.worker.revoked"

    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("reason", self.reason)


@dataclass(frozen=True)
class WorkerTrustChanged(_WorkerEvent):
    """How much the platform vouches for this implementation changed.

    Separate from the lifecycle events because trust and availability are
    separate axes. "We stopped trusting this build" and "we turned it off" are
    very different records during an incident.
    """

    EVENT_TYPE = "execution.worker.trust_changed"

    previous_trust: str = ""
    trust: str = ""
    reason: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("trust", self.trust)
        _require_text("reason", self.reason)


@dataclass(frozen=True)
class WorkerSelected(_WorkerEvent):
    """An implementation was chosen for one binding.

    The event replay reads to answer "which worker performed this, and why was
    it eligible" without re-running selection. It carries both digests: the
    worker's build and the binding's, so a later disagreement between them is
    visible in history rather than only inferable from it.
    """

    EVENT_TYPE = "execution.worker.selected"

    selection_id: str = ""
    selection_digest: str = ""
    policy_version: str = ""
    binding_id: str = ""
    binding_digest: str = ""
    capability_ref: str = ""
    capability_digest: str = ""
    provider: str = ""
    operation: str = ""
    environment: str = ""
    interface: str = ""
    execution_id: str = ""
    node_id: str = ""
    candidates_assessed: int = 0
    reasons: tuple = ()

    def __post_init__(self) -> None:
        super().__post_init__()
        for label in (
            "selection_id",
            "selection_digest",
            "binding_id",
            "binding_digest",
            "capability_ref",
            "environment",
        ):
            _require_text(label, getattr(self, label))


WORKER_EVENT_TYPES = (
    WorkerRegistered,
    WorkerValidated,
    WorkerEnabled,
    WorkerDisabled,
    WorkerRevoked,
    WorkerTrustChanged,
    WorkerSelected,
)
