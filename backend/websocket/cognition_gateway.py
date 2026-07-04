"""
Cognition Gateway — Production-Grade WebSocket Gateway
=======================================================
Enterprise-grade per-connection lifecycle manager for the CortexPrime
realtime WebSocket layer.

Architecture
------------
One ``CognitionGateway`` instance is created per accepted WebSocket
connection by ``websocket_router.py``.  The instance owns the full
lifecycle of that connection:

  HTTP handshake → Auth → Pool registration → Init snapshot → Message loop
       ↓
  Heartbeat pings (via HeartbeatMonitor)
       ↓
  Topic subscriptions (StreamRouter)
       ↓
  Incoming messages → validated → rate-checked → dispatched
       ↓
  Disconnect → reconnect token issued → pool cleanup → Redis cleanup

Security guardrails
-------------------
- Token authentication at HTTP upgrade time (pre-accept).
- Incoming message size hard-capped at ``MAX_MESSAGE_BYTES`` (64 KiB).
- All inbound messages validated as typed ``InboundMessage`` Pydantic models.
- Per-connection rate limiting (120 msg/min, 2 MiB/min by default).
- Reconnect tokens are single-use and expire after 2 minutes.
- No raw eval / exec of client-supplied data.

Frontend receives
-----------------
- ``init``                  — on connect: conn_id, snapshot, reconnect_token
- ``heartbeat_ping``        — server-initiated pings (expect pong back)
- ``snapshot``              — on demand via get_snapshot
- ``cognition_event``       — live cognition events (topic: cognition)
- ``orchestration_update``  — orchestration state (topic: orchestration)
- ``execution_event``       — execution progress (topic: execution)
- ``execution_stream``      — live execution output chunks
- ``runtime_metrics``       — periodic metrics (topic: metrics)
- ``agent_telemetry``       — per-agent activity (topic: agent:{name})
- ``ai_response``           — live LLM token stream (topic: ai_stream)
- ``error``                 — error messages
- ``reconnect_token``       — new token after each disconnect
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import WebSocket, WebSocketDisconnect

from backend.websocket.auth import (
    AuthenticationError,
    WSAuthContext,
    authenticate,
    rate_limiter,
    reconnect_token_store,
)
from backend.websocket.connection_pool import ConnectionContext, connection_pool
from backend.websocket.heartbeat_monitor import heartbeat_monitor
from backend.websocket.message_protocol import (
    MAX_MESSAGE_BYTES,
    InboundType,
    Topic,
    build_error,
    build_init,
    build_pong,
    build_rate_limited,
    build_reconnect_token,
    build_snapshot,
    build_subscribed,
    build_system,
    build_unsubscribed,
    parse_inbound,
)
from backend.websocket.stream_router import stream_router

log = logging.getLogger(__name__)


class CognitionGateway:
    """
    Production-grade per-connection WebSocket gateway.

    Instantiate once per accepted connection, then ``await gateway.run()``.
    """

    def __init__(
        self,
        websocket:         WebSocket,
        session_id:        str = "global",
        token:             Optional[str] = None,
        reconnect_token:   Optional[str] = None,
        remote_addr:       str = "",
    ) -> None:
        self.websocket       = websocket
        self.session_id      = session_id
        self.token           = token
        self.reconnect_token = reconnect_token
        self.remote_addr     = remote_addr

        self.conn_id:   str = str(uuid.uuid4())
        self._closed:   bool = False
        self._auth:     Optional[WSAuthContext] = None
        self._ctx:      Optional[ConnectionContext] = None

    # ------------------------------------------------------------------
    # Main lifecycle
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """
        Full connection lifecycle:
        1. Authenticate (before accept — returns 403 HTTP if fails)
        2. Accept WebSocket
        3. Register in pool
        4. Subscribe to default topics (+ resume from reconnect token)
        5. Send init payload
        6. Enter message receive loop
        7. Cleanup on disconnect
        """
        # ── 1. Authenticate ─────────────────────────────────────────
        try:
            self._auth = authenticate(self.token)
        except AuthenticationError as exc:
            # Reject at HTTP level — do not call accept()
            log.warning(
                "WS auth rejected conn=%s addr=%s: %s",
                self.conn_id, self.remote_addr, exc.detail,
            )
            await self.websocket.close(code=4001, reason=exc.detail)
            return

        # ── 2. Accept ────────────────────────────────────────────────
        await self.websocket.accept()

        # ── 3. Register in connection pool ───────────────────────────
        self._ctx = ConnectionContext(
            conn_id          = self.conn_id,
            session_id       = self.session_id,
            websocket        = self.websocket,
            is_authenticated = self._auth.is_authenticated,
            is_anonymous     = self._auth.is_anonymous,
            user_id          = self._auth.user_id,
            remote_addr      = self.remote_addr,
        )
        await connection_pool.register(self._ctx)

        # ── 4. Topic subscriptions ────────────────────────────────────
        resumed_topics: Set[str] = set()
        if self.reconnect_token:
            resumed_topics = await self._resume_from_token(self.reconnect_token)

        if not resumed_topics:
            # Default: subscribe to all core topics
            await stream_router.subscribe_defaults(self.conn_id)
        else:
            log.info(
                "WS reconnect resumed topics=%s conn=%s",
                resumed_topics, self.conn_id,
            )

        # Also register with Redis session store (for cross-process visibility)
        await self._register_redis_session()

        log.info(
            "WS connected: conn=%s session=%s user=%s addr=%s",
            self.conn_id, self.session_id, self._auth.user_id, self.remote_addr,
        )

        # ── 5. Init payload ───────────────────────────────────────────
        try:
            await self._send_init()
        except Exception as exc:
            log.warning("WS init payload error: %s", exc)

        # ── 6. Message loop ───────────────────────────────────────────
        await self._message_loop()

        # ── 7. Cleanup ────────────────────────────────────────────────
        await self._cleanup()

    # ------------------------------------------------------------------
    # Message receive loop
    # ------------------------------------------------------------------

    async def _message_loop(self) -> None:
        while not self._closed:
            try:
                raw = await asyncio.wait_for(
                    self.websocket.receive_text(),
                    timeout=None,   # HeartbeatMonitor handles timeout eviction
                )
            except WebSocketDisconnect:
                break
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.debug("WS receive error conn=%s: %s", self.conn_id, exc)
                break

            if self._ctx:
                self._ctx.messages_received += 1
                self._ctx.bytes_received    += len(raw)

            await self._handle_raw(raw)

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    async def _handle_raw(self, raw: str) -> None:
        """
        Validate, rate-check, parse, and dispatch a single incoming message.
        """
        # Size guard
        if len(raw) > MAX_MESSAGE_BYTES:
            await self._send(build_error(
                detail=f"Message exceeds {MAX_MESSAGE_BYTES} byte limit",
                code="message_too_large",
            ))
            return

        # Rate limit check — delegates to Redis-backed limiter with local fallback
        try:
            from backend.safety.rate_limiter import rate_limiter as _rl
            _allowed = await _rl.check_websocket(self.conn_id, len(raw))
        except Exception:
            # If the new limiter itself errors, fall back to the old in-process one
            _allowed = rate_limiter.check(self.conn_id, len(raw))
        if not _allowed:
            await self._send(build_rate_limited(retry_after_s=60))
            return

        # Parse + validate
        msg = parse_inbound(raw)
        if msg is None:
            await self._send(build_error(
                detail="Invalid message format or unknown message type",
                code="parse_error",
            ))
            return

        # Dispatch
        await self._dispatch(msg)

    async def _dispatch(self, msg) -> None:
        """Route a validated InboundMessage to its handler."""
        t = msg.type
        p = msg.payload or {}

        if t == InboundType.PING:
            await self._handle_ping(msg.seq)

        elif t == InboundType.PONG:
            self._handle_pong()

        elif t == InboundType.GET_SNAPSHOT:
            await self._handle_get_snapshot()

        elif t == InboundType.SUBSCRIBE_TOPIC:
            await self._handle_subscribe(p, msg.seq)

        elif t == InboundType.UNSUBSCRIBE_TOPIC:
            await self._handle_unsubscribe(p)

        elif t == InboundType.GET_COGNITION:
            await self._handle_get_cognition(p)

        elif t == InboundType.GET_EXECUTION:
            await self._handle_get_execution(p)

        elif t == InboundType.STREAM_REQUEST:
            await self._handle_stream_request(p)

        elif t == InboundType.COMMAND:
            await self._handle_command(p)

        elif t == InboundType.AUTH:
            # Post-connect re-auth (upgrade anonymous → authenticated)
            await self._handle_reauth(p)

        else:
            log.debug("WS unhandled type %s conn=%s", t, self.conn_id)

    # ------------------------------------------------------------------
    # Individual message handlers
    # ------------------------------------------------------------------

    async def _handle_ping(self, seq: Optional[int]) -> None:
        await self._send(build_pong(seq))

    def _handle_pong(self) -> None:
        heartbeat_monitor.record_pong(self.conn_id)
        if self._ctx:
            self._ctx.last_pong_s = __import__("time").monotonic()
            self._ctx.pending_ping_seq = None

    async def _handle_get_snapshot(self) -> None:
        try:
            from backend.infrastructure.redis.runtime_state_manager import runtime_state
            snapshot = await runtime_state.get_runtime_snapshot()
            await self._send(build_snapshot(snapshot))
        except Exception as exc:
            await self._send(build_error(f"Snapshot unavailable: {exc}"))

    async def _handle_subscribe(self, payload: Dict[str, Any], seq: Optional[int]) -> None:
        topic = payload.get("topic", "")
        if not topic:
            await self._send(build_error("Missing 'topic' in payload"))
            return

        # Validate topic name to prevent arbitrary channel subscription
        valid_prefixes = ("cognition", "orchestration", "execution", "metrics",
                          "ai_stream", "system", "agent:")
        if not any(topic.startswith(p) for p in valid_prefixes):
            await self._send(build_error(f"Unknown topic: {topic}", code="invalid_topic"))
            return

        await stream_router.subscribe(self.conn_id, topic)
        await self._send(build_subscribed(topic))

    async def _handle_unsubscribe(self, payload: Dict[str, Any]) -> None:
        topic = payload.get("topic", "")
        if topic:
            await stream_router.unsubscribe(self.conn_id, topic)
            await self._send(build_unsubscribed(topic))

    async def _handle_get_cognition(self, payload: Dict[str, Any]) -> None:
        exec_id = payload.get("execution_id", "")
        limit   = min(int(payload.get("limit", 50)), 200)
        if not exec_id:
            await self._send(build_error("Missing 'execution_id'"))
            return
        try:
            from backend.infrastructure.redis.runtime_state_manager import runtime_state
            events = await runtime_state.get_recent_cognition(exec_id, limit)
            await self._send({
                "type":         "cognition_history",
                "execution_id": exec_id,
                "events":       events,
                "timestamp":    datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:
            await self._send(build_error(f"Cognition fetch failed: {exc}"))

    async def _handle_get_execution(self, payload: Dict[str, Any]) -> None:
        exec_id = payload.get("execution_id", "")
        if not exec_id:
            await self._send(build_error("Missing 'execution_id'"))
            return
        try:
            from backend.infrastructure.redis.runtime_state_manager import runtime_state
            state = await runtime_state.get_execution_state(exec_id)
            await self._send({
                "type":         "execution_detail",
                "execution_id": exec_id,
                "state":        state or {},
                "timestamp":    datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:
            await self._send(build_error(f"Execution fetch failed: {exc}"))

    async def _handle_stream_request(self, payload: Dict[str, Any]) -> None:
        """
        Request to subscribe to an AI/execution stream.
        Subscribes the connection to ``ai_stream`` or ``execution:{id}`` topic.
        """
        stream_type = payload.get("stream_type", "ai_stream")
        stream_id   = payload.get("stream_id", "")

        if stream_type == "ai_stream":
            await stream_router.subscribe(self.conn_id, Topic.AI_STREAM)
            await self._send(build_subscribed(Topic.AI_STREAM))
        elif stream_type == "execution" and stream_id:
            topic = f"execution:{stream_id}"
            await stream_router.subscribe(self.conn_id, topic)
            await self._send(build_subscribed(topic))
        else:
            await self._send(build_error("Invalid stream_type or missing stream_id"))

    async def _handle_command(self, payload: Dict[str, Any]) -> None:
        """
        Forward a command to the Redis pub/sub broadcast channel so
        all in-process and cross-process handlers can react.
        """
        try:
            from backend.infrastructure.redis.pub_sub import pub_sub
            await pub_sub.broadcast({
                "type":       "client_command",
                "conn_id":    self.conn_id,
                "session_id": self.session_id,
                "user_id":    self._auth.user_id if self._auth else "anonymous",
                "payload":    payload,
                "timestamp":  datetime.now(timezone.utc).isoformat(),
            })
        except Exception as exc:
            await self._send(build_error(f"Command dispatch failed: {exc}"))

    async def _handle_reauth(self, payload: Dict[str, Any]) -> None:
        """
        Upgrade an anonymous connection to authenticated when the client
        provides a valid token post-connect.
        """
        token = payload.get("token", "")
        try:
            new_auth = authenticate(token)
            self._auth = new_auth
            if self._ctx:
                self._ctx.is_authenticated = new_auth.is_authenticated
                self._ctx.is_anonymous     = new_auth.is_anonymous
                self._ctx.user_id          = new_auth.user_id
            await self._send(build_system("Authentication successful", level="info"))
        except AuthenticationError as exc:
            await self._send(build_error(exc.detail, code="auth_failed"))

    # ------------------------------------------------------------------
    # Init payload
    # ------------------------------------------------------------------

    async def _send_init(self) -> None:
        """Send the initial connection payload."""
        from backend.infrastructure.redis.runtime_state_manager import runtime_state

        snapshot: Dict[str, Any] = {}
        try:
            snapshot = await runtime_state.get_runtime_snapshot()
        except Exception:
            pass

        # Issue a reconnect token the client can use to resume this session
        current_topics = set(self._ctx.topics) if self._ctx else set()
        rtoken = reconnect_token_store.issue(self.session_id, current_topics)

        topics_list = list(self._ctx.topics) if self._ctx else []

        await self._send(build_init(
            conn_id          = self.conn_id,
            session_id       = self.session_id,
            snapshot         = snapshot,
            reconnect_token  = rtoken,
            topics           = topics_list,
        ))

    # ------------------------------------------------------------------
    # Reconnect token resume
    # ------------------------------------------------------------------

    async def _resume_from_token(self, token: str) -> Set[str]:
        """
        Try to resume a previous session from a reconnect token.
        Returns the set of resumed topics, or empty set on failure.
        """
        record = reconnect_token_store.consume(token)
        if not record:
            log.debug("WS reconnect token invalid/expired conn=%s", self.conn_id)
            return set()

        topics: Set[str] = record.get("topics", set())
        for topic in topics:
            await stream_router.subscribe(self.conn_id, topic)

        return topics

    # ------------------------------------------------------------------
    # Redis session store sync
    # ------------------------------------------------------------------

    async def _register_redis_session(self) -> None:
        try:
            from backend.infrastructure.redis.websocket_session_store import ws_session_store
            await ws_session_store.register(
                conn_id    = self.conn_id,
                session_id = self.session_id,
                metadata   = {
                    "remote_addr":    self.remote_addr,
                    "user_id":        self._auth.user_id if self._auth else "anonymous",
                    "is_anonymous":   str(self._auth.is_anonymous if self._auth else True),
                },
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Send helper
    # ------------------------------------------------------------------

    async def _send(self, payload: Dict[str, Any]) -> None:
        if self._closed:
            return
        sent = await connection_pool.send_to(self.conn_id, payload)
        if not sent:
            self._closed = True

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def _cleanup(self) -> None:
        self._closed = True

        # Issue a new reconnect token so the client can reconnect smoothly
        if self._ctx:
            rtoken = reconnect_token_store.issue(
                self.session_id, set(self._ctx.topics)
            )
            # Best-effort: try to send the token before closing
            try:
                from backend.infrastructure.redis.pub_sub import pub_sub
                await pub_sub.publish_to_session(
                    self.session_id,
                    build_reconnect_token(rtoken),
                )
            except Exception:
                pass

        # Remove rate-limiter window
        rate_limiter.remove(self.conn_id)

        # Unregister from pool
        await connection_pool.unregister(self.conn_id)

        # Unregister from Redis session store
        try:
            from backend.infrastructure.redis.websocket_session_store import ws_session_store
            await ws_session_store.unregister(self.conn_id)
        except Exception:
            pass

        log.info(
            "WS disconnected: conn=%s session=%s user=%s",
            self.conn_id, self.session_id,
            self._auth.user_id if self._auth else "anonymous",
        )

        try:
            await self.websocket.close()
        except Exception:
            pass
