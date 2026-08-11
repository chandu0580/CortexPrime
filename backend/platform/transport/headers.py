"""Header handling: normalisation, forbidden names, and injection defence.

Why headers get their own module
----------------------------------
Headers are the one part of a request where a caller-supplied string becomes
protocol syntax. A newline in a header value does not corrupt a field — it ends
the field and starts another one, which is request smuggling and response
splitting depending on which direction it travels.

Two rules, and both are structural
------------------------------------
**No control characters, anywhere.** Checked over names and values before
anything is assembled.

**Credential headers cannot be supplied by a caller.** ``Authorization`` and
``Proxy-Authorization`` are refused from caller input entirely. They are produced
at the final boundary from material the credential fabric issued, and nowhere
else — a caller that could set one would be authenticating as somebody the
credential fabric never authorized.

Normalisation is security, not tidiness
-----------------------------------------
``Authorization``, ``authorization`` and ``AUTHORIZATION`` are one header to HTTP
and three strings to a naive filter. Names are lowercased before every check, so
a forbidden-name rule cannot be walked past by changing case.
"""

from __future__ import annotations

from typing import Mapping, Optional

from backend.contracts.errors import ContractViolation

__all__ = [
    "FORBIDDEN_CALLER_HEADERS",
    "HOP_BY_HOP_HEADERS",
    "normalise_header_name",
    "validate_caller_headers",
    "HeaderRefused",
]


class HeaderRefused(ContractViolation):
    """A header the transport will not send."""

    def __init__(self, name: str, reason: str) -> None:
        # The *name* only. A refused header's value is exactly the thing most
        # likely to be a secret, and this message reaches logs.
        super().__init__(f"header {name[:64]!r} refused: {reason}")
        self.header_name = name
        self.reason = reason


#: Headers a caller may never set. Each one would let caller input replace
#: something the fabric is responsible for producing.
FORBIDDEN_CALLER_HEADERS = frozenset(
    {
        # Authentication is the credential fabric's, exclusively.
        "authorization",
        "proxy-authorization",
        "cookie",
        "set-cookie",
        # Framing. A caller-set Content-Length or Transfer-Encoding is the
        # classic request-smuggling pair -- two disagreeing framing headers make
        # one request look like two to an intermediary.
        "content-length",
        "transfer-encoding",
        "connection",
        "upgrade",
        "te",
        "trailer",
        # Destination. A caller-set Host reaches a different virtual host than
        # the one the endpoint policy judged.
        "host",
        # Forwarding headers are trusted by things downstream; letting a caller
        # write them is letting a caller claim to be somebody else's proxy.
        "x-forwarded-for",
        "x-forwarded-host",
        "x-forwarded-proto",
        "forwarded",
    }
)

#: Headers that belong to one hop and must never be copied onward — notably
#: across a redirect, where forwarding them leaks connection state.
HOP_BY_HOP_HEADERS = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)

_MAX_NAME_LENGTH = 128
_MAX_VALUE_LENGTH = 8192

# RFC 7230 token characters. Anything outside is not a header name, whatever the
# caller believes.
_NAME_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz0123456789!#$%&'*+-.^_`|~"
)


def normalise_header_name(name: object) -> str:
    """Lowercase and validate a header name.

    Lowercasing first is what makes every later comparison total: a
    forbidden-name check against ``Authorization`` that misses ``AUTHORIZATION``
    is not a check.
    """
    if not isinstance(name, str) or not name:
        raise HeaderRefused(str(name), "a header name must be non-empty text")
    if len(name) > _MAX_NAME_LENGTH:
        raise HeaderRefused(name, f"longer than {_MAX_NAME_LENGTH} characters")
    lowered = name.lower()
    for character in lowered:
        if character not in _NAME_CHARS:
            raise HeaderRefused(
                name,
                "contains a character that is not a valid header-name token; a "
                "name with a colon, a space or a newline in it is two headers",
            )
    return lowered


def _validate_value(name: str, value: object) -> str:
    if not isinstance(value, str):
        raise HeaderRefused(name, "a header value must be text")
    if len(value) > _MAX_VALUE_LENGTH:
        raise HeaderRefused(name, f"value longer than {_MAX_VALUE_LENGTH} characters")
    for character in value:
        code = ord(character)
        # Horizontal tab is legal in a value; everything else below 0x20, plus
        # DEL, is not. CR and LF are the injection characters and are covered.
        if (code < 0x20 and character != "\t") or code == 0x7F:
            raise HeaderRefused(
                name,
                "value contains a control character; a newline here does not "
                "corrupt the field, it ends it and starts another one",
            )
    return value


def validate_caller_headers(
    headers: Optional[Mapping[str, str]],
    *,
    max_count: int,
    max_total_bytes: int,
) -> dict:
    """Normalise and check headers a caller supplied. Refuses, never sanitises.

    Refusing rather than stripping is deliberate. Silently dropping a caller's
    ``Authorization`` header means the caller believes it was sent and the
    request goes out unauthenticated, which fails in a way nobody can read. An
    explicit refusal says what happened.
    """
    if not headers:
        return {}
    if len(headers) > max_count:
        raise HeaderRefused(
            "<request>", f"more than {max_count} headers"
        )

    validated: dict = {}
    total = 0
    for raw_name, raw_value in headers.items():
        name = normalise_header_name(raw_name)
        if name in FORBIDDEN_CALLER_HEADERS:
            raise HeaderRefused(
                name,
                "this header may not be supplied by a caller; it is produced at "
                "the transport boundary from what the credential fabric issued, "
                "and a caller-set value would authenticate as somebody nobody "
                "authorized",
            )
        value = _validate_value(name, raw_value)
        if name in validated:
            # Duplicate security-relevant headers are how two intermediaries
            # disagree about one request.
            raise HeaderRefused(name, "supplied more than once")
        validated[name] = value
        total += len(name) + len(value) + 4
        if total > max_total_bytes:
            raise HeaderRefused(
                "<request>", f"headers exceed {max_total_bytes} bytes in total"
            )
    return validated
