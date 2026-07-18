from __future__ import annotations

import pytest
from datetime import datetime, timedelta, timezone

from backend.identity.jwt.key_store import InMemoryKeyStore, SigningKey
from backend.identity.jwt.access_token import AccessTokenProvider
from backend.identity.jwt.refresh_token import RefreshTokenProvider
from backend.identity.interfaces.authentication import TokenClaims


@pytest.fixture
def key_store():
    return InMemoryKeyStore(
        access_secret="test-access-secret-key-min-32-chars-long!!",
        refresh_secret="test-refresh-secret-key-min-32-chars-long!",
        access_algorithm="HS256",
        refresh_algorithm="HS256",
        access_expire_minutes=60,
        refresh_expire_hours=168,
    )


@pytest.fixture
def access_provider(key_store):
    return AccessTokenProvider(key_store)


@pytest.fixture
def refresh_provider(key_store):
    return RefreshTokenProvider(key_store)


class TestKeyStore:
    @pytest.mark.asyncio
    async def test_initializes_with_two_keys(self, key_store):
        health = await key_store.health()
        assert health["active_keys"] == 2
        assert health["active_kid"] is not None

    @pytest.mark.asyncio
    async def test_get_signing_key_returns_valid_key(self, key_store):
        key = await key_store.get_signing_key()
        assert key is not None
        assert key.is_valid
        assert key.algorithm == "HS256"

    @pytest.mark.asyncio
    async def test_rotate_key_creates_new_active_key(self, key_store):
        old_kid = await key_store.get_active_kid()
        new_kid = await key_store.rotate_key()
        assert new_kid != old_kid
        assert await key_store.get_active_kid() == new_kid

    @pytest.mark.asyncio
    async def test_old_key_still_valid_after_rotation(self, key_store):
        original = await key_store.get_signing_key()
        assert original is not None
        original_kid = original.kid

        await key_store.rotate_key()

        still_valid = await key_store.get_verification_key(original_kid)
        assert still_valid is not None
        assert still_valid.kid == original_kid

    @pytest.mark.asyncio
    async def test_get_verification_key_unknown_kid(self, key_store):
        key = await key_store.get_verification_key("nonexistent")
        assert key is None


class TestAccessTokenProvider:
    @pytest.mark.asyncio
    async def test_create_and_validate_access_token(self, access_provider):
        now = datetime.now(timezone.utc)
        claims = TokenClaims(
            sub="user-123",
            role="admin",
            type="access",
            jti="test-jti-001",
            iat=now,
            exp=now + timedelta(hours=1),
            tenant_id="tenant-abc",
            email="admin@test.com",
            permissions=["read:*", "write:*"],
        )
        token = await access_provider.create(claims)
        assert token is not None
        assert len(token) > 50

        validated = await access_provider.validate(token)
        assert validated is not None
        assert validated.sub == "user-123"
        assert validated.role == "admin"
        assert validated.tenant_id == "tenant-abc"
        assert validated.email == "admin@test.com"
        assert validated.jti == "test-jti-001"

    @pytest.mark.asyncio
    async def test_rejects_expired_token(self, access_provider):
        now = datetime.now(timezone.utc)
        past = now - timedelta(hours=2)
        claims = TokenClaims(
            sub="user-123", role="member", type="access",
            jti="expired-jti", iat=past, exp=past + timedelta(minutes=1),
        )
        token = await access_provider.create(claims)
        validated = await access_provider.validate(token)
        assert validated is None

    @pytest.mark.asyncio
    async def test_rejects_wrong_token_type(self, access_provider, refresh_provider):
        now = datetime.now(timezone.utc)
        claims = TokenClaims(
            sub="user-123", role="member", type="refresh",
            jti="refresh-jti-002", iat=now, exp=now + timedelta(hours=1),
        )
        token = await refresh_provider.create(claims)
        validated = await access_provider.validate(token)
        assert validated is None

    @pytest.mark.asyncio
    async def test_rejects_invalid_token_string(self, access_provider):
        validated = await access_provider.validate("invalid-token-string")
        assert validated is None

    @pytest.mark.asyncio
    async def test_get_expiry(self, access_provider):
        now = datetime.now(timezone.utc)
        claims = TokenClaims(
            sub="user-123", role="member", type="access",
            jti="exp-test", iat=now, exp=now + timedelta(hours=1),
        )
        token = await access_provider.create(claims)
        expiry = await access_provider.get_expiry(token)
        assert expiry is not None
        assert expiry > now


class TestRefreshTokenProvider:
    @pytest.mark.asyncio
    async def test_create_and_validate_refresh_token(self, refresh_provider):
        now = datetime.now(timezone.utc)
        claims = TokenClaims(
            sub="user-123", role="admin", type="refresh",
            jti="refresh-jti-001", iat=now, exp=now + timedelta(days=7),
        )
        token = await refresh_provider.create(claims)
        assert token is not None

        validated = await refresh_provider.validate(token)
        assert validated is not None
        assert validated.sub == "user-123"
        assert validated.type == "refresh"

    @pytest.mark.asyncio
    async def test_rejects_access_token_as_refresh(self, refresh_provider, access_provider):
        now = datetime.now(timezone.utc)
        claims = TokenClaims(
            sub="user-123", role="member", type="access",
            jti="cross-type", iat=now, exp=now + timedelta(hours=1),
        )
        token = await access_provider.create(claims)
        validated = await refresh_provider.validate(token)
        assert validated is None
