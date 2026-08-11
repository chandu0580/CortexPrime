"""The one way an adapter reaches a provider: through the Phase 4.2 broker.

Why a channel and not a client
--------------------------------
Every adapter needs the same six things — an endpoint, a policy, a credential
handed to transport rather than into a header, timeouts clamped to the authority
window, one attempt, and a classified answer. Written per adapter, the sixth one
is where they start to differ, and the differences are all in the direction of
"treat this ambiguous thing as a failure so the retry works".

So it is written once. An adapter composes a ``ProviderRequestPlan`` and hands it
here; what comes back is a ``ProviderExchange``, which is facts.

What this cannot do, structurally
-----------------------------------
**It cannot dial anything.** It holds a ``TransportBroker`` and no HTTP client,
no socket and no TLS context; there is no import in this module that could open
a connection. Address policy, SSRF judgement, DNS pinning, redirect rules and
resource budgets all happen inside the broker, on the far side of one method
call.

**It cannot set an ``Authorization`` header.** Credential material is passed as
``TransportRequest.credential`` and the header is produced at the transport
boundary. Caller headers go through ``validate_caller_headers``, which refuses
the credential-bearing names outright, so an adapter that tried would get a
refusal rather than a request (ADR-042 §57).

**It cannot retry.** One ``dial``, one answer. A network retry can duplicate a
privileged action, and whether repeating is safe is a question about the
binding's effect semantics that Execution answers (ADR-031).

**It cannot pick a destination.** The base endpoint is fixed at construction from
deployment configuration; a plan contributes a path built from a declared
template and validated parameters. There is no argument here that takes a URL.

The timeout is the smallest of everything that applies
--------------------------------------------------------
``min(provider limit, transport limit, remaining authority)`` — ADR-042 §23.
Clamping happens through ``TransportRequest.authority_seconds_remaining``, which
the broker already applies to every phase, so there is no second timeout regime
to keep in step with the first.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Tuple
from urllib.parse import quote, urlencode

from backend.contracts.errors import ContractViolation
from backend.contracts.provider import ProviderDelivery, ProviderFailure, ProviderRef
from backend.contracts.transport import TransportFailure, TransportKind
from backend.contexts.execution.domain.provider_invocation import ProviderAuthority
from backend.contexts.execution.domain.provider_operation import ProviderRequestPlan
from backend.platform.hashing import canonical_bytes, compute_digest
from backend.platform.transport import (
    ConnectionPolicy,
    DeliveryState,
    TransportBroker,
    TransportEndpoint,
    TransportOutcome,
    TransportRefused,
    TransportRequest,
    validate_caller_headers,
)

__all__ = [
    "ProviderChannel",
    "ProviderExchange",
    "TRANSPORT_FAILURE_MAP",
    "RATE_LIMIT_HEADERS",
]

log = logging.getLogger(__name__)

#: Response headers an adapter may read. A short allow-list rather than a filter
#: over everything: a provider controls its own header names, and "read whatever
#: looks like a request id" is how an unexpected header ends up in an audit
#: record. ``TransportOutcome`` already refuses the credential-bearing names, so
#: this is the second of two independent bounds rather than the only one.
RATE_LIMIT_HEADERS = (
    "retry-after",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
    "x-ratelimit-limit",
    "x-request-id",
    "x-github-request-id",
    "mcp-session-id",
)

#: Phase 4.2's transport vocabulary projected onto the provider-neutral one.
#: Every entry preserves ambiguity: a transport failure that might have been
#: delivered maps to something ``is_ambiguous``, never to a definite refusal.
TRANSPORT_FAILURE_MAP: Mapping[TransportFailure, ProviderFailure] = {
    TransportFailure.DNS_FAILURE: ProviderFailure.UNAVAILABLE,
    TransportFailure.DNS_TIMEOUT: ProviderFailure.UNAVAILABLE,
    TransportFailure.CONNECTION_REFUSED: ProviderFailure.UNAVAILABLE,
    TransportFailure.NETWORK_UNREACHABLE: ProviderFailure.UNAVAILABLE,
    TransportFailure.CONNECTION_RESET: ProviderFailure.UNKNOWN_OUTCOME,
    TransportFailure.TLS_FAILURE: ProviderFailure.TRANSPORT_REFUSED,
    TransportFailure.CERTIFICATE_INVALID: ProviderFailure.TRANSPORT_REFUSED,
    TransportFailure.HOSTNAME_MISMATCH: ProviderFailure.TRANSPORT_REFUSED,
    TransportFailure.TLS_DOWNGRADE_REFUSED: ProviderFailure.TRANSPORT_REFUSED,
    TransportFailure.TLS_TIMEOUT: ProviderFailure.TRANSPORT_REFUSED,
    TransportFailure.SSRF_REFUSED: ProviderFailure.TRANSPORT_REFUSED,
    TransportFailure.REDIRECT_REFUSED: ProviderFailure.TRANSPORT_REFUSED,
    TransportFailure.PROXY_REFUSED: ProviderFailure.TRANSPORT_REFUSED,
    TransportFailure.SCHEME_REFUSED: ProviderFailure.TRANSPORT_REFUSED,
    TransportFailure.ENDPOINT_REFUSED: ProviderFailure.TRANSPORT_REFUSED,
    TransportFailure.ENVIRONMENT_MISMATCH: ProviderFailure.TRANSPORT_REFUSED,
    TransportFailure.TENANT_MISMATCH: ProviderFailure.TRANSPORT_REFUSED,
    TransportFailure.POLICY_REFUSED: ProviderFailure.TRANSPORT_REFUSED,
    TransportFailure.MESSAGE_TOO_LARGE: ProviderFailure.RESPONSE_TOO_LARGE,
    TransportFailure.HEADERS_TOO_LARGE: ProviderFailure.RESPONSE_TOO_LARGE,
    TransportFailure.REQUEST_TOO_LARGE: ProviderFailure.VALIDATION_FAILURE,
    TransportFailure.CONNECTION_LIMIT: ProviderFailure.UNAVAILABLE,
    TransportFailure.STREAM_DURATION_EXCEEDED: ProviderFailure.TIMEOUT,
    TransportFailure.CONNECT_TIMEOUT: ProviderFailure.UNAVAILABLE,
    TransportFailure.READ_TIMEOUT: ProviderFailure.TIMEOUT,
    TransportFailure.IDLE_TIMEOUT: ProviderFailure.TIMEOUT,
    TransportFailure.CANCELLED: ProviderFailure.CANCELLED,
    TransportFailure.PROTOCOL_ERROR: ProviderFailure.PROTOCOL_ERROR,
    TransportFailure.CREDENTIAL_REFUSED: ProviderFailure.CREDENTIAL_REFUSED,
    TransportFailure.TRANSPORT_UNAVAILABLE: ProviderFailure.ADAPTER_UNAVAILABLE,
    TransportFailure.UNKNOWN_STATE: ProviderFailure.UNKNOWN_OUTCOME,
}

_MAX_DECODE_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True)
class ProviderExchange:
    """One completed provider exchange, as facts. Nothing here is a decision."""

    delivery: ProviderDelivery
    status_code: Optional[int] = None
    failure: Optional[ProviderFailure] = None
    reason: Optional[str] = None
    truncated: bool = False

    body: Optional[bytes] = field(default=None, repr=False, compare=False)
    """The raw answer, bounded by the transport budget. Held only long enough to
    be decoded and digested; never placed in a result, an event or an audit
    record — what survives is ``response_digest`` and the operation's declared
    evidence fields."""

    response_digest: Optional[str] = None
    headers: Mapping[str, str] = field(default_factory=dict)
    """Only the names in ``RATE_LIMIT_HEADERS``. Everything else is dropped
    before this object exists."""

    duration_seconds: float = 0.0
    connection_ref: Optional[str] = None

    @property
    def delivered(self) -> bool:
        return self.delivery is ProviderDelivery.DELIVERED

    @property
    def retry_after_seconds(self) -> Optional[float]:
        """What the provider said about coming back. **A fact, not a plan.**

        Nothing in this fabric sleeps on it. It is returned so Execution's
        recovery can decide whether another attempt is safe — which is a
        different question from whether the provider would accept one.
        """
        raw = self.headers.get("retry-after")
        if raw is None:
            return None
        try:
            # The delta-seconds form. The HTTP-date form is deliberately not
            # parsed: it needs a clock this layer does not own, and a
            # mis-parsed date is a worse answer than no answer.
            seconds = float(raw.strip())
        except (TypeError, ValueError):
            return None
        return seconds if seconds >= 0 else None

    @property
    def provider_request_id(self) -> Optional[str]:
        for name in ("x-github-request-id", "x-request-id"):
            value = self.headers.get(name)
            if value:
                return value[:128]
        return None

    def json(self) -> Tuple[Optional[Any], Optional[str]]:
        """Decode the body as JSON. Returns ``(value, problem)``; never raises.

        A truncated body is refused before parsing. Half a JSON document
        sometimes parses — an array cut after a complete element is still valid
        JSON — and a partial answer that parses cleanly is precisely the shape a
        provider could use to make an incomplete result look whole.
        """
        if self.truncated:
            return None, (
                "the response hit the transport budget and was truncated; a "
                "partial answer that parses is still a partial answer"
            )
        if self.body is None:
            return None, "no response body was returned"
        if not self.body.strip():
            return None, None  # A deliberate empty body, e.g. HTTP 204.
        if len(self.body) > _MAX_DECODE_BYTES:
            return None, "the response is too large to decode"
        try:
            return json.loads(self.body.decode("utf-8")), None
        except UnicodeDecodeError:
            return None, "the response is not valid UTF-8"
        except json.JSONDecodeError:
            return None, "the response is not valid JSON"

    def metadata(self) -> dict:
        """Non-sensitive facts for the outcome's detail. No body, ever."""
        facts: dict = {}
        for name in ("x-ratelimit-remaining", "x-ratelimit-limit", "x-ratelimit-reset"):
            if name in self.headers:
                facts[name.replace("-", "_")] = self.headers[name][:64]
        if self.truncated:
            facts["response_truncated"] = True
        if self.connection_ref:
            facts["connection"] = self.connection_ref
        return facts


class ProviderChannel:
    """An adapter's only route to a provider. Holds a broker, never a client."""

    def __init__(
        self,
        *,
        provider: ProviderRef,
        broker: TransportBroker,
        base_endpoint: TransportEndpoint,
        policy: ConnectionPolicy,
        transport: TransportKind = TransportKind.HTTPS,
    ) -> None:
        if not isinstance(provider, ProviderRef):
            raise ContractViolation("a channel must name the provider it reaches")
        if not isinstance(broker, TransportBroker):
            raise ContractViolation(
                "a provider channel reaches the network through the Phase 4.2 "
                "broker and through nothing else; without it there is no address "
                "policy, no pinning and no budget"
            )
        if not isinstance(base_endpoint, TransportEndpoint):
            raise ContractViolation("base_endpoint must be a TransportEndpoint")
        if not isinstance(policy, ConnectionPolicy):
            raise ContractViolation("policy must be a ConnectionPolicy")
        if base_endpoint.environment is not policy.environment:
            raise ContractViolation(
                "the endpoint and the policy name different environments; one of "
                "them is for a deployment this channel is not part of"
            )
        if base_endpoint.transport is not transport:
            raise ContractViolation(
                "the base endpoint and the declared transport kind disagree"
            )
        self._provider = provider
        self._broker = broker
        self._base = base_endpoint
        self._policy = policy
        self._transport = transport

    @property
    def provider(self) -> ProviderRef:
        return self._provider

    @property
    def base_endpoint(self) -> TransportEndpoint:
        return self._base

    # ------------------------------------------------------------------
    # The exchange
    # ------------------------------------------------------------------

    def send(
        self,
        authority: ProviderAuthority,
        plan: ProviderRequestPlan,
        *,
        provider_timeout_seconds: Optional[float] = None,
        max_response_bytes: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> ProviderExchange:
        """Dial once and classify. Never retries and never re-resolves."""
        moment = now or datetime.now(timezone.utc)

        if authority.cancelled:
            # Checked here as well as in the seam: the seam checked before
            # ``_perform`` and an adapter may do work in between.
            return ProviderExchange(
                delivery=ProviderDelivery.NOT_ATTEMPTED,
                failure=ProviderFailure.CANCELLED,
                reason="the invocation was cancelled before anything was sent",
            )

        window = authority.timeout_seconds(
            provider_timeout_seconds,
            self._policy.timeouts.total_seconds,
            now=moment,
        )
        if window <= 0:
            return ProviderExchange(
                delivery=ProviderDelivery.NOT_ATTEMPTED,
                failure=ProviderFailure.TRANSPORT_REFUSED,
                reason=(
                    "no authority window remains; a provider call started now "
                    "would outlive the permission for it"
                ),
            )

        try:
            endpoint = self._endpoint_for(plan)
            headers = self._headers_for(plan)
            body = self._body_for(plan)
        except ContractViolation as refusal:
            # A plan this channel will not send. Nothing left the process, so
            # this is a definite refusal rather than an ambiguous one.
            return ProviderExchange(
                delivery=ProviderDelivery.NOT_ATTEMPTED,
                failure=ProviderFailure.VALIDATION_FAILURE,
                reason=str(refusal)[:400],
            )

        policy = self._policy
        if max_response_bytes is not None:
            from dataclasses import replace

            # Narrowed, never widened: an operation may ask for a smaller
            # response budget than the deployment allows and may not ask for a
            # larger one, because the deployment's number is the one somebody
            # sized the process against.
            budget = replace(
                policy.budget,
                max_response_bytes=min(
                    policy.budget.max_response_bytes, max_response_bytes
                ),
            )
            policy = replace(policy, budget=budget)

        request = TransportRequest(
            endpoint=endpoint,
            policy=policy,
            tenant_id=authority.tenant_id,
            principal=authority.principal,
            on_behalf_of=authority.on_behalf_of,
            method=plan.method,
            headers=headers,
            body=body,
            execution_id=authority.execution_id,
            node_id=authority.node_id,
            attempt_id=authority.attempt_id,
            correlation_id=authority.correlation_id,
            causation_id=authority.causation_id,
            # Execution's key, passed through untouched. The channel never mints
            # one and never varies it per attempt.
            idempotency_key=authority.idempotency_key,
            authority_seconds_remaining=window,
            # The credential goes to transport, which produces the header. It is
            # never assembled into ``headers`` above -- that map is validated
            # against the forbidden-name list and would refuse it.
            credential=authority.credential_material,
        )

        try:
            outcome = self._broker.dial(request)
        except TransportRefused as refused:
            return ProviderExchange(
                delivery=(
                    ProviderDelivery.NOT_ATTEMPTED
                    if refused.delivery is DeliveryState.NOT_DELIVERED
                    else ProviderDelivery.UNKNOWN
                ),
                failure=TRANSPORT_FAILURE_MAP.get(
                    refused.failure, ProviderFailure.UNKNOWN_OUTCOME
                ),
                reason=refused.safe_message[:400],
            )
        except Exception as exc:  # noqa: BLE001 - unclassifiable is never failure
            from backend.platform.credentials import safe_exception_text

            log.warning(
                "the transport broker raised for %s: %s",
                self._provider.provider_id,
                safe_exception_text(exc),
            )
            return ProviderExchange(
                delivery=ProviderDelivery.UNKNOWN,
                failure=ProviderFailure.UNKNOWN_OUTCOME,
                reason=(
                    f"the transport raised ({type(exc).__name__}); whether the "
                    "operation reached the provider is unknown"
                ),
            )

        return self._classify(outcome)

    # ------------------------------------------------------------------
    # Request construction
    # ------------------------------------------------------------------

    def _endpoint_for(self, plan: ProviderRequestPlan) -> TransportEndpoint:
        """Compose the base endpoint with the plan's path. Never a whole URL.

        The scheme, host and port come from deployment configuration and cannot
        be influenced by a plan; only the path and query can, and both were
        built from a declared template and validated parameters. That is the
        structural reason there is no arbitrary-destination path here.
        """
        from dataclasses import replace

        if not plan.path.startswith("/"):
            raise ContractViolation("a provider request path must be absolute")
        if "://" in plan.path or plan.path.startswith("//"):
            # A path that is really a URL would be a destination the endpoint
            # policy never judged.
            raise ContractViolation(
                "a provider request path may not contain an authority; the "
                "destination is deployment configuration, not request input"
            )
        base_path = self._base.path.rstrip("/")
        # Path segments were validated as ``RESOURCE_SEGMENT`` before they got
        # here; percent-encoding is belt and braces for the characters that are
        # legal in an identifier and special in a URL.
        segments = [quote(part, safe="") for part in plan.path.split("/") if part]
        path = base_path + "/" + "/".join(segments) if segments else (base_path or "/")
        query = urlencode(sorted(plan.query.items())) if plan.query else ""
        return replace(self._base, path=path or "/", query=query)

    def _headers_for(self, plan: ProviderRequestPlan) -> Mapping[str, str]:
        """Validate the adapter's declared headers. Refuses the credential names.

        Runs the Phase 4.2 validator rather than a private check, so
        ``Authorization``, ``Cookie``, framing and forwarding headers are refused
        by the same list the transport enforces — one list, checked twice, and no
        second opinion about what is forbidden.
        """
        headers = dict(plan.headers)
        if plan.body is not None:
            headers.setdefault("content-type", "application/json")
        headers.setdefault("accept", "application/json")
        return validate_caller_headers(
            headers,
            max_count=self._policy.budget.max_header_count,
            max_total_bytes=self._policy.budget.max_header_bytes,
        )

    @staticmethod
    def _body_for(plan: ProviderRequestPlan) -> Optional[bytes]:
        """Canonical bytes, so the same plan always produces the same request.

        ``canonical_bytes`` rather than ``json.dumps``: key order, float
        formatting and escaping are all fixed, which is what makes "same
        binding, same input, same request" true rather than usually true
        (ADR-042 §55).
        """
        if plan.body is None:
            return None
        return canonical_bytes(dict(plan.body))

    # ------------------------------------------------------------------
    # Classification
    # ------------------------------------------------------------------

    def _classify(self, outcome: TransportOutcome) -> ProviderExchange:
        """Turn a transport outcome into provider-neutral facts.

        The only interesting rule: ``DeliveryState.UNKNOWN`` stays unknown. A
        transport that cannot say whether bytes arrived has told us the one thing
        that matters, and translating it into a definite answer here would undo
        the whole reason Phase 4.2 models three delivery states.
        """
        headers = {
            name: value
            for name, value in outcome.response_headers.items()
            if name in RATE_LIMIT_HEADERS
        }
        delivery = {
            DeliveryState.DELIVERED: ProviderDelivery.DELIVERED,
            DeliveryState.NOT_DELIVERED: ProviderDelivery.NOT_ATTEMPTED,
            DeliveryState.UNKNOWN: ProviderDelivery.UNKNOWN,
        }[outcome.delivery]

        failure = (
            TRANSPORT_FAILURE_MAP.get(outcome.failure, ProviderFailure.UNKNOWN_OUTCOME)
            if outcome.failure is not None
            else None
        )
        if outcome.truncated and failure is None:
            # A truncated body is not a transport failure -- the transport did
            # exactly what its budget says. It is a *provider* problem: the
            # answer cannot be validated, so it cannot be a success.
            failure = ProviderFailure.RESPONSE_TOO_LARGE

        return ProviderExchange(
            delivery=delivery,
            status_code=outcome.status_code,
            failure=failure,
            reason=(outcome.reason or None),
            truncated=outcome.truncated,
            body=outcome.body,
            response_digest=(
                compute_digest({"body_sha": _body_fingerprint(outcome.body)}).value
                if outcome.body is not None
                else None
            ),
            headers=headers,
            duration_seconds=outcome.duration_seconds,
            connection_ref=outcome.connection.value if outcome.connection else None,
        )


def _body_fingerprint(body: Optional[bytes]) -> str:
    """A hash of the raw answer, so two responses can be compared without either
    being stored. Hashing the bytes rather than a parsed form on purpose: the
    parse is where information is lost, and evidence should describe what
    actually arrived."""
    import hashlib

    return hashlib.sha256(body or b"").hexdigest()
