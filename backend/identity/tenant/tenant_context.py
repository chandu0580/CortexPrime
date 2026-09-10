from __future__ import annotations

import logging
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Optional

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.database.tenancy import set_current_tenant as set_db_tenant
from backend.identity.interfaces.authentication import Identity

log = logging.getLogger(__name__)


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


def _bearer(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        return token or None
    return None


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Propagate the *verified* tenant through the request's context variables.

    Phase 11.1 (ADR-121). Until this phase the middleware copied ``X-Tenant-ID``
    from the request headers straight into the tenant context and from there
    into ``backend.database.tenancy.set_current_tenant`` -- which is the value
    ``RedisKeys._tp()`` namespaces every Redis key by. An **unauthenticated**
    header therefore chose the Redis namespace of the request: a forged tenant
    primitive that no token check stood in front of. The token branch used a
    fresh in-memory key store per request from the retired identity subsystem,
    so it never validated a real token and never populated the identity.

    Now:

    * the tenant comes from the verified access token (``backend.auth``, the
      same verifier as the perimeter and ``require_user``), or from nowhere;
    * ``X-Tenant-ID`` / ``X-Tenant-Slug`` are honoured only when they *equal*
      what the token already says (a client restating its own tenant is
      harmless; a client naming another is logged and ignored);
    * an unauthenticated request gets an empty context and no database or
      Redis tenant is set.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        ctx = TenantContext(request_id=request.headers.get("X-Request-ID", ""))

        tenant_header = request.headers.get("X-Tenant-ID", "").strip()
        tenant_slug_header = request.headers.get("X-Tenant-Slug", "").strip()

        claims = None
        token = _bearer(request) or request.cookies.get("cortex_access")
        if token:
            try:
                from backend.auth.jwt_handler import decode_access_token

                claims = decode_access_token(token)
            except Exception:  # noqa: BLE001 - an undecodable token is no identity
                claims = None

        if claims:
            ctx.user_id = str(claims.get("sub") or "") or None
            ctx.role = claims.get("role")
            ctx.permissions = list(claims.get("permissions") or [])
            ctx.tenant_id = (str(claims.get("tenant_id")).strip() if claims.get("tenant_id") else None)
            ctx.tenant_slug = (str(claims.get("tenant_slug")).strip() if claims.get("tenant_slug") else None)
            ctx.email = claims.get("email")
            if ctx.user_id:
                try:
                    ctx.identity = Identity(
                        user_id=ctx.user_id,
                        email=ctx.email or "",
                        display_name=ctx.user_id,
                        role=ctx.role,
                        tenant_id=ctx.tenant_id,
                        tenant_slug=ctx.tenant_slug,
                        user_role=claims.get("user_role"),
                        permissions=ctx.permissions,
                    )
                except Exception:  # noqa: BLE001 - the identity DTO is informational
                    ctx.identity = None

        # A header may restate the verified tenant; it may never choose one.
        if tenant_header and tenant_header != (ctx.tenant_id or ""):
            log.warning(
                "X-Tenant-ID header (%s) ignored: it does not match the verified tenant (%s)",
                tenant_header[:64], ctx.tenant_id,
            )
        if tenant_slug_header and tenant_slug_header != (ctx.tenant_slug or ""):
            log.warning("X-Tenant-Slug header ignored: it does not match the verified tenant")

        if ctx.tenant_id:
            try:
                db_tenant_id = uuid.UUID(ctx.tenant_id)
                set_db_tenant(db_tenant_id)
            except (ValueError, AttributeError):
                pass

        set_current_tenant_context(ctx)
        request.state.tenant_context = ctx

        try:
            response = await call_next(request)
        finally:
            if ctx.tenant_id:
                set_db_tenant(None)
            set_current_tenant_context(None)

        return response
