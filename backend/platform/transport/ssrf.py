"""The network-level SSRF boundary. The first layer that can actually connect.

Why this exists here and not earlier
--------------------------------------
Capability discovery validates endpoint *structure* and says so plainly: it
records ``is_private`` rather than refusing it, because a platform-internal MCP
server on ``10.0.x.x`` is legitimate to discover. Nothing before this phase could
open a socket, so nothing before this phase needed an address policy.

Transport can connect. So the policy lives here, and it is the only place in
CortexPrime entitled to say a destination is reachable.

What this refuses to rely on
------------------------------
The repository's existing SSRF handling is a regex over URL text in
``safety/guardrails_engine``. It matches ``127.``, ``10.``, ``192.168.`` and a
few more as *string prefixes*. It misses, at minimum:

    2130706433              decimal form of 127.0.0.1
    0x7f000001              hexadecimal form
    0177.0.0.1              octal form
    [::ffff:127.0.0.1]      IPv4-mapped IPv6
    [::]                    unspecified
    [fe80::1]               IPv6 link-local (``fd`` is matched, ``fe80`` is not)
    100.64.0.1              carrier-grade NAT
    anything.that.resolves.to.a.private.address

Every one of those is handled below, and by parsing rather than by pattern:
``ipaddress`` normalises numeric forms for free, which is why the decimal and
hexadecimal cases are not special-cased here — they simply parse to the same
address object and are judged on what they *are*.

Two questions, deliberately separate
--------------------------------------
``classify_literal``  what is this address?  — pure, total, no I/O
``AddressResolver``   what does this name resolve to? — the only network call

Keeping them apart is what makes the first testable without a network and the
second replaceable without touching the policy.

The limitation, stated
------------------------
A hostname is resolved, every returned address is judged, and the approved
addresses are **pinned** onto the decision. A caller that connects to a pinned
address is safe from DNS rebinding. A caller that re-resolves the hostname itself
is not, and this module cannot prevent that — it can only make the safe path the
obvious one and say so. See ``ResolvedDestination.pinned_addresses``.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from backend.contracts.errors import ContractViolation

__all__ = [
    "AddressClass",
    "AddressJudgement",
    "ResolvedDestination",
    "AddressResolver",
    "SystemAddressResolver",
    "classify_literal",
    "CLOUD_METADATA_ADDRESSES",
    "LOOPBACK_ALIASES",
]

#: Addresses that serve cloud instance credentials to anything that asks. The
#: single highest-value SSRF target in existence: one unfiltered request returns
#: role credentials for the whole machine.
#:
#: Listed explicitly *as well as* being caught by the link-local and private
#: rules, because being explicit means the refusal names what was attempted, and
#: "somebody tried to reach the metadata service" is a sentence a security review
#: needs to be able to read directly.
CLOUD_METADATA_ADDRESSES = frozenset(
    {
        "169.254.169.254",  # AWS, Azure, GCP, DigitalOcean, OpenStack
        "169.254.170.2",  # AWS ECS task metadata
        "100.100.100.200",  # Alibaba Cloud
        "192.0.0.192",  # Oracle Cloud
        "fd00:ec2::254",  # AWS IMDSv6
    }
)

#: Names that mean "this machine" without being an address. Matched after
#: lowercasing and trailing-dot removal, because ``LOCALHOST.`` and ``localhost``
#: are the same destination and only one of them looks like it.
LOOPBACK_ALIASES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "ip6-localhost",
        "ip6-loopback",
    }
)


class AddressClass(str, Enum):
    """What an address is. One value per reason a destination may be refused."""

    PUBLIC = "public"
    """Globally routable. The only class reachable by default."""

    LOOPBACK = "loopback"
    PRIVATE = "private"
    LINK_LOCAL = "link_local"
    UNIQUE_LOCAL = "unique_local"
    """IPv6 ``fc00::/7``. The IPv6 equivalent of RFC1918, and the one most often
    missed because it does not look like ``10.``."""

    CARRIER_GRADE_NAT = "carrier_grade_nat"
    """``100.64.0.0/10``. Not private by ``ipaddress``'s reckoning in every
    version, routable inside a carrier network, and not somewhere a tenant's
    capability should be reaching."""

    MULTICAST = "multicast"
    UNSPECIFIED = "unspecified"
    """``0.0.0.0`` / ``::``. Means "this host" to a connect() call, which makes
    it a loopback in disguise."""

    RESERVED = "reserved"
    BROADCAST = "broadcast"
    CLOUD_METADATA = "cloud_metadata"

    @property
    def is_routable_by_default(self) -> bool:
        return self is AddressClass.PUBLIC

    @property
    def is_metadata(self) -> bool:
        return self is AddressClass.CLOUD_METADATA


@dataclass(frozen=True)
class AddressJudgement:
    """What one address is, and whether it may be reached under a policy."""

    address: str
    address_class: AddressClass
    family: int
    """``socket.AF_INET`` or ``AF_INET6``. Carried because a destination that
    resolves to both families must have *every* answer judged — approving on the
    strength of the IPv4 result and connecting over IPv6 is a real bypass."""

    def __post_init__(self) -> None:
        if not isinstance(self.address_class, AddressClass):
            raise ContractViolation("address_class must be an AddressClass")

    @property
    def is_public(self) -> bool:
        return self.address_class.is_routable_by_default

    def to_dict(self) -> dict:
        return {
            "address": self.address,
            "class": self.address_class.value,
            "family": "ipv6" if self.family == socket.AF_INET6 else "ipv4",
        }


def classify_literal(text: str) -> Optional[AddressJudgement]:
    """Classify a literal IP address. ``None`` when it is not one.

    Pure and total. Numeric forms — decimal ``2130706433``, hexadecimal
    ``0x7f000001``, octal ``0177.0.0.1`` — are **not** special-cased: they are
    parsed, and parsing normalises them to the address they denote. A rule that
    pattern-matched them would have to enumerate the forms, and would miss the
    next one somebody invents.

    IPv4-mapped IPv6 (``::ffff:127.0.0.1``) is unwrapped before judgement. It is
    the classic bypass: it looks like an IPv6 address, no IPv4 rule matches it,
    and it connects to loopback.
    """
    if not isinstance(text, str) or not text.strip():
        return None
    cleaned = text.strip().strip("[]").lower()
    if cleaned.endswith("."):
        cleaned = cleaned.rstrip(".")

    address: object
    try:
        address = ipaddress.ip_address(cleaned)
    except ValueError:
        # ``ipaddress`` is deliberately strict: it rejects leading zeros
        # (``0177.0.0.1``) and abbreviated forms (``127.1``) precisely because
        # they are ambiguous. **The operating system's resolver is not strict**,
        # and it is the resolver that decides where a connection actually goes.
        #
        # So the fallback is ``inet_aton``, which implements the classic BSD
        # parsing the resolver itself uses — octal, hexadecimal, bare integers,
        # and 1-to-3-part abbreviations all included. Anything the resolver would
        # turn into an address is classified as that address here.
        #
        # Erring toward *more* things being treated as literals is the safe
        # direction: a literal is judged by the address policy, while a string
        # that falls through is handed to DNS and judged on whatever comes back.
        resolved = _inet_aton_ipv4(cleaned)
        if resolved is None:
            return None
        address = resolved

    # IPv4-mapped and IPv4-compatible IPv6 unwrap to the address they reach.
    if isinstance(address, ipaddress.IPv6Address):
        mapped = address.ipv4_mapped
        if mapped is not None:
            address = mapped

    return AddressJudgement(
        address=str(address),
        address_class=_classify(address),
        family=(
            socket.AF_INET6
            if isinstance(address, ipaddress.IPv6Address)
            else socket.AF_INET
        ),
    )


def _inet_aton_ipv4(text: str) -> Optional[ipaddress.IPv4Address]:
    """Parse the permissive IPv4 forms the OS resolver accepts. ``None`` if not one.

    ``socket.inet_aton`` implements the historical ``a.b.c.d`` / ``a.b.c`` /
    ``a.b`` / ``a`` rules with octal (``0177``) and hexadecimal (``0x7f``) parts.
    Those spellings are exactly the classic SSRF filter bypasses, and they work
    because ``connect()`` accepts them even where a strict parser does not.

    A guard against ``inet_aton``'s one dangerous quirk: on some platforms it
    ignores trailing content. Anything with whitespace or characters outside the
    IPv4 alphabet is rejected before it is offered.
    """
    if not text or any(character not in "0123456789abcdefx." for character in text):
        return None
    try:
        packed = socket.inet_aton(text)
    except OSError:
        return None
    return ipaddress.IPv4Address(packed)


def _classify(address: object) -> AddressClass:
    """The single classification table. Ordered most-specific first."""
    text = str(address)
    if text in CLOUD_METADATA_ADDRESSES:
        return AddressClass.CLOUD_METADATA

    # Carrier-grade NAT before ``is_private``: some Python versions report
    # 100.64/10 as private and some do not, and a class that changes with the
    # interpreter version is not a security control.
    if isinstance(address, ipaddress.IPv4Address):
        if address in ipaddress.IPv4Network("100.64.0.0/10"):
            return AddressClass.CARRIER_GRADE_NAT
        if address == ipaddress.IPv4Address("255.255.255.255"):
            return AddressClass.BROADCAST

    if address.is_unspecified:
        return AddressClass.UNSPECIFIED
    if address.is_loopback:
        return AddressClass.LOOPBACK
    if address.is_link_local:
        return AddressClass.LINK_LOCAL
    if isinstance(address, ipaddress.IPv6Address) and address.is_site_local:
        return AddressClass.UNIQUE_LOCAL
    if isinstance(address, ipaddress.IPv6Address) and address in ipaddress.IPv6Network(
        "fc00::/7"
    ):
        return AddressClass.UNIQUE_LOCAL
    if address.is_multicast:
        return AddressClass.MULTICAST
    if address.is_private:
        return AddressClass.PRIVATE
    if address.is_reserved:
        return AddressClass.RESERVED
    return AddressClass.PUBLIC


@dataclass(frozen=True)
class ResolvedDestination:
    """A hostname, everything it resolved to, and what may be connected to.

    ``pinned_addresses`` is the security-relevant field. A caller that connects
    to one of these is connecting to something that was judged. A caller that
    hands the *hostname* to a socket library is re-resolving, and the second
    answer can differ from the first — which is DNS rebinding, and is the one
    attack this arrangement can describe but not unilaterally prevent.
    """

    host: str
    judgements: tuple = ()
    pinned_addresses: tuple = ()
    """Addresses approved by the policy. Empty when the destination was refused;
    a caller finding it empty must not connect."""

    refused: tuple = ()
    """Judgements that failed the policy, kept so a refusal can name what was
    actually found rather than only that something was."""

    resolved: bool = True
    """False when resolution was not performed -- a literal address needs none.
    Distinguished from "resolved to nothing", which is a DNS failure."""

    def __post_init__(self) -> None:
        if not isinstance(self.host, str) or not self.host.strip():
            raise ContractViolation("a resolved destination must name its host")

    @property
    def is_reachable(self) -> bool:
        """Whether anything survived the policy.

        **Every** answer must survive, not merely one: a host resolving to a
        public address and a loopback address is a host that will reach loopback
        half the time, and approving it because one answer was public is how a
        round-robin rebind succeeds on the second attempt.
        """
        return bool(self.pinned_addresses) and not self.refused

    @property
    def worst_class(self) -> Optional[AddressClass]:
        """The class a refusal should name. Metadata first -- it is the headline."""
        if not self.refused:
            return None
        for judgement in self.refused:
            if judgement.address_class.is_metadata:
                return judgement.address_class
        return self.refused[0].address_class

    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "resolved": self.resolved,
            "reachable": self.is_reachable,
            "pinned": list(self.pinned_addresses),
            "judgements": [j.to_dict() for j in self.judgements],
            "refused": [j.to_dict() for j in self.refused],
        }


@runtime_checkable
class AddressResolver(Protocol):
    """Turns a hostname into addresses. The only network operation in this module.

    A Protocol so the policy above stays testable without DNS, and so a
    deployment with its own resolver — a sidecar, a allow-listing forwarder —
    substitutes one without touching any security logic.
    """

    def resolve(self, host: str, port: int, *, timeout_seconds: float) -> tuple: ...


class SystemAddressResolver:
    """Resolution via the operating system, with a bounded timeout.

    ``socket.getaddrinfo`` has no per-call timeout, so the default socket
    timeout is set around the call. That is process-global state for the
    duration, which is ugly and is the reason this is isolated in one small
    class rather than spread through the fabric.
    """

    def resolve(self, host: str, port: int, *, timeout_seconds: float) -> tuple:
        if timeout_seconds <= 0:
            raise ContractViolation(
                "DNS resolution needs a positive timeout; an unbounded lookup is "
                "an unbounded hold on the execution that requested it"
            )
        previous = socket.getdefaulttimeout()
        try:
            socket.setdefaulttimeout(timeout_seconds)
            answers = socket.getaddrinfo(
                host, port, proto=socket.IPPROTO_TCP
            )
        finally:
            socket.setdefaulttimeout(previous)

        seen: list = []
        for family, _type, _proto, _canon, sockaddr in answers:
            address = sockaddr[0]
            if address not in seen:
                seen.append(address)
        return tuple(seen)
