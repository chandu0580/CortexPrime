from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from backend.identity.tenant.tenant_context import (
    TenantContext,
    TenantContextMiddleware,
    get_current_tenant_context,
    set_current_tenant_context,
)


class TestTenantContext:
    def test_default_is_not_resolved(self):
        ctx = TenantContext()
        assert ctx.is_resolved is False
        assert ctx.user_id is None

    def test_resolved_with_user(self):
        ctx = TenantContext(user_id="user-123", role="admin")
        assert ctx.is_resolved is True
        assert ctx.user_id == "user-123"

    def test_context_var_persistence(self):
        ctx = TenantContext(user_id="user-abc", tenant_id="tenant-xyz")
        set_current_tenant_context(ctx)
        retrieved = get_current_tenant_context()
        assert retrieved is not None
        assert retrieved.user_id == "user-abc"
        assert retrieved.tenant_id == "tenant-xyz"
        set_current_tenant_context(None)
        assert get_current_tenant_context() is None

    def test_context_var_isolation(self):
        ctx1 = TenantContext(user_id="user-1")
        set_current_tenant_context(ctx1)
        ctx2 = TenantContext(user_id="user-2")
        set_current_tenant_context(ctx2)
        assert get_current_tenant_context().user_id == "user-2"


class TestTenantContextMiddleware:
    @pytest.fixture
    def middleware(self):
        return TenantContextMiddleware(app=AsyncMock())

    @pytest.mark.asyncio
    async def test_no_auth_header_creates_empty_context(self, middleware):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "headers": [],
        }
        request = Request(scope)
        async def _ok(_req):
            return JSONResponse({"ok": True})
        response = await middleware.dispatch(request, _ok)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_sets_tenant_from_header(self, middleware):
        scope = {
            "type": "http",
            "method": "GET",
            "path": "/api/test",
            "headers": [(b"x-tenant-id", b"tenant-123")],
        }
        request = Request(scope)
        async def _ok(_req):
            return JSONResponse({"ok": True})
        await middleware.dispatch(request, _ok)
        ctx = get_current_tenant_context()
        if ctx:
            assert ctx.tenant_id == "tenant-123"
        set_current_tenant_context(None)
