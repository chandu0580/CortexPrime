"""
Redis Pub/Sub Manager for CortexPrime realtime event fanout.

Architecture
------------
  Publisher  : any coroutine calls ``pub_sub.publish(channel, payload)``
  Subscriber : long-running background task reads from Redis and dispatches
               messages to registered in-process handler coroutines.

Channels (see keys.py)
-----------------------
  cx:pub:broadcast          → all connected clients (global feed)
  cx:pub:session:{id}       → single session
  cx:pub:agent:{name}       → events for one agent

A dedicated ``pub_client`` (from the pool manager) is used for PUBLISH so
the main pool is not monopolised.  The subscriber loop runs on a background
``asyncio.Task`` started during app startup.

When Redis is unavailable, ``publish()`` calls handlers directly in-process
(fanout without persistence).
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

from backend.infrastructure.redis.connection import redis_connection
from backend.infrastructure.redis.keys import RedisKeys

log = logging.getLogger(__name__)

# Type alias
Handler = Callable[[str, Dict[str, Any]], Awaitable[None]]


class PubSubManager:
    """
    Async Redis Pub/Sub with automatic fallback to direct in-process fanout.

    Subscribers register Python async callables; when a message arrives on
    a channel, all matching handlers are invoked concurrently via
    ``asyncio.gather``.

    Usage
    -----
    1. Register handlers:
        pub_sub.subscribe("cx:pub:broadcast", my_async_handler)

    2. Start listener background task (call once on startup):
        await pub_sub.start()

    3. Publish from anywhere:
        await pub_sub.publish(RedisKeys.channel_broadcast(), {"type": "event", ...})
    """

    def __init__(self) -> None:
        self._handlers:  Dict[str, List[Handler]] = {}
        self._channels:  Set[str]                 = set()
        self._task:      Optional[asyncio.Task]   = None
        self._pubsub:    Optional[Any]            = None   # redis.asyncio.PubSub
        self._running:   bool                     = False

    # ------------------------------------------------------------------
    # Handler registry
    # ------------------------------------------------------------------

    def subscribe(self, channel: str, handler: Handler) -> None:
        """Register *handler* for messages on *channel*."""
        self._handlers.setdefault(channel, [])
        if handler not in self._handlers[channel]:
            self._handlers[channel].append(handler)
        self._channels.add(channel)

    def unsubscribe(self, channel: str, handler: Handler) -> None:
        """Remove a previously registered handler."""
        if channel in self._handlers:
            try:
                self._handlers[channel].remove(handler)
            except ValueError:
                pass

    def subscribe_broadcast(self, handler: Handler) -> None:
        """Convenience: register handler for the global broadcast channel."""
        self.subscribe(RedisKeys.channel_broadcast(), handler)

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    async def publish(
        self,
        channel: str,
        payload: Dict[str, Any],
    ) -> int:
        """
        Publish *payload* to *channel*.

        Returns the number of subscribers that received the message (from
        Redis), or the number of in-process handlers dispatched as fallback.
        """
        message = json.dumps(payload, default=str)

        if await redis_connection.ensure_connected() and redis_connection.pub_client:
            try:
                count = await redis_connection.pub_client.publish(channel, message)
                return count
            except Exception as exc:
                log.warning("PubSub publish Redis error: %s", exc)

        # Fallback: dispatch handlers in-process
        return await self._dispatch(channel, payload)

    async def broadcast(self, payload: Dict[str, Any]) -> int:
        """Publish to the global broadcast channel."""
        return await self.publish(RedisKeys.channel_broadcast(), payload)

    async def publish_to_session(
        self, session_id: str, payload: Dict[str, Any]
    ) -> int:
        return await self.publish(RedisKeys.channel_session(session_id), payload)

    async def publish_to_agent(
        self, agent: str, payload: Dict[str, Any]
    ) -> int:
        return await self.publish(RedisKeys.channel_agent(agent), payload)

    # ------------------------------------------------------------------
    # Background listener
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the background subscriber task. Safe to call multiple times."""
        if self._running:
            return
        if not self._channels:
            log.debug("PubSub: no channels registered — subscriber not started")
            return
        if not await redis_connection.ensure_connected():
            log.warning("PubSub: Redis unavailable — subscriber loop not started; "
                        "in-process fanout will be used instead")
            return
        self._running = True
        self._task    = asyncio.create_task(self._listener_loop())
        log.info("PubSub subscriber started for channels: %s", sorted(self._channels))

    async def stop(self) -> None:
        """Gracefully stop the background subscriber."""
        self._running = False
        if self._pubsub:
            try:
                await self._pubsub.unsubscribe()
                await self._pubsub.aclose()
            except Exception:
                pass
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("PubSub subscriber stopped")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _listener_loop(self) -> None:
        """Long-running coroutine that reads Redis pub/sub messages."""
        backoff = 1.0

        while self._running:
            try:
                client   = redis_connection.pub_client
                if client is None:
                    await asyncio.sleep(backoff)
                    continue

                self._pubsub = client.pubsub()
                await self._pubsub.subscribe(*list(self._channels))
                backoff = 1.0

                async for raw_msg in self._pubsub.listen():
                    if not self._running:
                        break
                    if raw_msg and raw_msg.get("type") == "message":
                        channel = raw_msg.get("channel", "")
                        data    = raw_msg.get("data", "{}")
                        try:
                            payload = json.loads(data)
                        except json.JSONDecodeError:
                            payload = {"raw": data}
                        await self._dispatch(channel, payload)

            except asyncio.CancelledError:
                break
            except Exception as exc:
                if self._running:
                    log.warning(
                        "PubSub listener error (reconnect in %.1fs): %s",
                        backoff, exc,
                    )
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, 60.0)

    async def _dispatch(self, channel: str, payload: Dict[str, Any]) -> int:
        """Invoke all handlers registered for *channel* concurrently."""
        handlers = self._handlers.get(channel, [])
        if not handlers:
            return 0
        results = await asyncio.gather(
            *[h(channel, payload) for h in handlers],
            return_exceptions=True,
        )
        errors = [r for r in results if isinstance(r, Exception)]
        for err in errors:
            log.warning("PubSub handler raised: %s", err)
        return len(handlers) - len(errors)


# ===========================================================================
# SINGLETON
# ===========================================================================

pub_sub = PubSubManager()
