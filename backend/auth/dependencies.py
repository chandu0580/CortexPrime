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
from backend.auth.tenant import Tenant, get_tenant_manager

bearer = HTTPBearer(auto_error=False)


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
    # Verify user belongs to at least one active tenant
    tenant_id = payload.get("tenant_id")
    if tenant_id:
        tm = get_tenant_manager()
        tenant = tm.get_tenant(tenant_id)
        if not tenant or not tenant.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant is inactive or does not exist",
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
    tm = get_tenant_manager()
    tenant = tm.get_tenant(tenant_id)
    if not tenant or not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant not found or inactive",
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


async def get_current_tenant(current_user: dict = Depends(require_tenant)) -> Tenant:
    tm = get_tenant_manager()
    tenant = tm.get_tenant(current_user["tenant_id"])
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return tenant


