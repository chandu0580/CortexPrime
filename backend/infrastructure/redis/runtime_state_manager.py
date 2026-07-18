"""
Runtime State Manager — unified facade for all Redis live-state services.

This module replaces the scattered ``redis_cache.*`` calls throughout the
codebase with a single, consistent API that:

  - Coordinates all Redis sub-services (execution, pipeline, cognition,
    agent activity, sessions, pub/sub)
  - Enforces TTL policy via ``keys.TTL`` constants
  - Publishes state-change events to the pub/sub bus so connected clients
    receive real-time updates without polling
  - Falls back to in-memory state when Redis is offline

Singleton: ``runtime_state``

Usage
-----
    from backend.infrastructure.redis.runtime_state_manager import runtime_state

    await runtime_state.set_execution_state(execution_id, state_dict)
    await runtime_state.record_cognition_event(execution_id, agent, ...)
    await runtime_state.update_agent_status(agent, "thinking", {...})
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.infrastructure.redis.agent_activity_store import agent_activity_store
from backend.infrastructure.redis.cognition_cache import cognition_cache
from backend.infrastructure.redis.connection import redis_connection
from backend.infrastructure.redis.keys import TTL, RedisKeys
from backend.infrastructure.redis.pub_sub import pub_sub
from backend.infrastructure.redis.transient_memory import transient_memory

log = logging.getLogger(__name__)


class RuntimeStateManager:
    """
    Unified facade for all realtime Redis state services.

    Every state mutation also fires a pub/sub event so WebSocket clients
    receive live updates without polling.
    """

    # In-memory fallback maps
    _executions: Dict[str, Dict[str, Any]] = {}
    _pipelines:  Dict[str, Dict[str, Any]] = {}

    # ==================================================================
    # Execution state
    # ==================================================================

    async def set_execution_state(
        self,
        execution_id: str,
        state:        Dict[str, Any],
    ) -> None:
        """Persist execution state and notify all connected clients."""
        data = json.dumps(state, default=str)

        if await redis_connection.ensure_connected():
            try:
                r = redis_connection.client
                await r.setex(
                    RedisKeys.execution_state(execution_id),
                    TTL.EXECUTION_STATE,
                    data,
                )
                await r.sadd(RedisKeys.active_executions(), execution_id)
            except Exception as exc:
                log.warning("RuntimeState set_execution_state Redis error: %s", exc)
                self._executions[execution_id] = state
        else:
            self._executions[execution_id] = state

        # Broadcast state change
        await pub_sub.broadcast({
            "type":         "execution_state_update",
            "execution_id": execution_id,
            "state":        state,
        })

    async def get_execution_state(
        self, execution_id: str
    ) -> Optional[Dict[str, Any]]:
        if await redis_connection.ensure_connected():
            try:
                raw = await redis_connection.client.get(
                    RedisKeys.execution_state(execution_id)
                )
                if raw:
                    return json.loads(raw)
            except Exception as exc:
                log.warning("RuntimeState get_execution_state Redis error: %s", exc)
        return self._executions.get(execution_id)

    async def delete_execution_state(self, execution_id: str) -> None:
        if await redis_connection.ensure_connected():
            try:
                r = redis_connection.client
                await r.delete(RedisKeys.execution_state(execution_id))
                await r.srem(RedisKeys.active_executions(), execution_id)
            except Exception as exc:
                log.warning("RuntimeState delete_execution_state Redis error: %s", exc)
        self._executions.pop(execution_id, None)
        await cognition_cache.clear_execution(execution_id)

        await pub_sub.broadcast({
            "type":         "execution_completed",
            "execution_id": execution_id,
        })

    async def list_active_executions(self) -> List[str]:
        if await redis_connection.ensure_connected():
            try:
                members = await redis_connection.client.smembers(
                    RedisKeys.active_executions()
                )
                return list(members)
            except Exception as exc:
                log.warning("RuntimeState list_active_executions Redis error: %s", exc)
        return list(self._executions.keys())

    # ==================================================================
    # Pipeline context
    # ==================================================================

    async def set_pipeline_context(
        self,
        execution_id: str,
        context:      Dict[str, Any],
    ) -> None:
        data = json.dumps(context, default=str)
        if await redis_connection.ensure_connected():
            try:
                await redis_connection.client.setex(
                    RedisKeys.pipeline_context(execution_id),
                    TTL.PIPELINE_CONTEXT,
                    data,
                )
                return
            except Exception as exc:
                log.warning("RuntimeState set_pipeline_context Redis error: %s", exc)
        self._pipelines[execution_id] = context

    async def get_pipeline_context(
        self, execution_id: str
    ) -> Optional[Dict[str, Any]]:
        if await redis_connection.ensure_connected():
            try:
                raw = await redis_connection.client.get(
                    RedisKeys.pipeline_context(execution_id)
                )
                if raw:
                    return json.loads(raw)
            except Exception as exc:
                log.warning("RuntimeState get_pipeline_context Redis error: %s", exc)
        return self._pipelines.get(execution_id)

    # ==================================================================
    # Cognition events
    # ==================================================================

    async def record_cognition_event(
        self,
        execution_id: str,
        agent:        str,
        event_type:   str,
        message:      str,
        phase:        Optional[str]            = None,
        payload:      Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """
        Cache a cognition event AND publish it to all subscribers.

        Returns the Redis Stream entry ID (or None on fallback).
        """
        stream_id = await cognition_cache.push_event(
            execution_id=execution_id,
            agent=agent,
            event_type=event_type,
            message=message,
            phase=phase,
            payload=payload,
        )

        # Real-time fanout
        await pub_sub.broadcast({
            "type":         "cognition_event",
            "execution_id": execution_id,
            "agent":        agent,
            "event_type":   event_type,
            "message":      message,
            "phase":        phase,
            "payload":      payload or {},
            "stream_id":    stream_id,
        })

        return stream_id

    async def get_recent_cognition(
        self,
        execution_id: str,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        return await cognition_cache.get_recent(execution_id, limit)

    # ==================================================================
    # Agent status
    # ==================================================================

    async def update_agent_status(
        self,
        agent:    str,
        status:   str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update agent state and broadcast to clients."""
        await agent_activity_store.set_state(agent, status, metadata)

        await pub_sub.broadcast({
            "type":     "agent_status_update",
            "agent":    agent,
            "status":   status,
            "metadata": metadata or {},
        })

    async def update_agent_activity(
        self,
        agent:        str,
        task:         str,
        execution_id: Optional[str]            = None,
        payload:      Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record fine-grained agent activity and broadcast."""
        await agent_activity_store.set_activity(
            agent, task, execution_id, payload
        )
        await pub_sub.publish_to_agent(agent, {
            "type":         "agent_activity",
            "agent":        agent,
            "task":         task,
            "execution_id": execution_id,
            "payload":      payload or {},
        })

    async def get_agent_states(self) -> Dict[str, Dict[str, Any]]:
        return await agent_activity_store.get_all_states()

    async def get_active_agents(self) -> List[str]:
        return await agent_activity_store.list_active_agents()

    # ==================================================================
    # Transient memory delegation
    # ==================================================================

    async def set_agent_memory(
        self, agent: str, key: str, value: Any
    ) -> None:
        await transient_memory.set(agent, key, value)

    async def get_agent_memory(self, agent: str, key: str) -> Optional[Any]:
        return await transient_memory.get(agent, key)

    async def get_agent_scratchpad(self, agent: str) -> Dict[str, Any]:
        return await transient_memory.get_all(agent)

    async def push_agent_thought(self, agent: str, thought: str) -> None:
        await transient_memory.push_thought(agent, thought)
        await pub_sub.publish_to_agent(agent, {
            "type":    "agent_thought",
            "agent":   agent,
            "thought": thought,
        })

    async def peek_agent_thoughts(
        self, agent: str, limit: int = 10
    ) -> List[str]:
        return await transient_memory.peek_thoughts(agent, limit)

    # ==================================================================
    # Global runtime snapshot
    # ==================================================================

    async def get_runtime_snapshot(self) -> Dict[str, Any]:
        """
        Return a composite snapshot of the current runtime state.
        Suitable for health endpoints and dashboard initialisation payloads.
        Includes full active execution state from the Redis-backed store.
        """
        active_execs   = await self.list_active_executions()
        active_agents  = await self.get_active_agents()
        agent_states   = await self.get_agent_states()
        ws_count: int  = 0

        try:
            from backend.infrastructure.redis.websocket_session_store import ws_session_store
            ws_count = await ws_session_store.count_active()
        except Exception:
            pass

        # Load rich execution records from the canonical store
        rich_executions: list = []
        try:
            from backend.runtime.runtime_state_store import runtime_state_store
            rich_executions = await runtime_state_store.list_active()
        except Exception:
            pass

        return {
            "timestamp":          datetime.now(timezone.utc).isoformat(),
            "active_executions":  active_execs,
            "execution_count":    len(active_execs),
            "executions":         rich_executions,    # full records for WS reconnect
            "active_agents":      active_agents,
            "agent_states":       agent_states,
            "ws_connections":     ws_count,
            "redis_available":    redis_connection.is_available,
        }

    # ==================================================================
    # Startup recovery
    # ==================================================================

    async def recover_on_startup(self) -> int:
        """
        Trigger recovery of persisted execution state after a restart.
        Delegates to the canonical runtime_state_store.
        Returns the count of recovered executions.
        """
        try:
            from backend.runtime.runtime_state_store import runtime_state_store
            return await runtime_state_store.recover_on_startup()
        except Exception as exc:
            log.warning("recover_on_startup failed: %s", exc)
            return 0

    # ==================================================================
    # Health
    # ==================================================================

    async def health(self) -> Dict[str, Any]:
        alive = await redis_connection.ping()
        return {
            "redis":         "healthy" if alive else "offline",
            "available":     redis_connection.is_available,
            "failure_count": redis_connection.failure_count,
        }


# ===========================================================================
# SINGLETON
# ===========================================================================

runtime_state = RuntimeStateManager()
runtime_state_manager = runtime_state  # alias: main.py imports this name
