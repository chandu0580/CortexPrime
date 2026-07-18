"""
Redis Token Blacklist â€” CortexPrime
=====================================
Immediate JWT invalidation without waiting for natural expiry.

Every revoked token is stored in Redis with a TTL that matches the token's
own remaining lifetime, so keys self-clean when they would have expired
anyway â€” no background sweep required.

Key schema
----------
cx:auth:bl:jti:{jti}          STRING  value="{user_id}"
                               TTL = remaining seconds until token expiry

cx:auth:bl:user:{user_id}     STRING  value="{revoked_at_epoch}"
                               TTL = JWT_REFRESH_EXPIRE_H * 3600
                               Presence means "revoke ALL tokens for this
                               user that were issued at or before this epoch".

cx:auth:sess:{user_id}        ZSET    member={jti}, score={expiry_epoch}
                               Tracks active sessions for health/audit
                               reporting; cleaned up on logout and expiry.

When Redis is unavailable, revocation checks default to:
  - FAIL CLOSED in production
  - FAIL OPEN in development / test

This keeps local auth usable when Redis is intentionally absent while
preserving the stricter production default. Operators can override the
behaviour explicitly via REVOCATION_FAIL_OPEN=true|false.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Seconds to keep the user-level revocation marker alive.
# Must cover the maximum possible token lifetime (refresh TTL).
_REFRESH_EXPIRE_H: int = int(os.getenv("JWT_REFRESH_EXPIRE_H", "168"))
_USER_REVOKE_TTL:  int = _REFRESH_EXPIRE_H * 3600   # 7 days by default

_FAIL_OPEN_DEFAULT_ENVS = {"development", "dev", "local", "test", "testing"}


def _runtime_environment() -> str:
    return (
        os.getenv("ENVIRONMENT")
        or os.getenv("ENV")
        or "development"
    ).strip().lower()


def _compute_fail_open() -> bool:
    """
    Production remains fail-closed by default.
    Local development and tests default to fail-open unless explicitly
    overridden so auth can still function without Redis.
    """
    env_default = "true" if _runtime_environment() in _FAIL_OPEN_DEFAULT_ENVS else "false"
    return os.getenv("REVOCATION_FAIL_OPEN", env_default).lower() == "true"


# When True: Redis errors allow the request through (fail-open).
# When False: Redis errors reject the request (fail-closed / secure).
_FAIL_OPEN: bool = _compute_fail_open()

# ---------------------------------------------------------------------------
# Key helpers
# ---------------------------------------------------------------------------

_PFX_JTI  = "cx:auth:bl:jti:"
_PFX_USER = "cx:auth:bl:user:"
_PFX_SESS = "cx:auth:sess:"


class TokenBlacklist:
    """
    Redis-backed JWT blacklist with per-token and per-user revocation.

    Usage
    -----
    All public methods are async and must be awaited.

    Instantiate once as a module-level singleton::

        token_blacklist = TokenBlacklist()

    Then inject wherever needed::

        if await token_blacklist.is_revoked(jti, user_id, issued_at):
            raise HTTPException(401, "Token revoked")
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_redis(self) -> Optional[Any]:
        """Return the live async Redis client or None."""
        try:
            from backend.infrastructure.redis.connection import redis_connection
            if await redis_connection.ensure_connected():
                return redis_connection.client
        except Exception as exc:
            log.debug("TokenBlacklist: Redis unavailable: %s", exc)
        return None

    async def _get_write_redis(self) -> Optional[Any]:
        """
        Return the Redis client for WRITE operations.

        In strict mode, missing Redis is fatal because revocation writes must
        not be silently lost. In fail-open mode we degrade to best-effort so
        development auth flows can continue without Redis.
        """
        redis = await self._get_redis()
        if redis is None:
            if _FAIL_OPEN:
                log.warning(
                    "Redis unavailable — skipping blacklist write "
                    "(REVOCATION_FAIL_OPEN=true)"
                )
                return None
            raise RuntimeError("Redis unavailable — cannot write to token blacklist")
        return redis

    # ------------------------------------------------------------------
    # Revoke a single token by JTI
    # ------------------------------------------------------------------

    async def revoke_token(
        self,
        jti:        str,
        user_id:    str,
        expires_at: float,           # Unix epoch (seconds) of token expiry
        token_type: str = "access",  # "access" | "refresh"
    ) -> None:
        """
        Add a JTI to the blacklist.

        The Redis key TTL is set to the remaining seconds until the token's
        natural expiry so memory is reclaimed automatically.

        Raises RuntimeError if Redis is unavailable (writes must not be lost).
        """
        if not jti:
            log.warning("revoke_token called with empty jti â€” skipping")
            return

        remaining = max(1, int(expires_at - time.time()))
        redis = await self._get_write_redis()
        if redis is None:
            return
        key   = f"{_PFX_JTI}{jti}"

        await redis.set(key, user_id, ex=remaining)
        log.info(
            "Token revoked: jti=%s user=%s type=%s ttl=%ds",
            jti[:8], user_id[:32], token_type, remaining,
        )

    # ------------------------------------------------------------------
    # Check whether a specific JTI is blacklisted
    # ------------------------------------------------------------------

    async def is_jti_revoked(self, jti: str) -> bool:
        """
        Return True if this specific JTI has been individually revoked.
        Fails closed when Redis is unavailable and REVOCATION_FAIL_OPEN=false.
        """
        if not jti:
            # Token without jti â†’ cannot verify â†’ reject unless fail-open
            return not _FAIL_OPEN

        redis = await self._get_redis()
        if redis is None:
            if _FAIL_OPEN:
                log.warning("Redis unavailable â€” failing OPEN (REVOCATION_FAIL_OPEN=true)")
                return False
            log.warning("Redis unavailable â€” rejecting token (fail-closed)")
            return True   # fail-closed

        try:
            result = await redis.get(f"{_PFX_JTI}{jti}")
            return result is not None
        except Exception as exc:
            log.error("Blacklist JTI check error: %s", exc)
            return not _FAIL_OPEN

    # ------------------------------------------------------------------
    # Check user-level revocation
    # ------------------------------------------------------------------

    async def revoke_all_user_tokens(self, user_id: str) -> float:
        """
        Revoke ALL tokens for a user issued at or before NOW.

        Stores the current epoch as the revocation marker.
        Any token with ``iat <= stored_epoch`` will be rejected.

        Returns the revocation epoch.
        Raises RuntimeError if Redis is unavailable.
        """
        now   = time.time()
        redis = await self._get_write_redis()
        if redis is None:
            log.warning(
                "Redis unavailable — user-wide revocation for %s was not persisted",
                user_id[:32],
            )
            return now
        key   = f"{_PFX_USER}{user_id}"

        await redis.set(key, str(now), ex=_USER_REVOKE_TTL)

        # Also remove all tracked sessions for this user
        await redis.delete(f"{_PFX_SESS}{user_id}")

        log.warning(
            "All tokens revoked for user=%s (epoch=%.3f)",
            user_id[:32], now,
        )
        return now

    async def is_user_globally_revoked(
        self, user_id: str, issued_at: float
    ) -> bool:
        """
        Return True if there is a user-level revocation event and the
        token's ``iat`` is at or before that event's epoch.

        Fails closed when Redis is unavailable.
        """
        redis = await self._get_redis()
        if redis is None:
            return not _FAIL_OPEN

        try:
            raw = await redis.get(f"{_PFX_USER}{user_id}")
            if raw is None:
                return False
            revoke_epoch = float(raw)
            return float(issued_at) <= revoke_epoch
        except Exception as exc:
            log.error("User revocation check error: %s", exc)
            return not _FAIL_OPEN

    # ------------------------------------------------------------------
    # Combined check â€” single call for the middleware/dependency
    # ------------------------------------------------------------------

    async def is_revoked(
        self,
        jti:       str,
        user_id:   str,
        issued_at: float,  # iat claim from JWT payload (epoch seconds)
    ) -> bool:
        """
        Check BOTH individual JTI revocation AND user-level revocation.

        Returns True (= reject the token) if either check fires.
        """
        if await self.is_jti_revoked(jti):
            return True
        if await self.is_user_globally_revoked(user_id, issued_at):
            return True
        return False

    # ------------------------------------------------------------------
    # Session tracking (for health endpoint active_sessions count)
    # ------------------------------------------------------------------

    async def track_session(
        self,
        jti:        str,
        user_id:    str,
        expires_at: float,
    ) -> None:
        """
        Record this JTI as an active session.
        Silently no-ops when Redis is unavailable.
        """
        redis = await self._get_redis()
        if redis is None:
            return
        try:
            key = f"{_PFX_SESS}{user_id}"
            pipe = redis.pipeline()
            # Prune expired members first
            pipe.zremrangebyscore(key, "-inf", time.time())
            # Add new session (score = expiry epoch)
            pipe.zadd(key, {jti: expires_at})
            # Keep the ZSET itself alive for the token lifetime
            pipe.expireat(key, int(expires_at) + 60)
            await pipe.execute()
        except Exception as exc:
            log.debug("track_session error (non-fatal): %s", exc)

    async def remove_session(self, jti: str, user_id: str) -> None:
        """Remove a JTI from the active session tracker (called on logout)."""
        redis = await self._get_redis()
        if redis is None:
            return
        try:
            await redis.zrem(f"{_PFX_SESS}{user_id}", jti)
        except Exception as exc:
            log.debug("remove_session error (non-fatal): %s", exc)

    # ------------------------------------------------------------------
    # Health / metrics
    # ------------------------------------------------------------------

    async def revoked_token_count(self) -> int:
        """Count of individual JTI entries currently in the blacklist."""
        redis = await self._get_redis()
        if redis is None:
            return -1   # unknown
        try:
            count  = 0
            cursor = 0
            while True:
                cursor, keys = await redis.scan(
                    cursor, match=f"{_PFX_JTI}*", count=200
                )
                count += len(keys)
                if cursor == 0:
                    break
            return count
        except Exception as exc:
            log.error("revoked_token_count error: %s", exc)
            return -1

    async def active_session_count(self) -> int:
        """
        Count of active (non-expired) sessions tracked across all users.
        Scans ``cx:auth:sess:*`` sorted sets; not suitable for very high
        user counts but fine for a health endpoint.
        """
        redis = await self._get_redis()
        if redis is None:
            return -1
        try:
            total  = 0
            now    = time.time()
            cursor = 0
            while True:
                cursor, keys = await redis.scan(
                    cursor, match=f"{_PFX_SESS}*", count=200
                )
                for key in keys:
                    # Count members with score > now (not yet expired)
                    count = await redis.zcount(key, now, "+inf")
                    total += count
                if cursor == 0:
                    break
            return total
        except Exception as exc:
            log.error("active_session_count error: %s", exc)
            return -1

    async def status(self) -> Dict[str, Any]:
        """Return a health dict for the /health/auth endpoint."""
        redis = await self._get_redis()
        redis_connected = redis is not None
        revoked = await self.revoked_token_count()
        sessions = await self.active_session_count()

        return {
            "status":               "healthy" if redis_connected else "degraded",
            "redis_connected":      redis_connected,
            "fail_open":            _FAIL_OPEN,
            "revoked_token_count":  revoked,
            "active_sessions":      sessions,
            "user_revoke_ttl_sec":  _USER_REVOKE_TTL,
        }


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

token_blacklist = TokenBlacklist()
