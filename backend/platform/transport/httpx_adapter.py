"""The first production transport. One client, pinned addresses, no defaults.

Where it sits
---------------
Behind ``TransportBroker``, and only behind it. By the time ``dial`` is called
the endpoint has been parsed and normalised, the authority window has been
checked, the host has been resolved, **every** answer has been judged, and the
approved addresses have been pinned. This adapter's job is to move bytes to
exactly those addresses and report what it observed.

It is the last CortexPrime code an outbound request passes through, and it holds
no authorization input of any kind — no capability, no operation, no grants. A
transport that could re-decide whether an action may happen would be a second
place the answer could differ.

Connecting to a pin, not to a name
------------------------------------
The whole DNS-rebinding defence rests on one thing: **the address that was
judged is the address that is connected to.** A client that re-resolves the
hostname between judgement and connection has stepped outside it, and every
HTTP client re-resolves by default.

So the request URL is rewritten to the pinned literal address and two things are
restored explicitly:

``Host``                   the original authority, so the provider routes to the
                           right virtual host
``sni_hostname`` extension the original hostname, which httpcore passes to
                           ``ssl_context.wrap_socket(server_hostname=...)`` — so
                           SNI *and* certificate hostname verification are both
                           performed against the real name, not against the IP

Getting the second one wrong is the subtle failure: connecting to an IP with the
certificate checked against that IP would fail on every legitimate provider, and
"fix" it by disabling verification.

Verification cannot be turned off
-----------------------------------
There is no ``verify=False`` here and no parameter that could produce one.
``ConnectionPolicy`` has no field for it either, so there is no value anywhere in
the fabric that disables certificate or hostname checking. A deployment needing a
private CA supplies ``TlsPolicy.ca_bundle_path``.

Nothing is inherited from the environment
-------------------------------------------
``trust_env=False`` is passed explicitly on every client. httpx honours
``HTTP_PROXY`` / ``HTTPS_PROXY`` / ``ALL_PROXY`` **by default**, which means a
proxy variable set anywhere in a deployment silently becomes the real
destination of every outbound request. That is an SSRF bypass no endpoint check
catches, and it is off here unless ``ProxyPolicy`` says otherwise in so many
words.

``trust_env=False`` also disables ``NETRC`` and ``SSL_CERT_FILE`` inheritance,
which is the same argument twice: credentials and trust anchors are configured,
never ambient.

Every timeout is stated
-------------------------
httpx models connect, read, write and pool separately and defaults them to five
seconds *combined* if given a bare number — a default nobody chose. Each is
mapped explicitly from ``TimeoutPolicy``, which the broker has already clamped to
the remaining authority window, so no request can outlive the permission for it.

No retry, ever
----------------
``httpx.HTTPTransport(retries=0)``. A network retry can duplicate a privileged
action. Connection establishment before a byte is written is the only thing that
could safely be repeated, and the broker owns that bound; once a request may have
been transmitted, control returns to Execution (ADR-031).

Response reading is bounded
-----------------------------
Streamed and stopped at ``budget.max_response_bytes``, reporting ``truncated``.
A provider is as capable of exhausting this process as a caller is, and rather
more likely to be overlooked.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Mapping, Optional, Tuple

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionEnvironment
from backend.contracts.transport import (
    ConnectionRef,
    TransportFailure,
    TransportKind,
)
from backend.platform.credentials.material import CredentialMaterial
from backend.platform.credentials.redaction import safe_exception_text
from backend.platform.transport.request import (
    DeliveryState,
    TransportOutcome,
    TransportRequest,
)

__all__ = ["HttpxTransportAdapter", "PRODUCTION_TRANSPORT_KINDS"]

log = logging.getLogger(__name__)

#: What this adapter can carry. ``MCP_SSE`` is absent: a long-lived
#: server-sent-event read needs idle-timeout and per-frame accounting that a
#: request/response client does not provide, and claiming it here would give an
#: SSE stream a total-timeout bound and nothing else. ``MCP_STDIO`` is absent
#: because it is not a network transport at all — see the module note below.
PRODUCTION_TRANSPORT_KINDS = frozenset(
    {TransportKind.HTTPS, TransportKind.MCP_STREAMABLE_HTTP}
)

#: How a credential type is presented. The **only** place in this fabric where a
#: secret becomes a header value, which is what makes ``grep -rn "\.reveal("``
#: a complete audit of secret handling.
_CREDENTIAL_HEADER = "authorization"


class HttpxTransportAdapter:
    """A production ``TransportAdapter`` over httpx. Constructed, never global."""

    def __init__(
        self,
        *,
        kinds: frozenset = PRODUCTION_TRANSPORT_KINDS,
        environments: Optional[frozenset] = None,
        user_agent: str = "CortexPrime/1.0",
    ) -> None:
        try:
            # Probed at construction rather than at the first privileged
            # operation: a platform that cannot dial should refuse to assemble,
            # not discover it halfway through a production change.
            import httpx  # noqa: F401  (probe)
        except ImportError as exc:  # pragma: no cover - deployment problem
            raise ContractViolation(
                "the production transport needs httpx installed; a platform "
                "that cannot dial should refuse at construction rather than at "
                "the first privileged operation"
            ) from exc

        for kind in kinds:
            if not isinstance(kind, TransportKind):
                raise ContractViolation("kinds must contain TransportKind values")
            if kind is TransportKind.MCP_STDIO:
                raise ContractViolation(
                    "stdio is not a network transport. Launching a local process "
                    "needs a sandbox and a process-execution boundary that does "
                    "not exist yet, and an HTTP client cannot provide one — so "
                    "it stays refused rather than approximated"
                )
            if kind is TransportKind.MCP_SSE:
                raise ContractViolation(
                    "server-sent events need idle-timeout and per-frame "
                    "accounting this request/response adapter does not provide; "
                    "carrying it here would bound a stream by its total timeout "
                    "and by nothing else"
                )
        if not kinds:
            raise ContractViolation("a transport adapter must declare its kinds")

        self._kinds = frozenset(kinds)
        self._environments = (
            frozenset(environments)
            if environments
            else frozenset(ExecutionEnvironment)
        )
        self._user_agent = user_agent

    @property
    def kinds(self) -> frozenset:
        return self._kinds

    # ------------------------------------------------------------------
    # The dial
    # ------------------------------------------------------------------

    def dial(
        self,
        request: TransportRequest,
        *,
        pinned_addresses: tuple,
        connection: ConnectionRef,
    ) -> TransportOutcome:
        """One request, to a pinned address, with everything stated."""
        import httpx

        endpoint = request.endpoint
        policy = request.policy

        if endpoint.environment not in self._environments:
            return TransportOutcome.refused(
                TransportFailure.ENVIRONMENT_MISMATCH,
                "this transport is not registered for that environment",
            )
        if not pinned_addresses:
            # The broker pins before dialling. An empty pinning means the
            # destination was not approved, and a transport must never dial one.
            return TransportOutcome.refused(
                TransportFailure.SSRF_REFUSED,
                "no approved address was pinned for this destination",
            )
        if endpoint.is_plaintext and not policy.tls.allow_plaintext:
            # Refused again here. The policy already refused it at the broker;
            # a transport that would have sent it anyway is one wiring mistake
            # away from being reachable another way.
            return TransportOutcome.refused(
                TransportFailure.TLS_DOWNGRADE_REFUSED,
                "plaintext is not permitted by this policy",
            )
        if (
            endpoint.environment is ExecutionEnvironment.PRODUCTION
            and endpoint.is_plaintext
        ):
            return TransportOutcome.refused(
                TransportFailure.TLS_DOWNGRADE_REFUSED,
                "plaintext is never permitted in production; it exposes both "
                "the credential and the payload",
            )

        timeouts = request.effective_timeouts
        address = pinned_addresses[0]
        target = _pinned_url(endpoint, address)
        headers = self._headers(request)

        try:
            client = httpx.Client(
                # Explicit, and the reason this adapter exists. httpx honours
                # HTTP_PROXY/HTTPS_PROXY/ALL_PROXY, NETRC and SSL_CERT_FILE from
                # the environment by default; a deployment variable would
                # silently become the real destination of every request.
                trust_env=policy.proxy.trust_environment,
                proxy=policy.proxy.proxy_url,
                # There is no verify=False and no parameter that produces one.
                # A private CA is a bundle path, which is configuration.
                verify=policy.tls.ca_bundle_path or True,
                # Redirects are judged by the broker, hop by hop, with the whole
                # endpoint and address policy re-run. Following them inside the
                # client would reach a destination nobody checked.
                follow_redirects=False,
                timeout=httpx.Timeout(
                    connect=timeouts.connect_seconds,
                    read=timeouts.read_seconds,
                    write=timeouts.read_seconds,
                    pool=timeouts.connect_seconds,
                ),
                limits=httpx.Limits(
                    max_connections=policy.budget.max_concurrent_connections,
                    max_keepalive_connections=0,
                    keepalive_expiry=0.0,
                ),
                # No retry. A network retry can duplicate a privileged action,
                # and whether repeating is safe is a question about the
                # binding's effect semantics that Execution answers.
                transport=httpx.HTTPTransport(
                    retries=0, verify=policy.tls.ca_bundle_path or True
                ),
            )
        except Exception as exc:  # noqa: BLE001 - nothing was sent
            log.warning("transport client construction failed: %s", safe_exception_text(exc))
            return TransportOutcome.refused(
                TransportFailure.POLICY_REFUSED,
                f"the transport could not be configured ({type(exc).__name__})",
            )

        try:
            with client:
                return self._send(
                    client,
                    request,
                    target=target,
                    headers=headers,
                    connection=connection,
                    pinned_addresses=pinned_addresses,
                )
        except Exception as exc:  # noqa: BLE001
            # Anything unclassifiable that escapes ``_send``. Never str(exc):
            # an httpx exception carries the request it was making.
            log.warning("transport dial failed: %s", safe_exception_text(exc))
            return TransportOutcome.unknown(
                f"the transport raised ({type(exc).__name__}); whether the "
                "request reached the provider is unknown",
                resolved_addresses=tuple(pinned_addresses),
            )

    # ------------------------------------------------------------------
    # Sending and classifying
    # ------------------------------------------------------------------

    def _send(
        self,
        client: Any,
        request: TransportRequest,
        *,
        target: str,
        headers: Mapping[str, str],
        connection: ConnectionRef,
        pinned_addresses: tuple,
    ) -> TransportOutcome:
        import httpx

        budget = request.policy.budget
        host = request.endpoint.host
        sent = False
        # Phase 11.3 (ADR-123): the policy's TOTAL budget, applied to the body.
        # connect/read/write timeouts are per operation on the socket; a body
        # that keeps trickling bytes (a Kubernetes watch that outlives its own
        # timeoutSeconds, a slow provider) never trips them and would be read
        # until the provider chose to stop. The total budget is the bound the
        # policy already declares; here it is finally enforced.
        deadline = time.monotonic() + float(request.effective_timeouts.total_seconds)

        try:
            built = client.build_request(
                request.method_normalised,
                target,
                headers=dict(headers),
                content=request.body,
                # Certificate hostname verification and SNI both use the *real*
                # hostname, not the pinned literal we are connecting to. Without
                # this, every legitimate provider fails verification and the
                # temptation is to turn verification off.
                extensions={"sni_hostname": host} if not request.endpoint.is_plaintext else {},
            )
            with client.stream(
                built.method,
                built.url,
                headers=built.headers,
                content=request.body,
                extensions=built.extensions,
            ) as response:
                # A status line means the request was written and read by the
                # provider. From here the operation was delivered whatever else
                # goes wrong.
                sent = True
                body, truncated = _read_bounded(response, budget.max_response_bytes,
                                                deadline=deadline)
                return TransportOutcome(
                    delivery=DeliveryState.DELIVERED,
                    connection=connection,
                    status_code=response.status_code,
                    response_bytes=len(body),
                    truncated=truncated,
                    body=body,
                    response_headers=_safe_response_headers(response.headers),
                    resolved_addresses=tuple(pinned_addresses),
                )

        except httpx.ConnectTimeout:
            return _refuse(TransportFailure.CONNECT_TIMEOUT, "connect timed out")
        except httpx.ConnectError as exc:
            return _refuse(
                TransportFailure.CONNECTION_REFUSED,
                f"the destination refused the connection ({type(exc).__name__})",
            )
        except httpx.ReadTimeout:
            # Ambiguous on purpose: the request was written and the answer was
            # not read. Whether the provider applied it is unknown.
            return _unknown(
                TransportFailure.READ_TIMEOUT,
                "the provider stopped responding after the request was sent",
                connection,
                pinned_addresses,
            )
        except httpx.WriteTimeout:
            return _unknown(
                TransportFailure.READ_TIMEOUT,
                "the request could not be written within its timeout; how much "
                "of it reached the provider is unknown",
                connection,
                pinned_addresses,
            )
        except httpx.PoolTimeout:
            return _refuse(
                TransportFailure.CONNECTION_LIMIT,
                "no connection slot became available within its timeout",
            )
        except httpx.TooManyRedirects:
            return _unknown(
                TransportFailure.REDIRECT_REFUSED,
                "the provider redirected more than this policy permits",
                connection,
                pinned_addresses,
            )
        except httpx.ProtocolError as exc:
            return _unknown(
                TransportFailure.PROTOCOL_ERROR,
                f"the provider spoke something this transport could not parse "
                f"({type(exc).__name__})",
                connection,
                pinned_addresses,
            )
        except httpx.RemoteProtocolError:
            return _unknown(
                TransportFailure.CONNECTION_RESET,
                "the connection ended mid-exchange",
                connection,
                pinned_addresses,
            )
        except Exception as exc:  # noqa: BLE001
            name = type(exc).__name__.lower()
            if "ssl" in name or "certificate" in name:
                # TLS fails before a byte of the request is written, so this is
                # one of the few genuinely definite negatives.
                return _refuse(
                    TransportFailure.CERTIFICATE_INVALID,
                    f"the TLS handshake failed ({type(exc).__name__})",
                )
            log.warning("transport send failed: %s", safe_exception_text(exc))
            if not sent:
                return _unknown(
                    TransportFailure.UNKNOWN_STATE,
                    f"the transport failed ({type(exc).__name__}); whether the "
                    "request reached the provider is unknown",
                    connection,
                    pinned_addresses,
                )
            return _unknown(
                TransportFailure.UNKNOWN_STATE,
                f"the response could not be read ({type(exc).__name__}); the "
                "provider may have applied the operation",
                connection,
                pinned_addresses,
            )

    # ------------------------------------------------------------------
    # Headers
    # ------------------------------------------------------------------

    def _headers(self, request: TransportRequest) -> dict:
        """Assemble the wire headers. **The only place a credential is read.**

        Caller headers were validated by ``validate_caller_headers`` before this
        request existed, and that list refuses ``Authorization`` outright — so a
        caller-supplied value cannot be here to be overwritten. ``Host`` is set
        by this adapter because the URL names a pinned literal address and the
        provider needs the real authority to route.
        """
        headers = {name.lower(): value for name, value in dict(request.headers).items()}
        headers["host"] = request.endpoint.authority
        headers.setdefault("user-agent", self._user_agent)
        headers.setdefault("accept-encoding", "identity")
        if request.idempotency_key:
            # Only where a caller put it in ``headers`` already does the provider
            # see a key; this is metadata for intermediaries, not a claim that
            # the provider honours one.
            headers.setdefault("x-cortexprime-idempotency-key", request.idempotency_key)

        material = request.credential
        if material is not None:
            if not isinstance(material, CredentialMaterial):
                raise ContractViolation(
                    "the transport was handed something that is not "
                    "CredentialMaterial; a raw secret reaching here would be a "
                    "secret outside the boundary designed to hold it"
                )
            headers[_CREDENTIAL_HEADER] = _present(material)
        return headers


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _present(material: CredentialMaterial) -> str:
    """Render credential material as an ``Authorization`` value.

    One ``reveal`` call, with a stated purpose, at the last possible moment. The
    value is built and handed straight to the client; it is never stored, never
    returned, and never placed in an object that has a ``to_dict``.
    """
    from backend.contracts.credential import CredentialType

    secret = material.reveal(purpose="transport authorization header")
    if material.credential_type is CredentialType.API_KEY:
        # A bare API key is presented as a bearer token unless a provider needs
        # otherwise; a provider that needs a different scheme declares it, and
        # that declaration belongs to the credential adapter, not here.
        return f"Bearer {secret}"
    if material.credential_type in {
        CredentialType.BEARER,
        CredentialType.OAUTH_ACCESS_TOKEN,
        CredentialType.CLOUD_TEMPORARY,
    }:
        return f"Bearer {secret}"
    if material.credential_type is CredentialType.SIGNED_ASSERTION:
        return f"Bearer {secret}"
    raise ContractViolation(
        f"{material.credential_type.value} cannot be presented as an "
        "Authorization header; mTLS material is a reference to a key held "
        "elsewhere and never becomes a header value"
    )


def _pinned_url(endpoint: Any, address: str) -> str:
    """Rebuild the URL against the judged address. The rebinding defence."""
    literal = f"[{address}]" if ":" in address else address
    query = f"?{endpoint.query}" if endpoint.query else ""
    return f"{endpoint.scheme}://{literal}:{endpoint.port}{endpoint.path}{query}"


def _read_bounded(response: Any, limit: int, *, deadline: Optional[float] = None) -> Tuple[bytes, bool]:
    """Read at most ``limit`` bytes, and say so when there was more.

    Never silently: a truncated body that looked complete would be parsed as
    complete, and a provider could use that to make a partial answer look whole.

    ``deadline`` (a ``time.monotonic`` instant) bounds the WHOLE read: a body
    still arriving past it raises ``httpx.ReadTimeout``, which the caller
    classifies exactly like a socket read timeout. Without it a stream that
    keeps sending bytes is read for as long as the provider likes.
    """
    chunks: list = []
    total = 0
    for chunk in response.iter_bytes():
        if deadline is not None and time.monotonic() > deadline:
            import httpx

            raise httpx.ReadTimeout("the transport total budget elapsed while the body was still arriving")
        remaining = limit - total
        if remaining <= 0:
            return b"".join(chunks), True
        if len(chunk) > remaining:
            chunks.append(chunk[:remaining])
            return b"".join(chunks), True
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks), False


#: Response headers worth reporting upward. An allow-list rather than a
#: deny-list: a provider controls its own header names, and "report everything
#: except the ones we thought of" is how an unexpected header reaches an audit
#: record. ``TransportOutcome`` refuses the credential-bearing names as a second,
#: independent bound.
_REPORTABLE_RESPONSE_HEADERS = frozenset(
    {
        "content-type",
        "content-length",
        "retry-after",
        "x-ratelimit-limit",
        "x-ratelimit-remaining",
        "x-ratelimit-reset",
        "x-request-id",
        "x-github-request-id",
        "mcp-session-id",
        "location",
        "etag",
    }
)


def _safe_response_headers(headers: Any) -> dict:
    return {
        name.lower(): str(value)[:1024]
        for name, value in headers.items()
        if name.lower() in _REPORTABLE_RESPONSE_HEADERS
    }


def _refuse(failure: TransportFailure, reason: str) -> TransportOutcome:
    """A failure that provably occurred before a byte was written."""
    return TransportOutcome.refused(failure, reason)


def _unknown(
    failure: TransportFailure,
    reason: str,
    connection: ConnectionRef,
    pinned_addresses: tuple,
) -> TransportOutcome:
    """A failure after which nobody can say whether the provider acted."""
    return TransportOutcome(
        delivery=DeliveryState.UNKNOWN,
        connection=connection,
        failure=failure,
        reason=reason,
        resolved_addresses=tuple(pinned_addresses),
    )
