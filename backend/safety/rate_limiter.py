"""
Enterprise API Rate Limiter — CortexPrime
==========================================
Redis-backed sliding-window rate limiting for all HTTP routes and
WebSocket connections.

Algorithm: Sliding Window Log using Redis Sorted Sets.
  - Key: ``cx:rl:{endpoint_key}:{identity}``
  - Score: Unix timestamp (milliseconds, float)
  - Members: unique request UUIDs (no collision under concurrency)
  - On each request:
      1. ZREMRANGEBYSCORE to evict entries outside the window
      2. ZCARD to count current requests
      3. If count < limit: ZADD + EXPIRE + allow
      4. If count >= limit: deny, compute retry-after from oldest entry

Fallback: when Redis is unavailable the limiter falls back to a local
in-process sliding-window counter.  This provides best-effort protection
without crashing the API.

Configuration (environment variables)
--------------------------------------
  RATE_LIMIT_ENABLED          true | false (default: true)
  RATE_LIMIT_WINDOW_SEC       window size in seconds (default: 60)

  Per-route limits (all in req/window):
  RATE_LIMIT_ORCHESTRATE      50
  RATE_LIMIT_EXECUTE          20
  RATE_LIMIT_VOICE            30
  RATE_LIMIT_OPERATOR         20
  RATE_LIMIT_GOVERNANCE       20
  RATE_LIMIT_GET              100
  RATE_LIMIT_DEFAULT          60
  RATE_LIMIT_WEBHOOK          120   (Phase 11.1: provider webhooks, per source IP)
  RATE_LIMIT_INGEST           300   (Phase 11.1: token-authenticated ingestion, per identity)

  WebSocket:
  RATE_LIMIT_WS_MSG_PER_MIN   120  (messages per minute per connection)
  RATE_LIMIT_WS_BYTES_PER_MIN 2097152  (bytes per minute per connection = 2 MiB)
"""
from __future__ import annotations

import logging
import os
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional, Tuple

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_ENABLED:     bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() != "false"
_WINDOW_SEC:  int  = int(os.getenv("RATE_LIMIT_WINDOW_SEC", "60"))

# Route-specific limits (requests per window)
_LIMITS: Dict[str, int] = {
    "orchestrate": int(os.getenv("RATE_LIMIT_ORCHESTRATE",  "50")),
    "execute":     int(os.getenv("RATE_LIMIT_EXECUTE",      "20")),
    "voice":       int(os.getenv("RATE_LIMIT_VOICE",        "30")),
    "operator":    int(os.getenv("RATE_LIMIT_OPERATOR",     "20")),
    "governance":  int(os.getenv("RATE_LIMIT_GOVERNANCE",   "20")),
    "get":         int(os.getenv("RATE_LIMIT_GET",          "100")),
    "default":     int(os.getenv("RATE_LIMIT_DEFAULT",      "60")),
    # Phase 11.1 (ADR-121): the externally reachable ingestion boundary gets
    # its own buckets so a webhook flood cannot consume the operator's default
    # budget, and so the limits are documented where an operator looks.
    "webhook":     int(os.getenv("RATE_LIMIT_WEBHOOK",      "120")),
    "ingest":      int(os.getenv("RATE_LIMIT_INGEST",       "300")),
}

# WebSocket
_WS_MSG_PER_MIN:   int = int(os.getenv("RATE_LIMIT_WS_MSG_PER_MIN",   "120"))
_WS_BYTES_PER_MIN: int = int(os.getenv("RATE_LIMIT_WS_BYTES_PER_MIN", str(2 * 1024 * 1024)))

# Redis key prefix
_KEY_PREFIX = "cx:rl:"


# ---------------------------------------------------------------------------
# Decision dataclass
# ---------------------------------------------------------------------------

@dataclass
class RateLimitDecision:
    allowed:     bool
    limit:       int
    remaining:   int
    window_sec:  int
    retry_after: int        # seconds until window resets (only meaningful when denied)
    identity:    str
    endpoint:    str
    backend:     str        # "redis" | "local"

    def headers(self) -> Dict[str, str]:
        """HTTP headers to attach to every response."""
        return {
            "X-RateLimit-Limit":     str(self.limit),
            "X-RateLimit-Remaining": str(max(self.remaining, 0)),
            "X-RateLimit-Window":    str(self.window_sec),
            "X-RateLimit-Backend":   self.backend,
        }

    def retry_headers(self) -> Dict[str, str]:
        """Extra headers when a 429 is returned."""
        return {
            **self.headers(),
            "Retry-After": str(self.retry_after),
        }


# ---------------------------------------------------------------------------
# In-process fallback counter (used when Redis is unavailable)
# ---------------------------------------------------------------------------

class _LocalSlidingWindow:
    """
    Pure-Python sliding window per (endpoint, identity).
    Thread-safe enough for asyncio; not for multi-process.
    """

    def __init__(self) -> None:
        # (endpoint, identity) → deque of request timestamps (float seconds)
        self._windows: Dict[Tuple[str, str], Deque[float]] = defaultdict(deque)

    def check(self, endpoint: str, identity: str, limit: int, window_sec: int) -> Tuple[bool, int, int]:
        """
        Returns (allowed, remaining, retry_after_sec).
        """
        key = (endpoint, identity)
        now = time.time()
        cutoff = now - window_sec
        dq = self._windows[key]

        # Evict expired entries
        while dq and dq[0] < cutoff:
            dq.popleft()

        count = len(dq)
        if count < limit:
            dq.append(now)
            remaining = limit - count - 1
            return True, remaining, 0
        else:
            # retry_after = how long until the oldest entry expires
            oldest = dq[0] if dq else now
            retry_after = max(1, int(oldest + window_sec - now) + 1)
            return False, 0, retry_after

    def active_key_count(self) -> int:
        return len(self._windows)


_local_fallback = _LocalSlidingWindow()


# ---------------------------------------------------------------------------
# Redis sliding window implementation
# ---------------------------------------------------------------------------

async def _redis_check(
    redis_client: Any,
    endpoint: str,
    identity: str,
    limit: int,
    window_sec: int,
) -> Tuple[bool, int, int]:
    """
    Sliding window log via Redis Sorted Set.

    Returns (allowed, remaining, retry_after_sec).
    Uses a Lua script for atomicity — ZADD + ZREMRANGEBYSCORE + ZCARD in one round-trip.
    """
    key     = f"{_KEY_PREFIX}{endpoint}:{identity}"
    now_ms  = time.time() * 1000          # milliseconds float
    cutoff  = now_ms - (window_sec * 1000)
    member  = str(uuid.uuid4())

    # Atomic Lua script: prune + count + conditionally add + expire
    _LUA = """
local key       = KEYS[1]
local cutoff    = tonumber(ARGV[1])
local now_ms    = tonumber(ARGV[2])
local limit     = tonumber(ARGV[3])
local window_ms = tonumber(ARGV[4])
local member    = ARGV[5]

-- Remove entries outside the sliding window
redis.call('ZREMRANGEBYSCORE', key, '-inf', cutoff)

-- Current count
local count = redis.call('ZCARD', key)

if count < limit then
    -- Add this request
    redis.call('ZADD', key, now_ms, member)
    -- Expire the key slightly after one full window
    redis.call('PEXPIRE', key, math.ceil(window_ms * 1.1))
    return {1, limit - count - 1, 0}
else
    -- Compute retry-after from the oldest entry still in the window
    local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
    local oldest_ms = tonumber(oldest[2]) or now_ms
    local retry_after_ms = oldest_ms + window_ms - now_ms
    return {0, 0, math.max(1000, math.ceil(retry_after_ms))}
end
"""
    try:
        result = await redis_client.eval(
            _LUA,
            1,
            key,
            cutoff,
            now_ms,
            limit,
            window_sec * 1000,
            member,
        )
        allowed      = bool(result[0])
        remaining    = int(result[1])
        # result[2] is retry-after in milliseconds when denied
        retry_after  = max(1, int(result[2] / 1000) + 1) if not allowed else 0
        return allowed, remaining, retry_after
    except Exception as exc:
        log.warning("Redis rate-limit eval failed, falling back to local: %s", exc)
        raise


# ---------------------------------------------------------------------------
# WebSocket Redis counter (per-connection, per-minute)
# ---------------------------------------------------------------------------

async def _ws_redis_check(
    redis_client: Any,
    conn_id: str,
    msg_size_bytes: int,
) -> bool:
    """
    Check a WebSocket message against per-connection msg+byte limits.
    Uses two Redis INCRBY counters with 60 s TTL.
    Returns True if within limits.
    """
    now_bucket   = int(time.time() // 60)   # 1-minute bucket
    key_msg      = f"{_KEY_PREFIX}ws:msg:{conn_id}:{now_bucket}"
    key_bytes    = f"{_KEY_PREFIX}ws:bytes:{conn_id}:{now_bucket}"

    try:
        pipe = redis_client.pipeline()
        pipe.incr(key_msg)
        pipe.incrby(key_bytes, msg_size_bytes)
        pipe.expire(key_msg, 120)
        pipe.expire(key_bytes, 120)
        results = await pipe.execute()

        msg_count  = int(results[0])
        byte_count = int(results[1])

        if msg_count > _WS_MSG_PER_MIN:
            log.warning("WS Redis rate limit: conn=%s msg_count=%d", conn_id, msg_count)
            return False
        if byte_count > _WS_BYTES_PER_MIN:
            log.warning("WS Redis rate limit: conn=%s byte_count=%d", conn_id, byte_count)
            return False
        return True
    except Exception as exc:
        log.warning("WS Redis rate check failed, using local: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Endpoint classifier
# ---------------------------------------------------------------------------

def _classify_endpoint(path: str, method: str) -> str:
    """
    Map a request path + method to a rate-limit bucket name.
    GET requests all share one generous bucket.
    """
    if method.upper() == "GET":
        return "get"

    # POST/PUT/PATCH path matching (longest-prefix wins)
    path_lower = path.lower()
    # Ingestion buckets first: a webhook path can also contain "/execute"-like
    # fragments in provider names, and the boundary bucket must win.
    if path_lower.endswith("/webhook") or "/webhook/" in path_lower:
        return "webhook"
    if "/ingest/" in path_lower or path_lower.endswith("/otel/v1/traces"):
        return "ingest"
    if "/orchestrate" in path_lower:
        return "orchestrate"
    if "/execute" in path_lower:
        return "execute"
    if "/voice" in path_lower:
        return "voice"
    if "/operator" in path_lower:
        return "operator"
    if "/governance" in path_lower:
        return "governance"
    return "default"


# ---------------------------------------------------------------------------
# Public API — RateLimiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """
    Enterprise Redis-backed sliding-window rate limiter.

    Usage
    -----
    Typically called by ``RateLimitMiddleware``.  Can also be injected
    directly into FastAPI route handlers via ``Depends(get_rate_limiter)``.

    The limiter self-heals when Redis comes back up: every call tries Redis
    first, falls back to local memory on failure.
    """

    def __init__(self) -> None:
        self._redis_ok: bool = True   # optimistic — will be corrected on first failure

    async def _get_redis(self) -> Optional[Any]:
        """Return the Redis client if available, else None."""
        try:
            from backend.infrastructure.redis.connection import redis_connection
            if await redis_connection.ensure_connected():
                return redis_connection.client
        except Exception:
            pass
        return None

    async def check(
        self,
        path:     str,
        method:   str,
        identity: str,
    ) -> RateLimitDecision:
        """
        Check whether the (identity, endpoint) pair is within its limit.

        ``identity`` should be user_id from JWT, falling back to client IP.
        """
        if not _ENABLED:
            endpoint = _classify_endpoint(path, method)
            limit    = _LIMITS.get(endpoint, _LIMITS["default"])
            return RateLimitDecision(
                allowed=True, limit=limit, remaining=limit - 1,
                window_sec=_WINDOW_SEC, retry_after=0,
                identity=identity, endpoint=endpoint, backend="disabled",
            )

        endpoint = _classify_endpoint(path, method)
        limit    = _LIMITS.get(endpoint, _LIMITS["default"])
        redis    = await self._get_redis()

        if redis is not None:
            try:
                allowed, remaining, retry_after = await _redis_check(
                    redis, endpoint, identity, limit, _WINDOW_SEC
                )
                self._redis_ok = True
                return RateLimitDecision(
                    allowed=allowed, limit=limit, remaining=remaining,
                    window_sec=_WINDOW_SEC, retry_after=retry_after,
                    identity=identity, endpoint=endpoint, backend="redis",
                )
            except Exception:
                self._redis_ok = False
                # fall through to local

        # Local fallback
        allowed, remaining, retry_after = _local_fallback.check(
            endpoint, identity, limit, _WINDOW_SEC
        )
        return RateLimitDecision(
            allowed=allowed, limit=limit, remaining=remaining,
            window_sec=_WINDOW_SEC, retry_after=retry_after,
            identity=identity, endpoint=endpoint, backend="local",
        )

    async def check_websocket(
        self,
        conn_id:        str,
        msg_size_bytes: int,
    ) -> bool:
        """
        Check a single WebSocket message against per-connection limits.
        Returns True if within limits.
        Falls back to the existing in-process limiter when Redis is down.
        """
        redis = await self._get_redis()
        if redis is not None:
            try:
                return await _ws_redis_check(redis, conn_id, msg_size_bytes)
            except Exception:
                pass  # fall through to local

        # Local fallback using the existing in-process window
        from backend.websocket.auth import rate_limiter as _ws_local
        return _ws_local.check(conn_id, msg_size_bytes)

    async def active_key_count(self) -> int:
        """Return the number of distinct rate-limit keys currently in Redis."""
        redis = await self._get_redis()
        if redis is None:
            return _local_fallback.active_key_count()
        try:
            # Scan for all cx:rl:* keys — use SCAN to avoid blocking
            count = 0
            cursor = 0
            while True:
                cursor, keys = await redis.scan(cursor, match=f"{_KEY_PREFIX}*", count=200)
                count += len(keys)
                if cursor == 0:
                    break
            return count
        except Exception:
            return _local_fallback.active_key_count()

    async def status(self) -> Dict[str, Any]:
        """Return a health snapshot for the /health/rate-limiter endpoint."""
        redis = await self._get_redis()
        redis_connected = redis is not None
        active_keys     = await self.active_key_count()

        return {
            "status":         "healthy" if redis_connected else "degraded",
            "enabled":        _ENABLED,
            "redis_connected": redis_connected,
            "backend":        "redis" if redis_connected else "local_fallback",
            "active_keys":    active_keys,
            "window_sec":     _WINDOW_SEC,
            "limits":         _LIMITS,
            "ws_limits": {
                "msg_per_min":   _WS_MSG_PER_MIN,
                "bytes_per_min": _WS_BYTES_PER_MIN,
            },
        }


# Singleton
rate_limiter = RateLimiter()
