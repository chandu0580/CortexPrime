"""
CortexPrime — Standard Error Response Model
=============================================

All API errors follow this envelope so clients have a single
contract regardless of the route or subsystem that generated the error.

Schema
------
{
  "success": false,
  "error": {
    "code":       "SNAKE_CASE_ERROR_CODE",
    "message":    "Human-readable description (no secrets, no paths).",
    "request_id": "uuid4"
  }
}

Usage
-----
    from backend.core.errors import error_response, CortexError

    # Raise a mapped HTTP error anywhere in a route:
    raise CortexError(status_code=403, code="PERMISSION_DENIED",
                      message="You do not have access to this resource.")

    # Or build a JSONResponse manually:
    return error_response(request, 404, "NOT_FOUND", "Mission not found.")
"""

from __future__ import annotations

from typing import Optional

from fastapi import Request
from fastapi.responses import JSONResponse

from backend.core.logging import get_request_id

# ─── Canonical error codes ─────────────────────────────────────────────────

class ErrorCode:
    # 4xx
    BAD_REQUEST          = "BAD_REQUEST"
    UNAUTHORIZED         = "UNAUTHORIZED"
    FORBIDDEN            = "FORBIDDEN"
    NOT_FOUND            = "NOT_FOUND"
    METHOD_NOT_ALLOWED   = "METHOD_NOT_ALLOWED"
    CONFLICT             = "CONFLICT"
    UNPROCESSABLE        = "UNPROCESSABLE_ENTITY"
    RATE_LIMITED         = "TOO_MANY_REQUESTS"
    # 5xx
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    SERVICE_UNAVAILABLE   = "SERVICE_UNAVAILABLE"
    GATEWAY_TIMEOUT       = "GATEWAY_TIMEOUT"
    # Domain
    MISSION_NOT_FOUND    = "MISSION_NOT_FOUND"
    AGENT_UNAVAILABLE    = "AGENT_UNAVAILABLE"
    LLM_PROVIDER_ERROR   = "LLM_PROVIDER_ERROR"
    MEMORY_ERROR         = "MEMORY_ERROR"
    GUARDRAIL_BLOCKED    = "GUARDRAIL_BLOCKED"
    APPROVAL_REQUIRED    = "APPROVAL_REQUIRED"
    APPROVAL_TIMEOUT     = "APPROVAL_TIMEOUT"


# ─── Exception class ──────────────────────────────────────────────────────

class CortexError(Exception):
    """
    Raise this from any route handler to return a standardized error response.

        raise CortexError(
            status_code = 404,
            code        = ErrorCode.NOT_FOUND,
            message     = "The requested mission was not found.",
        )
    """

    def __init__(
        self,
        status_code: int,
        code:        str,
        message:     str,
        request_id:  Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code        = code
        self.message     = message
        self.request_id  = request_id or get_request_id()


# ─── Response builder ─────────────────────────────────────────────────────

def error_response(
    request:     Optional[Request],
    status_code: int,
    code:        str,
    message:     str,
) -> JSONResponse:
    """
    Build a standardized JSON error response.

        return error_response(request, 404, ErrorCode.NOT_FOUND, "Not found.")
    """
    request_id = (
        getattr(request.state, "request_id", None) if request else None
    ) or get_request_id()

    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code":       code,
                "message":    message,
                "request_id": request_id,
            },
        },
        headers={"X-Request-ID": request_id},
    )


# ─── HTTP status → (code, message) defaults ──────────────────────────────

_HTTP_DEFAULTS: dict[int, tuple[str, str]] = {
    400: (ErrorCode.BAD_REQUEST,         "The request was malformed or contained invalid parameters."),
    401: (ErrorCode.UNAUTHORIZED,        "Authentication is required. Please provide a valid token."),
    403: (ErrorCode.FORBIDDEN,           "You do not have permission to perform this action."),
    404: (ErrorCode.NOT_FOUND,           "The requested resource was not found."),
    405: (ErrorCode.METHOD_NOT_ALLOWED,  "This HTTP method is not supported for this endpoint."),
    409: (ErrorCode.CONFLICT,            "The request conflicts with the current state of the resource."),
    422: (ErrorCode.UNPROCESSABLE,       "The request body failed validation."),
    429: (ErrorCode.RATE_LIMITED,        "Rate limit exceeded. Please slow down and retry after the specified delay."),
    500: (ErrorCode.INTERNAL_SERVER_ERROR, "An unexpected error occurred. Please try again later."),
    503: (ErrorCode.SERVICE_UNAVAILABLE,   "The service is temporarily unavailable. Please try again later."),
}


def http_error_response(
    request:     Optional[Request],
    status_code: int,
    message:     Optional[str] = None,
    code:        Optional[str] = None,
) -> JSONResponse:
    """
    Convenience wrapper that picks sensible defaults for standard HTTP codes.
    """
    default_code, default_msg = _HTTP_DEFAULTS.get(
        status_code,
        (ErrorCode.INTERNAL_SERVER_ERROR, "An unexpected error occurred."),
    )
    return error_response(
        request,
        status_code,
        code    or default_code,
        message or default_msg,
    )
