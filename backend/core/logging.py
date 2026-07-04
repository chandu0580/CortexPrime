"""
CortexPrime — Centralized Structured Logging
=============================================

Provides a JSON-formatted logger that attaches:
  - timestamp  (ISO-8601 UTC)
  - request_id (pulled from contextvars, set by RequestIDMiddleware)
  - service    ("cortexprime-backend")
  - module     (name of calling logger)
  - level      (DEBUG / INFO / WARNING / ERROR / CRITICAL)
  - message

Usage
-----
    from backend.core.logging import get_logger
    log = get_logger(__name__)

    log.info("Mission started", extra={"mission_id": "abc", "agent": "planner"})

The logger still works even when there is no active request_id (e.g. during
startup, background tasks, tests) — it emits "no-request-id" as the value.

Structured output (JSON) is emitted when STRUCTURED_LOGGING=true (default in
production). Plain text is used otherwise for developer friendliness.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# ─── Context variable — set by RequestIDMiddleware ─────────────────────────
_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="no-request-id")
_user_id_ctx:    ContextVar[Optional[str]] = ContextVar("user_id",    default=None)
_mission_id_ctx: ContextVar[Optional[str]] = ContextVar("mission_id", default=None)
_session_id_ctx: ContextVar[Optional[str]] = ContextVar("session_id", default=None)

SERVICE_NAME = os.getenv("SERVICE_NAME", "cortexprime-backend")
_STRUCTURED   = os.getenv("STRUCTURED_LOGGING", "true").lower() in ("1", "true", "yes")


def set_request_id(request_id: str) -> None:
    """Called by middleware — sets the active request ID for this async context."""
    _request_id_ctx.set(request_id)


def get_request_id() -> str:
    """Returns the current request_id or 'no-request-id' if outside a request."""
    return _request_id_ctx.get()


def set_context(
    *,
    user_id:    Optional[str] = None,
    mission_id: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """Attach optional identifiers to all subsequent logs in this async context."""
    if user_id    is not None: _user_id_ctx.set(user_id)
    if mission_id is not None: _mission_id_ctx.set(mission_id)
    if session_id is not None: _session_id_ctx.set(session_id)


def get_log_context() -> Dict[str, Any]:
    """Return the full correlation context for the current async context."""
    ctx: Dict[str, Any] = {"request_id": get_request_id()}
    if _user_id_ctx.get():    ctx["user_id"]    = _user_id_ctx.get()
    if _mission_id_ctx.get(): ctx["mission_id"] = _mission_id_ctx.get()
    if _session_id_ctx.get(): ctx["session_id"] = _session_id_ctx.get()
    return ctx


# ─── JSON formatter ────────────────────────────────────────────────────────

class _StructuredFormatter(logging.Formatter):
    """
    Emits each log record as a single-line JSON object.

    Merges any extra= dict fields passed by the caller into the top-level
    JSON object so they appear alongside the standard fields.
    """

    _STANDARD_FIELDS = frozenset({
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "taskName",
    })

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()

        obj: Dict[str, Any] = {
            "timestamp":  datetime.now(timezone.utc).isoformat(),
            "request_id": get_request_id(),
            "service":    SERVICE_NAME,
            "module":     record.name,
            "level":      record.levelname,
            "message":    record.message,
        }

        # Merge optional correlation context
        if _user_id_ctx.get():    obj["user_id"]    = _user_id_ctx.get()
        if _mission_id_ctx.get(): obj["mission_id"] = _mission_id_ctx.get()
        if _session_id_ctx.get(): obj["session_id"] = _session_id_ctx.get()

        # Merge caller-supplied extra= fields (skip standard LogRecord attrs)
        for key, value in record.__dict__.items():
            if key not in self._STANDARD_FIELDS and not key.startswith("_"):
                obj[key] = value

        # Attach exception if present
        if record.exc_info:
            obj["exception"] = self.formatException(record.exc_info)

        return json.dumps(obj, default=str, ensure_ascii=False)


class _PlainFormatter(logging.Formatter):
    """
    Human-readable format for development.

    [LEVEL]  module  request_id  message  {extra}
    """

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        rid  = get_request_id()
        base = (
            f"[{record.levelname:<8}] {record.name}  rid={rid}  {record.message}"
        )
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


# ─── Root logger configuration ─────────────────────────────────────────────

def configure_root_logger(level: int = logging.INFO) -> None:
    """
    Configure the root logger once.
    Should be called at application startup (before any log is emitted).

    Idempotent — safe to call multiple times.
    """
    root = logging.getLogger()

    # Avoid adding duplicate handlers (e.g. when called by tests)
    if any(isinstance(h, logging.StreamHandler) and hasattr(h, "_cortex_structured")
           for h in root.handlers):
        return

    handler = logging.StreamHandler(sys.stdout)
    handler._cortex_structured = True  # type: ignore[attr-defined]

    if _STRUCTURED:
        handler.setFormatter(_StructuredFormatter())
    else:
        handler.setFormatter(_PlainFormatter())

    root.setLevel(level)
    root.addHandler(handler)

    # Silence noisy third-party loggers unless DEBUG
    if level > logging.DEBUG:
        for noisy in ("uvicorn.access", "httpx", "httpcore", "asyncpg", "aio_pika"):
            logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Return a module logger wired to the structured formatter.

    Calling configure_root_logger() is not required — the first call to
    get_logger() bootstraps it automatically.
    """
    # Auto-bootstrap on first use
    if not logging.getLogger().handlers:
        configure_root_logger()
    return logging.getLogger(name)
