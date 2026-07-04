"""
Shared FastAPI auth dependencies.

Supports access-token auth via:
1) Authorization: Bearer <token>
2) HttpOnly cookie: cortex_access
"""
from __future__ import annotations

import os
from typing import Optional

from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.jwt_handler import decode_access_token

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


_AUTH_DISABLED: bool = os.getenv("AUTH_DISABLED", "").lower() in ("true", "1", "yes")


async def require_user_or_bypass(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    cortex_access: Optional[str] = Cookie(default=None),
) -> dict:
    if _AUTH_DISABLED:
        return {"sub": "test-user", "role": "operator", "type": "access"}
    return await require_user(creds, cortex_access)
