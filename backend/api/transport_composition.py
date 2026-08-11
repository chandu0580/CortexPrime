"""Composition root: transport policy assembled from deployment configuration.

Why policy is built here
--------------------------
Transport policy must come from explicit configuration and from nowhere else.
Not from a provider's metadata, not from a capability's declaration, not from a
caller string, and not from a model. A provider that says plaintext is fine, or
that its metadata endpoint is a legitimate destination, changes nothing — this
module is the only source, and it reads deployment configuration.

Environment shapes the defaults, and production is the strict one
------------------------------------------------------------------
``production`` refuses plaintext, refuses private destinations, refuses
redirects, refuses proxies and requires DNS resolution. ``development`` relaxes
exactly two of those — plaintext and private addresses — because an in-cluster
provider on ``10.0.x.x`` over http is the ordinary local setup, and a policy that
made local development impossible would be replaced with one that made production
unsafe.

Nothing relaxes cloud metadata, and nothing relaxes TLS verification, in any
environment.

No transport is wired
-----------------------
``build_transport_broker`` returns a broker with no adapter. Every dial refuses
with ``transport_unavailable``. That is correct for Phase 4.2 and is the same
shape the worker directory took when it had no workers: refuse rather than
invent a default.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping, Optional

from backend.contracts.execution import ExecutionEnvironment
from backend.contracts.transport import TransportKind
from backend.platform.transport import (
    AddressClass,
    ConnectionPolicy,
    DevelopmentTransport,
    ProxyPolicy,
    RedirectPolicy,
    ResourceBudget,
    TimeoutPolicy,
    TlsPolicy,
    TransportBroker,
)

__all__ = [
    "build_connection_policy",
    "build_transport_broker",
    "build_development_transport_broker",
]

log = logging.getLogger(__name__)


def build_connection_policy(
    environment: ExecutionEnvironment,
    *,
    allow_private_destinations: bool = False,
    allow_plaintext: bool = False,
    proxy_url: Optional[str] = None,
    trust_environment_proxy: bool = False,
    follow_redirects: bool = False,
    max_redirect_hops: int = 0,
    ca_bundle_path: Optional[str] = None,
    client_certificate_ref: Optional[str] = None,
    timeouts: Optional[TimeoutPolicy] = None,
    budget: Optional[ResourceBudget] = None,
) -> ConnectionPolicy:
    """Assemble a policy. Every relaxation is a named argument somebody passed.

    There is no ``allow_insecure`` and no way to disable certificate or hostname
    verification — those are not parameters here because they are not fields on
    ``TlsPolicy``. A deployment needing a private CA passes ``ca_bundle_path``.

    ``allow_private_destinations`` and ``allow_plaintext`` are **refused for
    production** by ``ConnectionPolicy`` itself, so this cannot be used to build
    a production policy that reaches ``10.0.0.0/8`` over http.
    """
    if not isinstance(environment, ExecutionEnvironment):
        raise ValueError("environment must be an ExecutionEnvironment")

    classes = {AddressClass.PUBLIC}
    if allow_private_destinations:
        if environment is ExecutionEnvironment.PRODUCTION:
            # Stated as a hard refusal rather than a silent drop: a deployment
            # that asked for this in production has a configuration problem it
            # needs to see.
            raise ValueError(
                "private destinations cannot be enabled for production through "
                "this builder. An in-cluster production provider needs an "
                "explicit, reviewed policy naming exactly which classes it "
                "reaches -- not a boolean"
            )
        classes |= {AddressClass.PRIVATE, AddressClass.LOOPBACK}

    return ConnectionPolicy(
        environment=environment,
        tls=TlsPolicy(
            allow_plaintext=allow_plaintext,
            ca_bundle_path=ca_bundle_path,
            client_certificate_ref=client_certificate_ref,
        ),
        redirects=RedirectPolicy(
            follow=follow_redirects,
            max_hops=max_redirect_hops if follow_redirects else 0,
            same_origin_only=True,
        ),
        proxy=ProxyPolicy(
            proxy_url=proxy_url,
            # Off unless a deployment says otherwise. Every HTTP client in
            # Python honours HTTP_PROXY by default, which means a proxy nobody
            # configured can silently become the real destination.
            trust_environment=trust_environment_proxy,
        ),
        timeouts=timeouts or TimeoutPolicy(),
        budget=budget or ResourceBudget(),
        allowed_address_classes=frozenset(classes),
        require_dns_resolution=True,
    )


def build_transport_broker(
    *,
    adapters: Optional[Mapping[TransportKind, Any]] = None,
    resolver: Optional[Any] = None,
    audit: Optional[Any] = None,
    metrics: Optional[Any] = None,
    clock: Optional[Any] = None,
) -> TransportBroker:
    """The broker. Empty by default, and that is the correct default.

    With no adapter every dial refuses ``transport_unavailable``. A platform
    with no transport should refuse rather than find one, and there is no
    default adapter to fall back to.
    """
    return TransportBroker(
        adapters=adapters,
        resolver=resolver,
        audit=audit,
        metrics=metrics,
        clock=clock,
    )


def build_development_transport_broker(
    *,
    kinds: frozenset = frozenset({TransportKind.HTTPS}),
    responder: Optional[Any] = None,
    environment: ExecutionEnvironment = ExecutionEnvironment.DEVELOPMENT,
    **kwargs: Any,
) -> TransportBroker:
    """A broker with the scripted development transport. **Never production.**

    A separately-named function rather than a flag, for the same reason
    ``build_development_broker`` is one in the credential fabric: a flag is
    something configuration can set by accident, and a differently-named
    function is something a person has to type.
    """
    if environment is ExecutionEnvironment.PRODUCTION:
        raise ValueError(
            "build_development_transport_broker cannot serve production; a mock "
            "transport there would make every action look performed"
        )
    broker = build_transport_broker(**kwargs)
    broker.register(
        DevelopmentTransport(
            kinds=kinds,
            allow_non_production=True,
            responder=responder,
            environments=frozenset({environment}),
        )
    )
    return broker
