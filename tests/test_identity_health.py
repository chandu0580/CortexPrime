from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.identity.health import IdentityHealth
from backend.identity.jwt.key_store import InMemoryKeyStore
from backend.identity.session.session_runtime import SessionRuntime


class TestIdentityHealth:
    @pytest.fixture
    def health(self):
        key_store = InMemoryKeyStore(
            access_secret="test-access-secret-key-min-32-chars-long!!",
            refresh_secret="test-refresh-secret-key-min-32-chars-long!",
        )
        session_runtime = SessionRuntime()
        return IdentityHealth(key_store, session_runtime)

    @pytest.mark.asyncio
    async def test_health_returns_expected_structure(self, health):
        result = await health.check()
        assert "status" in result
        assert "identity_runtime" in result
        assert "jwt" in result
        assert "sessions" in result
        assert "repositories" in result

    @pytest.mark.asyncio
    async def test_identity_runtime_status(self, health):
        result = await health.check()
        identity = result["identity_runtime"]
        assert "key_store" in identity
        assert "session_runtime" in identity
        assert "redis" in identity

    @pytest.mark.asyncio
    async def test_jwt_health(self, health):
        result = await health.check()
        jwt = result["jwt"]
        assert jwt["active_keys"] == 2
        assert jwt["healthy"] is True

    @pytest.mark.asyncio
    async def test_sessions_health(self, health):
        result = await health.check()
        sessions = result["sessions"]
        assert "active_count" in sessions
