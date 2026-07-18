"""
WebSocket Router
================
Defines the ``/ws`` and ``/ws/admin`` endpoints.

Primary path  : CognitionGateway (production-grade)
Fallback path : legacy ConnectionManager handler (when new gateway unavailable)

Query parameters
----------------
session_id      : logical session identifier (default "global")
reconnect_token : optional token from a previous connection to resume topics
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from backend.events.event_bus import event_bus
from backend.websocket.connection_manager import connection_manager

log = logging.getLogger(__name__)

router = APIRouter()


# ===========================================================================
# PRIMARY WEBSOCKET ENDPOINT
# ===========================================================================

@router.websocket("/ws")
async def websocket_endpoint(
    websocket:       WebSocket,
    session_id:      str           = Query(default="global"),
    reconnect_token: str           = Query(default=""),
):
    """
    Primary realtime WebSocket endpoint.

    Delegates to ``CognitionGateway`` which handles:
      - Authentication (pre-accept)
      - Connection pool registration
      - Topic subscriptions (cognition/orchestration/execution/metrics)
      - Heartbeat monitoring
      - Rate limiting + message size validation
      - Reconnect token issuance
      - Graceful cleanup on disconnect

    Falls back to legacy handler if the gateway cannot be imported.
    """
    remote = str(getattr(websocket, "client", ""))

    try:
        from backend.websocket.cognition_gateway import CognitionGateway

        gateway = CognitionGateway(
            websocket       = websocket,
            session_id      = session_id or "global",
            token           = websocket.cookies.get("cortex_access") or None,
            reconnect_token = reconnect_token or None,
            remote_addr     = remote,
        )
        await gateway.run()

    except ImportError as exc:
        log.warning("CognitionGateway unavailable, falling back to legacy: %s", exc)
        await _legacy_handler(websocket)


# ===========================================================================
# ADMIN / OBSERVABILITY ENDPOINT
# ===========================================================================

@router.websocket("/ws/admin")
async def websocket_admin_endpoint(
    websocket:  WebSocket,
):
    """
    Admin WebSocket endpoint — receives all topics by default,
    including metrics and system events.
    Requires the WS_AUTH_TOKEN to be provided.
    """
    remote = str(getattr(websocket, "client", ""))

    try:
        from backend.websocket.cognition_gateway import CognitionGateway

        gateway = CognitionGateway(
            websocket   = websocket,
            session_id  = "observability",
            token       = websocket.cookies.get("cortex_access") or None,
            remote_addr = remote,
        )
        await gateway.run()

    except ImportError as exc:
        log.warning("CognitionGateway unavailable: %s", exc)
        await websocket.close(code=1011)


# ===========================================================================
# REST: WEBSOCKET STATUS
# ===========================================================================

@router.get("/api/websocket/status")
async def websocket_status():
    """Return current connection pool statistics."""
    try:
        from backend.websocket.connection_pool import connection_pool
        from backend.websocket.heartbeat_monitor import heartbeat_monitor

        pool_stats = connection_pool.stats()
        hb_stats   = heartbeat_monitor.stats()
        connections = [
            ctx.to_dict() for ctx in connection_pool.all_connections()
        ]
        return {
            "status":      "ok",
            "pool":        pool_stats,
            "heartbeat":   hb_stats,
            "connections": connections,
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


@router.get("/api/websocket/topics")
async def websocket_topics():
    """Return topic subscriber counts."""
    try:
        from backend.websocket.connection_pool import connection_pool
        stats = connection_pool.stats()
        return {
            "topic_counts": stats.get("topic_subscriber_counts", {}),
            "total_connections": stats.get("total_connections", 0),
        }
    except Exception as exc:
        return {"status": "error", "detail": str(exc)}


# ===========================================================================
# LEGACY FALLBACK
# ===========================================================================

async def _legacy_handler(websocket: WebSocket) -> None:
    """Original connection_manager-based handler (kept for backward compat)."""
    await connection_manager.connect(websocket)
    try:
        events = event_bus.get_events()
        for event in events:
            await connection_manager.send_message(websocket, event)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connection_manager.disconnect(websocket)

