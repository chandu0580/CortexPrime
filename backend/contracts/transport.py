"""Transport vocabulary: how a connection is made, never whether it may be.

Owner: the transport fabric (Phase 4.2). Published here because Execution's
worker adapters name a transport kind and audit records carry a connection
reference, and those cross a boundary the two sides may not import across.

The distinction this module keeps
-----------------------------------
**Protocol is not transport, and neither is a provider.**

    MCP                 an application protocol -- a way of talking
    Streamable HTTP     one transport MCP can be spoken over
    SSE                 another
    stdio               another
    GitHub              a provider, which is none of the above

Collapsing any pair makes the security model wrong somewhere. If ``MCP == HTTP``
then an MCP-over-stdio server inherits HTTP's rules and none of its own; if
``provider == transport`` then every provider needs its own transport security
and one of them will get it wrong.

Connection identity is not capability identity
------------------------------------------------
``ConnectionRef`` names a channel. It is deliberately not a ``CapabilityRef``,
a ``WorkerRef`` or a ``CredentialRef``: a connection existing must never imply an
ability exists, an implementation is trusted, or a secret is held. The chain is

    Capability → Binding → Provider → Connection → Credential

and each arrow is a separate decision made by a separate component.

Vocabulary only, no parsing
-----------------------------
No URL parsing, no address classification, no network anything. ``contracts/`` is
a leaf package with a short reviewed list of permitted standard-library imports
(``DEP-CONTRACTS-LEAF``), and security-sensitive parsing needs ``ipaddress`` and
``urllib`` — so it lives in ``platform.transport`` where those are allowed.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = [
    "TransportKind",
    "ConnectionState",
    "TransportFailure",
    "ConnectionRef",
]


class TransportKind(str, Enum):
    """How bytes move. Not what they mean, and not who is at the other end."""

    HTTPS = "https"
    """A single request and response over TLS. The ordinary case."""

    MCP_STREAMABLE_HTTP = "mcp_streamable_http"
    """MCP spoken over HTTP with a streaming response body."""

    MCP_SSE = "mcp_sse"
    """MCP spoken over Server-Sent Events. A long-lived read that must be
    bounded in duration, in idle time, and in event size."""

    MCP_STDIO = "mcp_stdio"
    """MCP spoken to a local process over its standard streams. **A seam only.**
    Nothing in Phase 4.2 launches a process; that needs a sandbox and belongs to
    the worker layer under its own security boundary."""

    @property
    def is_mcp(self) -> bool:
        return self in {
            TransportKind.MCP_STREAMABLE_HTTP,
            TransportKind.MCP_SSE,
            TransportKind.MCP_STDIO,
        }

    @property
    def is_network(self) -> bool:
        """Whether this reaches the network, and therefore needs SSRF rules.

        ``MCP_STDIO`` does not — it talks to a local process, which is a
        different and in some ways worse problem, handled by a different
        boundary rather than by pretending an address policy applies.
        """
        return self is not TransportKind.MCP_STDIO

    @property
    def is_streaming(self) -> bool:
        return self in {
            TransportKind.MCP_STREAMABLE_HTTP,
            TransportKind.MCP_SSE,
        }

    @property
    def requires_tls(self) -> bool:
        """Whether the transport is meaningless without TLS.

        Every network kind here does. Plaintext is a policy exception that has to
        be stated per connection, never a property of the transport type.
        """
        return self.is_network


class ConnectionState(str, Enum):
    """Where a connection is in its life. Five states, no implicit ones."""

    OPENING = "opening"
    OPEN = "open"
    DRAINING = "draining"
    """Finishing in-flight work and accepting nothing new. How a connection
    closes without cutting off a response mid-read."""

    CLOSED = "closed"
    FAILED = "failed"

    @property
    def permits_use(self) -> bool:
        return self is ConnectionState.OPEN

    @property
    def is_terminal(self) -> bool:
        return self in {ConnectionState.CLOSED, ConnectionState.FAILED}


class TransportFailure(str, Enum):
    """What went wrong, in provider-neutral terms.

    Distinguishable on purpose. Collapsing these into ``connection_failed`` would
    take away exactly what Execution's recovery reads: a DNS failure and a
    refused redirect call for different responses, and ``UNKNOWN_STATE`` must
    never be confused with either.

    Transport reports facts. **Execution decides what to do about them** —
    nothing here is a retry instruction.
    """

    # -- resolution and reachability --------------------------------------
    DNS_FAILURE = "dns_failure"
    CONNECTION_REFUSED = "connection_refused"
    CONNECTION_RESET = "connection_reset"
    NETWORK_UNREACHABLE = "network_unreachable"

    # -- TLS -----------------------------------------------------------------
    TLS_FAILURE = "tls_failure"
    CERTIFICATE_INVALID = "certificate_invalid"
    HOSTNAME_MISMATCH = "hostname_mismatch"
    TLS_DOWNGRADE_REFUSED = "tls_downgrade_refused"

    # -- policy ----------------------------------------------------------------
    SSRF_REFUSED = "ssrf_refused"
    REDIRECT_REFUSED = "redirect_refused"
    PROXY_REFUSED = "proxy_refused"
    SCHEME_REFUSED = "scheme_refused"
    ENDPOINT_REFUSED = "endpoint_refused"
    ENVIRONMENT_MISMATCH = "environment_mismatch"
    TENANT_MISMATCH = "tenant_mismatch"
    POLICY_REFUSED = "policy_refused"

    # -- budgets -----------------------------------------------------------------
    MESSAGE_TOO_LARGE = "message_too_large"
    HEADERS_TOO_LARGE = "headers_too_large"
    REQUEST_TOO_LARGE = "request_too_large"
    CONNECTION_LIMIT = "connection_limit"
    STREAM_DURATION_EXCEEDED = "stream_duration_exceeded"

    # -- time --------------------------------------------------------------------
    DNS_TIMEOUT = "dns_timeout"
    CONNECT_TIMEOUT = "connect_timeout"
    TLS_TIMEOUT = "tls_timeout"
    READ_TIMEOUT = "read_timeout"
    IDLE_TIMEOUT = "idle_timeout"

    # -- lifecycle ------------------------------------------------------------------
    CANCELLED = "cancelled"
    PROTOCOL_ERROR = "protocol_error"
    CREDENTIAL_REFUSED = "credential_refused"
    TRANSPORT_UNAVAILABLE = "transport_unavailable"

    UNKNOWN_STATE = "unknown_state"
    """The request may or may not have reached the provider. **The honest answer
    after a lost connection mid-send**, and the one that must never be reported
    as either success or definite failure -- Execution's ambiguity rules read
    this and refuse to retry a mutation on the strength of it."""

    @property
    def reached_the_provider_is_unknown(self) -> bool:
        """Whether the request might have been delivered despite the failure.

        The question Execution's retry rules actually ask. A refused redirect
        happened *after* a response, so something was delivered; a DNS failure
        means nothing left. The ambiguous set is the one where nobody can say.
        """
        return self in {
            TransportFailure.UNKNOWN_STATE,
            TransportFailure.READ_TIMEOUT,
            TransportFailure.IDLE_TIMEOUT,
            TransportFailure.CONNECTION_RESET,
            TransportFailure.STREAM_DURATION_EXCEEDED,
        }

    @property
    def is_definitely_not_delivered(self) -> bool:
        """Whether nothing can have reached the provider.

        Only failures that occur before a byte of the request is written.
        Deliberately conservative: anything not listed here is treated as
        possibly-delivered, because the cost of being wrong in that direction is
        a duplicated production change.
        """
        return self in {
            TransportFailure.DNS_FAILURE,
            TransportFailure.DNS_TIMEOUT,
            TransportFailure.CONNECTION_REFUSED,
            TransportFailure.NETWORK_UNREACHABLE,
            TransportFailure.CONNECT_TIMEOUT,
            TransportFailure.TLS_FAILURE,
            TransportFailure.TLS_TIMEOUT,
            TransportFailure.CERTIFICATE_INVALID,
            TransportFailure.HOSTNAME_MISMATCH,
            TransportFailure.TLS_DOWNGRADE_REFUSED,
            TransportFailure.SSRF_REFUSED,
            TransportFailure.PROXY_REFUSED,
            TransportFailure.SCHEME_REFUSED,
            TransportFailure.ENDPOINT_REFUSED,
            TransportFailure.ENVIRONMENT_MISMATCH,
            TransportFailure.TENANT_MISMATCH,
            TransportFailure.POLICY_REFUSED,
            TransportFailure.REQUEST_TOO_LARGE,
            TransportFailure.CONNECTION_LIMIT,
            TransportFailure.CREDENTIAL_REFUSED,
            TransportFailure.TRANSPORT_UNAVAILABLE,
        }

    @property
    def is_security_relevant(self) -> bool:
        return self in {
            TransportFailure.SSRF_REFUSED,
            TransportFailure.REDIRECT_REFUSED,
            TransportFailure.PROXY_REFUSED,
            TransportFailure.CERTIFICATE_INVALID,
            TransportFailure.HOSTNAME_MISMATCH,
            TransportFailure.TLS_DOWNGRADE_REFUSED,
            TransportFailure.TENANT_MISMATCH,
            TransportFailure.ENVIRONMENT_MISMATCH,
        }


@dataclass(frozen=True)
class ConnectionRef(Contract):
    """An opaque handle to a connection. Safe to persist, log, and audit.

    Carries no secret and nowhere to put one. Rendered
    ``conn://<tenant>/<kind>/<opaque-id>`` so anything printing it shows a
    reference, and so it is greppable as a reference rather than mistakable for
    a URL.

    Tenant-qualified in the identity itself, for the same reason ``CredentialRef``
    is: a handle whose tenant could be changed by editing a neighbouring field
    is a handle that eventually names another tenant's channel.

    **Not a capability identity.** A connection existing says a channel was
    opened, never that an ability exists or an action is permitted.
    """

    CONTRACT_NAME = "cortexprime.transport.connection_ref"

    tenant_id: str
    kind: TransportKind
    connection_id: str
    """Opaque, assigned by the fabric. Never derived from an endpoint, a
    credential, or anything else that would make the handle disclose what it
    points at."""

    def __post_init__(self) -> None:
        for label in ("tenant_id", "connection_id"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")
            if "/" in value or value != value.strip():
                raise ContractViolation(
                    f"{label} must not contain a separator or surrounding "
                    "whitespace; a reference that does not round-trip is one "
                    "that eventually names something else"
                )
        if not isinstance(self.kind, TransportKind):
            raise ContractViolation("kind must be a TransportKind")
        if len(self.connection_id) > 128:
            raise ContractViolation(
                "connection_id is implausibly long for an identifier; something "
                "that is not an identifier was probably passed"
            )

    @property
    def value(self) -> str:
        return f"conn://{self.tenant_id}/{self.kind.value}/{self.connection_id}"

    def __str__(self) -> str:
        return self.value

    def belongs_to(self, tenant_id: str) -> bool:
        return self.tenant_id == tenant_id

    def to_dict(self) -> dict:
        return {
            "ref": self.value,
            "tenant_id": self.tenant_id,
            "kind": self.kind.value,
            "connection_id": self.connection_id,
        }
