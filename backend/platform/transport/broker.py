"""The transport broker: the one place a destination is approved and dialled.

The order is the security property
------------------------------------
    endpoint policy → resolve → judge every address → pin
    → connection limit → adapter → outcome classification

Resolution before judgement, judgement before pinning, pinning before dialling.
An address that was not judged is never pinned, and an adapter is handed pinned
addresses rather than a hostname — which is the whole DNS-rebinding defence and
also its limit, since an adapter that re-resolves has stepped outside it.

What this is not
------------------
Not an authorization system. It has no capability, no operation, no grants and
no approval, and it cannot re-decide any of them. The invocation gateway admitted
the action before a transport request existed; this decides only whether the
*destination* is one CortexPrime may open a socket to.

Two different questions, and the confusion between them is the classic mistake:

    "may CortexPrime do this?"     answered by the gateway, already
    "is this address reachable?"   answered here

A successful TLS handshake answers neither.

No transport is implemented here
----------------------------------
There is no HTTP client, no socket connect, no TLS context. ``TransportAdapter``
is the seam a Phase 4.3 implementation occupies, and with none attached every
dial refuses with ``transport_unavailable`` — the correct behaviour for a
platform that has no transport, and the same shape the worker directory took
when it had no workers.

**No retry.** A network retry can duplicate a privileged action. Connection
establishment may be retried before any byte is written, and that bound is
expressed as ``connect_attempts`` on the adapter contract; once a request may
have been transmitted, control returns to Execution.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Optional, Protocol, runtime_checkable

from backend.contracts.errors import ContractViolation
from backend.contracts.transport import (
    ConnectionRef,
    TransportFailure,
    TransportKind,
)
from backend.platform.credentials import safe_exception_text
from backend.platform.transport.endpoint import (
    TransportEndpoint,
    UnsafeTransportEndpoint,
)
from backend.platform.transport.policy import ConnectionPolicy, PolicyRefusal
from backend.platform.transport.request import (
    TransportOutcome,
    TransportRefused,
    TransportRequest,
)
from backend.platform.transport.ssrf import (
    AddressResolver,
    ResolvedDestination,
    SystemAddressResolver,
    classify_literal,
    LOOPBACK_ALIASES,
    AddressClass,
    AddressJudgement,
)
from backend.platform.identity import monotonic_ulid

__all__ = [
    "TransportAdapter",
    "TransportBroker",
    "ConnectionSlots",
    "TRANSPORT_METRICS",
]

log = logging.getLogger(__name__)

TRANSPORT_METRICS = (
    "transport.connection.attempt",
    "transport.connection.success",
    "transport.connection.failure",
    "transport.dns.failure",
    "transport.tls.failure",
    "transport.timeout",
    "transport.ssrf.refusal",
    "transport.redirect.refusal",
    "transport.proxy.refusal",
    "transport.message.limit",
    "transport.connection.limit",
    "transport.cancelled",
)


@runtime_checkable
class TransportAdapter(Protocol):
    """A concrete transport. **Nothing implements this in Phase 4.2.**

    Receives a request whose destination has already been judged and pinned, and
    whose timeouts are already clamped to the authority window. Its job is to
    move bytes and report what it observed.

    An implementation **must**:

    - connect only to ``pinned_addresses``, never re-resolving the hostname;
    - honour every timeout in ``request.effective_timeouts``;
    - refuse to disable certificate or hostname verification, which the policy
      offers no way to express;
    - ignore ``HTTP_PROXY``-style environment variables unless
      ``policy.proxy.trust_environment`` is set;
    - stop reading at ``policy.budget.max_response_bytes`` and report
      ``truncated``;
    - report ``DeliveryState.UNKNOWN`` whenever it cannot establish that the
      request did or did not reach the provider.
    """

    @property
    def kinds(self) -> frozenset:
        """Transport kinds this adapter can carry. Explicit; no wildcard."""
        ...

    def dial(
        self,
        request: TransportRequest,
        *,
        pinned_addresses: tuple,
        connection: ConnectionRef,
    ) -> TransportOutcome: ...

    def close(self, connection: ConnectionRef) -> None:
        """Release a connection. Must be safe to call twice."""
        ...


class ConnectionSlots:
    """Bounded concurrency, keyed by tenant and provider.

    A provider that accepts connections and never answers can otherwise occupy
    every slot in the process. Keyed per tenant as well as per host so one
    tenant's misbehaving provider cannot starve another's — a fairness property
    that is also an isolation one.

    Deliberately not a connection *pool*: nothing authenticated is reused. See
    ``TransportBroker`` on why pooling is off in this phase.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counts: dict = {}

    @staticmethod
    def _key(tenant_id: str, endpoint: TransportEndpoint) -> tuple:
        return (tenant_id, endpoint.scheme, endpoint.host, endpoint.port)

    def acquire(
        self, tenant_id: str, endpoint: TransportEndpoint, *, limit: int
    ) -> bool:
        key = self._key(tenant_id, endpoint)
        with self._lock:
            current = self._counts.get(key, 0)
            if current >= limit:
                return False
            self._counts[key] = current + 1
            return True

    def release(self, tenant_id: str, endpoint: TransportEndpoint) -> None:
        key = self._key(tenant_id, endpoint)
        with self._lock:
            current = self._counts.get(key, 0)
            if current <= 1:
                self._counts.pop(key, None)
            else:
                self._counts[key] = current - 1

    def in_use(self, tenant_id: str, endpoint: TransportEndpoint) -> int:
        with self._lock:
            return self._counts.get(self._key(tenant_id, endpoint), 0)


class TransportBroker:
    """Approves a destination and hands it to an adapter. Refuses otherwise."""

    def __init__(
        self,
        *,
        adapters: Optional[Mapping[TransportKind, TransportAdapter]] = None,
        resolver: Optional[AddressResolver] = None,
        slots: Optional[ConnectionSlots] = None,
        audit: Optional[Any] = None,
        metrics: Optional[Any] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._adapters: dict = dict(adapters or {})
        self._resolver = resolver or SystemAddressResolver()
        self._slots = slots or ConnectionSlots()
        self._audit = audit
        self._metrics = metrics
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, adapter: TransportAdapter) -> None:
        """Attach a transport. Explicit, and never silently replaced."""
        kinds = adapter.kinds
        if not kinds:
            raise ContractViolation(
                "a transport adapter must declare which kinds it carries; an "
                "adapter for nothing would either never be selected or -- read as "
                "'anything' -- carry MCP over a client written for plain HTTP"
            )
        for kind in kinds:
            if not isinstance(kind, TransportKind):
                raise ContractViolation("kinds must contain TransportKind values")
            if kind in self._adapters:
                raise ContractViolation(
                    f"an adapter for {kind.value} is already registered; replacing "
                    "one silently would change how bytes move without anybody "
                    "deciding"
                )
        for kind in kinds:
            self._adapters[kind] = adapter

    @property
    def kinds(self) -> tuple:
        return tuple(sorted(k.value for k in self._adapters))

    # ------------------------------------------------------------------
    # The gate
    # ------------------------------------------------------------------

    def approve(self, request: TransportRequest) -> ResolvedDestination:
        """Everything that must hold before a socket exists. Returns the pinning.

        Public so a caller can validate a destination without dialling it —
        useful for configuration checking, and it performs no I/O beyond DNS.
        """
        if not isinstance(request, TransportRequest):
            raise ContractViolation("approve takes a TransportRequest")
        policy = request.policy
        endpoint = request.endpoint

        # 1. The endpoint itself: scheme, plaintext, environment, size.
        refusals = policy.judge_endpoint(endpoint)
        if refusals:
            raise self._refuse_policy(request, refusals[0], refusals)

        # 2. The authority window, before anything is opened.
        if request.authority_seconds_remaining is not None:
            if request.authority_seconds_remaining <= 0:
                raise self._refuse(
                    request,
                    TransportFailure.POLICY_REFUSED,
                    "no authority window remains; a connection opened now would "
                    "outlive the permission for it",
                )

        # 3. Resolve and judge. A literal address needs no lookup; a name does,
        #    and every answer it gives is judged, not the first.
        destination = self._resolve(request)
        address_refusals = policy.judge_destination(destination)
        if address_refusals:
            self._count("transport.ssrf.refusal", request)
            first = address_refusals[0]
            raise self._refuse(
                request,
                first.failure,
                first.reason,
                detail={
                    "host": destination.host,
                    "classes": sorted(
                        {j.address_class.value for j in destination.judgements}
                    ),
                },
            )
        return destination

    def _resolve(self, request: TransportRequest) -> ResolvedDestination:
        """Turn the host into judged addresses. The only network call here."""
        host = request.endpoint.host
        policy = request.policy

        # A literal address is already the destination -- resolving it would be
        # a lookup that cannot change the answer.
        literal = classify_literal(host)
        if literal is not None:
            return ResolvedDestination(
                host=host,
                judgements=(literal,),
                pinned_addresses=(literal.address,),
                refused=(),
                resolved=False,
            )

        # Names that mean "this machine" without being an address. Caught before
        # resolution so a resolver that answers oddly cannot matter.
        if host in LOOPBACK_ALIASES:
            judgement = AddressJudgement(
                address=host,
                address_class=AddressClass.LOOPBACK,
                family=0,
            )
            return ResolvedDestination(
                host=host,
                judgements=(judgement,),
                pinned_addresses=(),
                refused=(judgement,),
                resolved=False,
            )

        if not policy.require_dns_resolution:
            # Explicitly configured off. The destination is unjudged, so it is
            # refused rather than assumed public -- turning resolution off means
            # something else does the checking, and this fabric cannot see it.
            raise self._refuse(
                request,
                TransportFailure.SSRF_REFUSED,
                "this policy does not resolve hostnames, so this destination "
                "cannot be judged; only literal addresses may be dialled",
                detail={"host": host},
            )

        timeouts = request.effective_timeouts
        try:
            addresses = self._resolver.resolve(
                host, request.endpoint.port, timeout_seconds=timeouts.dns_seconds
            )
        except Exception as exc:  # noqa: BLE001 - unresolvable is unreachable
            self._count("transport.dns.failure", request)
            raise self._refuse(
                request,
                TransportFailure.DNS_FAILURE,
                f"the host could not be resolved ({type(exc).__name__})",
                detail={"host": host},
            ) from None

        judgements: list = []
        approved: list = []
        refused: list = []
        for address in addresses:
            judgement = classify_literal(address)
            if judgement is None:
                # A resolver answer that is not an address. Refused rather than
                # skipped: something is wrong and proceeding on the remainder
                # would hide it.
                raise self._refuse(
                    request,
                    TransportFailure.DNS_FAILURE,
                    "the resolver returned something that is not an address",
                    detail={"host": host},
                )
            judgements.append(judgement)
            if request.policy.judge_address(judgement) is None:
                approved.append(judgement.address)
            else:
                refused.append(judgement)

        return ResolvedDestination(
            host=host,
            judgements=tuple(judgements),
            # Empty when anything was refused: partial approval of a
            # multi-answer host is how a rebind wins on the second attempt.
            pinned_addresses=tuple(approved) if not refused else (),
            refused=tuple(refused),
            resolved=True,
        )

    # ------------------------------------------------------------------
    # Dialling
    # ------------------------------------------------------------------

    def dial(self, request: TransportRequest) -> TransportOutcome:
        """Approve, then hand to an adapter exactly once. Never retries."""
        started = self._clock()
        self._count("transport.connection.attempt", request)

        destination = self.approve(request)

        adapter = self._adapters.get(request.endpoint.transport)
        if adapter is None:
            # No transport in this deployment. Correct for Phase 4.2, and
            # correct in general: there is no default transport and no fallback.
            raise self._refuse(
                request,
                TransportFailure.TRANSPORT_UNAVAILABLE,
                f"no transport adapter is registered for "
                f"{request.endpoint.transport.value}",
            )

        limit = request.policy.budget.max_concurrent_connections
        if not self._slots.acquire(request.tenant_id, request.endpoint, limit=limit):
            self._count("transport.connection.limit", request)
            raise self._refuse(
                request,
                TransportFailure.CONNECTION_LIMIT,
                f"this tenant already holds {limit} connections to this endpoint",
            )

        connection = ConnectionRef(
            tenant_id=request.tenant_id,
            kind=request.endpoint.transport,
            connection_id=monotonic_ulid(),
        )
        try:
            outcome = adapter.dial(
                request,
                pinned_addresses=destination.pinned_addresses,
                connection=connection,
            )
        except TransportRefused:
            raise
        except Exception as exc:  # noqa: BLE001
            # An adapter that raised mid-dial cannot say whether anything was
            # written. UNKNOWN is the only honest answer, and never str(exc):
            # an HTTP client's exception carries the request it was making.
            log.warning("transport adapter failed: %s", safe_exception_text(exc))
            self._count("transport.connection.failure", request)
            return TransportOutcome.unknown(
                f"the transport adapter raised ({type(exc).__name__}); whether the "
                "request reached the provider is unknown",
                connection=connection,
                duration_seconds=self._elapsed(started),
                resolved_addresses=destination.pinned_addresses,
            )
        finally:
            self._slots.release(request.tenant_id, request.endpoint)

        outcome = self._check_outcome(outcome, connection, destination, started)
        self._record(request, outcome, destination)
        self._count(
            "transport.connection.success"
            if outcome.succeeded
            else "transport.connection.failure",
            request,
        )
        return outcome

    def _check_outcome(
        self,
        outcome: Any,
        connection: ConnectionRef,
        destination: ResolvedDestination,
        started: datetime,
    ) -> TransportOutcome:
        """An adapter's answer must be interpretable. Otherwise it is unknown."""
        if not isinstance(outcome, TransportOutcome):
            return TransportOutcome.unknown(
                f"the adapter returned {type(outcome).__name__}, not a "
                "TransportOutcome; what it did is unknown",
                connection=connection,
                duration_seconds=self._elapsed(started),
                resolved_addresses=destination.pinned_addresses,
            )
        from dataclasses import replace

        # The connection reference and the resolved addresses are the broker's
        # to state -- an adapter reporting a different destination than the one
        # that was pinned would make the audit record describe a request that
        # was not the one approved.
        return replace(
            outcome,
            connection=connection,
            resolved_addresses=destination.pinned_addresses,
            duration_seconds=outcome.duration_seconds or self._elapsed(started),
        )

    # ------------------------------------------------------------------
    # Redirects
    # ------------------------------------------------------------------

    def approve_redirect(
        self,
        request: TransportRequest,
        location: str,
        *,
        hop: int,
    ) -> tuple:
        """Judge a redirect target. Returns ``(endpoint, credentials_may_follow)``.

        The target goes through the **whole** endpoint and address judgement
        again. A redirect that was not re-validated is a destination nobody
        checked, and it is the easiest SSRF bypass there is: a provider answers
        302 to ``http://169.254.169.254/`` and a client that follows blindly
        fetches instance credentials.
        """
        origin = request.endpoint
        try:
            target = TransportEndpoint.parse(
                location,
                transport=origin.transport,
                environment=origin.environment,
            )
        except UnsafeTransportEndpoint as exc:
            self._count("transport.redirect.refusal", request)
            raise self._refuse(
                request,
                TransportFailure.REDIRECT_REFUSED,
                f"the redirect target is not a dialable endpoint: {exc.reason}",
            ) from None

        refusals = request.policy.judge_redirect(origin, target, hop)
        if refusals:
            self._count("transport.redirect.refusal", request)
            raise self._refuse(
                request, refusals[0].failure, refusals[0].reason
            )

        # Re-resolve and re-judge the new host. Same rules, no exceptions.
        probe = _with_endpoint(request, target)
        self.approve(probe)

        return target, ConnectionPolicy.credentials_may_follow(origin, target)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _elapsed(self, started: datetime) -> float:
        return max(0.0, (self._clock() - started).total_seconds())

    def _refuse(
        self,
        request: TransportRequest,
        failure: TransportFailure,
        message: str,
        *,
        detail: Optional[Mapping[str, Any]] = None,
    ) -> TransportRefused:
        self._record_refusal(request, failure, message)
        return TransportRefused(
            failure,
            message,
            correlation_id=request.correlation_id,
            detail=dict(detail or {}),
        )

    def _refuse_policy(
        self,
        request: TransportRequest,
        first: PolicyRefusal,
        refusals: tuple,
    ) -> TransportRefused:
        return self._refuse(
            request,
            first.failure,
            first.reason,
            detail={"refusals": [r.to_dict() for r in refusals]},
        )

    # -- audit and metrics ------------------------------------------------

    def _record(
        self,
        request: TransportRequest,
        outcome: TransportOutcome,
        destination: ResolvedDestination,
    ) -> None:
        if self._audit is None:
            return
        from backend.contracts.audit import AuditEventKind

        self._safe_audit(
            AuditEventKind.CONNECTOR_OPERATION,
            subject_reference=request.endpoint.normalised,
            detail={**request.to_dict(), **outcome.to_dict()},
        )

    def _record_refusal(
        self, request: TransportRequest, failure: TransportFailure, message: str
    ) -> None:
        if self._audit is None:
            return
        from backend.contracts.audit import AuditEventKind

        self._safe_audit(
            AuditEventKind.EXECUTION_REFUSED,
            subject_reference=request.endpoint.normalised,
            detail={
                **request.to_dict(),
                "failure": failure.value,
                "reason": message,
                "security_relevant": failure.is_security_relevant,
            },
        )

    def _safe_audit(self, kind: Any, **fields: Any) -> None:
        """Audit failure can never turn a refusal into an allow."""
        try:
            self._audit.record(kind, **fields)
        except Exception:  # noqa: BLE001
            log.error("recording a transport audit fact failed", exc_info=False)

    def _count(self, name: str, request: TransportRequest) -> None:
        """Labels carry tenant, transport and host. **Never a full URL**.

        A query string routinely carries a token or a signature, so the URL is
        the one field that must not become a metric dimension.
        """
        if self._metrics is None:
            return
        try:
            self._metrics.increment(
                name,
                labels={
                    "tenant": request.tenant_id,
                    "transport": request.endpoint.transport.value,
                    "host": request.endpoint.host,
                    "environment": request.endpoint.environment.value,
                },
            )
        except Exception:  # noqa: BLE001 - measurement never changes an outcome
            log.debug("transport metric failed", exc_info=False)


def _with_endpoint(
    request: TransportRequest, endpoint: TransportEndpoint
) -> TransportRequest:
    """A copy of a request aimed at a different endpoint, for redirect judging.

    Credentials are dropped. This copy exists only to run the address policy, and
    a copy carrying material would be one more object holding a secret for no
    reason.
    """
    from dataclasses import replace

    return replace(request, endpoint=endpoint, credential=None)
