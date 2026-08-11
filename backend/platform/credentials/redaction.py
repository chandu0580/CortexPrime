"""Redaction: the last line, for everything the type system cannot reach.

``CredentialMaterial`` cannot be serialised, formatted, or compared, so a secret
held *in the fabric* cannot escape by accident. This module covers the rest: a
provider that returns a token inside a JSON error body, an exception whose text
happens to contain a bearer header, a config dump, a metrics label.

Two mechanisms, and they are different
----------------------------------------
``redact_mapping`` works by **key**. Anything whose key looks like a secret is
replaced whatever its value is. This is the reliable one: keys are ours, are
stable, and are enumerable.

``scrub_text`` works by **pattern**, over free text where there is no key to
inspect — exception messages, provider error bodies. It is best-effort by nature
and is documented as such. Pattern matching cannot be complete, so it never
substitutes for the key-based path and never for not putting secrets in text.

Why redact at all when nothing should be there
------------------------------------------------
Because "should" is doing a lot of work in that sentence. Provider responses are
written by other people; exception messages are assembled from strings nobody
audited. This exists for the material that arrives from outside the boundary the
type system defends.
"""

from __future__ import annotations

import re
from typing import Any, Mapping

from backend.platform.credentials.material import REDACTED

__all__ = [
    "SENSITIVE_KEY_FRAGMENTS",
    "NON_SENSITIVE_KEYS",
    "is_sensitive_key",
    "redact_mapping",
    "scrub_text",
    "safe_exception_text",
]

#: Key fragments that mean "this holds a secret". Matched case-insensitively as
#: substrings, so ``github_api_key``, ``X-Api-Key`` and ``apiKey`` all match.
#: Deliberately over-broad: a redacted field that did not need redacting costs a
#: debugging session, and the reverse costs a breach.
SENSITIVE_KEY_FRAGMENTS = (
    "secret",
    "token",
    "password",
    "passwd",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
    "privatekey",
    "credential",
    "authorization",
    "auth_header",
    "session_key",
    "client_secret",
    "refresh",
    "signature",
    "cookie",
    "bearer",
    "salt",
    "passphrase",
)

#: Shapes that are recognisably secret in free text. Ordered longest-first so a
#: broader pattern cannot consume part of a narrower one and leave a fragment.
_TEXT_PATTERNS = (
    # Authorization headers, with or without a scheme.
    re.compile(r"(?i)\b(authorization\s*[:=]\s*)(\S+)"),
    re.compile(r"(?i)\b(bearer|basic|token)\s+([A-Za-z0-9._\-+/=]{12,})"),
    # key=value / "key": "value" in serialised bodies.
    re.compile(
        r"(?i)([\"']?(?:{fragments})[\"']?\s*[:=]\s*[\"']?)([^\s\"',}}\)]{{6,}})".format(
            fragments="|".join(
                f for f in SENSITIVE_KEY_FRAGMENTS if f not in {"salt", "cookie"}
            )
        )
    ),
    # Provider-shaped tokens that are unmistakable on sight.
    re.compile(r"\b(gh[pousr]_)([A-Za-z0-9]{16,})"),
    re.compile(r"\b(xox[baprs]-)([A-Za-z0-9\-]{10,})"),
    re.compile(r"\b(sk-)([A-Za-z0-9]{16,})"),
    re.compile(r"\b(AKIA)([0-9A-Z]{12,})"),
    # PEM blocks -- the whole body, not just the header.
    re.compile(
        r"(-----BEGIN [A-Z ]*PRIVATE KEY-----)(.*?)(-----END [A-Z ]*PRIVATE KEY-----)",
        re.S,
    ),
)


#: Keys that contain a sensitive fragment but are known **not** to be secret.
#: Digests, policy effects and expiry timestamps about an authorization are the
#: substance of an audit record, and redacting them would take the fidelity out
#: of exactly the trail somebody reads during an incident.
#:
#: Deliberately an explicit list rather than a pattern: every entry is a claim
#: that a specific named field is safe, made once, reviewably. A pattern here
#: would eventually un-redact something nobody intended.
NON_SENSITIVE_KEYS = frozenset(
    {
        "authorization_digest",
        "authorization_effect",
        "authorization_expires_at",
        "authorization_policy_version",
        "authorization_outcome",
        "credential_ref",
        "credential_fingerprint",
        "credential_type",
        "credential_scope",
        "credential_expires_at",
        "credential_required",
        "credential_state",
        "signature_algorithm",
    }
)


def is_sensitive_key(key: Any) -> bool:
    """Whether a mapping key names something that must never be shown.

    Separators are normalised away before matching, so ``X-Api-Key``,
    ``api_key``, ``apiKey`` and ``API KEY`` all match the same fragment. Without
    that, a header name written with hyphens slips past a fragment written with
    underscores — which is exactly how ``X-Api-Key`` reaches a log while
    ``api_key`` is redacted beside it.
    """
    if not isinstance(key, str):
        return False
    if key.lower() in NON_SENSITIVE_KEYS:
        return False
    normalised = re.sub(r"[-_\s.]", "", key.lower())
    return any(
        re.sub(r"[-_\s.]", "", fragment) in normalised
        for fragment in SENSITIVE_KEY_FRAGMENTS
    )


def redact_mapping(data: Any, *, depth: int = 0) -> Any:
    """Replace every sensitive value in a nested structure. Key-based.

    Recurses through dicts, lists and tuples so a token nested three levels
    inside a provider response is still caught. Depth-bounded because a cyclic
    or adversarially-deep structure from a provider must not be able to exhaust
    the stack inside an audit path — the point of failure would be the logging,
    which is the worst possible place to fail.

    Returns plain containers rather than mutating: the caller keeps its object,
    and the redacted copy is what gets written down.
    """
    if depth > 12:
        return "<truncated: structure too deep to redact safely>"

    if isinstance(data, Mapping):
        return {
            key: (
                REDACTED
                if is_sensitive_key(key)
                else redact_mapping(value, depth=depth + 1)
            )
            for key, value in data.items()
        }
    if isinstance(data, (list, tuple)):
        rendered = [redact_mapping(item, depth=depth + 1) for item in data]
        return type(data)(rendered) if isinstance(data, tuple) else rendered
    if isinstance(data, str):
        return scrub_text(data)
    return data


def scrub_text(text: str, *, max_length: int = 2000) -> str:
    """Best-effort removal of secret-shaped substrings from free text.

    **Best-effort, and stated as such.** Pattern matching over text somebody else
    wrote cannot be complete: a token with no recognisable prefix, in a field
    with no recognisable name, will pass through. This is the last line, not the
    defence — the defence is that secrets do not enter text in the first place.

    Length-bounded so a provider returning a megabyte of HTML cannot turn one
    audit write into a memory event.
    """
    if not isinstance(text, str):
        return text
    scrubbed = text
    for pattern in _TEXT_PATTERNS:
        if pattern.groups >= 3:
            scrubbed = pattern.sub(rf"\1{REDACTED}\3", scrubbed)
        else:
            scrubbed = pattern.sub(rf"\1{REDACTED}", scrubbed)
    if len(scrubbed) > max_length:
        scrubbed = scrubbed[:max_length] + "…<truncated>"
    return scrubbed


def safe_exception_text(exc: BaseException, *, max_length: int = 300) -> str:
    """An exception rendered for a caller. Type name plus scrubbed message.

    Never ``str(exc)`` directly on a path that could carry credential material:
    an HTTP client's exception routinely contains the request it was making,
    headers included. The type name is always safe and is usually the part that
    was actually diagnostic.
    """
    return f"{type(exc).__name__}: {scrub_text(str(exc), max_length=max_length)}"
