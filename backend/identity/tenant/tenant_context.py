from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.database.tenancy import set_current_tenant as set_db_tenant
from backend.identity.interfaces.authentication import Identity


@dataclass
class TenantContext:
    tenant_id: Optional[str] = None
    tenant_slug: Optional[str] = None
    user_id: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    permissions: list[str] = field(default_factory=list)
    identity: Optional[Identity] = None
    request_id: Optional[str] = None

    @property
    def is_resolved(self) -> bool:
        return self.user_id is not None


_current_context: ContextVar[Optional[TenantContext]] = ContextVar("identity_tenant_context", default=None)


def set_current_tenant_context(ctx: Optional[TenantContext]) -> None:
    _current_context.set(ctx)


def get_current_tenant_context() -> Optional[TenantContext]:
    return _current_context.get()


class TenantContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        ctx = TenantContext(request_id=request.headers.get("X-Request-ID", ""))

        auth_header = request.headers.get("Authorization", "")
        tenant_header = request.headers.get("X-Tenant-ID", "")
        tenant_slug_header = request.headers.get("X-Tenant-Slug", "")

        if tenant_header:
            ctx.tenant_id = tenant_header
        if tenant_slug_header:
            ctx.tenant_slug = tenant_slug_header

        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            try:
                from backend.identity.jwt.access_token import AccessTokenProvider
                from backend.identity.jwt.key_store import InMemoryKeyStore
                key_store = InMemoryKeyStore()
                access_provider = AccessTokenProvider(key_store)
                claims = await access_provider.validate(token)
                if claims:
                    ctx.user_id = claims.sub
                    ctx.role = claims.role
                    ctx.permissions = claims.permissions
                    ctx.tenant_id = claims.tenant_id or ctx.tenant_id
                    ctx.tenant_slug = claims.tenant_slug or ctx.tenant_slug
                    ctx.email = claims.email
                    ctx.identity = Identity(
                        user_id=claims.sub,
                        email=claims.email or "",
                        display_name=claims.sub,
                        role=claims.role,
                        tenant_id=claims.tenant_id,
                        tenant_slug=claims.tenant_slug,
                        user_role=claims.user_role,
                        permissions=claims.permissions,
                    )
            except Exception:
                pass

        if ctx.tenant_id:
            try:
                db_tenant_id = uuid.UUID(ctx.tenant_id)
                set_db_tenant(db_tenant_id)
            except (ValueError, AttributeError):
                pass

        set_current_tenant_context(ctx)
        request.state.tenant_context = ctx

        response = await call_next(request)

        if ctx.tenant_id:
            set_db_tenant(None)
        set_current_tenant_context(None)

        return response
