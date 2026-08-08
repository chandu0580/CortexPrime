"""Structured failure classification.

Why a taxonomy rather than a string
-------------------------------------
``failure_reason: str`` tells an operator what happened. It tells the *runtime*
nothing. Every automatic decision this context has to make -- retry or not, wait
or escalate, reconcile or compensate -- depends on what kind of failure it was,
and a free-text reason cannot be reasoned about.

Turning every exception into "execution failed" is what makes a runtime retry an
authorization error thirty times and give up on a transient one.

The classification is deliberately about *the runtime's next move*, not about
where the error came from. Two failures from completely different subsystems that
call for the same response share a class.

The one that matters most
---------------------------
``UNKNOWN_OUTCOME`` is not a failure. It is the absence of knowledge about
whether the work succeeded. It exists because the alternative -- calling a lost
response a failure and retrying -- is how a delete runs twice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional

from backend.contracts.errors import ContractViolation

__all__ = ["FailureClass", "FailureRecord"]


class FailureClass(str, Enum):
    """What kind of failure this was, in terms of what to do about it."""

    VALIDATION_FAILURE = "validation_failure"
    """The request was wrong. Retrying it unchanged fails identically."""

    AUTHORIZATION_FAILURE = "authorization_failure"
    """Refused for lack of permission. A retry is a retry of the refusal."""

    TRANSIENT_FAILURE = "transient_failure"
    """Expected to clear on its own. The archetypal retryable case."""

    PERMANENT_FAILURE = "permanent_failure"
    """Will not clear by waiting. Retrying only delays the report."""

    TIMEOUT = "timeout"
    """A deadline fired. Whether the work happened is a separate question --
    see ``outcome_known``."""

    CANCELLATION = "cancellation"
    """Somebody called it off. Operationally not a failure at all, and it must
    never turn into one: 'user cancelled the deploy' and 'the deploy broke' are
    different facts that lead to different conversations."""

    WORKER_FAILURE = "worker_failure"
    """The worker died, not the work. Another worker may well succeed."""

    NETWORK_FAILURE = "network_failure"
    """The request may or may not have arrived. Ambiguous by nature."""

    EXTERNAL_SYSTEM_FAILURE = "external_system_failure"
    """The far side reported an error. It knows what happened; we do not."""

    UNKNOWN_OUTCOME = "unknown_outcome"
    """We do not know whether the work happened. Not a failure -- an absence of
    knowledge, and the only honest answer after a lost response."""

    CONCURRENCY_CONFLICT = "concurrency_conflict"
    """Somebody else moved first. Reload and reconsider, do not force."""

    POLICY_REFUSAL = "policy_refusal"
    """The runtime refused on purpose. Retrying is arguing with the policy."""

    RECOVERY_REQUIRED = "recovery_required"
    """The run cannot proceed automatically. A decision is owed."""

    @property
    def is_ambiguous(self) -> bool:
        """Whether the external outcome is unknown.

        These are the classes where "just retry it" can apply an action twice.
        A timeout is included on purpose: a deadline says when we stopped
        waiting, never what the far side did.
        """
        return self in {
            FailureClass.UNKNOWN_OUTCOME,
            FailureClass.NETWORK_FAILURE,
            FailureClass.TIMEOUT,
        }

    @property
    def is_worth_retrying(self) -> bool:
        """Whether a further attempt could plausibly succeed.

        Advisory only. Whether a retry is *safe* is a separate question that
        depends on the effect, and both must agree before anything runs again.
        """
        return self in {
            FailureClass.TRANSIENT_FAILURE,
            FailureClass.WORKER_FAILURE,
            FailureClass.NETWORK_FAILURE,
            FailureClass.CONCURRENCY_CONFLICT,
            FailureClass.TIMEOUT,
        }

    @property
    def is_terminal_for_the_node(self) -> bool:
        """Whether further attempts are pointless without human change."""
        return self in {
            FailureClass.VALIDATION_FAILURE,
            FailureClass.AUTHORIZATION_FAILURE,
            FailureClass.PERMANENT_FAILURE,
            FailureClass.POLICY_REFUSAL,
            FailureClass.CANCELLATION,
        }

    @property
    def needs_a_decision(self) -> bool:
        return self in {
            FailureClass.UNKNOWN_OUTCOME,
            FailureClass.RECOVERY_REQUIRED,
        }


@dataclass(frozen=True)
class FailureRecord:
    """One classified failure, with the evidence that supports the class."""

    failure_class: FailureClass
    reason: str
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    source: Optional[str] = None
    retryable_hint: Optional[bool] = None
    detail: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.failure_class, FailureClass):
            raise ContractViolation("failure_class must be a FailureClass")
        if not isinstance(self.reason, str) or not self.reason.strip():
            raise ContractViolation(
                "a failure must say why in words a human can act on; the class "
                "tells the runtime what to do and the reason tells the operator "
                "what happened, and neither substitutes for the other"
            )
        if self.occurred_at.tzinfo is None:
            raise ContractViolation("occurred_at must be timezone-aware")

    @property
    def outcome_known(self) -> bool:
        """Whether we can say what happened on the far side."""
        return not self.failure_class.is_ambiguous

    def to_dict(self) -> dict:
        return {
            "failure_class": self.failure_class.value,
            "reason": self.reason,
            "occurred_at": self.occurred_at.isoformat(),
            "source": self.source,
            "retryable_hint": self.retryable_hint,
            "detail": dict(self.detail),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "FailureRecord":
        return cls(
            failure_class=FailureClass(data["failure_class"]),
            reason=data["reason"],
            occurred_at=datetime.fromisoformat(data["occurred_at"]),
            source=data.get("source"),
            retryable_hint=data.get("retryable_hint"),
            detail=data.get("detail", {}),
        )
