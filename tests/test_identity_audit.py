from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from backend.identity.audit.audit_hooks import IdentityAuditHooks


class TestIdentityAuditHooks:
    @pytest.fixture
    def hooks(self):
        return IdentityAuditHooks()

    @pytest.mark.asyncio
    async def test_login_publishes_event(self, hooks):
        with patch("backend.events.event_bus.event_bus") as mock_bus:
            mock_bus.publish = AsyncMock()
            await hooks.login("user-123", "ok", tenant_id="tenant-abc")
            mock_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_logout_publishes_event(self, hooks):
        with patch("backend.events.event_bus.event_bus") as mock_bus:
            mock_bus.publish = AsyncMock()
            await hooks.logout("user-123", "ok")
            mock_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_token_refresh_publishes_event(self, hooks):
        with patch("backend.events.event_bus.event_bus") as mock_bus:
            mock_bus.publish = AsyncMock()
            await hooks.token_refresh("user-123", "ok")
            mock_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_created_publishes_event(self, hooks):
        with patch("backend.events.event_bus.event_bus") as mock_bus:
            mock_bus.publish = AsyncMock()
            await hooks.session_created("user-123", "ok")
            mock_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_revoked_publishes_event(self, hooks):
        with patch("backend.events.event_bus.event_bus") as mock_bus:
            mock_bus.publish = AsyncMock()
            await hooks.session_revoked("user-123", "ok")
            mock_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_token_revoked_publishes_event(self, hooks):
        with patch("backend.events.event_bus.event_bus") as mock_bus:
            mock_bus.publish = AsyncMock()
            await hooks.token_revoked("user-123", "ok")
            mock_bus.publish.assert_called_once()

    @pytest.mark.asyncio
    async def test_permission_denied_publishes_event(self, hooks):
        with patch("backend.events.event_bus.event_bus") as mock_bus:
            mock_bus.publish = AsyncMock()
            await hooks.permission_denied("user-123", "projects", "write")
            mock_bus.publish.assert_called_once()
            call_args = mock_bus.publish.call_args[0][0]
            assert "permission_denied" in call_args.message
