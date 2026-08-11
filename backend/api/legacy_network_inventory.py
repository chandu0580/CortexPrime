"""V1 outbound network paths: what exists, and what each one actually does.

Scope
-------
Phase 4.2 builds the transport fabric. It does not migrate thirty httpx clients
onto it — rewriting every connector on the strength of an architecture document
is how a security phase becomes an outage.

So each pre-existing outbound path is recorded with what was found by reading it,
not by assuming. The findings below are the ones that matter for Phase 4.3, which
is where these begin moving.

The property that holds across all of them
--------------------------------------------
None of these bypasses the **invocation gateway** — every V1 execution route is
gated (ADR-039) and refuses by default. What they bypass is the *transport
fabric*: they dial by their own means, with their own TLS defaults and no address
policy.

So the exposure is bounded by the gate in front of them, not by anything in the
client itself. That is what makes migrating them a matter of order rather than
emergency — with one exception, noted below.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "LegacyNetworkPath",
    "LEGACY_NETWORK_PATHS",
    "hazards",
    "summary",
]


@dataclass(frozen=True)
class LegacyNetworkPath:
    """One pre-existing way bytes leave this process."""

    location: str
    client: str
    finding: str
    tls_verified: bool
    ssrf_controls: str
    follows_redirects: bool
    timeout: str
    inherits_env_proxy: bool
    caller_controls_url: bool
    hazard: bool
    disposition: str


LEGACY_NETWORK_PATHS: tuple = (
    LegacyNetworkPath(
        location="backend/mcp/connectors/web.py :: WebConnector",
        client="httpx.AsyncClient(timeout=30.0, follow_redirects=True)",
        finding="Exposes ``fetch_url`` and ``http_get`` tools taking a "
        "**caller-supplied URL** and caller-supplied headers, following "
        "redirects. This is a complete SSRF primitive: any reachable address, "
        "any scheme httpx accepts, and a redirect chain that is never "
        "re-validated. The only guard anywhere is a regex in "
        "``safety/guardrails_engine`` matching string prefixes like ``127.`` "
        "and ``10.`` — it misses decimal (``2130706433``), hexadecimal "
        "(``0x7f000001``), octal, IPv4-mapped IPv6 (``[::ffff:127.0.0.1]``), "
        "IPv6 link-local ``fe80::``, carrier-grade NAT, and every hostname "
        "that merely *resolves* to a private address.",
        tls_verified=True,
        ssrf_controls="a prefix regex in guardrails_engine; see above",
        follows_redirects=True,
        timeout="30s total, no separate connect/read bound",
        inherits_env_proxy=True,
        caller_controls_url=True,
        hazard=True,
        disposition="**The one genuine hazard.** Reachable only through "
        "``POST /api/v2/mcp/execute``, which is gated off by default (ADR-038), "
        "so it is inert unless an operator sets the migration flag. Migrate to "
        "the transport fabric in Phase 4.3, or remove the two tools. Not "
        "changed here: this phase builds the fabric, and rewriting a connector "
        "to use it is 4.3 work.",
    ),
    LegacyNetworkPath(
        location="backend/connectors/*.py (~18 provider clients)",
        client="httpx.AsyncClient(base_url=..., timeout=30.0)",
        finding="Each connector builds its own client against a fixed provider "
        "base URL. TLS verification is httpx's default (on). No address policy, "
        "no redirect policy, one combined timeout rather than separate connect "
        "and read bounds. URLs are provider-fixed, not caller-supplied.",
        tls_verified=True,
        ssrf_controls="none; destinations are fixed at construction",
        follows_redirects=False,
        timeout="30s combined",
        inherits_env_proxy=True,
        caller_controls_url=False,
        hazard=False,
        disposition="Strangler targets, behind the generic ``ConnectorAdapter``. "
        "Phase 4.3 migrated the first (GitHub) as an ``OperationCatalog`` and a "
        "response translator; the rest are inventoried in "
        "``legacy_provider_inventory``. Lower risk than the web connector "
        "because the destination is fixed rather than caller-chosen. Their "
        "credential handling is separately inventoried in the Phase 4.1 "
        "credential inventory.",
    ),
    LegacyNetworkPath(
        location="backend/identity/providers/*.py (okta, azure_ad, google, keycloak)",
        client="httpx",
        finding="OIDC/OAuth provider clients dialling configured issuer URLs. "
        "Fixed destinations from deployment configuration.",
        tls_verified=True,
        ssrf_controls="none; destinations are configuration, not caller input",
        follows_redirects=False,
        timeout="client default",
        inherits_env_proxy=True,
        caller_controls_url=False,
        hazard=False,
        disposition="Authentication infrastructure rather than capability "
        "execution. Out of scope for the execution transport fabric; if it "
        "migrates at all it does so as part of identity work, not 4.3.",
    ),
    LegacyNetworkPath(
        location="backend/api/system_health_routes.py",
        client="httpx.AsyncClient() with no explicit timeout",
        finding="A health probe constructed with no timeout argument, so it "
        "takes the library default rather than a stated one. Destination is "
        "internal.",
        tls_verified=True,
        ssrf_controls="none needed; destination is not caller-controlled",
        follows_redirects=False,
        timeout="httpx library default, not explicit",
        inherits_env_proxy=True,
        caller_controls_url=False,
        hazard=False,
        disposition="Health checking, not execution. Noted because §14 of the "
        "directive forbids library-default timeouts in the fabric — this is "
        "outside the fabric, and is recorded so the exception is deliberate.",
    ),
    LegacyNetworkPath(
        location="backend/providers/tavily_provider.py, backend/llm_provider/**",
        client="httpx",
        finding="Model and search provider clients dialling fixed vendor APIs.",
        tls_verified=True,
        ssrf_controls="none; destinations are fixed",
        follows_redirects=False,
        timeout="varies by provider",
        inherits_env_proxy=True,
        caller_controls_url=False,
        hazard=False,
        disposition="Model-provider traffic, not capability execution. Not a "
        "transport-fabric target: these are CortexPrime's own dependencies "
        "rather than tenant-directed provider calls.",
    ),
    LegacyNetworkPath(
        location="backend/infrastructure/vault/client.py",
        client="hvac (corrected in Phase 4.4; this entry previously said httpx)",
        finding="Reads ``VAULT_ADDR``/``VAULT_TOKEN`` from the environment, "
        "defaulting to ``http://localhost:8200`` — plaintext loopback. It "
        "is an ``hvac.Client``, which does its own HTTP with its own TLS and "
        "proxy handling, so wrapping it would have added a second outbound "
        "path rather than removing one.",
        tls_verified=True,
        ssrf_controls="none; destination is configuration",
        follows_redirects=False,
        timeout="client default",
        inherits_env_proxy=True,
        caller_controls_url=False,
        hazard=False,
        disposition="**Superseded in Phase 4.4.** ``VaultCredentialAdapter`` "
        "speaks KV v2 over the transport broker, so the credential path has "
        "the same address policy, DNS pinning and budgets as every provider "
        "call. Production configuration refuses a plaintext Vault address "
        "outright rather than defaulting to one.",
    ),
)


#: **Phase 4.4 correction.** ``HttpxTransportAdapter`` passes
#: ``trust_env=policy.proxy.trust_environment``, which defaults to ``False``,
#: so the governed path no longer inherits process proxy variables. The
#: finding below still describes every *V1* client.
#:
#: Every V1 httpx client in the repository is constructed with ``trust_env``
#: at its default, which is ``True``. That means all of them silently honour
#: ``HTTP_PROXY``, ``HTTPS_PROXY`` and ``ALL_PROXY`` from the process
#: environment.
#:
#: Recorded as a single cross-cutting finding rather than repeated per entry: a
#: proxy variable set in a deployment changes the real destination of every
#: outbound request at once, and no client in the repository opts out. The
#: transport fabric's ``ProxyPolicy.trust_environment`` defaults to ``False`` and
#: adapters are required to honour it, which is the fix — for traffic that has
#: migrated.
ENVIRONMENT_PROXY_FINDING = (
    "All V1 httpx clients use trust_env=True (the default) and therefore honour "
    "HTTP_PROXY/HTTPS_PROXY/ALL_PROXY silently. The transport fabric defaults "
    "trust_environment to False; V1 paths remain affected until migrated."
)

#: No ``verify=False``, no ``ssl._create_unverified_context``, and no
#: ``check_hostname = False`` appears anywhere in the repository. Searched
#: rather than assumed. TLS and hostname verification are therefore on across
#: every existing path, which is the one thing V1 gets right by default.
TLS_FINDING = (
    "No TLS verification bypass exists anywhere in the repository (searched for "
    "verify=False, _create_unverified_context, check_hostname). Every V1 client "
    "verifies certificates and hostnames by library default."
)


def hazards() -> tuple:
    """Paths needing a decision before Phase 4.3 rather than during it."""
    return tuple(p for p in LEGACY_NETWORK_PATHS if p.hazard)


def caller_controlled_paths() -> tuple:
    """Paths where a caller chooses the destination. The SSRF-relevant set."""
    return tuple(p for p in LEGACY_NETWORK_PATHS if p.caller_controls_url)


def summary() -> dict:
    """A queryable form, so the gap is inspectable rather than only readable."""
    return {
        "total": len(LEGACY_NETWORK_PATHS),
        "hazards": [p.location for p in hazards()],
        "caller_controlled_destinations": [
            p.location for p in caller_controlled_paths()
        ],
        "follow_redirects": [
            p.location for p in LEGACY_NETWORK_PATHS if p.follows_redirects
        ],
        "inherit_environment_proxy": [
            p.location for p in LEGACY_NETWORK_PATHS if p.inherits_env_proxy
        ],
        "migrated_to_fabric": 1,
        "production_transport": (
            "HttpxTransportAdapter (Phase 4.4): pinned addresses, "
            "sni_hostname verification, trust_env from policy, retries=0, "
            "redirects off, separate connect/read/write/pool timeouts "
            "clamped to the authority window, bounded response reads"
        ),
        "tls_finding": TLS_FINDING,
        "proxy_finding": ENVIRONMENT_PROXY_FINDING,
        "note": (
            "None of these bypasses the invocation gateway; every V1 execution "
            "route is gated off by default (ADR-039). They bypass the transport "
            "fabric: they dial by their own means with no address policy."
        ),
    }
