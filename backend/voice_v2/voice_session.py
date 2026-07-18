"""
Voice V2 session models and in-memory session store.

Includes Redis-backed persistence for multi-turn conversation continuity
and recovery after disconnect.
"""

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional

log = logging.getLogger(__name__)

# Maximum turns kept in transcript_log (older turns pruned to bound memory)
_MAX_TRANSCRIPT_TURNS = 200

# Number of recent turns injected into mission context
CONTEXT_TURNS = 20


@dataclass
class VoiceSession:
    session_id:          str
    room_name:           str
    user_identity:       str
    workspace_id:        Optional[str]
    created_at:          float = field(default_factory=time.time)
    last_activity:       float = field(default_factory=time.time)
    is_active:           bool  = True
    transcript_log:      list  = field(default_factory=list)
    # Conversation telemetry
    turn_count:          int   = 0
    memory_recall_count: int   = 0
    # Recovery telemetry
    disconnect_count:    int   = 0
    reconnect_count:     int   = 0
    last_disconnect_at:  Optional[float] = None
    last_reconnect_at:   Optional[float] = None

    def touch(self) -> None:
        self.last_activity = time.time()

    def record_disconnect(self) -> None:
        """Mark a client disconnect; bumps counter and timestamp."""
        self.disconnect_count  += 1
        self.last_disconnect_at = time.time()
        self.touch()

    def record_reconnect(self) -> None:
        """Mark a successful client reconnect; bumps counter and timestamp."""
        self.reconnect_count  += 1
        self.last_reconnect_at = time.time()
        self.is_active         = True
        self.touch()

    def append_turn(self, role: str, text: str) -> None:
        """Append a single conversation turn and update counters."""
        self.transcript_log.append({
            "role":      role,
            "text":      text,
            "timestamp": time.time(),
        })
        self.turn_count += 1
        # Bound the in-memory log to avoid unbounded growth
        if len(self.transcript_log) > _MAX_TRANSCRIPT_TURNS:
            self.transcript_log = self.transcript_log[-_MAX_TRANSCRIPT_TURNS:]
        self.touch()

    def last_n_turns(self, n: int = CONTEXT_TURNS) -> str:
        """
        Return the last *n* transcript entries as a formatted context block.

        Example output:
            ## Voice Conversation History
            User: Explain Redis.
            Assistant: Redis is an in-memory data structure store...
            User: Summarize that.
        """
        if not self.transcript_log:
            return ""
        recent = self.transcript_log[-n:]
        lines  = ["## Voice Conversation History (current session)"]
        for entry in recent:
            role = entry.get("role", "user").capitalize()
            text = entry.get("text", "").strip()
            lines.append(f"{role}: {text}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Lightweight dict for API responses (no full transcript)."""
        return {
            "session_id":          self.session_id,
            "room_name":           self.room_name,
            "user_identity":       self.user_identity,
            "workspace_id":        self.workspace_id,
            "created_at":          self.created_at,
            "last_activity":       self.last_activity,
            "is_active":           self.is_active,
            "turn_count":          self.turn_count,
            "memory_recall_count": self.memory_recall_count,
            "disconnect_count":    self.disconnect_count,
            "reconnect_count":     self.reconnect_count,
            "last_disconnect_at":  self.last_disconnect_at,
            "last_reconnect_at":   self.last_reconnect_at,
        }

    def to_redis_dict(self) -> dict:
        """Full serialisable dict including transcript_log for Redis storage."""
        return {
            "session_id":          self.session_id,
            "room_name":           self.room_name,
            "user_identity":       self.user_identity,
            "workspace_id":        self.workspace_id,
            "created_at":          self.created_at,
            "last_activity":       self.last_activity,
            "is_active":           self.is_active,
            "transcript_log":      self.transcript_log,
            "turn_count":          self.turn_count,
            "memory_recall_count": self.memory_recall_count,
            "disconnect_count":    self.disconnect_count,
            "reconnect_count":     self.reconnect_count,
            "last_disconnect_at":  self.last_disconnect_at,
            "last_reconnect_at":   self.last_reconnect_at,
        }

    @classmethod
    def from_redis_dict(cls, data: dict) -> "VoiceSession":
        """Reconstruct a VoiceSession from Redis-stored JSON."""
        return cls(
            session_id          = data["session_id"],
            room_name           = data["room_name"],
            user_identity       = data["user_identity"],
            workspace_id        = data.get("workspace_id"),
            created_at          = data.get("created_at", time.time()),
            last_activity       = data.get("last_activity", time.time()),
            is_active           = data.get("is_active", True),
            transcript_log      = data.get("transcript_log", []),
            turn_count          = data.get("turn_count", 0),
            memory_recall_count = data.get("memory_recall_count", 0),
            disconnect_count    = data.get("disconnect_count", 0),
            reconnect_count     = data.get("reconnect_count", 0),
            last_disconnect_at  = data.get("last_disconnect_at"),
            last_reconnect_at   = data.get("last_reconnect_at"),
        )


class VoiceSessionStore:
    """
    Voice session registry with in-memory primary store and Redis
    persistence for multi-turn conversation recovery.
    """

    def __init__(self) -> None:
        self._sessions: Dict[str, VoiceSession] = {}

    # ── In-memory CRUD ────────────────────────────────────────────────────

    def create(
        self,
        room_name:     str,
        user_identity: str,
        workspace_id:  Optional[str] = None,
    ) -> VoiceSession:
        session_id = str(uuid.uuid4())
        session    = VoiceSession(
            session_id    = session_id,
            room_name     = room_name,
            user_identity = user_identity,
            workspace_id  = workspace_id,
        )
        self._sessions[session_id] = session
        return session

    def get(self, session_id: str) -> Optional[VoiceSession]:
        return self._sessions.get(session_id)

    def close(self, session_id: str) -> bool:
        s = self._sessions.get(session_id)
        if s:
            s.is_active = False
            return True
        return False

    def remove(self, session_id: str) -> bool:
        return bool(self._sessions.pop(session_id, None))

    def list_active(self) -> list:
        return [s.to_dict() for s in self._sessions.values() if s.is_active]

    def prune_stale(self, max_idle_secs: int = 1800) -> int:
        now   = time.time()
        stale = [sid for sid, s in self._sessions.items()
                 if not s.is_active or (now - s.last_activity) > max_idle_secs]
        for sid in stale:
            del self._sessions[sid]
        return len(stale)

    # ── Redis persistence ─────────────────────────────────────────────────

    async def persist(self, session: VoiceSession) -> None:
        """Write the full session (including transcript) to Redis."""
        try:
            from backend.infrastructure.redis.connection import redis_connection
            from backend.infrastructure.redis.keys import TTL, RedisKeys
            r = await redis_connection.ensure_connected()
            key  = RedisKeys.voice_session(session.session_id)
            data = json.dumps(session.to_redis_dict())
            await r.setex(key, TTL.VOICE_SESSION, data)
            # Maintain index (ZSET scored by created_at)
            await r.zadd(
                RedisKeys.voice_session_index(),
                {session.session_id: session.created_at},
            )
        except Exception as exc:
            log.warning("Voice session persist failed: %s", exc)

    async def restore(self, session_id: str) -> Optional[VoiceSession]:
        """
        Restore a session from Redis.
        Registers it in the in-memory store and returns it, or None.
        """
        try:
            from backend.infrastructure.redis.connection import redis_connection
            from backend.infrastructure.redis.keys import RedisKeys
            r    = await redis_connection.ensure_connected()
            key  = RedisKeys.voice_session(session_id)
            raw  = await r.get(key)
            if not raw:
                return None
            data    = json.loads(raw)
            session = VoiceSession.from_redis_dict(data)
            self._sessions[session_id] = session
            log.info(
                "🔄 Voice session restored from Redis | id=%s | turns=%d",
                session_id[:8], session.turn_count,
            )
            return session
        except Exception as exc:
            log.warning("Voice session restore failed: %s", exc)
            return None

    async def get_or_restore(self, session_id: str) -> Optional[VoiceSession]:
        """
        Return in-memory session, falling back to Redis restore.
        Used by the LLM processor after a reconnect.
        """
        s = self._sessions.get(session_id)
        if s:
            return s
        return await self.restore(session_id)

    async def get_history(self, session_id: str) -> List[dict]:
        """
        Return transcript_log for a session (from memory or Redis).
        Used by the recovery endpoint.
        """
        s = await self.get_or_restore(session_id)
        return s.transcript_log if s else []

    async def record_disconnect(self, session_id: str) -> None:
        """Mark session disconnected, persist updated telemetry to Redis."""
        s = await self.get_or_restore(session_id)
        if s:
            s.record_disconnect()
            await self.persist(s)

    async def record_reconnect(self, session_id: str) -> None:
        """Mark session reconnected, persist updated telemetry to Redis."""
        s = self._sessions.get(session_id)
        if s:
            s.record_reconnect()
            await self.persist(s)


voice_session_store = VoiceSessionStore()
