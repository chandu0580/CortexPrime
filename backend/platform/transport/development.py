"""A non-production transport that answers without a network.

Why it exists
---------------
The whole point of Phase 4.2 is that the *gate* is real while no transport is.
Without something that can answer ``dial``, the gate can only be tested up to the
refusal, and the paths after a successful approval — outcome classification,
budget enforcement, connection accounting — stay unexercised.

What it does not do
---------------------
It does not bypass anything. It sits **behind** the broker, so every request it
sees has already passed endpoint policy, address judgement and pinning. It cannot
be reached without them, which is the difference between a test double and a
hole.

Named for what it is
----------------------
``DevelopmentTransport``, and it refuses ``PRODUCTION`` at construction and again
at dial. A mock transport that returned success in production would make every
provider look reachable and every action look performed — the most dangerous
possible failure for an execution engine, because it is silent.
"""

from __future__ import annotations

from typing import Any, Callable, Mapping, Optional

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionEnvironment
from backend.contracts.transport import (
    ConnectionRef,
    TransportFailure,
    TransportKind,
)
from backend.platform.transport.request import (
    DeliveryState,
    TransportOutcome,
    TransportRequest,
)

__all__ = ["DevelopmentTransport"]


class DevelopmentTransport:
    """A scripted transport for exercising the fabric. **Never for production.**"""

    def __init__(
        self,
        *,
        kinds: frozenset,
        allow_non_production: bool,
        responder: Optional[Callable[[TransportRequest], Mapping[str, Any]]] = None,
        environments: Optional[frozenset] = None,
    ) -> None:
        if allow_non_production is not True:
            raise ContractViolation(
                "DevelopmentTransport requires allow_non_production=True to be "
                "passed explicitly. A mock transport reaching production would "
                "make every provider look reachable and every action look "
                "performed, silently"
            )
        if not kinds:
            raise ContractViolation("a transport must declare the kinds it carries")
        for kind in kinds:
            if not isinstance(kind, TransportKind):
                raise ContractViolation("kinds must contain TransportKind values")

        allowed = frozenset(
            environments
            or {ExecutionEnvironment.DEVELOPMENT, ExecutionEnvironment.STAGING}
        )
        if ExecutionEnvironment.PRODUCTION in allowed:
            raise ContractViolation(
                "DevelopmentTransport cannot serve PRODUCTION; it sends nothing "
                "and answers from a script"
            )

        self._kinds = frozenset(kinds)
        self._environments = allowed
        self._responder = responder
        self._closed: set = set()

    @property
    def kinds(self) -> frozenset:
        return self._kinds

    def dial(
        self,
        request: TransportRequest,
        *,
        pinned_addresses: tuple,
        connection: ConnectionRef,
    ) -> TransportOutcome:
        # Asserted again at the point of use: a construction-time check alone is
        # bypassable by anything that mutates the attribute afterwards.
        if request.endpoint.environment is ExecutionEnvironment.PRODUCTION:
            return TransportOutcome.refused(
                TransportFailure.ENVIRONMENT_MISMATCH,
                "the development transport does not serve production",
            )
        if request.endpoint.environment not in self._environments:
            return TransportOutcome.refused(
                TransportFailure.ENVIRONMENT_MISMATCH,
                "the development transport is not registered for this environment",
            )
        if not pinned_addresses and request.endpoint.transport.is_network:
            # The broker pins before dialling. An empty pinning means the
            # destination was not approved, and a transport must never dial one.
            return TransportOutcome.refused(
                TransportFailure.SSRF_REFUSED,
                "no approved address was pinned for this destination",
            )

        scripted = self._responder(request) if self._responder else {}
        body = scripted.get("body", b"")
        budget = request.policy.budget
        truncated = len(body) > budget.max_response_bytes
        if truncated:
            body = body[: budget.max_response_bytes]

        return TransportOutcome(
            delivery=DeliveryState.DELIVERED,
            connection=connection,
            status_code=int(scripted.get("status", 200)),
            response_bytes=len(body),
            truncated=truncated,
            # Carried so a provider adapter can normalise the answer, under the
            # same budget a real transport enforces -- the truncation above
            # happens before this, so a scripted over-budget response is
            # truncated and *says so* rather than arriving whole.
            body=body,
            duration_seconds=0.0,
            resolved_addresses=tuple(pinned_addresses),
        )

    def close(self, connection: ConnectionRef) -> None:
        self._closed.add(connection.connection_id)

    def __repr__(self) -> str:
        return (
            f"<DevelopmentTransport kinds={sorted(k.value for k in self._kinds)} "
            "NON-PRODUCTION>"
        )
