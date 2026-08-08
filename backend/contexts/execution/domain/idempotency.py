"""Idempotency identity and its lifecycle.

The key must be derived, not invented
---------------------------------------
A random UUID per request is not an idempotency key. It makes every attempt look
like a new operation, which is the opposite of what the mechanism is for. The key
has to be a function of *the logical operation*, so that the same operation
arriving twice presents the same key both times.

Here it is derived from the facts that identify the operation:

    tenant + execution + workflow digest + node + declared operation key

The workflow digest is included deliberately: the same node in a workflow that
has been revised is **not** the same logical operation, and letting the new
version reuse the old key would suppress work that genuinely needs to happen.

The attempt number is deliberately **excluded**. Including it would give every
retry a fresh key, which would make retries duplicate rather than collapse --
the exact bug this module exists to prevent.

What the record is for
------------------------
The key alone answers "have I seen this before". The record answers "and what
came of it", which is what a caller needs when the answer is yes. It also holds
the one fact that matters after a crash: whether the operation was *committed*
before the process died.

``response_digest`` stores a digest, never the response. Storing external
payloads here would put third-party data of unbounded size into the runtime's
own state; a digest is enough to tell whether two answers agree.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Mapping, Optional

from backend.contracts.errors import ContractViolation
from backend.platform.hashing import compute_digest

__all__ = [
    "IdempotencyStatus",
    "IdempotencyKey",
    "IdempotencyRecord",
    "derive_key",
]

_DEFAULT_TTL_HOURS = 24


class IdempotencyStatus(str, Enum):
    """Where a logical operation had got to when it was last written down."""

    IN_FLIGHT = "in_flight"
    """Started, no outcome recorded. After a crash this is the interesting one:
    it means the operation may or may not have reached the far side."""

    COMMITTED = "committed"
    """The side effect is known to have happened. A duplicate must return this
    rather than doing the work again."""

    FAILED = "failed"
    """Known not to have happened. A duplicate may legitimately try again."""

    UNKNOWN = "unknown"
    """In flight when contact was lost. Not committed, not failed, and not
    something to guess about."""

    @property
    def is_settled(self) -> bool:
        return self in {IdempotencyStatus.COMMITTED, IdempotencyStatus.FAILED}

    @property
    def permits_a_fresh_attempt(self) -> bool:
        """Whether seeing this record again may lead to doing the work.

        ``UNKNOWN`` does not. That is the point of it.
        """
        return self is IdempotencyStatus.FAILED


@dataclass(frozen=True)
class IdempotencyKey:
    """A deterministic name for one logical operation."""

    value: str
    tenant_id: str
    execution_id: str
    node_id: str
    workflow_digest: str

    def __post_init__(self) -> None:
        for label in ("value", "tenant_id", "execution_id", "node_id", "workflow_digest"):
            got = getattr(self, label)
            if not isinstance(got, str) or not got.strip():
                raise ContractViolation(f"{label} must be non-blank text")

    def __str__(self) -> str:
        return self.value


def derive_key(
    *,
    tenant_id: str,
    execution_id: str,
    node_id: str,
    workflow_digest: str,
    operation_key: Optional[str] = None,
) -> IdempotencyKey:
    """Derive the key for one logical operation.

    Uses the platform's canonical hashing; this module does not implement its
    own. Note the absent attempt number -- see the module docstring.
    """
    payload = {
        "tenant_id": tenant_id,
        "execution_id": execution_id,
        "node_id": node_id,
        "workflow_digest": workflow_digest,
        "operation_key": operation_key or node_id,
    }
    return IdempotencyKey(
        value=compute_digest(payload).value,
        tenant_id=tenant_id,
        execution_id=execution_id,
        node_id=node_id,
        workflow_digest=workflow_digest,
    )


@dataclass(frozen=True)
class IdempotencyRecord:
    """What is known about one logical operation, durable across attempts."""

    key: str
    tenant_id: str
    operation: str
    status: IdempotencyStatus
    execution_id: str
    node_id: str
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: Optional[datetime] = None
    attempt: int = 1
    outcome_reference: Optional[str] = None
    response_digest: Optional[str] = None
    expires_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        for label in ("key", "tenant_id", "operation", "execution_id", "node_id"):
            got = getattr(self, label)
            if not isinstance(got, str) or not got.strip():
                raise ContractViolation(f"{label} must be non-blank text")
        if not isinstance(self.status, IdempotencyStatus):
            raise ContractViolation("status must be an IdempotencyStatus")
        if self.first_seen.tzinfo is None:
            raise ContractViolation("first_seen must be timezone-aware")
        if self.status is IdempotencyStatus.COMMITTED and not self.outcome_reference:
            raise ContractViolation(
                "a committed operation must reference its outcome; a record that "
                "says the work happened but cannot say what came of it gives a "
                "duplicate caller nothing to return"
            )

    @classmethod
    def opened(
        cls,
        key: IdempotencyKey,
        *,
        operation: str,
        attempt: int = 1,
        now: Optional[datetime] = None,
        ttl_hours: int = _DEFAULT_TTL_HOURS,
    ) -> "IdempotencyRecord":
        moment = now or datetime.now(timezone.utc)
        return cls(
            key=key.value,
            tenant_id=key.tenant_id,
            operation=operation,
            status=IdempotencyStatus.IN_FLIGHT,
            execution_id=key.execution_id,
            node_id=key.node_id,
            first_seen=moment,
            attempt=attempt,
            expires_at=moment + timedelta(hours=ttl_hours),
        )

    def committed(
        self,
        *,
        outcome_reference: str,
        response: Optional[Mapping[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> "IdempotencyRecord":
        from dataclasses import replace

        return replace(
            self,
            status=IdempotencyStatus.COMMITTED,
            outcome_reference=outcome_reference,
            response_digest=compute_digest(dict(response)).value if response else None,
            updated_at=now or datetime.now(timezone.utc),
        )

    def failed(self, *, now: Optional[datetime] = None) -> "IdempotencyRecord":
        from dataclasses import replace

        return replace(
            self,
            status=IdempotencyStatus.FAILED,
            updated_at=now or datetime.now(timezone.utc),
        )

    def unknown(self, *, now: Optional[datetime] = None) -> "IdempotencyRecord":
        """Contact was lost while this was in flight."""
        from dataclasses import replace

        if self.status is not IdempotencyStatus.IN_FLIGHT:
            raise ContractViolation(
                f"only an in-flight operation can become unknown; this one is "
                f"{self.status.value}, and downgrading a settled fact to a "
                "question loses the answer"
            )
        return replace(
            self,
            status=IdempotencyStatus.UNKNOWN,
            updated_at=now or datetime.now(timezone.utc),
        )

    def has_expired_at(self, moment: datetime) -> bool:
        return self.expires_at is not None and moment >= self.expires_at

    def agrees_with(self, response: Mapping[str, Any]) -> bool:
        """Whether a fresh response matches the one already recorded."""
        if not self.response_digest:
            return False
        return compute_digest(dict(response)).value == self.response_digest

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "tenant_id": self.tenant_id,
            "operation": self.operation,
            "status": self.status.value,
            "execution_id": self.execution_id,
            "node_id": self.node_id,
            "first_seen": self.first_seen.isoformat(),
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "attempt": self.attempt,
            "outcome_reference": self.outcome_reference,
            "response_digest": self.response_digest,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }
