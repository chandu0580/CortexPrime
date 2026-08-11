"""The connector adapter. Generic, catalog-driven, and it stays generic.

No provider lives here
------------------------
There is no GitHub, no Jira, no Slack, no AWS and no Kubernetes in this module,
and none may be added to it. What varies between providers is expressed as data
(an ``OperationCatalog``) and as one narrow port (``ProviderResponseTranslator``),
both supplied at composition. The moment a provider acquires a branch in this
file, the generic adapter stops being generic and every later provider inherits
the shape of the first.

What it translates
--------------------
    binding + validated input   →  a declared operation  →  a provider request
    provider response           →  a normalised outcome

Both halves are bounded by declarations made before the invocation existed. The
adapter chooses nothing: the operation comes from the binding, the request shape
comes from the catalog entry for that operation, and the destination comes from
the channel's configured endpoint.

Why there is no ``request(url, method, body)``
------------------------------------------------
Because that is an authenticated HTTP proxy with a capability check in front of
it. Every operation it could perform would be "whatever the caller typed", the
capability that authorized it would describe nothing, and the approval that
covered it would have covered nothing. See ``provider_operation`` for the model
that replaces it — and note that this module has no code path that builds a
request from anything except a catalog entry.

Validation runs twice, deliberately
-------------------------------------
The invocation gateway is the authoritative input boundary and validated this
payload before the action was digested. This validates again against the
operation's own declaration, because the two answer slightly different questions
— "does this match the capability contract" and "can this provider's API accept
it" — and because a single wiring mistake should not remove both.

The V1 connectors in ``backend/connectors`` are **strangler targets**, not
dependencies. Nothing here imports them and no part of the new fabric depends on
``connector_registry``'s state.
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Protocol, Tuple, runtime_checkable

from backend.contracts.errors import ContractViolation
from backend.contracts.provider import ProviderDelivery, ProviderFailure, ProviderRef
from backend.contexts.execution.domain.provider_invocation import ProviderAuthority
from backend.contexts.execution.domain.provider_operation import (
    OperationCatalog,
    ProviderOperationSpec,
    UnknownOperation,
)
from backend.contexts.execution.domain.worker import WorkerKind
from backend.contexts.execution.domain.worker_contract import WorkerExecutionRequest
from backend.contexts.execution.domain.worker_directory import (
    WorkerImplementation,
    WorkerInterface,
)
from backend.contexts.execution.infrastructure.adapters.base import (
    AdapterPreflight,
    AdapterSeam,
    ProviderOutcome,
)
from backend.contexts.execution.infrastructure.adapters.channel import (
    ProviderChannel,
    ProviderExchange,
)

__all__ = [
    "ConnectorAdapter",
    "ProviderResponseTranslator",
    "HttpStatusTranslator",
    "DEFAULT_STATUS_FAILURES",
]

#: HTTP status to provider-neutral failure. The mapping most providers follow,
#: and the default a specific translator narrows rather than replaces.
#:
#: ``409`` is ``CONFLICT`` rather than a validation failure on purpose: a
#: conflict can follow a partially applied change, so it must not land anywhere
#: that reads as "definitely did not happen".
DEFAULT_STATUS_FAILURES: Mapping[int, ProviderFailure] = {
    400: ProviderFailure.VALIDATION_FAILURE,
    401: ProviderFailure.AUTHENTICATION_FAILURE,
    402: ProviderFailure.QUOTA_EXCEEDED,
    403: ProviderFailure.AUTHORIZATION_FAILURE,
    404: ProviderFailure.NOT_FOUND,
    405: ProviderFailure.OPERATION_NOT_SUPPORTED,
    408: ProviderFailure.TIMEOUT,
    409: ProviderFailure.CONFLICT,
    410: ProviderFailure.NOT_FOUND,
    412: ProviderFailure.PRECONDITION_FAILED,
    413: ProviderFailure.VALIDATION_FAILURE,
    422: ProviderFailure.VALIDATION_FAILURE,
    428: ProviderFailure.PRECONDITION_FAILED,
    429: ProviderFailure.RATE_LIMITED,
    500: ProviderFailure.UNAVAILABLE,
    501: ProviderFailure.OPERATION_NOT_SUPPORTED,
    502: ProviderFailure.UNAVAILABLE,
    503: ProviderFailure.UNAVAILABLE,
    504: ProviderFailure.TIMEOUT,
}


@runtime_checkable
class ProviderResponseTranslator(Protocol):
    """Where a provider's own dialect is understood. One port, per provider.

    Exists so that "GitHub says 403 with 'rate limit' in the body when it means
    429" lives in one file about GitHub, rather than as a branch in the generic
    adapter that every other provider then has to be checked against.

    A translator classifies and describes. It **cannot** authorize, cannot
    change the operation, cannot choose a destination and cannot decide to
    retry: it is handed a status and a decoded body and returns a classification
    and a safe message.
    """

    def classify(
        self, spec: ProviderOperationSpec, exchange: ProviderExchange, body: Any
    ) -> Optional[ProviderFailure]:
        """The failure this answer represents, or ``None`` if it succeeded."""
        ...

    def describe(self, exchange: ProviderExchange, body: Any) -> Tuple[Optional[str], Optional[str]]:
        """``(error_code, safe_message)``. Both bounded, neither a secret."""
        ...


class HttpStatusTranslator:
    """The default translator: status codes and nothing provider-specific.

    Useful on its own for a provider whose API is conventional, and the base a
    specific translator narrows. It reads no body field by name, because field
    names are exactly the part that differs between providers.
    """

    def classify(
        self, spec: ProviderOperationSpec, exchange: ProviderExchange, body: Any
    ) -> Optional[ProviderFailure]:
        status = exchange.status_code
        if status is None:
            # Delivered without a status is not a thing a real HTTP transport
            # produces; if it ever arrives, nobody can say what happened.
            return ProviderFailure.UNKNOWN_OUTCOME
        if status in spec.success_statuses:
            return None
        mapped = DEFAULT_STATUS_FAILURES.get(status)
        if mapped is not None:
            return mapped
        if 500 <= status < 600:
            return ProviderFailure.UNAVAILABLE
        if 400 <= status < 500:
            return ProviderFailure.VALIDATION_FAILURE
        # A 2xx or 3xx that the operation did not declare as success. The
        # provider answered something this operation does not define, and an
        # undefined success is not one.
        return ProviderFailure.PROTOCOL_ERROR

    def describe(
        self, exchange: ProviderExchange, body: Any
    ) -> Tuple[Optional[str], Optional[str]]:
        code = str(exchange.status_code) if exchange.status_code is not None else None
        # Deliberately no body text. A provider error message is caller-
        # influenced content that reaches logs; a specific translator that knows
        # its provider's message field can extract a bounded one.
        return code, exchange.reason


class ConnectorAdapter(AdapterSeam):
    """Performs a connector capability through a declared operation catalog."""

    WORKER_KIND = WorkerKind.CONNECTOR
    INTERFACE = WorkerInterface.CONNECTOR
    IMPLEMENTATION_VERSION = "1.0.0"

    def __init__(
        self,
        *,
        implementation: WorkerImplementation,
        provider: ProviderRef,
        catalog: Optional[OperationCatalog] = None,
        channel: Optional[ProviderChannel] = None,
        translator: Optional[ProviderResponseTranslator] = None,
        preflight: Optional[AdapterPreflight] = None,
        metrics: Optional[Any] = None,
    ) -> None:
        if catalog is not None and catalog.provider_id != provider.provider_id:
            raise ContractViolation(
                f"the catalog describes {catalog.provider_id!r} but this adapter "
                f"serves {provider.provider_id!r}; an adapter using another "
                "provider's operation declarations would build the wrong request "
                "for the right authority"
            )
        if channel is not None and not channel.provider.matches(provider.provider_id):
            raise ContractViolation(
                "the channel reaches a different provider than this adapter serves"
            )
        super().__init__(
            implementation=implementation,
            provider=provider,
            # The channel *is* the transport for a connector. With none
            # attached the seam refuses having sent nothing, which is the
            # correct answer for a provider nobody can reach.
            invoker=channel,
            preflight=preflight,
            metrics=metrics,
        )
        self._catalog = catalog
        self._channel = channel
        self._translator = translator or HttpStatusTranslator()

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def catalog(self) -> Optional[OperationCatalog]:
        return self._catalog

    def supports_operation(self, operation: str) -> bool:
        """Exact catalog membership. No prefix and no closest match."""
        return self._catalog is not None and operation in self._catalog

    def describe(self) -> dict:
        return {
            "adapter": self.adapter.value,
            "provider": self.provider.value,
            "operations": list(self._catalog.operations) if self._catalog else [],
            "catalog_digest": self._catalog.digest if self._catalog else None,
            "endpoint": (
                self._channel.base_endpoint.normalised if self._channel else None
            ),
            "translator": type(self._translator).__name__,
        }

    # ------------------------------------------------------------------
    # The provider call
    # ------------------------------------------------------------------

    def _perform(
        self,
        context: Any,
        request: WorkerExecutionRequest,
        authority: ProviderAuthority,
    ) -> ProviderOutcome:
        if self._catalog is None or self._channel is None:
            return ProviderOutcome.refused(
                ProviderFailure.ADAPTER_UNAVAILABLE,
                "this connector adapter has no operation catalog or no channel; "
                "nothing was sent",
            )

        try:
            spec = self._catalog.require(authority.operation)
        except UnknownOperation as unknown:
            return ProviderOutcome.refused(
                ProviderFailure.OPERATION_NOT_SUPPORTED, str(unknown)[:400]
            )

        # 1. Does the declaration still agree with what was authorized? The
        #    contract drift check (§16, §54). Refused, never accommodated.
        drift = spec.contract_refusals(authority.binding)
        if drift:
            return ProviderOutcome.refused(
                ProviderFailure.CONTRACT_MISMATCH, "; ".join(drift)[:400]
            )

        # 2. Input, against the operation's own declaration. Before the request
        #    is built and before anything is sent, so malformed input never
        #    causes provider communication.
        problems = spec.input_problems(authority.payload)
        if problems:
            return ProviderOutcome.refused(
                ProviderFailure.VALIDATION_FAILURE, "; ".join(problems)[:400]
            )

        # 3. The request. Deterministic: the same authority builds the same one.
        try:
            plan = spec.plan(
                authority.payload,
                # Execution's key. Passed only where the provider declares it
                # reads one -- sending it to a provider that ignores it would be
                # a key that did nothing while looking like protection.
                idempotency_key=authority.idempotency_key,
            )
        except ContractViolation as refusal:
            return ProviderOutcome.refused(
                ProviderFailure.VALIDATION_FAILURE, str(refusal)[:400]
            )

        exchange = self._channel.send(
            authority,
            plan,
            provider_timeout_seconds=spec.provider_timeout_seconds,
            max_response_bytes=spec.max_response_bytes,
        )
        return self._normalise(spec, authority, exchange)

    # ------------------------------------------------------------------
    # Normalisation
    # ------------------------------------------------------------------

    def _normalise(
        self,
        spec: ProviderOperationSpec,
        authority: ProviderAuthority,
        exchange: ProviderExchange,
    ) -> ProviderOutcome:
        """Turn one exchange into a provider-neutral outcome.

        The order matters. Delivery is settled first, because an undelivered
        request cannot be a success whatever its status says. Then the body is
        decoded, then the status is classified, then the *shape* of the answer is
        checked — and only an answer that survives all four is a success.
        """
        common = {
            "status_code": exchange.status_code,
            "response_digest": exchange.response_digest,
            "retry_after_seconds": exchange.retry_after_seconds,
            "provider_request_id": exchange.provider_request_id,
            "metadata": exchange.metadata(),
            "delivery": exchange.delivery,
        }

        # -- transport-level refusals and ambiguity ---------------------
        if exchange.delivery is not ProviderDelivery.DELIVERED:
            failure = exchange.failure or (
                ProviderFailure.UNKNOWN_OUTCOME
                if exchange.delivery is ProviderDelivery.UNKNOWN
                else ProviderFailure.TRANSPORT_REFUSED
            )
            return ProviderOutcome(
                ambiguous=exchange.delivery is ProviderDelivery.UNKNOWN,
                provider_failure=failure,
                error_message=(
                    exchange.reason
                    or "the operation did not reach the provider, or nobody can say"
                ),
                **common,
            )

        # -- the body -----------------------------------------------------
        body, decode_problem = exchange.json()
        if decode_problem is not None:
            # Delivered and unreadable. The provider may well have applied the
            # change, so this is ambiguous rather than failed -- what is missing
            # is a trustworthy account of it.
            return ProviderOutcome(
                ambiguous=True,
                provider_failure=(
                    ProviderFailure.RESPONSE_TOO_LARGE
                    if exchange.truncated
                    else ProviderFailure.MALFORMED_RESPONSE
                ),
                error_message=decode_problem,
                **common,
            )

        # -- the provider's own verdict ---------------------------------
        failure = self._translator.classify(spec, exchange, body)
        if failure is not None:
            code, message = self._translator.describe(exchange, body)
            return ProviderOutcome(
                provider_failure=failure,
                error_code=code,
                error_message=(
                    message
                    or f"the provider refused {spec.operation!r} with "
                    f"status {exchange.status_code}"
                )[:500],
                ambiguous=failure.is_ambiguous,
                **common,
            )

        # -- the shape of the answer ------------------------------------
        shape = spec.response_problems(body)
        if shape:
            # A 200 with the wrong body is not a success. The operation is
            # defined by what it returns, and this did not return it.
            return ProviderOutcome(
                ambiguous=True,
                provider_failure=ProviderFailure.MALFORMED_RESPONSE,
                error_message="; ".join(shape)[:400],
                **common,
            )

        return ProviderOutcome(
            succeeded=True,
            output=body if isinstance(body, Mapping) else None,
            evidence=spec.evidence(body),
            # What the *catalog* declares this operation does, not what the
            # provider claims. The seam compares it against the binding, and a
            # provider-supplied effect would make that comparison circular.
            observed_effect=spec.side_effect_class,
            **common,
        )
