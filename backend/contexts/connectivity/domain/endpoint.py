"""Where a discovered capability was observed, and what is safe to record.

Scope, stated first
---------------------
**Nothing in this phase fetches anything.** There is no HTTP client, no socket,
no DNS lookup anywhere in the discovery implementation. An endpoint here is
*provenance* -- a record of where an observation came from -- not something the
platform dials.

That matters for how to read this module. The validation below is not an SSRF
defence in the usual sense, because there is no request to defend. It is the
structural boundary that has to be right **before** anything is ever fetched, so
that the day a transport is added it cannot be handed a `file://` URL or an
endpoint with a password baked into it.

Why this exists at all rather than reusing something
------------------------------------------------------
The repository's only SSRF handling is a regex over prompt text inside V1's
``guardrails_engine`` -- it inspects model output for private-range URLs. It is
not a network-security primitive, it is not reusable, and it lives outside
``contracts/`` and ``platform/``, so a bounded context may not import it
(Constitution S2).

So this is the smallest explicit seam rather than a parallel framework: it uses
only the standard library, it makes structural judgements (scheme, embedded
credentials, address family), and it deliberately does **not** decide policy.

Where policy belongs
----------------------
``is_private`` is *recorded*, not refused. A platform-internal MCP server on
``10.0.x.x`` is an entirely legitimate thing to discover, and a rule that
refused it here would be wrong for half of all deployments. Whether a given
endpoint may be contacted is a governance decision that needs to know the
deployment, and this module hands governance the fact it needs to make it.
"""

from __future__ import annotations

import ipaddress
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit

from backend.contracts.errors import ContractViolation

__all__ = ["DiscoveryEndpoint", "PERMITTED_SCHEMES", "UnsafeEndpoint"]

#: Schemes a capability source may be described by.
#:
#: ``file`` and ``data`` are absent deliberately: a discovery source that can be
#: pointed at the local filesystem turns "add a source" into "read any file this
#: process can read". ``stdio`` is included because MCP servers are commonly run
#: as local subprocesses, and refusing to *describe* one would mean the most
#: ordinary MCP deployment could not be recorded at all.
PERMITTED_SCHEMES = frozenset({"https", "http", "stdio"})

_MAX_ENDPOINT_LENGTH = 2048


class UnsafeEndpoint(ContractViolation):
    """An endpoint this context refuses to record."""

    def __init__(self, value: str, reason: str) -> None:
        super().__init__(f"cannot record endpoint {value[:120]!r}: {reason}")
        self.value = value
        self.reason = reason


def _is_private_host(host: str) -> bool:
    """Whether the host names a private, loopback, or link-local address.

    Literal addresses only. Resolving a name to find out would be a DNS lookup,
    and this module performs no network operations -- including that one. A
    hostname that resolves into a private range is therefore reported as public
    here, which is a real limitation and is why this is a recorded fact rather
    than a security control.
    """
    if not host:
        return False
    cleaned = host.strip("[]").lower()
    if cleaned in {"localhost", "localhost.localdomain"}:
        return True
    try:
        address = ipaddress.ip_address(cleaned)
    except ValueError:
        return False
    return (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
    )


@dataclass(frozen=True)
class DiscoveryEndpoint:
    """A validated record of where an observation came from."""

    value: str
    scheme: str
    host: Optional[str]
    port: Optional[int]
    is_private: bool
    is_loopback_scheme: bool

    def __post_init__(self) -> None:
        if not isinstance(self.value, str) or not self.value.strip():
            raise UnsafeEndpoint(str(self.value), "an endpoint must be non-blank text")

    @property
    def is_remote(self) -> bool:
        return self.scheme in {"http", "https"}

    @property
    def is_plaintext(self) -> bool:
        """Whether a future fetch would be unencrypted.

        Recorded, not refused: a local ``http://`` MCP server inside a cluster is
        ordinary, and refusing it here would push deployments toward disabling
        the check rather than fixing the transport.
        """
        return self.scheme == "http"

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "scheme": self.scheme,
            "host": self.host,
            "port": self.port,
            "is_private": self.is_private,
            "is_remote": self.is_remote,
            "is_plaintext": self.is_plaintext,
        }

    @classmethod
    def parse(cls, value: str) -> "DiscoveryEndpoint":
        """Validate structurally and record what was found.

        Refuses only what is structurally unsafe to hold at all. Everything that
        is merely *risky* -- private ranges, plaintext -- is recorded as a fact
        for governance to weigh.
        """
        if not isinstance(value, str) or not value.strip():
            raise UnsafeEndpoint(str(value), "an endpoint must be non-blank text")
        text = value.strip()
        if len(text) > _MAX_ENDPOINT_LENGTH:
            raise UnsafeEndpoint(
                text, f"longer than {_MAX_ENDPOINT_LENGTH} characters"
            )
        if any(ch in text for ch in ("\n", "\r", "\t", "\x00")):
            raise UnsafeEndpoint(
                text,
                "contains control characters; these are how a single field "
                "becomes two when something later writes it into a header or a log",
            )

        parts = urlsplit(text)
        scheme = (parts.scheme or "").lower()
        if not scheme:
            raise UnsafeEndpoint(
                text,
                "no scheme; an endpoint without one is ambiguous and something "
                "downstream will pick a default nobody chose",
            )
        if scheme not in PERMITTED_SCHEMES:
            raise UnsafeEndpoint(
                text,
                f"scheme {scheme!r} is not permitted (allowed: "
                f"{', '.join(sorted(PERMITTED_SCHEMES))}). A source that can name "
                "a file or data URL turns adding a source into reading local files",
            )

        # Credentials in a URL end up in logs, in events, and in the registry.
        if parts.username or parts.password or "@" in parts.netloc:
            raise UnsafeEndpoint(
                text,
                "contains embedded credentials; this context stores no secrets, "
                "and an endpoint recorded here is written to events and audit "
                "records that are deliberately widely readable",
            )

        if scheme == "stdio":
            # A locally-launched MCP server. There is no host to reason about,
            # and it is local by definition.
            return cls(
                value=text,
                scheme=scheme,
                host=None,
                port=None,
                is_private=True,
                is_loopback_scheme=True,
            )

        host = (parts.hostname or "").lower()
        if not host:
            raise UnsafeEndpoint(text, "no host")

        try:
            port = parts.port
        except ValueError as exc:
            raise UnsafeEndpoint(text, "invalid port") from exc

        return cls(
            value=text,
            scheme=scheme,
            host=host,
            port=port,
            is_private=_is_private_host(host),
            is_loopback_scheme=False,
        )
