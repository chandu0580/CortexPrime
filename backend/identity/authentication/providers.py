from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from backend.database.repositories.iam import UserRepository
from backend.identity.authentication.password_verifier import PasswordVerifier
from backend.identity.interfaces.authentication import (
    AuthenticationProvider,
    Identity,
    IdentityProvider,
    TokenClaims,
    TokenProvider,
    TokenResult,
)
from backend.identity.jwt.access_token import AccessTokenProvider
from backend.identity.jwt.key_store import KeyStore
from backend.identity.jwt.keys import IdentityRedisKeys
from backend.identity.jwt.refresh_token import RefreshTokenProvider

log = logging.getLogger(__name__)

try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None


class DefaultAuthenticationProvider(AuthenticationProvider):
    def __init__(
        self,
        password_verifier: PasswordVerifier,
        user_repository: UserRepository,
    ):
        self._password_verifier = password_verifier
        self._user_repo = user_repository

    async def authenticate(self, identifier: str, secret: str, tenant_id: Optional[str] = None) -> Optional[Identity]:
        user = await self._user_repo.get_by_email(identifier.strip().lower())
        if user is None:
            return None
        if user.status != "active":
            return None
        if user.password_hash and not self._password_verifier.verify_password(secret, user.password_hash):
            return None
        if not user.password_hash:
            return None
        return Identity(
            user_id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            role="admin" if "admin" in (user.roles or []) else "member",
            permissions=user.roles or [],
            metadata={"user_model_id": str(user.id)},
        )

    async def get_identity(self, user_id: str) -> Optional[Identity]:
        import uuid
        try:
            uid = uuid.UUID(user_id)
        except ValueError:
            return None
        user = await self._user_repo.get(uid)
        if user is None:
            return None
        return Identity(
            user_id=str(user.id),
            email=user.email,
            display_name=user.display_name,
            role="admin" if "admin" in (user.roles or []) else "member",
            permissions=user.roles or [],
            metadata={"user_model_id": str(user.id)},
        )


class DefaultTokenProvider(TokenProvider):
    def __init__(
        self,
        key_store: KeyStore,
        access_token_provider: AccessTokenProvider,
        refresh_token_provider: RefreshTokenProvider,
    ):
        self._key_store = key_store
        self._access_provider = access_token_provider
        self._refresh_provider = refresh_token_provider
        self._redis_client: Optional[Any] = None

    async def _get_redis(self) -> Optional[Any]:
        if self._redis_client is not None:
            try:
                await self._redis_client.ping()
                return self._redis_client
            except Exception:
                self._redis_client = None
        try:
            from backend.infrastructure.redis.connection import redis_connection
            if await redis_connection.ensure_connected():
                self._redis_client = redis_connection.client
                return self._redis_client
        except Exception:
            pass
        return None

    async def create_token_pair(self, identity: Identity) -> TokenResult:
        now = datetime.now(timezone.utc)
        jti = secrets.token_hex(16)
        access_exp = now + timedelta(minutes=self._key_store.access_expire_minutes)
        refresh_exp = now + timedelta(hours=self._key_store.refresh_expire_hours)

        access_claims = TokenClaims(
            sub=identity.user_id,
            role=identity.role,
            type="access",
            jti=jti,
            iat=now,
            exp=access_exp,
            tenant_id=identity.tenant_id,
            tenant_slug=identity.tenant_slug,
            user_role=identity.user_role,
            email=identity.email,
            permissions=identity.permissions,
        )
        refresh_claims = TokenClaims(
            sub=identity.user_id,
            role=identity.role,
            type="refresh",
            jti=secrets.token_hex(16),
            iat=now,
            exp=refresh_exp,
            tenant_id=identity.tenant_id,
            tenant_slug=identity.tenant_slug,
            user_role=identity.user_role,
            email=identity.email,
        )
        access_token = await self._access_provider.create(access_claims)
        refresh_token = await self._refresh_provider.create(refresh_claims)

        return TokenResult(
            access_token=access_token,
            refresh_token=refresh_token,
            access_expires_at=access_exp,
            refresh_expires_at=refresh_exp,
            claims=access_claims,
        )

    async def validate_access_token(self, token: str) -> Optional[TokenClaims]:
        claims = await self._access_provider.validate(token)
        if claims is None:
            return None
        if await self.is_token_revoked(claims.jti, claims.sub, claims.iat):
            return None
        return claims

    async def validate_refresh_token(self, token: str) -> Optional[TokenClaims]:
        return await self._refresh_provider.validate(token)

    async def refresh_access_token(self, refresh_token: str) -> Optional[TokenResult]:
        old_claims = await self._refresh_provider.validate(refresh_token)
        if old_claims is None:
            return None
        if await self.is_token_revoked(old_claims.jti, old_claims.sub, old_claims.iat):
            return None
        await self.revoke_token(old_claims.jti, old_claims.sub, old_claims.exp)
        identity = Identity(
            user_id=old_claims.sub,
            email=old_claims.email or "",
            display_name=old_claims.sub,
            role=old_claims.role,
            tenant_id=old_claims.tenant_id,
            tenant_slug=old_claims.tenant_slug,
            user_role=old_claims.user_role,
            permissions=[],
        )
        return await self.create_token_pair(identity)

    async def revoke_token(self, jti: str, user_id: str, expires_at: datetime) -> None:
        redis = await self._get_redis()
        if redis is None:
            log.warning("Redis unavailable — token revocation skipped")
            return
        remaining = max(1, int(expires_at.timestamp() - time.time()))
        await redis.set(IdentityRedisKeys.jti_key(jti), user_id, ex=remaining)
        log.info("Token revoked: jti=%s user=%s ttl=%ds", jti[:8], user_id[:16], remaining)

    async def revoke_all_user_tokens(self, user_id: str) -> float:
        now = time.time()
        redis = await self._get_redis()
        if redis is None:
            log.warning("Redis unavailable — user revocation for %s not persisted", user_id[:16])
            return now
        refresh_expire_h = self._key_store.refresh_expire_hours
        ttl = refresh_expire_h * 3600
        await redis.set(IdentityRedisKeys.user_revoke_key(user_id), str(now), ex=ttl)
        await redis.delete(IdentityRedisKeys.session_key(user_id))
        log.warning("All tokens revoked for user=%s epoch=%.3f", user_id[:16], now)
        return now

    async def is_token_revoked(self, jti: str, user_id: str, issued_at: datetime) -> bool:
        redis = await self._get_redis()
        if redis is None:
            return False
        try:
            result = await redis.get(IdentityRedisKeys.jti_key(jti))
            if result is not None:
                return True
            raw = await redis.get(IdentityRedisKeys.user_revoke_key(user_id))
            if raw is not None:
                revoke_epoch = float(raw)
                return issued_at.timestamp() <= revoke_epoch
            return False
        except Exception as exc:
            log.error("Token revocation check error: %s", exc)
            return False


class DefaultIdentityProvider(IdentityProvider):
    def __init__(self, token_provider: TokenProvider, authentication_provider: AuthenticationProvider):
        self._token_provider = token_provider
        self._auth_provider = authentication_provider
        self._current_identity: Optional[Identity] = None

    async def resolve_identity(self, token: str) -> Optional[Identity]:
        claims = await self._token_provider.validate_access_token(token)
        if claims is None:
            return None
        identity = await self._auth_provider.get_identity(claims.sub)
        if identity is None:
            return None
        identity.tenant_id = claims.tenant_id or identity.tenant_id
        identity.tenant_slug = claims.tenant_slug
        identity.user_role = claims.user_role or identity.user_role
        self._current_identity = identity
        return identity

    async def get_current_identity(self) -> Optional[Identity]:
        return self._current_identity
