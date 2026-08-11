"""The endpoint a transport may dial. Parsed once, normalised, and refusing.

Different from ``DiscoveryEndpoint``, deliberately
----------------------------------------------------
``connectivity.domain.endpoint.DiscoveryEndpoint`` records where an observation
came from. It permits ``http`` and ``stdio``, and it *records* ``is_private``
rather than refusing it — correctly, because a platform-internal MCP server on
``10.0.x.x`` is legitimate to discover and refusing it there would be wrong for
half of all deployments.

This one is dialled. So it refuses rather than records, and the two are separate
types because they give different answers to the same input on purpose. Merging
them would force one of the two to be wrong.

The structural parsing is shared
----------------------------------
The *checks they agree on* — length, control characters, scheme presence,
embedded credentials, port validity — are one function, ``parse_url_structure``,
used by both. Security-sensitive parsing written twice is security-sensitive
parsing that gets fixed once.

Normalisation is part of the security boundary
------------------------------------------------
An endpoint that compares unequal to itself cannot be allow-listed, cannot be
pooled safely, and cannot be audited coherently. So the host is lowercased, the
trailing root dot removed, a default port made explicit, and the path normalised.
Two spellings of one destination become one string, which is what makes every
later comparison mean something.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlsplit, urlunsplit

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionEnvironment
from backend.contracts.transport import TransportKind

__all__ = [
    "TransportEndpoint",
    "UrlStructure",
    "parse_url_structure",
    "UnsafeTransportEndpoint",
    "DIALLABLE_SCHEMES",
    "MAX_ENDPOINT_LENGTH",
]

#: Schemes a transport may dial. ``http`` is present but is **refused by policy
#: unless explicitly permitted** — see ``ConnectionPolicy``. It is here rather
#: than absent so that a plaintext endpoint produces "policy refused plaintext"
#: rather than "unknown scheme", which is a materially more useful refusal.
#:
#: ``file``, ``data``, ``javascript``, ``ftp``, ``gopher`` and everything else are
#: absent: a transport that can name a file turns "call a provider" into "read
#: any file this process can read", and ``gopher://`` in particular is the
#: classic SSRF protocol-smuggling vector.
DIALLABLE_SCHEMES = frozenset({"https", "http"})

MAX_ENDPOINT_LENGTH = 2048
_MAX_HOST_LENGTH = 253
_MAX_LABEL_LENGTH = 63
_DEFAULT_PORTS = {"https": 443, "http": 80}


class UnsafeTransportEndpoint(ContractViolation):
    """An endpoint the transport refuses to dial."""

    def __init__(self, value: str, reason: str) -> None:
        # Truncated: an endpoint is caller-influenced text and this message
        # reaches logs.
        super().__init__(f"cannot dial endpoint {value[:120]!r}: {reason}")
        self.value = value
        self.reason = reason


@dataclass(frozen=True)
class UrlStructure:
    """The structural facts of a URL, after the checks every consumer shares."""

    text: str
    scheme: str
    host: Optional[str]
    port: Optional[int]
    path: str
    query: str

    def to_dict(self) -> dict:
        return {
            "scheme": self.scheme,
            "host": self.host,
            "port": self.port,
            "path": self.path,
        }


def parse_url_structure(
    value: str,
    *,
    permitted_schemes: frozenset,
    max_length: int = MAX_ENDPOINT_LENGTH,
    require_host: bool = True,
) -> UrlStructure:
    """The structural checks every endpoint consumer needs. One implementation.

    Refuses what is unsafe to *hold*, regardless of what the caller intends to do
    with it. Policy — plaintext, private ranges, environment — is the caller's,
    because those answers differ legitimately between a discovery record and a
    destination about to be dialled.
    """
    if not isinstance(value, str) or not value.strip():
        raise UnsafeTransportEndpoint(str(value), "an endpoint must be non-blank text")
    text = value.strip()

    if len(text) > max_length:
        raise UnsafeTransportEndpoint(
            text,
            f"longer than {max_length} characters; an unbounded URL is an "
            "unbounded allocation in every parser that touches it",
        )
    # Control characters are how one field becomes two in a header, a log line,
    # or a request. Checked over the whole string before any parsing, because a
    # parser may silently drop them and hand back something that looks clean.
    for character in text:
        if ord(character) < 0x20 or ord(character) == 0x7F:
            raise UnsafeTransportEndpoint(
                text,
                "contains a control character; these are how a single field "
                "becomes two when something later writes it into a header",
            )

    parts = urlsplit(text)
    scheme = (parts.scheme or "").lower()
    if not scheme:
        raise UnsafeTransportEndpoint(
            text,
            "no scheme; something downstream would pick a default nobody chose",
        )
    if scheme not in permitted_schemes:
        raise UnsafeTransportEndpoint(
            text,
            f"scheme {scheme!r} is not permitted (allowed: "
            f"{', '.join(sorted(permitted_schemes))})",
        )

    # Credentials in a URL reach logs, events, audit records and pool keys.
    if parts.username or parts.password or "@" in parts.netloc:
        raise UnsafeTransportEndpoint(
            text,
            "contains embedded credentials; the credential fabric is the only "
            "way a secret reaches a provider, and a URL is written down in "
            "places a secret must never be",
        )

    host: Optional[str] = None
    if require_host or parts.netloc:
        raw_host = parts.hostname
        if not raw_host:
            raise UnsafeTransportEndpoint(text, "no host")
        host = raw_host.lower().rstrip(".")
        if not host or len(host) > _MAX_HOST_LENGTH:
            raise UnsafeTransportEndpoint(
                text, f"host is empty or longer than {_MAX_HOST_LENGTH} characters"
            )
        # A bracketed IPv6 literal has no labels to check.
        if not raw_host.startswith("[") and ":" not in host:
            for label in host.split("."):
                if not label or len(label) > _MAX_LABEL_LENGTH:
                    raise UnsafeTransportEndpoint(
                        text, "host contains an empty or over-long label"
                    )

    try:
        port = parts.port
    except ValueError as exc:
        # urlsplit raises on a non-numeric or out-of-range port only when asked.
        raise UnsafeTransportEndpoint(text, "invalid port") from exc
    if port is not None and not (1 <= port <= 65535):
        raise UnsafeTransportEndpoint(text, f"port {port} is out of range")

    return UrlStructure(
        text=text,
        scheme=scheme,
        host=host,
        port=port,
        path=parts.path or "/",
        query=parts.query or "",
    )


@dataclass(frozen=True)
class TransportEndpoint:
    """A normalised destination, safe to compare, pool by, and audit."""

    scheme: str
    host: str
    port: int
    path: str
    transport: TransportKind
    environment: ExecutionEnvironment
    query: str = ""
    """Kept, and **never logged**. A query string routinely carries a token,
    a signature or a session id -- ``normalised`` and ``to_dict`` both omit it,
    and only ``dial_target`` reassembles it."""

    def __post_init__(self) -> None:
        for label in ("scheme", "host", "path"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value:
                raise ContractViolation(f"{label} must be non-empty text")
        if self.scheme != self.scheme.lower() or self.host != self.host.lower():
            raise ContractViolation(
                "an endpoint must be normalised before construction; two "
                "spellings of one destination cannot be compared, pooled, or "
                "allow-listed"
            )
        if not (1 <= self.port <= 65535):
            raise ContractViolation(f"port {self.port} is out of range")
        if not isinstance(self.transport, TransportKind):
            raise ContractViolation("transport must be a TransportKind")
        if not isinstance(self.environment, ExecutionEnvironment):
            raise ContractViolation(
                "an endpoint must state its environment; a production endpoint "
                "selected for a development binding is the mistake this field "
                "exists to make impossible"
            )

    # -- identity -------------------------------------------------------

    @property
    def is_plaintext(self) -> bool:
        return self.scheme == "http"

    @property
    def authority(self) -> str:
        """``host:port``. IPv6 literals are bracketed so the string round-trips."""
        host = f"[{self.host}]" if ":" in self.host else self.host
        return f"{host}:{self.port}"

    @property
    def normalised(self) -> str:
        """The canonical form. **Query deliberately excluded** -- this is logged."""
        return f"{self.scheme}://{self.authority}{self.path}"

    def dial_target(self) -> str:
        """The full URL including query. For dialling only, never for a log."""
        host = f"[{self.host}]" if ":" in self.host else self.host
        return urlunsplit((self.scheme, f"{host}:{self.port}", self.path, self.query, ""))

    def same_origin_as(self, other: "TransportEndpoint") -> bool:
        """Scheme, host and port all equal. What a redirect is judged against.

        Path is excluded and query is excluded: a redirect within one origin
        keeps the security properties that were checked, and one that crosses
        any of the three does not — which is exactly when credentials must not
        follow.
        """
        return (
            self.scheme == other.scheme
            and self.host == other.host
            and self.port == other.port
        )

    def to_dict(self) -> dict:
        """Safe for audit and metrics. No query string, ever."""
        return {
            "scheme": self.scheme,
            "host": self.host,
            "port": self.port,
            "path": self.path,
            "transport": self.transport.value,
            "environment": self.environment.value,
            "normalised": self.normalised,
            "plaintext": self.is_plaintext,
        }

    # -- construction ----------------------------------------------------

    @classmethod
    def parse(
        cls,
        value: str,
        *,
        transport: TransportKind,
        environment: ExecutionEnvironment,
    ) -> "TransportEndpoint":
        """Parse and normalise, refusing anything structurally unsafe to dial.

        Policy is *not* applied here — plaintext and private destinations are
        parsed successfully and refused by ``ConnectionPolicy``. Keeping the two
        apart means a policy refusal can say which rule refused it, rather than
        every problem arriving as "unparseable".
        """
        if not isinstance(transport, TransportKind):
            raise ContractViolation("transport must be a TransportKind")
        if transport is TransportKind.MCP_STDIO:
            raise UnsafeTransportEndpoint(
                str(value),
                "stdio transports have no network endpoint; a stdio target names "
                "a local process and is governed by the worker sandbox boundary, "
                "not by an address policy",
            )

        structure = parse_url_structure(value, permitted_schemes=DIALLABLE_SCHEMES)
        host = structure.host or ""
        port = structure.port or _DEFAULT_PORTS[structure.scheme]

        # Normalise the path so ``/a/../b`` and ``/b`` do not become two
        # allow-list entries for one destination.
        path = structure.path or "/"
        if not path.startswith("/"):
            path = "/" + path

        return cls(
            scheme=structure.scheme,
            host=host,
            port=port,
            path=path,
            query=structure.query,
            transport=transport,
            environment=environment,
        )
