"""The secure transport and connection fabric (Phase 4.2).

Where it sits
---------------
Below the credential fabric and above nothing — this is the last CortexPrime
code an outbound request passes through. It answers one question:

    "How can this already-authorized invocation reach the selected provider?"

It never answers "may this action happen?". The invocation gateway answered that
before a transport request existed, and a transport that could re-answer it would
be a second place the answer could differ.

The chain
-----------
    Capability → Binding → Authorization → Worker → Credential
    → Endpoint → Address policy → Pinning → Transport → Provider

Each arrow is a separate decision by a separate component. A connection existing
implies none of the ones before it.

What is here and what is not
------------------------------
Here: the endpoint model, the SSRF address policy, DNS resolution and pinning,
connection policy, header rules, resource budgets, the outcome vocabulary, and
the broker that enforces them.

**Phase 4.4 attached the first production transport.** ``HttpxTransportAdapter``
implements ``TransportAdapter`` over httpx: it connects to pinned addresses,
never re-resolves, states every timeout, and cannot be configured to skip
verification. Everything above it is unchanged — the broker still approves, still
pins, and still refuses ``transport_unavailable`` when no adapter is registered
for a kind, which is what an unwired deployment gets.

Still not here: no socket, no subprocess, no stdio. ``MCP_STDIO`` remains
refused, because launching a local process needs a sandbox boundary that does not
exist yet and an HTTP client cannot approximate one.

    endpoint     parse and normalise a destination; refuse what is unsafe to hold
    ssrf         classify addresses; resolve names; pin what was judged
    policy       TLS, redirects, proxy, timeouts, budgets -- transport safety only
    headers      normalisation, forbidden names, injection defence
    request      the request, the outcome, and delivery state
    broker       the one gate; approve, pin, dial once, classify
    development  a non-production transport that refuses production
    httpx_adapter the production transport: pinned addresses, stated timeouts
"""

from backend.platform.transport.broker import (
    TRANSPORT_METRICS,
    ConnectionSlots,
    TransportAdapter,
    TransportBroker,
)
from backend.platform.transport.development import DevelopmentTransport
from backend.platform.transport.httpx_adapter import (
    PRODUCTION_TRANSPORT_KINDS,
    HttpxTransportAdapter,
)
from backend.platform.transport.endpoint import (
    DIALLABLE_SCHEMES,
    MAX_ENDPOINT_LENGTH,
    TransportEndpoint,
    UnsafeTransportEndpoint,
    UrlStructure,
    parse_url_structure,
)
from backend.platform.transport.headers import (
    FORBIDDEN_CALLER_HEADERS,
    HOP_BY_HOP_HEADERS,
    HeaderRefused,
    normalise_header_name,
    validate_caller_headers,
)
from backend.platform.transport.policy import (
    ConnectionPolicy,
    PolicyRefusal,
    ProxyPolicy,
    RedirectPolicy,
    ResourceBudget,
    TimeoutPolicy,
    TlsPolicy,
)
from backend.platform.transport.request import (
    DeliveryState,
    TransportOutcome,
    TransportRefused,
    TransportRequest,
)
from backend.platform.transport.ssrf import (
    CLOUD_METADATA_ADDRESSES,
    LOOPBACK_ALIASES,
    AddressClass,
    AddressJudgement,
    AddressResolver,
    ResolvedDestination,
    SystemAddressResolver,
    classify_literal,
)

__all__ = [
    "TransportBroker",
    "TransportAdapter",
    "ConnectionSlots",
    "TRANSPORT_METRICS",
    "TransportEndpoint",
    "UnsafeTransportEndpoint",
    "UrlStructure",
    "parse_url_structure",
    "DIALLABLE_SCHEMES",
    "MAX_ENDPOINT_LENGTH",
    "ConnectionPolicy",
    "TlsPolicy",
    "RedirectPolicy",
    "ProxyPolicy",
    "TimeoutPolicy",
    "ResourceBudget",
    "PolicyRefusal",
    "TransportRequest",
    "TransportOutcome",
    "TransportRefused",
    "DeliveryState",
    "AddressClass",
    "AddressJudgement",
    "ResolvedDestination",
    "AddressResolver",
    "SystemAddressResolver",
    "classify_literal",
    "CLOUD_METADATA_ADDRESSES",
    "LOOPBACK_ALIASES",
    "FORBIDDEN_CALLER_HEADERS",
    "HOP_BY_HOP_HEADERS",
    "normalise_header_name",
    "validate_caller_headers",
    "HeaderRefused",
    "DevelopmentTransport",
    "HttpxTransportAdapter",
    "PRODUCTION_TRANSPORT_KINDS",
]
