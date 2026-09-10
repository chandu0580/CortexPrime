"""
Shared FastAPI auth dependencies.

Supports access-token auth via:
1) Authorization: Bearer <token>
2) HttpOnly cookie: cortex_access
"""
from __future__ import annotations

from typing import Callable, Optional

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.jwt_handler import decode_access_token

bearer = HTTPBearer(auto_error=False)


async def verify_request_token(
    authorization: Optional[str],
    cortex_access: Optional[str],
) -> Optional[dict]:
    """Verify one access token from a raw ``Authorization`` header or the cookie.

    Phase 11.1. This is the single verification used by every dependency below
    AND by the authentication perimeter (``backend.safety.auth_perimeter``), so
    the edge and the routes cannot disagree about what a valid token is:
    signature and expiry via ``decode_access_token``, then the revocation list.
    Returns the claims, or ``None`` for anything that is not a live token.
    """
    token: Optional[str] = None
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value.strip():
            token = value.strip()
    if not token and cortex_access:
        token = cortex_access
    if not token:
        return None
    return await _verify_token(token)


async def _decode_and_verify(
    creds: Optional[HTTPAuthorizationCredentials],
    cortex_access: Optional[str],
) -> Optional[dict]:
    token: Optional[str] = None

    if creds and creds.credentials:
        token = creds.credentials
    elif cortex_access:
        token = cortex_access

    if not token:
        return None
    return await _verify_token(token)


async def _verify_token(token: str) -> Optional[dict]:

    payload = decode_access_token(token)
    if not payload:
        return None

    from backend.auth.token_blacklist import token_blacklist

    revoked = await token_blacklist.is_revoked(
        jti=payload.get("jti", ""),
        user_id=payload.get("sub", ""),
        issued_at=float(payload.get("iat", 0)),
    )
    if revoked:
        return None

    return payload


async def require_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    cortex_access: Optional[str] = Cookie(default=None),
) -> dict:
    payload = await _decode_and_verify(creds, cortex_access)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Verify the token names a tenant that exists and is live.
    #
    # Phase 10.10. This check is older than ``require_tenant`` and runs before
    # it, and it read ``data/tenants/tenants.json`` -- so until this phase the
    # JSON file could refuse a request no matter what the durable store said,
    # which is both halves of "JSON and PostgreSQL are both authoritative".
    # The durable store is asked first and is the answer whenever it is
    # composed; the file remains only as a fallback for a process that has no
    # engine, and that fallback refuses on absence exactly as this one does.
    tenant_id = payload.get("tenant_id")
    if tenant_id:
        from backend.api.product.app import current_engine
        from backend.auth.tenants import resolve_tenant

        # Phase 10.11: no JSON fallback. A missing store is not permission to
        # fall back to a file nobody governs -- it refuses, like every other
        # unreadable authority in this codebase.
        record, reason = resolve_tenant(
            tenant_id=tenant_id,
            tenants=getattr(current_engine(), "tenants", None))
        if record is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tenant is inactive or does not exist ({reason})",
            )
    return payload


async def require_admin(current_user: dict = Depends(require_user)) -> dict:
    if current_user.get("role") not in ("admin", "ADMIN"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    return current_user


async def get_optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    cortex_access: Optional[str] = Cookie(default=None),
) -> Optional[dict]:
    return await _decode_and_verify(creds, cortex_access)


async def require_tenant(current_user: dict = Depends(require_user)) -> dict:
    tenant_id = current_user.get("tenant_id")
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenant association in token",
        )
    # Phase 10.10. Tenant existence and state come from the durable store
    # (``cp_tenant``), not from ``data/tenants/tenants.json``. Until this phase
    # an edit to that gitignored file disabled governance for a whole tenant.
    #
    # The JSON manager remains ONLY as a fallback for processes that have not
    # composed the durable engine -- and that fallback refuses on absence just
    # as the durable path does, so neither direction fails open.
    from backend.api.product.app import current_engine
    from backend.auth.tenants import resolve_tenant

    record, reason = resolve_tenant(
        tenant_id=tenant_id,
        tenants=getattr(current_engine(), "tenants", None))
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Tenant not found or inactive ({reason})",
        )
    return current_user


def require_tenant_role(required_role: str) -> Callable:
    async def _role_checker(current_user: dict = Depends(require_tenant)) -> dict:
        user_role = current_user.get("user_role", "")
        if user_role != required_role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Tenant role '{required_role}' required, got '{user_role}'",
            )
        return current_user
    return _role_checker


