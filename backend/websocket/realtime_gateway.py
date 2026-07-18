"""
Realtime WebSocket Gateway — Redis pub/sub ↔ WebSocket bridge.

This module forms the real-time spine of CortexPrime:

  Redis pub/sub  →  RealtimeGateway  →  WebSocket clients
  WebSocket msg  →  RealtimeGateway  →  Redis pub/sub / in-process handlers

Responsibilities
----------------
1. On each new WebSocket connection:
     - Register the session in ``ws_session_store``
     - Subscribe the ``_broadcast_handler`` to ``cx:pub:broadcast``
     - Subscribe the ``_session_handler``   to ``cx:pub:session:{session_id}``
     - Send the current runtime snapshot as an init payload

2. On every incoming client message:
     - Refresh the session heartbeat
     - Route command payloads to appropriate handlers

3. On disconnect:
     - Unregister the session

4. Pub/sub handler (``_broadcast_handler``):
     - Receives every event published to ``cx:pub:broadcast``
     - Fans out to all currently connected WebSocket sockets

Architecture note
-----------------
The gateway is NOT a singleton — one instance is created per WebSocket
connection lifecycle in ``websocket_router.py``.  The class-level
``pub_sub.subscribe_broadcast`` registration is de-duplicated by the
PubSubManager so multiple connections share a single Redis subscription.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import WebSocket, WebSocketDisconnect

from backend.infrastructure.redis.keys import RedisKeys
from backend.infrastructure.redis.pub_sub import pub_sub
from backend.infrastructure.redis.runtime_state_manager import runtime_state
from backend.infrastructure.redis.websocket_session_store import ws_session_store

log = logging.getLogger(__name__)


class RealtimeGateway:
    """
    Per-connection WebSocket ↔ Redis bridge.

    Instantiate once per accepted WebSocket, then call ``run()``.
    """

    def __init__(
        self,
        websocket:  WebSocket,
        session_id: str = "global",
    ) -> None:
        self.websocket  = websocket
        self.session_id = session_id
        self.conn_id    = str(uuid.uuid4())
        self._closed    = False

    # ------------------------------------------------------------------
    # Main lifecycle
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """
        Accept the connection, register it, loop on incoming messages,
        and clean up on disconnect.
        """
        await self.websocket.accept()

        # Register with Redis session store
        await ws_session_store.register(
            conn_id    = self.conn_id,
            session_id = self.session_id,
            metadata   = {"remote": str(getattr(self.websocket, "client", ""))},
        )

        # Register pub/sub handlers
        pub_sub.subscribe(RedisKeys.channel_broadcast(),         self._on_broadcast)
        pub_sub.subscribe(RedisKeys.channel_session(self.session_id), self._on_session_msg)

        log.info("WS connected: conn=%s session=%s", self.conn_id, self.session_id)

        try:
            # Send runtime snapshot as connection init payload
            await self._send_init_snapshot()

            # Message receive loop
            while not self._closed:
                try:
                    raw = await self.websocket.receive_text()
                    await ws_session_store.heartbeat(self.conn_id)
                    await self._handle_client_message(raw)
                except WebSocketDisconnect:
                    break
                except Exception as exc:
                    log.warning("WS receive error (conn=%s): %s", self.conn_id, exc)
                    break

        finally:
            await self._cleanup()

    # ------------------------------------------------------------------
    # Init snapshot
    # ------------------------------------------------------------------

    async def _send_init_snapshot(self) -> None:
        """Send current runtime state immediately after connection."""
        try:
            snapshot = await runtime_state.get_runtime_snapshot()
            await self._send({
                "type":      "init",
                "conn_id":   self.conn_id,
                "session_id": self.session_id,
                "snapshot":  snapshot,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:
            log.warning("WS init snapshot error: %s", exc)

    # ------------------------------------------------------------------
    # Pub/sub handlers
    # ------------------------------------------------------------------

    async def _on_broadcast(
        self, channel: str, payload: Dict[str, Any]
    ) -> None:
        """Forward every broadcast event to this WebSocket connection."""
        if not self._closed:
            await self._send(payload)

    async def _on_session_msg(
        self, channel: str, payload: Dict[str, Any]
    ) -> None:
        """Forward session-targeted messages to this connection."""
        if not self._closed:
            await self._send(payload)

    # ------------------------------------------------------------------
    # Client message routing
    # ------------------------------------------------------------------

    async def _handle_client_message(self, raw: str) -> None:
        """
        Parse and route an incoming client WebSocket message.

        Supported message types
        -----------------------
        ``{"type": "ping"}``                   → pong response
        ``{"type": "subscribe_agent", "agent": ...}``  → subscribe to agent channel
        ``{"type": "get_snapshot"}``           → resend runtime snapshot
        ``{"type": "get_cognition", "execution_id": ...}``  → recent events
        ``{"type": "command", "payload": ...}``  → forward to pub/sub
        """
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            await self._send({"type": "error", "detail": "invalid JSON"})
            return

        msg_type = msg.get("type", "")

        if msg_type == "ping":
            await self._send({"type": "pong", "timestamp": datetime.now(timezone.utc).isoformat()})

        elif msg_type == "get_snapshot":
            await self._send_init_snapshot()

        elif msg_type == "subscribe_agent":
            agent = msg.get("agent", "")
            if agent:
                pub_sub.subscribe(RedisKeys.channel_agent(agent), self._on_broadcast)
                await self._send({"type": "subscribed", "agent": agent})

        elif msg_type == "get_cognition":
            exec_id = msg.get("execution_id", "")
            limit   = int(msg.get("limit", 50))
            if exec_id:
                events = await runtime_state.get_recent_cognition(exec_id, limit)
                await self._send({
                    "type":         "cognition_history",
                    "execution_id": exec_id,
                    "events":       events,
                })

        elif msg_type == "command":
            # Forward arbitrary commands to the broadcast channel
            await pub_sub.broadcast({
                "type":     "client_command",
                "conn_id":  self.conn_id,
                "session_id": self.session_id,
                "payload":  msg.get("payload", {}),
            })

        else:
            log.debug("WS unhandled message type '%s' from conn=%s", msg_type, self.conn_id)

    # ------------------------------------------------------------------
    # Send helper
    # ------------------------------------------------------------------

    async def _send(self, payload: Dict[str, Any]) -> None:
        if self._closed:
            return
        try:
            await self.websocket.send_json(payload)
        except Exception as exc:
            log.debug("WS send failed (conn=%s): %s — marking closed", self.conn_id, exc)
            self._closed = True

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def _cleanup(self) -> None:
        self._closed = True
        pub_sub.unsubscribe(RedisKeys.channel_broadcast(),         self._on_broadcast)
        pub_sub.unsubscribe(RedisKeys.channel_session(self.session_id), self._on_session_msg)
        await ws_session_store.unregister(self.conn_id)
        log.info("WS disconnected: conn=%s session=%s", self.conn_id, self.session_id)
        try:
            await self.websocket.close()
        except Exception:
            pass
