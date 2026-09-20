"""The stable connector error taxonomy (Phase 11.1-K).

Providers fail in provider-specific ways; the fabric already classifies them
into ``ProviderFailure`` (what went wrong at the provider), the gateway into
``InvocationRefusal`` (what the platform refused), the credential broker into
``CredentialRefusal``, and verification into verdicts. Every one of those is
right for the layer that raises it and wrong to show a user or an agent: an
operator asking "why did the connector fail" should get one of twelve stable
answers, the same for every connector.

This module is that answer -- a pure mapping, not a new error system. It never
replaces the detailed classification (which stays on the execution record and
in the audit trail); it names the class the product API, connector health and
metrics speak in.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

__all__ = ["ConnectorErrorClass", "classify_provider_failure", "classify_failure_text",
           "classify_status"]


class ConnectorErrorClass(str, Enum):
    AUTHENTICATION_FAILED = "authentication_failed"
    AUTHORIZATION_DENIED = "authorization_denied"
    NOT_FOUND = "not_found"
    INVALID_REQUEST = "invalid_request"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    NETWORK_FAILURE = "network_failure"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    CONFLICT = "conflict"
    VERIFICATION_FAILED = "verification_failed"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    INTERNAL_ERROR = "internal_error"


_E = ConnectorErrorClass

_PROVIDER_FAILURE = {
    "authentication_failure": _E.AUTHENTICATION_FAILED,
    "authorization_failure": _E.AUTHORIZATION_DENIED,
    "not_found": _E.NOT_FOUND,
    "conflict": _E.CONFLICT,
    "precondition_failed": _E.CONFLICT,
    "validation_failure": _E.INVALID_REQUEST,
    "rate_limited": _E.RATE_LIMITED,
    "quota_exceeded": _E.RATE_LIMITED,
    "unavailable": _E.PROVIDER_UNAVAILABLE,
    "timeout": _E.TIMEOUT,
    "cancelled": _E.TIMEOUT,
    "protocol_error": _E.NETWORK_FAILURE,
    "malformed_response": _E.PROVIDER_UNAVAILABLE,
    "response_too_large": _E.PROVIDER_UNAVAILABLE,
    "transport_refused": _E.NETWORK_FAILURE,
    "credential_refused": _E.AUTHENTICATION_FAILED,
    "operation_not_supported": _E.INVALID_REQUEST,
    "provider_mismatch": _E.INTERNAL_ERROR,
    "adapter_unavailable": _E.PROVIDER_UNAVAILABLE,
    "contract_mismatch": _E.INTERNAL_ERROR,
    "effect_exceeded": _E.INTERNAL_ERROR,
    "unknown_outcome": _E.INTERNAL_ERROR,
}


def classify_provider_failure(failure: Any) -> ConnectorErrorClass:
    """A ``ProviderFailure`` (or its value) as a stable class."""
    value = getattr(failure, "value", failure)
    return _PROVIDER_FAILURE.get(str(value or ""), _E.INTERNAL_ERROR)


def classify_status(status: Optional[int]) -> Optional[ConnectorErrorClass]:
    """An HTTP status the provider answered, as a stable class (``None`` = success)."""
    if status is None or 200 <= status < 300:
        return None
    return {400: _E.INVALID_REQUEST, 401: _E.AUTHENTICATION_FAILED, 403: _E.AUTHORIZATION_DENIED,
            404: _E.NOT_FOUND, 408: _E.TIMEOUT, 409: _E.CONFLICT, 410: _E.CONFLICT,
            412: _E.CONFLICT, 422: _E.CONFLICT, 429: _E.RATE_LIMITED, 504: _E.TIMEOUT,
            }.get(status, _E.PROVIDER_UNAVAILABLE if status >= 500 else _E.INVALID_REQUEST)


# Ordered: the first matching fragment wins. Fragments are the platform's own
# refusal vocabulary (gateway, credential broker, transport, adapter), never
# provider free text a provider could shape.
_TEXT = (
    ("rate_limited", _E.RATE_LIMITED), ("rate limit", _E.RATE_LIMITED),
    ("verification_failed", _E.VERIFICATION_FAILED),
    ("insufficient_evidence", _E.INSUFFICIENT_EVIDENCE),
    ("unauthorized", _E.AUTHENTICATION_FAILED), ("authentication", _E.AUTHENTICATION_FAILED),
    ("credential", _E.AUTHENTICATION_FAILED), ("vault refused", _E.AUTHENTICATION_FAILED),
    ("forbidden", _E.AUTHORIZATION_DENIED), ("authorization refused", _E.AUTHORIZATION_DENIED),
    ("approval", _E.AUTHORIZATION_DENIED), ("outside this tenant", _E.AUTHORIZATION_DENIED),
    ("no connection", _E.AUTHORIZATION_DENIED),
    ("input_invalid", _E.INVALID_REQUEST), ("validation", _E.INVALID_REQUEST),
    ("not_found", _E.NOT_FOUND), ("not found", _E.NOT_FOUND),
    ("conflict", _E.CONFLICT), ("precondition", _E.CONFLICT), ("stale", _E.CONFLICT),
    ("timeout", _E.TIMEOUT), ("timed out", _E.TIMEOUT), ("deadline", _E.TIMEOUT),
    ("ssrf", _E.NETWORK_FAILURE), ("transport", _E.NETWORK_FAILURE),
    ("could not be reached", _E.PROVIDER_UNAVAILABLE), ("unreachable", _E.NETWORK_FAILURE),
    ("connect", _E.NETWORK_FAILURE), ("unavailable", _E.PROVIDER_UNAVAILABLE),
)


def classify_failure_text(reason: Optional[str]) -> ConnectorErrorClass:
    """A platform refusal/failure reason string as a stable class."""
    text = str(reason or "").lower()
    for fragment, error_class in _TEXT:
        if fragment in text:
            return error_class
    return _E.INTERNAL_ERROR
