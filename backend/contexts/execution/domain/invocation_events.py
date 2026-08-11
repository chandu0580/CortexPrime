"""Invocation lifecycle events. Namespaced ``capability.invocation.*``.

Five facts, and why each is genuinely new
-------------------------------------------
``execution.runtime.*`` describes a *run*. ``execution.worker.*`` describes the
*fabric*. Neither says whether the authority chain held at the instant work was
about to happen, which is the only thing this gate decides.

    admitted    every authority agreed; nothing has run
    started     credentials were acquired and the adapter was called
    completed   the invocation returned a knowable outcome
    ambiguous   the invocation returned, and nobody can say what happened
    refused     the chain did not hold, and no worker was called

``admitted`` and ``started`` are not one fact. Credential acquisition happens
between them — deliberately last, after every authorization check — so a run
stuck between the two is a run whose credential broker hung, and collapsing them
would make that indistinguishable from a worker that never answered.

``completed`` and ``ambiguous`` are not one fact either. That distinction is the
whole of Phase 3.1: a call that timed out is not a call that failed, and an
ambiguous mutation must never be retried the way a definite failure can be.

What is deliberately absent
-----------------------------
No ``CapabilityRebound``, no ``WorkerRebound``, no ``BindingUpdated``. Bindings
and worker selections are immutable, so an event announcing one changed would
describe something that structurally cannot happen.

Refusals are first-class
--------------------------
``refused`` carries the same attribution as a success. A denial that is merely
logged is a denial nobody can count, and "how often is this capability being
refused, and for whom" is a question asked during every incident.

None of these carries a credential, a token, or a raw payload — only digests.
"""

from __future__ import annotations

from dataclasses import dataclass

from backend.contracts.errors import ContractViolation
from backend.platform.events import DomainEvent

__all__ = [
    "INVOCATION_AGGREGATE_TYPE",
    "InvocationAdmitted",
    "InvocationStarted",
    "InvocationCompleted",
    "InvocationAmbiguous",
    "InvocationRefusedEvent",
    "INVOCATION_EVENT_TYPES",
]

INVOCATION_AGGREGATE_TYPE = "execution"
"""The run, not a new aggregate. An invocation is something that happens *to* an
execution; giving it its own aggregate would split one run's history across two
streams and make ordering between them unrecoverable."""


def _require_text(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ContractViolation(f"{label} must be non-blank text")


@dataclass(frozen=True)
class _InvocationEvent(DomainEvent):
    """Shared attribution: which run, which attempt, which authority."""

    execution_id: str = ""
    attempt_id: str = ""
    node_id: str = ""
    tenant_id: str = ""
    principal_id: str = ""
    capability_ref: str = ""
    capability_digest: str = ""
    binding_id: str = ""
    binding_digest: str = ""
    operation: str = ""
    environment: str = ""
    correlation_id_ref: str = ""
    """The correlation id as an explicit payload field. Also on ``metadata``;
    carried here too because the payload is what survives into the outbox and an
    operator correlating across systems should not have to unwrap an envelope."""

    def __post_init__(self) -> None:
        super().__post_init__()
        for label in (
            "execution_id",
            "attempt_id",
            "node_id",
            "tenant_id",
            "principal_id",
            "capability_ref",
            "binding_id",
            "operation",
            "environment",
        ):
            _require_text(label, getattr(self, label))


@dataclass(frozen=True)
class InvocationAdmitted(_InvocationEvent):
    """Every authority agreed. Nothing has run yet.

    The most security-relevant event in the phase: it is the record that the
    whole chain was checked and held, at a stated instant, against stated
    digests. ``action_digest`` is what binds it to a concrete action rather than
    to a capability in the abstract.
    """

    EVENT_TYPE = "capability.invocation.admitted"

    worker_id: str = ""
    worker_digest: str = ""
    worker_selection_id: str = ""
    action_digest: str = ""
    policy_version: str = ""
    authorization_digest: str = ""
    approval_artifact_id: str = ""
    risk: str = ""
    effect_semantics: str = ""
    side_effect_class: str = ""
    effective_expiry: str = ""
    expiry_limited_by: str = ""
    deadline_seconds: int = 0

    def __post_init__(self) -> None:
        super().__post_init__()
        for label in ("worker_id", "worker_digest", "action_digest"):
            _require_text(label, getattr(self, label))


@dataclass(frozen=True)
class InvocationStarted(_InvocationEvent):
    """Credentials were acquired and the adapter was called."""

    EVENT_TYPE = "capability.invocation.started"

    worker_id: str = ""
    worker_digest: str = ""
    action_digest: str = ""
    deadline_seconds: int = 0
    credential_required: bool = False
    """Whether a credential was needed at all. Never *which* credential, never a
    handle, never a reference that could be resolved to one."""


@dataclass(frozen=True)
class InvocationCompleted(_InvocationEvent):
    """The invocation returned an outcome somebody can state."""

    EVENT_TYPE = "capability.invocation.completed"

    worker_id: str = ""
    worker_digest: str = ""
    action_digest: str = ""
    outcome: str = ""
    result_digest: str = ""
    observed_effect: str = ""
    duration_seconds: float = 0.0
    failure_class: str = ""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("outcome", self.outcome)


@dataclass(frozen=True)
class InvocationAmbiguous(_InvocationEvent):
    """The invocation returned and nobody can say whether the effect happened.

    Separate from ``completed`` because the response differs completely. A
    definite failure can be retried; this may already have applied a production
    change, and re-running it is exactly what the ambiguity is about.

    ``mutating`` is the field an operator reads first: an ambiguous read is a
    nuisance, an ambiguous write is an incident.
    """

    EVENT_TYPE = "capability.invocation.ambiguous"

    worker_id: str = ""
    worker_digest: str = ""
    action_digest: str = ""
    outcome: str = ""
    failure_class: str = ""
    reason: str = ""
    mutating: bool = False
    idempotent: bool = False
    """Whether a retry would be safe. An ambiguous, mutating, non-idempotent
    operation is the one case with no safe automatic recovery at all."""

    duration_seconds: float = 0.0


@dataclass(frozen=True)
class InvocationRefusedEvent(_InvocationEvent):
    """The authority chain did not hold. No worker was called.

    Named with an ``Event`` suffix because ``InvocationRefused`` is the exception
    raised at the boundary. One is a fact in the log; the other stops a call
    stack, and giving them the same name is how somebody eventually catches the
    wrong one.
    """

    EVENT_TYPE = "capability.invocation.refused"

    refusal: str = ""
    reason: str = ""
    retryable: bool = False
    security_relevant: bool = False
    worker_id: str = ""
    worker_digest: str = ""
    action_digest: str = ""
    stage: str = ""
    """Which link in the chain broke -- identity, tenancy, authorization,
    approval, binding, worker, input, lease, deadline, credential, result."""

    def __post_init__(self) -> None:
        super().__post_init__()
        _require_text("refusal", self.refusal)
        _require_text("reason", self.reason)


INVOCATION_EVENT_TYPES = (
    InvocationAdmitted,
    InvocationStarted,
    InvocationCompleted,
    InvocationAmbiguous,
    InvocationRefusedEvent,
)
