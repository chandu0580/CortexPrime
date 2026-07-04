"""
WebSocket Message Protocol
==========================
Canonical typed message schema for the CortexPrime WebSocket gateway.

Inbound  (client → server): validated Pydantic models with size guard.
Outbound (server → client): lightweight builder functions that return
                             plain dicts (fast JSON serialisation).

Security guardrails
-------------------
- MAX_MESSAGE_BYTES:   Hard limit on incoming raw message size.
- Enum-constrained type fields prevent injection via unknown message types.
- All Pydantic models use ``model_config = {"extra": "ignore"}`` so
  extra client fields are silently dropped (no leakage into handlers).
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Size constants
# ---------------------------------------------------------------------------

MAX_MESSAGE_BYTES: int = 65_536       # 64 KiB hard cap on inbound messages
MAX_PAYLOAD_KEYS:  int = 64           # max dict keys inside payload
RECONNECT_TOKEN_TTL_S: int = 120      # reconnect token valid window (seconds)


# ---------------------------------------------------------------------------
# Topic constants
# ---------------------------------------------------------------------------

class Topic(str, Enum):
    """Named pub/sub subscription topics a client can subscribe to."""
    COGNITION     = "cognition"        # CognitionEvent stream
    ORCHESTRATION = "orchestration"    # Orchestration state updates
    EXECUTION     = "execution"        # Execution progress events
    METRICS       = "metrics"          # Runtime metrics snapshots
    AI_STREAM     = "ai_stream"        # Live LLM token streaming
    AGENT         = "agent"            # Per-agent telemetry
    SYSTEM        = "system"           # System/health notices


# ---------------------------------------------------------------------------
# Inbound message types (client → server)
# ---------------------------------------------------------------------------

class InboundType(str, Enum):
    PING              = "ping"
    PONG              = "pong"               # heartbeat reply
    GET_SNAPSHOT      = "get_snapshot"
    SUBSCRIBE_TOPIC   = "subscribe_topic"
    UNSUBSCRIBE_TOPIC = "unsubscribe_topic"
    GET_COGNITION     = "get_cognition"
    GET_EXECUTION     = "get_execution"
    STREAM_REQUEST    = "stream_request"     # request AI token stream
    COMMAND           = "command"            # forward arbitrary command
    AUTH              = "auth"               # post-connect auth message


# ---------------------------------------------------------------------------
# Outbound message types (server → client)
# ---------------------------------------------------------------------------

class OutboundType(str, Enum):
    PONG               = "pong"
    INIT               = "init"
    SNAPSHOT           = "snapshot"
    COGNITION_EVENT    = "cognition_event"
    ORCHESTRATION_UPDATE = "orchestration_update"
    EXECUTION_EVENT    = "execution_event"
    EXECUTION_STREAM   = "execution_stream"
    RUNTIME_METRICS    = "runtime_metrics"
    AGENT_TELEMETRY    = "agent_telemetry"
    AI_RESPONSE        = "ai_response"       # streaming token chunk
    AI_RESPONSE_DONE   = "ai_response_done"
    ERROR              = "error"
    SYSTEM             = "system"
    HEARTBEAT_PING     = "heartbeat_ping"    # server-initiated ping
    RECONNECT_TOKEN    = "reconnect_token"
    RATE_LIMITED       = "rate_limited"
    SUBSCRIBED         = "subscribed"
    UNSUBSCRIBED       = "unsubscribed"
    COGNITION_HISTORY  = "cognition_history"
    EXECUTION_DETAIL   = "execution_detail"


# ---------------------------------------------------------------------------
# Inbound model
# ---------------------------------------------------------------------------

class InboundMessage(BaseModel):
    """Validated inbound WebSocket message."""

    model_config = {"extra": "ignore"}

    type:    InboundType
    payload: Optional[Dict[str, Any]] = Field(default_factory=dict)
    seq:     Optional[int] = None        # optional client sequence number

    @field_validator("payload")
    @classmethod
    def _limit_payload_keys(cls, v: Optional[Dict]) -> Optional[Dict]:
        if v and len(v) > MAX_PAYLOAD_KEYS:
            raise ValueError(f"payload exceeds {MAX_PAYLOAD_KEYS} keys")
        return v


def parse_inbound(raw: str) -> Optional[InboundMessage]:
    """
    Parse a raw JSON string into an ``InboundMessage``.

    Returns ``None`` on any parse/validation error so callers can send
    a structured error response instead of raising.
    """
    import json
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        return InboundMessage.model_validate(data)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Outbound message builders
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_pong(seq: Optional[int] = None) -> Dict[str, Any]:
    return {"type": OutboundType.PONG, "timestamp": _now(), "seq": seq}


def build_init(
    conn_id: str,
    session_id: str,
    snapshot: Dict[str, Any],
    reconnect_token: str,
    topics: List[str],
) -> Dict[str, Any]:
    return {
        "type":            OutboundType.INIT,
        "conn_id":         conn_id,
        "session_id":      session_id,
        "snapshot":        snapshot,
        "reconnect_token": reconnect_token,
        "topics":          topics,
        "timestamp":       _now(),
    }


def build_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": OutboundType.SNAPSHOT, "snapshot": snapshot, "timestamp": _now()}


def build_cognition_event(event: Dict[str, Any]) -> Dict[str, Any]:
    return {"type": OutboundType.COGNITION_EVENT, "event": event, "timestamp": _now()}


def build_orchestration_update(update: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type":      OutboundType.ORCHESTRATION_UPDATE,
        "update":    update,
        "timestamp": _now(),
    }


def build_execution_event(event: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type":      OutboundType.EXECUTION_EVENT,
        "event":     event,
        "timestamp": _now(),
    }


def build_execution_stream(
    execution_id: str,
    chunk: str,
    done: bool = False,
    seq: int = 0,
) -> Dict[str, Any]:
    return {
        "type":         OutboundType.EXECUTION_STREAM,
        "execution_id": execution_id,
        "chunk":        chunk,
        "done":         done,
        "seq":          seq,
        "timestamp":    _now(),
    }


def build_runtime_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type":      OutboundType.RUNTIME_METRICS,
        "metrics":   metrics,
        "timestamp": _now(),
    }


def build_agent_telemetry(agent: str, telemetry: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "type":      OutboundType.AGENT_TELEMETRY,
        "agent":     agent,
        "telemetry": telemetry,
        "timestamp": _now(),
    }


def build_ai_response(
    stream_id: str,
    token: str,
    done: bool = False,
    seq: int = 0,
) -> Dict[str, Any]:
    return {
        "type":      OutboundType.AI_RESPONSE if not done else OutboundType.AI_RESPONSE_DONE,
        "stream_id": stream_id,
        "token":     token,
        "done":      done,
        "seq":       seq,
        "timestamp": _now(),
    }


def build_error(detail: str, code: str = "error") -> Dict[str, Any]:
    return {
        "type":      OutboundType.ERROR,
        "code":      code,
        "detail":    detail,
        "timestamp": _now(),
    }


def build_system(message: str, level: str = "info") -> Dict[str, Any]:
    return {
        "type":      OutboundType.SYSTEM,
        "message":   message,
        "level":     level,
        "timestamp": _now(),
    }


def build_heartbeat_ping(seq: int) -> Dict[str, Any]:
    return {
        "type":      OutboundType.HEARTBEAT_PING,
        "seq":       seq,
        "timestamp": _now(),
    }


def build_reconnect_token(token: str, ttl_s: int = RECONNECT_TOKEN_TTL_S) -> Dict[str, Any]:
    return {
        "type":    OutboundType.RECONNECT_TOKEN,
        "token":   token,
        "ttl_s":   ttl_s,
        "timestamp": _now(),
    }


def build_rate_limited(retry_after_s: int = 60) -> Dict[str, Any]:
    return {
        "type":           OutboundType.RATE_LIMITED,
        "retry_after_s":  retry_after_s,
        "timestamp":      _now(),
    }


def build_subscribed(topic: str) -> Dict[str, Any]:
    return {"type": OutboundType.SUBSCRIBED, "topic": topic, "timestamp": _now()}


def build_unsubscribed(topic: str) -> Dict[str, Any]:
    return {"type": OutboundType.UNSUBSCRIBED, "topic": topic, "timestamp": _now()}
