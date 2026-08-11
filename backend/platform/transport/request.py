"""The transport request, its outcome, and the refusal vocabulary.

A transport request is already authorized
-------------------------------------------
By the time one of these exists, the invocation gateway has admitted the action
and the credential fabric has issued material for it. This object carries what a
transport needs to *make the connection* and nothing that would let it decide
whether the connection may be made — no capability, no operation, no grants.

That absence is deliberate: a transport holding an authorization input is a
transport that can be argued into re-deciding.

Credential material is referenced, never embedded
---------------------------------------------------
``credential`` holds the Phase 4.1 ``CredentialMaterial`` for the moment of use
and is excluded from every serialisation the same way ``InvocationAdmission``
excludes it — ``repr=False``, absent from ``to_dict``, and unserialisable in
itself, so writing a request down fails loudly rather than quietly leaking.

Outcomes report facts, never decisions
----------------------------------------
``TransportOutcome`` says what was observed. It does not say whether to retry,
whether the node failed, or what the run's state becomes — Execution decides all
three, and it needs ``delivery`` to do it. A transport that classified a lost
connection as a definite failure would licence a retry that duplicates a
production change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional

from backend.contracts.errors import ContractViolation
from backend.contracts.identity import PrincipalRef
from backend.contracts.transport import ConnectionRef, TransportFailure
from backend.platform.transport.endpoint import TransportEndpoint
from backend.platform.transport.policy import ConnectionPolicy

__all__ = [
    "DeliveryState",
    "TransportRequest",
    "TransportOutcome",
    "TransportRefused",
]


#: Response headers a transport must never report upward. Each one is a
#: credential in header form, and the point of refusing them here rather than
#: filtering later is that there is then no code path where one exists in memory
#: as a reportable fact.
_UNREPORTABLE_RESPONSE_HEADERS = frozenset(
    {"set-cookie", "authorization", "proxy-authenticate", "www-authenticate"}
)


class DeliveryState(str, Enum):
    """Whether the request reached the provider. The field Execution reads.

    Three answers, and the third is not a hedge — it is the only honest report
    for a connection that dropped mid-send. Collapsing it into either neighbour
    is how an ambiguous mutation gets retried.
    """

    NOT_DELIVERED = "not_delivered"
    """Provably nothing left this process. Only for failures that occur before a
    byte of the request is written."""

    DELIVERED = "delivered"
    """The provider received it and answered. Says nothing about whether it
    liked the request."""

    UNKNOWN = "unknown"
    """Nobody can say. The default whenever the fabric is not certain, because
    certainty is the thing being claimed."""

    @property
    def is_safe_to_repeat_blindly(self) -> bool:
        """Only when nothing was delivered. Execution still decides."""
        return self is DeliveryState.NOT_DELIVERED


class TransportRefused(ContractViolation):
    """The transport declined. Carries a classified failure and no secret."""

    def __init__(
        self,
        failure: TransportFailure,
        message: str,
        *,
        correlation_id: Optional[str] = None,
        detail: Optional[Mapping[str, Any]] = None,
    ) -> None:
        super().__init__(f"{failure.value}: {message}")
        self.failure = failure
        self.reason_code = failure.value
        self.safe_message = message
        self.correlation_id = correlation_id
        self.detail = dict(detail or {})

    @property
    def delivery(self) -> DeliveryState:
        """A refusal happens before anything is sent -- unless it cannot say so."""
        if self.failure.is_definitely_not_delivered:
            return DeliveryState.NOT_DELIVERED
        return DeliveryState.UNKNOWN

    def to_dict(self) -> dict:
        return {
            "failure": self.failure.value,
            "reason": self.safe_message,
            "delivery": self.delivery.value,
            "security_relevant": self.failure.is_security_relevant,
            "correlation_id": self.correlation_id,
            **self.detail,
        }


@dataclass(frozen=True)
class TransportRequest:
    """One connection attempt. Everything explicit, nothing ambient."""

    endpoint: TransportEndpoint
    policy: ConnectionPolicy
    tenant_id: str
    principal: PrincipalRef

    method: str = "POST"
    headers: Mapping[str, str] = field(default_factory=dict)
    """Caller-supplied headers, already validated. ``Authorization`` cannot be
    among them — see ``headers.FORBIDDEN_CALLER_HEADERS``."""

    body: Optional[bytes] = None

    execution_id: Optional[str] = None
    node_id: Optional[str] = None
    attempt_id: Optional[str] = None
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None

    idempotency_key: Optional[str] = None
    """Execution's key, passed through untouched. The transport never mints one
    and never varies it per connection attempt: a new key per attempt would make
    every retry a new operation to the provider, which is the opposite of what
    an idempotency key is for."""

    on_behalf_of: Optional[PrincipalRef] = None
    authority_seconds_remaining: Optional[float] = None
    """How long the invocation's authority still has. Every timeout is clamped to
    it, so a connection cannot outlive the permission for it."""

    credential: Optional[Any] = field(default=None, repr=False, compare=False)
    """Phase 4.1 ``CredentialMaterial``, present only for the moment of use.

    ``repr=False`` and ``compare=False``, absent from ``to_dict``, and
    unserialisable in itself — so a request that somebody tries to write down
    fails loudly rather than quietly emitting a token."""

    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.endpoint, TransportEndpoint):
            raise ContractViolation("endpoint must be a TransportEndpoint")
        if not isinstance(self.policy, ConnectionPolicy):
            raise ContractViolation("policy must be a ConnectionPolicy")
        if not isinstance(self.principal, PrincipalRef):
            raise ContractViolation("principal must be a PrincipalRef")
        if not isinstance(self.tenant_id, str) or not self.tenant_id.strip():
            raise ContractViolation(
                "a transport request must name its tenant; there is no ambient "
                "tenant and no default"
            )
        if self.endpoint.environment is not self.policy.environment:
            raise ContractViolation(
                "the endpoint and the policy name different environments; one of "
                "them is for a deployment this request is not part of"
            )
        if not isinstance(self.method, str) or not self.method.isalpha():
            raise ContractViolation("method must be alphabetic text")
        if self.body is not None and not isinstance(self.body, (bytes, bytearray)):
            raise ContractViolation(
                "a request body must be bytes; encoding belongs to the caller so "
                "that the transport never guesses a charset"
            )
        if self.body is not None and len(self.body) > self.policy.budget.max_request_bytes:
            raise ContractViolation(
                f"the request body exceeds the {self.policy.budget.max_request_bytes}"
                "-byte budget"
            )

    @property
    def method_normalised(self) -> str:
        return self.method.upper()

    @property
    def effective_timeouts(self):
        """Timeouts clamped to the remaining authority window."""
        return self.policy.timeouts.bounded_by(self.authority_seconds_remaining)

    def to_dict(self) -> dict:
        """Safe for audit. No body, no headers, no credential, no query string."""
        return {
            "endpoint": self.endpoint.to_dict(),
            "tenant_id": self.tenant_id,
            "principal_id": self.principal.principal_id,
            "on_behalf_of": (
                self.on_behalf_of.principal_id if self.on_behalf_of else None
            ),
            "method": self.method_normalised,
            "transport": self.endpoint.transport.value,
            "execution_id": self.execution_id,
            "node_id": self.node_id,
            "attempt_id": self.attempt_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "idempotency_key_present": self.idempotency_key is not None,
            "credential_present": self.credential is not None,
            "body_bytes": len(self.body) if self.body else 0,
            "requested_at": self.requested_at.isoformat(),
        }


@dataclass(frozen=True)
class TransportOutcome:
    """What the transport observed. Execution decides what it means."""

    delivery: DeliveryState
    connection: Optional[ConnectionRef] = None
    status_code: Optional[int] = None
    failure: Optional[TransportFailure] = None
    reason: Optional[str] = None

    response_bytes: int = 0
    truncated: bool = False
    """Whether the response hit the budget. **Never silently**: a truncated body
    that looked complete would be parsed as complete, and a provider could use
    that to make a partial answer look whole."""

    body: Optional[bytes] = field(default=None, repr=False, compare=False)
    """The response bytes, bounded by ``budget.max_response_bytes``.

    **Added in Phase 4.3**, and the one field on this type that is not safe to
    write down. A provider adapter has to see the answer to normalise it: §26 of
    ADR-042 requires a response to be *validated* before it counts as success,
    and there is no other channel — transport is the only thing that reads bytes.

    Carried under the same rules as ``TransportRequest.credential``: ``repr=False``,
    ``compare=False``, and absent from ``to_dict``, so an outcome that somebody
    logs or audits emits its classification and never its content. What survives
    into an execution event is a digest and a handful of declared evidence
    fields (ADR-042 §56), never this.

    ``None`` where nothing was read. Never confuse that with an empty body: a
    provider that answered ``204`` sent zero bytes deliberately, and a connection
    that dropped sent none at all.
    """

    response_headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    """Lower-cased response headers, for the metadata a provider publishes there.

    **Added in Phase 4.3.** Rate-limit state, a provider's request id and
    ``Retry-After`` are header-only facts, and ADR-042 §58 requires them to be
    returned rather than acted on. Adapters read a declared handful of names;
    nothing here is forwarded anywhere.

    Credential-bearing names are refused at construction rather than filtered
    downstream — ``set-cookie`` in particular is a session credential that
    would otherwise be one careless ``to_dict`` away from an audit record. A
    transport that returns one is reporting something it must not, and the
    refusal makes that a bug at the source instead of a leak at the sink.
    """

    duration_seconds: float = 0.0
    redirects_followed: int = 0
    resolved_addresses: tuple = ()
    """What the destination actually resolved to. The audit record that answers
    "where did this request really go" after the fact."""

    def __post_init__(self) -> None:
        if not isinstance(self.delivery, DeliveryState):
            raise ContractViolation("delivery must be a DeliveryState")
        if self.failure is not None and not isinstance(self.failure, TransportFailure):
            raise ContractViolation("failure must be a TransportFailure")
        if self.succeeded and self.failure is not None:
            raise ContractViolation(
                "a successful outcome cannot carry a failure; reporting both "
                "leaves whoever reads it to decide which was true"
            )
        if self.delivery is DeliveryState.NOT_DELIVERED and self.status_code is not None:
            raise ContractViolation(
                "an undelivered request cannot have a status code; a status came "
                "from a provider, which means it was delivered"
            )
        if self.body is not None:
            if not isinstance(self.body, (bytes, bytearray)):
                raise ContractViolation(
                    "a response body must be bytes; decoding belongs to whoever "
                    "knows the content type, so the transport never guesses one"
                )
            if self.delivery is DeliveryState.NOT_DELIVERED:
                raise ContractViolation(
                    "an undelivered request cannot have a response body; bytes "
                    "came back from somewhere, which means something was sent"
                )
        if self.response_headers:
            cleaned = {}
            for name, value in self.response_headers.items():
                if not isinstance(name, str) or not isinstance(value, str):
                    raise ContractViolation("response headers must be text pairs")
                lowered = name.lower()
                if lowered in _UNREPORTABLE_RESPONSE_HEADERS:
                    raise ContractViolation(
                        f"a transport must not report {lowered!r}; it carries "
                        "credential material, and a header map is one careless "
                        "serialisation away from an audit record"
                    )
                cleaned[lowered] = value[:1024]
            object.__setattr__(self, "response_headers", cleaned)

    @property
    def succeeded(self) -> bool:
        """Delivered, answered, and not a failure. Nothing weaker counts."""
        return (
            self.delivery is DeliveryState.DELIVERED
            and self.failure is None
            and self.status_code is not None
        )

    @property
    def outcome_is_known(self) -> bool:
        return self.delivery is not DeliveryState.UNKNOWN

    def to_dict(self) -> dict:
        return {
            "delivery": self.delivery.value,
            "succeeded": self.succeeded,
            "outcome_known": self.outcome_is_known,
            "connection": self.connection.value if self.connection else None,
            "status_code": self.status_code,
            "failure": self.failure.value if self.failure else None,
            "reason": self.reason,
            "response_bytes": self.response_bytes,
            "truncated": self.truncated,
            "duration_seconds": self.duration_seconds,
            "redirects_followed": self.redirects_followed,
            "resolved_addresses": list(self.resolved_addresses),
        }

    @classmethod
    def refused(
        cls, failure: TransportFailure, reason: str
    ) -> "TransportOutcome":
        """A refusal before anything was sent, where that can be established."""
        return cls(
            delivery=(
                DeliveryState.NOT_DELIVERED
                if failure.is_definitely_not_delivered
                else DeliveryState.UNKNOWN
            ),
            failure=failure,
            reason=reason,
        )

    @classmethod
    def unknown(cls, reason: str, **fields: Any) -> "TransportOutcome":
        """The safe answer when nobody can say. Always available."""
        return cls(
            delivery=DeliveryState.UNKNOWN,
            failure=TransportFailure.UNKNOWN_STATE,
            reason=reason,
            **fields,
        )
