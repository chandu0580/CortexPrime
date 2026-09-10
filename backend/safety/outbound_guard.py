"""The outbound-request guard for V1 code — Phase 11.1 (ADR-121).

Phase 4.4 built the governed transport fabric: address policy, DNS pinning,
redirects off, credentials never crossing an origin. It also recorded, rather
than fixed, that every *V1* client dials by its own means with no address
policy (``backend/api/legacy_network_inventory.py``), and that the only V1
defence was a prefix regex in ``guardrails_engine``.

This module is not a second fabric. It composes the fabric's own judgement --
``parse_url_structure`` for structure, ``classify_literal`` for what an address
*is*, ``SystemAddressResolver`` for what a name resolves to -- into the two
things a V1 call site can actually use:

``judge_outbound_url``  decide, with a reason. Pure apart from DNS.
``guarded_get``         *make* the request, at the real boundary: connect to the
                        judged address (not the hostname -- the rebinding
                        defence), send the original ``Host`` and SNI, follow at
                        most a few redirects and judge **every hop**, never
                        forward caller headers across an origin, read a bounded
                        body.

What it refuses, and why by parsing rather than pattern
---------------------------------------------------------
Loopback, RFC1918 private, link-local (including every cloud metadata
address), IPv6 unique-local and site-local, carrier-grade NAT, multicast,
unspecified (``0.0.0.0``/``::``), broadcast and reserved ranges; unsupported
schemes; credential-bearing URLs; control characters; decimal, hexadecimal,
octal and abbreviated IPv4 spellings; IPv4-mapped IPv6; and any hostname that
*resolves* to any of the above. A host resolving to one public and one private
address is refused: approving on the public answer is how a round-robin rebind
succeeds on the second attempt.

The limitation, stated
------------------------
``judge_outbound_url`` pins addresses; a caller that then hands the *hostname*
to its own client re-resolves and is not protected. ``guarded_get`` is the safe
path. Where a V1 call site cannot use it (a ``git clone`` subprocess resolves
for itself), the judgement still refuses literal and currently-resolving
private targets, and the residual rebinding window is recorded in ADR-121.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping, Optional
from urllib.parse import urljoin

from backend.platform.transport.endpoint import (
    UnsafeTransportEndpoint,
    UrlStructure,
    parse_url_structure,
)
from backend.platform.transport.ssrf import (
    LOOPBACK_ALIASES,
    AddressClass,
    AddressResolver,
    SystemAddressResolver,
    classify_literal,
)

log = logging.getLogger(__name__)

__all__ = [
    "OutboundRefused",
    "OutboundJudgement",
    "GuardedResponse",
    "DEFAULT_SCHEMES",
    "HTTPS_ONLY",
    "judge_outbound_url",
    "assert_outbound_url",
    "guarded_get",
]

DEFAULT_SCHEMES = frozenset({"https", "http"})
HTTPS_ONLY = frozenset({"https"})
_DEFAULT_PORTS = {"https": 443, "http": 80}
_MAX_RESPONSE_BYTES = 4 * 1024 * 1024
_HOP_SAFE_HEADERS = frozenset({"accept", "accept-encoding", "user-agent"})


class OutboundRefused(ValueError):
    """The guard refused a destination. ``reason`` is safe to show a caller."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"outbound request refused for {url[:120]!r}: {reason}")
        self.url = url
        self.reason = reason


@dataclass(frozen=True)
class OutboundJudgement:
    url: str
    allowed: bool
    reason: str
    scheme: str = ""
    host: str = ""
    port: int = 0
    path: str = "/"
    query: str = ""
    pinned_addresses: tuple = ()
    address_class: Optional[str] = None
    resolved: bool = False

    def to_dict(self) -> dict:
        return {
            "url": self.url[:200],
            "allowed": self.allowed,
            "reason": self.reason,
            "host": self.host,
            "port": self.port,
            "pinned": list(self.pinned_addresses),
            "address_class": self.address_class,
            "resolved": self.resolved,
        }


def _refused(url: str, reason: str, **fields: Any) -> OutboundJudgement:
    return OutboundJudgement(url=url, allowed=False, reason=reason, **fields)


def judge_outbound_url(
    url: str,
    *,
    permitted_schemes: frozenset = DEFAULT_SCHEMES,
    allowed_hosts: Optional[frozenset] = None,
    resolve: bool = True,
    resolver: Optional[AddressResolver] = None,
    timeout_seconds: float = 3.0,
) -> OutboundJudgement:
    """Decide whether ``url`` may be dialled, and pin what it resolves to.

    ``allowed_hosts`` -- when given, the host must be one of them (exact, after
    lowercasing) *in addition to* passing the address policy. A call site that
    only ever talks to one provider should say so.
    """
    try:
        structure: UrlStructure = parse_url_structure(
            url, permitted_schemes=permitted_schemes, require_host=True)
    except UnsafeTransportEndpoint as exc:
        return _refused(str(url), exc.reason)

    host = structure.host or ""
    port = structure.port or _DEFAULT_PORTS.get(structure.scheme, 0)
    base = dict(scheme=structure.scheme, host=host, port=port,
                path=structure.path, query=structure.query)

    if host in LOOPBACK_ALIASES or host.endswith(".localhost"):
        return _refused(url, f"host {host!r} is a loopback alias",
                        address_class=AddressClass.LOOPBACK.value, **base)

    if allowed_hosts is not None and host not in {h.lower() for h in allowed_hosts}:
        return _refused(url, f"host {host!r} is not on this call site's allow-list", **base)

    literal = classify_literal(host)
    if literal is not None:
        if not literal.is_public:
            return _refused(url, f"address {literal.address} is {literal.address_class.value}",
                            address_class=literal.address_class.value, **base)
        return OutboundJudgement(url=url, allowed=True, reason="public literal address",
                                 pinned_addresses=(literal.address,),
                                 address_class=literal.address_class.value,
                                 resolved=False, **base)

    if not resolve:
        return OutboundJudgement(url=url, allowed=True,
                                 reason="hostname accepted without resolution (literal checks only)",
                                 resolved=False, **base)

    active = resolver or SystemAddressResolver()
    try:
        answers = active.resolve(host, port, timeout_seconds=timeout_seconds)
    except Exception as exc:  # noqa: BLE001 - DNS failure is a refusal, not a pass
        return _refused(url, f"hostname {host!r} did not resolve ({type(exc).__name__})", **base)
    if not answers:
        return _refused(url, f"hostname {host!r} resolved to nothing", **base)

    approved: list = []
    for answer in answers:
        judged = classify_literal(str(answer))
        if judged is None:
            return _refused(url, "the resolver returned something that is not an address", **base)
        if not judged.is_public:
            return _refused(
                url,
                f"hostname {host!r} resolves to {judged.address} which is {judged.address_class.value}",
                address_class=judged.address_class.value, resolved=True, **base)
        approved.append(judged.address)
    return OutboundJudgement(url=url, allowed=True, reason="every resolved address is public",
                             pinned_addresses=tuple(approved),
                             address_class=AddressClass.PUBLIC.value, resolved=True, **base)


def assert_outbound_url(url: str, **kwargs: Any) -> OutboundJudgement:
    """``judge_outbound_url`` that raises ``OutboundRefused`` on refusal."""
    judgement = judge_outbound_url(url, **kwargs)
    if not judgement.allowed:
        log.warning("outbound guard refused %r: %s", str(url)[:120], judgement.reason)
        raise OutboundRefused(str(url), judgement.reason)
    return judgement


@dataclass(frozen=True)
class GuardedResponse:
    status_code: int
    headers: dict
    body: bytes
    final_url: str
    hops: tuple
    truncated: bool

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


def _pinned_url(j: OutboundJudgement, address: str) -> str:
    literal = f"[{address}]" if ":" in address else address
    query = f"?{j.query}" if j.query else ""
    return f"{j.scheme}://{literal}:{j.port}{j.path}{query}"


def _authority(j: OutboundJudgement) -> str:
    default = _DEFAULT_PORTS.get(j.scheme)
    return j.host if j.port == default else f"{j.host}:{j.port}"


def _same_origin(a: OutboundJudgement, b: OutboundJudgement) -> bool:
    return (a.scheme, a.host, a.port) == (b.scheme, b.host, b.port)


async def guarded_get(
    url: str,
    *,
    headers: Optional[Mapping[str, str]] = None,
    timeout_seconds: float = 30.0,
    max_hops: int = 3,
    max_bytes: int = _MAX_RESPONSE_BYTES,
    permitted_schemes: frozenset = HTTPS_ONLY,
    allowed_hosts: Optional[frozenset] = None,
    resolver: Optional[AddressResolver] = None,
    transport: Any = None,
) -> GuardedResponse:
    """GET ``url`` at the real boundary: judged, pinned, every hop re-judged.

    Caller headers travel only to the first origin. On a cross-origin redirect
    only ``Accept``/``User-Agent``-class headers survive; anything that could be
    a credential does not. The response body is read up to ``max_bytes``.

    ``transport`` exists so a test can substitute an httpx mock transport and
    observe exactly which pinned URL, ``Host`` and headers would be sent.
    """
    import httpx

    if max_hops < 0 or max_hops > 5:
        raise ValueError("max_hops must be between 0 and 5")

    first = assert_outbound_url(url, permitted_schemes=permitted_schemes,
                                allowed_hosts=allowed_hosts, resolver=resolver)
    current = first
    current_headers = {str(k): str(v) for k, v in (headers or {}).items()}
    hops: list = []
    timeout = httpx.Timeout(timeout_seconds)
    client_kwargs: dict = dict(follow_redirects=False, trust_env=False, timeout=timeout)
    if transport is not None:
        client_kwargs["transport"] = transport

    async with httpx.AsyncClient(**client_kwargs) as client:
        for hop in range(max_hops + 1):
            address = current.pinned_addresses[0]
            send_headers = {k: v for k, v in current_headers.items()
                            if k.lower() != "host"}
            send_headers["host"] = _authority(current)
            extensions = {"sni_hostname": current.host} if current.scheme == "https" else {}
            request = client.build_request("GET", _pinned_url(current, address),
                                           headers=send_headers, extensions=extensions)
            response = await client.send(request, stream=True)
            try:
                if response.is_redirect and "location" in response.headers:
                    location = urljoin(current.url, response.headers["location"])
                    hops.append({"from": current.url[:200], "to": location[:200],
                                 "status": response.status_code})
                    if hop == max_hops:
                        raise OutboundRefused(location, f"more than {max_hops} redirect hops")
                    nxt = assert_outbound_url(location, permitted_schemes=permitted_schemes,
                                              allowed_hosts=allowed_hosts, resolver=resolver)
                    if not _same_origin(current, nxt):
                        current_headers = {k: v for k, v in current_headers.items()
                                           if k.lower() in _HOP_SAFE_HEADERS}
                    current = nxt
                    continue
                chunks: list = []
                total = 0
                truncated = False
                async for chunk in response.aiter_bytes():
                    if total + len(chunk) > max_bytes:
                        chunks.append(chunk[: max_bytes - total])
                        truncated = True
                        break
                    chunks.append(chunk)
                    total += len(chunk)
                return GuardedResponse(
                    status_code=response.status_code,
                    headers={k: v for k, v in response.headers.items()
                             if k.lower() != "set-cookie"},
                    body=b"".join(chunks),
                    final_url=current.url,
                    hops=tuple(hops),
                    truncated=truncated,
                )
            finally:
                await response.aclose()
    raise OutboundRefused(url, "redirect chain did not terminate")  # pragma: no cover
