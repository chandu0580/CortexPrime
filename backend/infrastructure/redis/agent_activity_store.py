"""
Agent Activity Store — Redis-backed live agent tracking.

Maintains three complementary views of every agent's activity:

  1. cx:agent:state:{agent}         HASH   — current status + metadata
  2. cx:agent:activity:{agent}      HASH   — current task detail
  3. cx:agent:timeline:{agent}      ZSET   — activity events (score=epoch)
  4. cx:agent:ops:{agent}           STRING — total operation counter
  5. cx:agent:active                SET    — agents that have been seen

All entries carry TTLs; an agent that stops sending heartbeats falls off
the active set automatically.
"""
from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.infrastructure.redis.connection import redis_connection
from backend.infrastructure.redis.keys import TTL, RedisKeys

log = logging.getLogger(__name__)

TIMELINE_MAXLEN = 500   # keep last N activity events per agent


class AgentActivityStore:
    """Track live agent activity, state, and timeline in Redis."""

    # In-memory fallback
    _mem_state:    Dict[str, Dict[str, Any]] = {}
    _mem_activity: Dict[str, Dict[str, Any]] = {}
    _mem_timeline: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    _mem_ops:      Dict[str, int] = defaultdict(int)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    async def set_state(
        self,
        agent:    str,
        status:   str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Record an agent's operational status.

        ``status`` should be one of: idle | thinking | acting | waiting | error
        """
        now   = datetime.now(timezone.utc).isoformat()
        state = {
            "agent":      agent,
            "status":     status,
            "updated_at": now,
            **(metadata or {}),
        }

        if await redis_connection.ensure_connected():
            try:
                r = redis_connection.client
                await r.hset(
                    RedisKeys.agent_state(agent),
                    mapping={k: json.dumps(v) if not isinstance(v, str) else v
                             for k, v in state.items()},
                )
                await r.expire(RedisKeys.agent_state(agent), TTL.AGENT_STATE)
                # Heartbeat
                await r.set(
                    RedisKeys.agent_heartbeat(agent),
                    now,
                    ex=TTL.AGENT_HEARTBEAT,
                )
                # Active agents set
                await r.sadd(RedisKeys.active_agents(), agent)
                return
            except Exception as exc:
                log.warning("AgentActivity set_state Redis error: %s", exc)

        self._mem_state[agent] = state

    async def get_state(self, agent: str) -> Optional[Dict[str, Any]]:
        if await redis_connection.ensure_connected():
            try:
                raw = await redis_connection.client.hgetall(
                    RedisKeys.agent_state(agent)
                )
                if raw:
                    return {k: _decode(v) for k, v in raw.items()}
            except Exception as exc:
                log.warning("AgentActivity get_state Redis error: %s", exc)
        return self._mem_state.get(agent)

    # ------------------------------------------------------------------
    # Activity detail
    # ------------------------------------------------------------------

    async def set_activity(
        self,
        agent:        str,
        task:         str,
        execution_id: Optional[str]            = None,
        payload:      Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record what the agent is currently doing (fine-grained)."""
        now   = time.time()
        entry = {
            "agent":        agent,
            "task":         task,
            "execution_id": execution_id or "",
            "epoch":        str(now),
            "payload":      json.dumps(payload or {}),
        }
        entry_js = json.dumps({**entry, "payload": payload or {}})

        if await redis_connection.ensure_connected():
            try:
                r = redis_connection.client
                # Current detail hash
                await r.hset(RedisKeys.agent_activity(agent), mapping=entry)
                await r.expire(RedisKeys.agent_activity(agent), TTL.AGENT_ACTIVITY)
                # Timeline sorted set
                await r.zadd(RedisKeys.agent_activity_timeline(agent), {entry_js: now})
                await r.zremrangebyrank(
                    RedisKeys.agent_activity_timeline(agent), 0, -(TIMELINE_MAXLEN + 1)
                )
                await r.expire(RedisKeys.agent_activity_timeline(agent), TTL.AGENT_ACTIVITY)
                # Increment ops counter
                await r.incr(RedisKeys.agent_ops_counter(agent))
                await r.expire(RedisKeys.agent_ops_counter(agent), TTL.RUNTIME_METRICS)
                return
            except Exception as exc:
                log.warning("AgentActivity set_activity Redis error: %s", exc)

        self._mem_activity[agent] = {**entry, "payload": payload or {}}
        self._mem_ops[agent] += 1
        self._mem_timeline[agent].insert(0, self._mem_activity[agent])

    async def get_activity(self, agent: str) -> Optional[Dict[str, Any]]:
        if await redis_connection.ensure_connected():
            try:
                raw = await redis_connection.client.hgetall(
                    RedisKeys.agent_activity(agent)
                )
                if raw:
                    result = dict(raw)
                    if "payload" in result:
                        try:
                            result["payload"] = json.loads(result["payload"])
                        except json.JSONDecodeError:
                            pass
                    return result
            except Exception as exc:
                log.warning("AgentActivity get_activity Redis error: %s", exc)
        return self._mem_activity.get(agent)

    # ------------------------------------------------------------------
    # Active agents
    # ------------------------------------------------------------------

    async def list_active_agents(self) -> List[str]:
        """Return names of all agents that have been seen (not necessarily live)."""
        if await redis_connection.ensure_connected():
            try:
                members = await redis_connection.client.smembers(
                    RedisKeys.active_agents()
                )
                return sorted(members)
            except Exception as exc:
                log.warning("AgentActivity list_active_agents Redis error: %s", exc)
        return list(self._mem_state.keys())

    async def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """Return current state for all known agents."""
        agents = await self.list_active_agents()
        result = {}
        for agent in agents:
            state = await self.get_state(agent)
            if state:
                result[agent] = state
        return result

    # ------------------------------------------------------------------
    # Timeline
    # ------------------------------------------------------------------

    async def get_timeline(
        self,
        agent:       str,
        limit:       int   = 50,
        since_epoch: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Return the last *limit* activity entries for an agent."""
        if await redis_connection.ensure_connected():
            try:
                items = await redis_connection.client.zrangebyscore(
                    RedisKeys.agent_activity_timeline(agent),
                    min=since_epoch,
                    max="+inf",
                    withscores=False,
                    start=0,
                    num=limit,
                )
                return [json.loads(i) for i in reversed(items)]
            except Exception as exc:
                log.warning("AgentActivity get_timeline Redis error: %s", exc)
        entries = self._mem_timeline.get(agent, [])
        return [e for e in entries if float(e.get("epoch", 0)) >= since_epoch][:limit]

    # ------------------------------------------------------------------
    # Counters
    # ------------------------------------------------------------------

    async def get_ops_count(self, agent: str) -> int:
        if await redis_connection.ensure_connected():
            try:
                raw = await redis_connection.client.get(
                    RedisKeys.agent_ops_counter(agent)
                )
                return int(raw) if raw else 0
            except Exception as exc:
                log.warning("AgentActivity get_ops_count Redis error: %s", exc)
        return self._mem_ops.get(agent, 0)


def _decode(v: str) -> Any:
    try:
        return json.loads(v)
    except (json.JSONDecodeError, TypeError):
        return v


# ===========================================================================
# SINGLETON
# ===========================================================================

agent_activity_store = AgentActivityStore()
