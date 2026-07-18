from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.identity.authentication.password_verifier import PasswordVerifier
from backend.identity.authentication.providers import (
    DefaultAuthenticationProvider,
    DefaultIdentityProvider,
    DefaultTokenProvider,
)
from backend.identity.interfaces.authentication import Identity
from backend.identity.jwt.key_store import InMemoryKeyStore
from backend.identity.jwt.access_token import AccessTokenProvider
from backend.identity.jwt.refresh_token import RefreshTokenProvider


@pytest.fixture
def password_verifier():
    return PasswordVerifier()


class TestPasswordVerifier:
    def test_hash_and_verify(self, password_verifier):
        pw_hash = password_verifier.hash_password("SecureP@ss123")
        assert password_verifier.verify_password("SecureP@ss123", pw_hash) is True
        assert password_verifier.verify_password("WrongPassword", pw_hash) is False

    def test_generate_temp_password(self, password_verifier):
        temp = password_verifier.generate_temp_password()
        assert len(temp) == 32
        assert isinstance(temp, str)


class TestDefaultAuthenticationProvider:
    @pytest.fixture
    def mock_user_repo(self):
        repo = AsyncMock()
        user_id = uuid.uuid4()
        user = MagicMock()
        user.id = user_id
        user.email = "test@example.com"
        user.display_name = "Test User"
        user.status = "active"
        user.password_hash = None
        user.roles = ["member"]
        repo.get_by_email = AsyncMock(return_value=user)
        repo.get = AsyncMock(return_value=user)
        return repo

    @pytest.fixture
    def auth_provider(self, mock_user_repo, password_verifier):
        return DefaultAuthenticationProvider(password_verifier, mock_user_repo)

    @pytest.mark.asyncio
    async def test_get_identity_returns_identity(self, auth_provider, mock_user_repo):
        identity = await auth_provider.get_identity(str(uuid.uuid4()))
        assert identity is not None
        assert identity.email == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_identity_returns_none_for_missing(self, auth_provider):
        auth_provider._user_repo.get = AsyncMock(return_value=None)
        identity = await auth_provider.get_identity(str(uuid.uuid4()))
        assert identity is None


class TestDefaultTokenProvider:
    @pytest.fixture
    def key_store(self):
        return InMemoryKeyStore(
            access_secret="test-access-secret-key-min-32-chars-long!!",
            refresh_secret="test-refresh-secret-key-min-32-chars-long!",
            access_expire_minutes=15,
            refresh_expire_hours=168,
        )

    @pytest.fixture
    def token_provider(self, key_store):
        return DefaultTokenProvider(
            key_store,
            AccessTokenProvider(key_store),
            RefreshTokenProvider(key_store),
        )

    @pytest.mark.asyncio
    async def test_create_token_pair(self, token_provider):
        identity = Identity(
            user_id="user-123",
            email="test@example.com",
            display_name="Test User",
            role="admin",
            tenant_id="tenant-abc",
        )
        result = await token_provider.create_token_pair(identity)
        assert result.access_token is not None
        assert result.refresh_token is not None
        assert result.access_expires_at > datetime.now(timezone.utc)
        assert result.refresh_expires_at > datetime.now(timezone.utc)
        assert result.claims.sub == "user-123"

    @pytest.mark.asyncio
    async def test_validate_valid_access_token(self, token_provider):
        identity = Identity(user_id="user-456", email="a@b.com", display_name="A", role="member")
        pair = await token_provider.create_token_pair(identity)
        claims = await token_provider.validate_access_token(pair.access_token)
        assert claims is not None
        assert claims.sub == "user-456"
        assert claims.role == "member"

    @pytest.mark.asyncio
    async def test_validate_invalid_token_returns_none(self, token_provider):
        claims = await token_provider.validate_access_token("invalid-token")
        assert claims is None

    @pytest.mark.asyncio
    async def test_refresh_access_token(self, token_provider):
        identity = Identity(user_id="user-789", email="c@d.com", display_name="C", role="admin")
        pair = await token_provider.create_token_pair(identity)
        new_pair = await token_provider.refresh_access_token(pair.refresh_token)
        assert new_pair is not None
        assert new_pair.access_token != pair.access_token
        assert new_pair.refresh_token != pair.refresh_token

    @pytest.mark.asyncio
    async def test_refresh_with_invalid_token_returns_none(self, token_provider):
        result = await token_provider.refresh_access_token("invalid-refresh-token")
        assert result is None


class TestDefaultIdentityProvider:
    @pytest.fixture
    def key_store(self):
        return InMemoryKeyStore(
            access_secret="test-access-secret-key-min-32-chars-long!!",
            refresh_secret="test-refresh-secret-key-min-32-chars-long!",
        )

    @pytest.fixture
    def token_provider(self, key_store):
        return DefaultTokenProvider(
            key_store,
            AccessTokenProvider(key_store),
            RefreshTokenProvider(key_store),
        )

    @pytest.fixture
    def identity_provider(self, token_provider):
        auth_provider = AsyncMock(spec=DefaultAuthenticationProvider)
        auth_provider.get_identity = AsyncMock(
            return_value=Identity(user_id="user-123", email="test@test.com", display_name="Test", role="admin")
        )
        return DefaultIdentityProvider(token_provider, auth_provider)

    @pytest.mark.asyncio
    async def test_resolve_identity(self, identity_provider, token_provider):
        identity = Identity(user_id="user-123", email="test@test.com", display_name="Test", role="admin")
        pair = await token_provider.create_token_pair(identity)
        resolved = await identity_provider.resolve_identity(pair.access_token)
        assert resolved is not None
        assert resolved.user_id == "user-123"
