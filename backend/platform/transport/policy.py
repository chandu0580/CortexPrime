"""Connection policy: transport safety, and deliberately not business permission.

What it decides
-----------------
Whether a destination may be dialled at all: scheme, TLS, address class,
redirects, proxies, timeouts, and how much of CortexPrime a provider may consume.

What it must never become
---------------------------
A second authorization engine. It has no concept of a capability, an operation,
a principal's grants or an approval — those are answered before anything reaches
here, and a policy that could re-answer them would be a second place the answer
could differ.

The test: every rule below is one somebody would want *even for an action they
had already fully authorized*. TLS verification, response size limits and SSRF
refusal are all still correct for a request nobody doubts.

Secure by default, structurally
---------------------------------
The default construction refuses plaintext, refuses private destinations,
refuses redirects, refuses proxies, and bounds every timeout and every budget.
Loosening any of them is an argument somebody has to pass, and each one is named
for what it actually permits rather than for how convenient it is.

**There is no ``verify=False``.** TLS verification and hostname verification are
not fields, so there is no value anybody can set to turn them off. A deployment
needing a private CA supplies a bundle; a deployment wanting no verification at
all is asking for something this fabric does not offer.

Policy comes from configuration, never from a provider
--------------------------------------------------------
A provider declaring that plaintext is fine, or that its metadata endpoint is
safe, changes nothing. Policy is supplied by the composition root from deployment
configuration. Nothing here reads provider metadata, a model, or a caller string.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionEnvironment
from backend.contracts.transport import TransportFailure, TransportKind
from backend.platform.transport.endpoint import TransportEndpoint
from backend.platform.transport.ssrf import (
    AddressClass,
    AddressJudgement,
    ResolvedDestination,
)

__all__ = [
    "TlsPolicy",
    "RedirectPolicy",
    "ProxyPolicy",
    "TimeoutPolicy",
    "ResourceBudget",
    "ConnectionPolicy",
    "PolicyRefusal",
]


@dataclass(frozen=True)
class PolicyRefusal:
    """One reason a connection was refused, and what it was about."""

    failure: TransportFailure
    reason: str
    detail: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "failure": self.failure.value,
            "reason": self.reason,
            "detail": self.detail,
            "security_relevant": self.failure.is_security_relevant,
        }


@dataclass(frozen=True)
class TlsPolicy:
    """How TLS must be done. Verification is not optional and is not a field.

    ``verify_certificates`` and ``verify_hostname`` are absent by design. A
    boolean that can be set to ``False`` will be set to ``False`` by somebody
    debugging a certificate at 2am, and it will stay that way. Both are always
    on, and this type describes only the things that legitimately vary.
    """

    minimum_version: str = "TLSv1.2"
    """Modern floor. A provider cannot lower it -- metadata is not authority."""

    ca_bundle_path: Optional[str] = None
    """An explicit additional trust anchor. A *path*, never certificate bytes:
    trust configuration belongs in deployment configuration, not in an object
    that gets passed around and logged."""

    client_certificate_ref: Optional[str] = None
    """An opaque reference to mTLS material held by the credential fabric.
    **Never the key.** The private key stays behind ``CredentialProvider`` and
    reaches a transport as runtime material at the moment of use, exactly as a
    bearer token does."""

    allow_plaintext: bool = False
    """Permits ``http://``. Off by default. A deployment with an in-cluster
    plaintext sidecar states it here, per policy, rather than globally."""

    _ALLOWED_VERSIONS = frozenset({"TLSv1.2", "TLSv1.3"})

    def __post_init__(self) -> None:
        if self.minimum_version not in TlsPolicy._ALLOWED_VERSIONS:
            raise ContractViolation(
                f"TLS minimum {self.minimum_version!r} is not supported; "
                f"permitted: {', '.join(sorted(TlsPolicy._ALLOWED_VERSIONS))}. "
                "Legacy TLS is an explicit architectural decision, not a "
                "configuration value"
            )
        if self.client_certificate_ref is not None and (
            "BEGIN" in self.client_certificate_ref
        ):
            # Cheap guard against the exact mistake this field exists to prevent.
            raise ContractViolation(
                "client_certificate_ref holds what looks like certificate or key "
                "material; it must be an opaque reference. Private keys never "
                "enter transport state"
            )

    def to_dict(self) -> dict:
        return {
            "minimum_version": self.minimum_version,
            "verify_certificates": True,
            "verify_hostname": True,
            "ca_bundle_configured": self.ca_bundle_path is not None,
            "mtls_configured": self.client_certificate_ref is not None,
            "allow_plaintext": self.allow_plaintext,
        }


@dataclass(frozen=True)
class RedirectPolicy:
    """Whether a provider may send us somewhere else. Off by default.

    A redirect changes host, scheme, port and network zone — every property the
    endpoint checks established. Following one blindly means the destination
    that was validated is not the destination that was reached.

    When redirects are permitted, each hop is re-validated from scratch and
    **credentials never cross an origin**. That is not configurable: forwarding
    an ``Authorization`` header to whatever host a provider names is credential
    disclosure by request.
    """

    follow: bool = False
    max_hops: int = 0
    same_origin_only: bool = True
    """When following is on, restrict hops to the same scheme/host/port. The
    common legitimate case (a trailing-slash redirect) stays inside one origin;
    the dangerous case does not."""

    def __post_init__(self) -> None:
        if self.follow and self.max_hops < 1:
            raise ContractViolation(
                "a policy that follows redirects must allow at least one hop"
            )
        if not self.follow and self.max_hops:
            raise ContractViolation(
                "max_hops is meaningless when redirects are not followed; one of "
                "the two settings is not what its author intended"
            )
        if self.max_hops > 5:
            raise ContractViolation(
                "more than five redirect hops is a redirect loop with extra steps"
            )

    def to_dict(self) -> dict:
        return {
            "follow": self.follow,
            "max_hops": self.max_hops,
            "same_origin_only": self.same_origin_only,
            "credentials_cross_origin": False,
        }


@dataclass(frozen=True)
class ProxyPolicy:
    """Whether traffic may go through an intermediary. Off by default.

    Two separate dangers. A proxy changes the actual destination, so a
    user-controlled proxy URL is an SSRF bypass that no endpoint check catches.
    And an *inherited* proxy is worse: ``HTTP_PROXY`` in the environment is
    honoured silently by most HTTP clients, so a deployment can route privileged
    traffic through an intermediary nobody configured deliberately.

    ``trust_environment`` is therefore ``False`` by default and must be turned on
    explicitly. Every transport adapter is required to honour it.
    """

    proxy_url: Optional[str] = None
    trust_environment: bool = False

    def __post_init__(self) -> None:
        if self.proxy_url is not None:
            if not isinstance(self.proxy_url, str) or not self.proxy_url.strip():
                raise ContractViolation("proxy_url must be non-blank text when set")
            if not self.proxy_url.startswith(("http://", "https://")):
                raise ContractViolation(
                    "a proxy must be an http or https URL; any other scheme is a "
                    "protocol-smuggling vector wearing a proxy's name"
                )
            if "@" in self.proxy_url:
                raise ContractViolation(
                    "proxy_url contains embedded credentials; proxy authentication "
                    "goes through the credential fabric like everything else"
                )

    @property
    def enabled(self) -> bool:
        return self.proxy_url is not None

    def to_dict(self) -> dict:
        # The URL itself is included: it is deployment configuration, contains no
        # credentials by construction, and an operator debugging a routing
        # problem needs to see it.
        return {
            "enabled": self.enabled,
            "proxy_url": self.proxy_url,
            "trust_environment": self.trust_environment,
        }


@dataclass(frozen=True)
class TimeoutPolicy:
    """Every phase bounded separately. No infinite anything.

    Separate values because the phases fail differently: a slow DNS server and a
    slow provider response need different limits, and one combined timeout means
    tuning either one wrongly. All are floats of seconds and all have a ceiling —
    a timeout large enough to outlive the authority window is not a timeout.
    """

    dns_seconds: float = 5.0
    connect_seconds: float = 10.0
    tls_handshake_seconds: float = 10.0
    read_seconds: float = 30.0
    idle_seconds: float = 60.0
    total_seconds: float = 120.0
    """The whole operation, including every retry-free phase above. What an
    authority window is compared against."""

    _CEILING = 600.0

    def __post_init__(self) -> None:
        for label in (
            "dns_seconds",
            "connect_seconds",
            "tls_handshake_seconds",
            "read_seconds",
            "idle_seconds",
            "total_seconds",
        ):
            value = getattr(self, label)
            if not isinstance(value, (int, float)) or value <= 0:
                raise ContractViolation(
                    f"{label} must be positive; an unbounded or absent timeout is "
                    "a hold on the execution that requested it with no end"
                )
            if value > TimeoutPolicy._CEILING:
                raise ContractViolation(
                    f"{label} exceeds the {TimeoutPolicy._CEILING}s ceiling"
                )
        if self.total_seconds < self.connect_seconds:
            raise ContractViolation(
                "the total timeout is shorter than the connect timeout; the "
                "operation would be abandoned before it could begin"
            )

    def bounded_by(self, authority_seconds: Optional[float]) -> "TimeoutPolicy":
        """Clamp every phase to the remaining authority window.

        Work must not outlive the permission for it. Applied by taking the
        minimum rather than by scaling, so a short window shortens everything
        instead of preserving proportions nobody asked for.
        """
        if authority_seconds is None:
            return self
        if authority_seconds <= 0:
            raise ContractViolation(
                "no authority window remains; a connection started now would "
                "outlive the permission for it"
            )
        from dataclasses import replace

        limit = float(authority_seconds)
        return replace(
            self,
            dns_seconds=min(self.dns_seconds, limit),
            connect_seconds=min(self.connect_seconds, limit),
            tls_handshake_seconds=min(self.tls_handshake_seconds, limit),
            read_seconds=min(self.read_seconds, limit),
            idle_seconds=min(self.idle_seconds, limit),
            total_seconds=min(self.total_seconds, limit),
        )

    def to_dict(self) -> dict:
        return {
            "dns_seconds": self.dns_seconds,
            "connect_seconds": self.connect_seconds,
            "tls_handshake_seconds": self.tls_handshake_seconds,
            "read_seconds": self.read_seconds,
            "idle_seconds": self.idle_seconds,
            "total_seconds": self.total_seconds,
        }


@dataclass(frozen=True)
class ResourceBudget:
    """How much of CortexPrime a provider may consume.

    **A malicious provider is as dangerous as a malicious caller**, and rather
    more likely to be overlooked. Every limit here bounds something an external
    system controls: how much it sends, how long it holds a stream open, how many
    connections it can tie up.
    """

    max_response_bytes: int = 10 * 1024 * 1024
    max_request_bytes: int = 4 * 1024 * 1024
    max_header_count: int = 64
    max_header_bytes: int = 16 * 1024
    max_url_length: int = 2048
    max_frame_bytes: int = 1024 * 1024
    """One SSE event or one stream frame. Separate from the response total: a
    provider can stay inside a total budget while sending one frame large enough
    to exhaust memory assembling it."""

    max_stream_seconds: float = 300.0
    max_concurrent_connections: int = 8
    """Per tenant, per provider. Bounds one tenant's ability to occupy the
    process, which is a fairness property as much as a security one."""

    def __post_init__(self) -> None:
        for label in (
            "max_response_bytes",
            "max_request_bytes",
            "max_header_count",
            "max_header_bytes",
            "max_url_length",
            "max_frame_bytes",
            "max_concurrent_connections",
        ):
            value = getattr(self, label)
            if not isinstance(value, int) or value < 1:
                raise ContractViolation(f"{label} must be a positive integer")
        if self.max_stream_seconds <= 0:
            raise ContractViolation("max_stream_seconds must be positive")
        if self.max_frame_bytes > self.max_response_bytes:
            raise ContractViolation(
                "a single frame may not exceed the whole response budget"
            )

    def to_dict(self) -> dict:
        return {
            "max_response_bytes": self.max_response_bytes,
            "max_request_bytes": self.max_request_bytes,
            "max_header_count": self.max_header_count,
            "max_header_bytes": self.max_header_bytes,
            "max_url_length": self.max_url_length,
            "max_frame_bytes": self.max_frame_bytes,
            "max_stream_seconds": self.max_stream_seconds,
            "max_concurrent_connections": self.max_concurrent_connections,
        }


@dataclass(frozen=True)
class ConnectionPolicy:
    """The complete transport-safety decision for one connection.

    Immutable, and immutable *for the connection*: a policy that could change
    while a connection is open would mean the rules a channel was opened under
    are not the rules it operates under.
    """

    environment: ExecutionEnvironment
    tls: TlsPolicy = field(default_factory=TlsPolicy)
    redirects: RedirectPolicy = field(default_factory=RedirectPolicy)
    proxy: ProxyPolicy = field(default_factory=ProxyPolicy)
    timeouts: TimeoutPolicy = field(default_factory=TimeoutPolicy)
    budget: ResourceBudget = field(default_factory=ResourceBudget)

    allowed_address_classes: frozenset = field(
        default_factory=lambda: frozenset({AddressClass.PUBLIC})
    )
    """Public only, by default. A deployment reaching an in-cluster provider adds
    ``PRIVATE`` here **deliberately and per policy** — never globally, and never
    by a provider claiming its address is fine.

    ``CLOUD_METADATA`` is refused even if listed: see ``judge_destination``."""

    allowed_private_addresses: frozenset = field(default_factory=frozenset)
    """Phase 11.1-K: the explicit, reviewed in-cluster policy the production
    builder has always demanded ("an in-cluster production provider needs an
    explicit reviewed policy naming exactly which classes it reaches -- not a
    boolean"). Exact IP literals, each of which must itself be PRIVATE or
    UNIQUE_LOCAL: a destination resolving to one of these is reachable even
    though its class is not in ``allowed_address_classes``. Nothing wider --
    no CIDR, no class, no loopback, no link-local, never cloud metadata. A
    connector composes it from the addresses its OWN configured endpoints
    resolve to, so the policy names exactly the destinations it was built for."""

    require_dns_resolution: bool = True
    """Whether a hostname must be resolved and every answer judged before
    connecting. On by default. Turning it off means dialling a name that was
    never checked, and is only defensible where an egress proxy does the checking
    instead."""

    def __post_init__(self) -> None:
        if not isinstance(self.environment, ExecutionEnvironment):
            raise ContractViolation("a policy must state its environment")
        for address in self.allowed_private_addresses:
            import ipaddress as _ipaddress

            try:
                parsed = _ipaddress.ip_address(address)
            except ValueError as exc:
                raise ContractViolation(
                    "allowed_private_addresses holds exact IP literals only") from exc
            if not parsed.is_private or parsed.is_loopback or parsed.is_link_local:
                raise ContractViolation(
                    f"{address} is not a private cluster address; the exact-address "
                    "allowance exists for in-cluster providers and nothing else")
        for entry in self.allowed_address_classes:
            if not isinstance(entry, AddressClass):
                raise ContractViolation(
                    "allowed_address_classes must contain AddressClass values"
                )
        if not self.allowed_address_classes:
            raise ContractViolation(
                "a policy allowing no address class can never connect; an empty "
                "set is a misconfiguration rather than a lockdown"
            )
        if (
            self.environment is ExecutionEnvironment.PRODUCTION
            and self.tls.allow_plaintext
        ):
            raise ContractViolation(
                "plaintext is not permitted in production. A production endpoint "
                "reached over http exposes both the credential and the payload, "
                "and no deployment convenience outweighs that"
            )

    # ------------------------------------------------------------------
    # Decisions
    # ------------------------------------------------------------------

    def judge_endpoint(self, endpoint: TransportEndpoint) -> tuple:
        """Everything wrong with dialling this endpoint. Empty means proceed.

        Returns every refusal rather than the first, so an operator fixing one
        does not rediscover the next.
        """
        refusals: list = []

        if endpoint.environment is not self.environment:
            refusals.append(
                PolicyRefusal(
                    TransportFailure.ENVIRONMENT_MISMATCH,
                    "the endpoint's environment differs from the policy's",
                    f"{endpoint.environment.value} != {self.environment.value}",
                )
            )
        if endpoint.is_plaintext and not self.tls.allow_plaintext:
            refusals.append(
                PolicyRefusal(
                    TransportFailure.TLS_DOWNGRADE_REFUSED,
                    "plaintext http is not permitted by this policy",
                    endpoint.normalised,
                )
            )
        if len(endpoint.dial_target()) > self.budget.max_url_length:
            refusals.append(
                PolicyRefusal(
                    TransportFailure.REQUEST_TOO_LARGE,
                    "the URL exceeds the configured maximum length",
                )
            )
        if endpoint.transport is TransportKind.MCP_STDIO:
            refusals.append(
                PolicyRefusal(
                    TransportFailure.POLICY_REFUSED,
                    "stdio has no network endpoint and is not dialled by this fabric",
                )
            )
        return tuple(refusals)

    def judge_address(self, judgement: AddressJudgement) -> Optional[PolicyRefusal]:
        """Whether one resolved address may be reached.

        Cloud metadata is refused **unconditionally** — even when its class is
        listed in ``allowed_address_classes``. A deployment permitting private
        destinations is saying "our providers live in the cluster"; it is not
        saying "the instance credential service is a valid provider", and no
        configuration should be able to say the second by accident.
        """
        if judgement.address_class.is_metadata:
            return PolicyRefusal(
                TransportFailure.SSRF_REFUSED,
                "the cloud instance metadata service is never a valid destination",
                judgement.address,
            )
        if (judgement.address in self.allowed_private_addresses
                and judgement.address_class in (AddressClass.PRIVATE,
                                                AddressClass.UNIQUE_LOCAL)):
            return None
        if judgement.address_class not in self.allowed_address_classes:
            return PolicyRefusal(
                TransportFailure.SSRF_REFUSED,
                f"destination is {judgement.address_class.value} and this policy "
                f"permits only "
                f"{', '.join(sorted(c.value for c in self.allowed_address_classes))}",
                judgement.address,
            )
        return None

    def judge_destination(self, destination: ResolvedDestination) -> tuple:
        """Judge every address a host resolved to. All of them must pass.

        Not "any of them": a host resolving to one public and one loopback
        address will reach loopback on some fraction of connections, and
        approving it because one answer looked fine is how a round-robin rebind
        succeeds on the second attempt.
        """
        refusals: list = []
        if not destination.judgements:
            return (
                PolicyRefusal(
                    TransportFailure.DNS_FAILURE,
                    "the host resolved to no addresses",
                    destination.host,
                ),
            )
        for judgement in destination.judgements:
            refusal = self.judge_address(judgement)
            if refusal is not None:
                refusals.append(refusal)
        return tuple(refusals)

    def judge_redirect(
        self, origin: TransportEndpoint, target: TransportEndpoint, hop: int
    ) -> tuple:
        """Whether a redirect may be followed, and whether credentials may go."""
        refusals: list = []
        if not self.redirects.follow:
            return (
                PolicyRefusal(
                    TransportFailure.REDIRECT_REFUSED,
                    "this policy does not follow redirects; the destination that "
                    "was validated is the only one that will be reached",
                    target.normalised,
                ),
            )
        if hop > self.redirects.max_hops:
            refusals.append(
                PolicyRefusal(
                    TransportFailure.REDIRECT_REFUSED,
                    f"more than {self.redirects.max_hops} redirect hops",
                )
            )
        if self.redirects.same_origin_only and not origin.same_origin_as(target):
            refusals.append(
                PolicyRefusal(
                    TransportFailure.REDIRECT_REFUSED,
                    "the redirect leaves the origin and this policy is same-origin",
                    target.normalised,
                )
            )
        # The target gets the full endpoint judgement again. A redirect that was
        # not re-validated is a destination nobody checked.
        refusals.extend(self.judge_endpoint(target))
        return tuple(refusals)

    @staticmethod
    def credentials_may_follow(
        origin: TransportEndpoint, target: TransportEndpoint
    ) -> bool:
        """Whether credentials may cross to a redirect target. Same origin only.

        A ``staticmethod`` and not a policy field: this is not configurable.
        Forwarding an ``Authorization`` header to whatever host a provider names
        in a ``Location`` is credential disclosure on request, and no deployment
        has a good reason for it.
        """
        return origin.same_origin_as(target)

    def to_dict(self) -> dict:
        return {
            "environment": self.environment.value,
            "tls": self.tls.to_dict(),
            "redirects": self.redirects.to_dict(),
            "proxy": self.proxy.to_dict(),
            "timeouts": self.timeouts.to_dict(),
            "budget": self.budget.to_dict(),
            "allowed_address_classes": sorted(
                c.value for c in self.allowed_address_classes
            ),
            "require_dns_resolution": self.require_dns_resolution,
        }
