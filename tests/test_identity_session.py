from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from backend.identity.interfaces.session import Session, SessionCreateRequest
from backend.identity.session.session_runtime import SessionRuntime


class TestSessionRuntime:
    @pytest.fixture
    def session_runtime(self):
        return SessionRuntime()

    @pytest.mark.asyncio
    async def test_create_session(self, session_runtime):
        request = SessionCreateRequest(
            user_id="user-123",
            tenant_id="tenant-abc",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session = await session_runtime.create_session(request)
        assert session.session_id is not None
        assert session.user_id == "user-123"
        assert session.tenant_id == "tenant-abc"
        assert session.is_active is True
        assert session.is_revoked is False

    @pytest.mark.asyncio
    async def test_session_without_redis_returns_created(self, session_runtime):
        request = SessionCreateRequest(
            user_id="user-456",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        session = await session_runtime.create_session(request)
        assert session is not None
        assert session.user_id == "user-456"

    @pytest.mark.asyncio
    async def test_validate_session_without_redis(self, session_runtime):
        valid = await session_runtime.validate_session("nonexistent")
        assert valid is False

    @pytest.mark.asyncio
    async def test_revoke_session_without_redis(self, session_runtime):
        result = await session_runtime.revoke_session("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_revoke_all_user_sessions_without_redis(self, session_runtime):
        count = await session_runtime.revoke_all_user_sessions("user-123")
        assert count == 0

    @pytest.mark.asyncio
    async def test_touch_session_without_redis(self, session_runtime):
        result = await session_runtime.touch_session("nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_active_sessions_without_redis(self, session_runtime):
        sessions = await session_runtime.list_active_sessions("user-123")
        assert sessions == []

    @pytest.mark.asyncio
    async def test_count_active_sessions_without_redis(self, session_runtime):
        count = await session_runtime.count_active_sessions()
        assert count == -1

    @pytest.mark.asyncio
    async def test_created_session_is_expired_correctly(self, session_runtime):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        request = SessionCreateRequest(user_id="user-1", expires_at=future)
        session = await session_runtime.create_session(request)
        assert session.is_expired is False

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        request2 = SessionCreateRequest(user_id="user-2", expires_at=past)
        session2 = await session_runtime.create_session(request2)
        assert session2.is_expired is True
