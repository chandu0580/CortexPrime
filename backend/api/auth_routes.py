"""
Auth Routes — Enterprise JWT Revocation
=========================================
POST /api/auth/login            — credentials → access token + refresh token
POST /api/auth/refresh          — refresh token → new access + rotated refresh
POST /api/auth/logout           — revoke current access + refresh token
GET  /api/auth/me               — validate access token, return user profile
POST /api/auth/revoke-all       — revoke ALL tokens for the calling user
POST /api/auth/admin/revoke-user/{user_id}  — admin: revoke all tokens for any user
GET  /api/auth/health           — auth service health with Redis stats
"""
from __future__ import annotations

import logging
import os
import time
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from backend.auth.jwt_handler import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    get_token_expiry,
    verify_credentials,
)
from backend.auth.rbac import require_permission
from backend.auth.token_blacklist import token_blacklist

log    = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["Authentication"])
bearer = HTTPBearer(auto_error=False)

_REFRESH_EXPIRE_H: int = int(os.getenv("JWT_REFRESH_EXPIRE_H", "168"))
_EXPIRE_MIN:       int = int(os.getenv("JWT_EXPIRE_MINUTES",
                                str(int(os.getenv("JWT_EXPIRE_HOURS", "1")) * 60)))
_SECURE_COOKIE: bool   = os.getenv("ENVIRONMENT", "development").lower() == "production"


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token:  str
    token_type:    str = "bearer"
    expires_in:    int           # seconds
    user:          dict


class UserProfile(BaseModel):
    user_id:   str
    role:      str
    clearance: str = "LEVEL-5"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Write the refresh token as an httpOnly cookie."""
    response.set_cookie(
        key="cortex_refresh",
        value=refresh_token,
        httponly=True,
        secure=_SECURE_COOKIE,
        samesite="lax",
        max_age=_REFRESH_EXPIRE_H * 3600,
        path="/api/auth",          # only sent to auth endpoints
    )


def _set_access_cookie(response: Response, access_token: str) -> None:
    """Write the access token as an httpOnly cookie for all API/WS auth."""
    response.set_cookie(
        key="cortex_access",
        value=access_token,
        httponly=True,
        secure=_SECURE_COOKIE,
        samesite="lax",
        max_age=_EXPIRE_MIN * 60,
        path="/",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key="cortex_refresh", path="/api/auth")


def _clear_access_cookie(response: Response) -> None:
    response.delete_cookie(key="cortex_access", path="/")


def _set_session_hint_cookie(response: Response) -> None:
    """Non-HttpOnly companion cookie carrying no auth material — just a
    boolean the frontend can read to know a session *might* exist, so it
    knows whether attempting /api/auth/refresh after a failed /me is worth
    it. The real cookies stay HttpOnly; this exists so the frontend isn't
    stuck guessing from response bodies, which deliberately never reveal
    *why* auth failed (see backend/core/exception_handlers.py)."""
    response.set_cookie(
        key="cortex_session_hint",
        value="1",
        httponly=False,
        secure=_SECURE_COOKIE,
        samesite="lax",
        max_age=_REFRESH_EXPIRE_H * 3600,
        path="/",
    )


def _clear_session_hint_cookie(response: Response) -> None:
    response.delete_cookie(key="cortex_session_hint", path="/")


def _token_expiry_epoch(token: str) -> float:
    """Return the expiry epoch of any JWT; falls back to now+1h."""
    exp_dt = get_token_expiry(token)
    if exp_dt:
        return exp_dt.timestamp()
    return time.time() + 3600   # safe fallback


# ---------------------------------------------------------------------------
# Dependency: validate bearer access token + blacklist check
# ---------------------------------------------------------------------------

async def get_current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
    cortex_access: Optional[str] = Cookie(default=None),
) -> dict:
    """FastAPI dependency — raises 401 if token is missing, invalid, or revoked."""
    token = creds.credentials if creds else cortex_access
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_access_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Blacklist check — reject revoked tokens immediately
    revoked = await token_blacklist.is_revoked(
        jti=payload.get("jti", ""),
        user_id=payload.get("sub", ""),
        issued_at=float(payload.get("iat", 0)),
    )
    if revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


# ---------------------------------------------------------------------------
# Tenant claims (Phase 10.2)
# ---------------------------------------------------------------------------

def _tenant_claims(user_id: str) -> dict:
    """The authenticated user's tenant membership, resolved from the store.

    Why this exists
    ---------------
    The governed Product API refuses any token with no tenant claim (403), and
    until now login minted tokens with none -- so no browser session could ever
    reach it. This is the missing wire, not a new mechanism: ``TenantManager``
    already maps a user to a tenant and a role, and ``create_access_token``
    already accepts ``tenant_id`` / ``tenant_slug`` / ``user_role``.

    Fail-closed by construction
    ---------------------------
    No membership, an inactive membership, an inactive tenant, or any failure
    reading the store -> **no claims at all**, exactly as before this change.
    The caller cannot influence the result: the only input is the identity that
    already passed authentication. There is no header, body or query that
    reaches this function, so a client can neither choose nor suggest a tenant.
    """
    try:
        from backend.auth.tenant import get_tenant_manager

        tm = get_tenant_manager()
        member = tm.get_user_by_email(user_id)
        if member is None or not getattr(member, "is_active", False):
            return {}
        tenant = tm.get_tenant(member.tenant_id)
        if tenant is None or not tenant.is_active:
            return {}
        return {
            "tenant_id": tenant.tenant_id,
            "tenant_slug": tenant.slug,
            "user_role": member.role,
        }
    except Exception:  # noqa: BLE001 - a store failure must not grant a tenant
        log.warning("tenant membership lookup failed; issuing token with no "
                    "tenant claim", exc_info=True)
        return {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, response: Response):
    """
    Authenticate with username + password.
    Returns an access token in the body and sets a httpOnly refresh-token cookie.
    """
    if not verify_credentials(request.username, request.password):
        log.warning("Failed login for user=%s", request.username[:32])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    role          = "operator"
    claims        = _tenant_claims(request.username)
    access_token  = create_access_token(user_id=request.username, role=role, **claims)
    refresh_token = create_refresh_token(user_id=request.username, role=role)

    _set_access_cookie(response, access_token)
    _set_refresh_cookie(response, refresh_token)
    _set_session_hint_cookie(response)

    # Track access token session for health reporting
    access_payload = decode_access_token(access_token)
    if access_payload:
        await token_blacklist.track_session(
            jti        = access_payload.get("jti", ""),
            user_id    = request.username,
            expires_at = float(access_payload.get("exp", time.time() + 3600)),
        )

    _audit_auth("login", request.username, "ok")
    log.info("Login OK: user=%s", request.username[:32])

    return TokenResponse(
        access_token = access_token,
        expires_in   = _EXPIRE_MIN * 60,
        user = {
            "user_id":   request.username,
            "role":      role.upper(),
            "clearance": "LEVEL-5",
        },
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response:        Response,
    cortex_refresh:  Optional[str] = Cookie(default=None),
):
    """
    Exchange a valid refresh token (httpOnly cookie) for new tokens.

    Behaviour:
    - Validates the refresh token.
    - Revokes the OLD refresh token's JTI (refresh-token rotation with revocation).
    - Issues a new access token + rotated refresh token.
    """
    if not cortex_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token",
        )
    old_payload = decode_refresh_token(cortex_refresh)
    if not old_payload:
        _clear_refresh_cookie(response)
        _clear_session_hint_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token invalid or expired — please log in again",
        )

    # Check whether this refresh token has already been revoked
    old_jti  = old_payload.get("jti", "")
    user_id  = old_payload["sub"]
    old_iat  = float(old_payload.get("iat", 0))

    revoked = await token_blacklist.is_revoked(
        jti=old_jti, user_id=user_id, issued_at=old_iat
    )
    if revoked:
        _clear_refresh_cookie(response)
        _clear_session_hint_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked — please log in again",
        )

    # Revoke the OLD refresh token (prevent replay attacks)
    old_exp = float(old_payload.get("exp", time.time()))
    await token_blacklist.revoke_token(
        jti=old_jti, user_id=user_id, expires_at=old_exp, token_type="refresh"
    )

    role = old_payload.get("role", "operator")

    # Issue new pair (refresh-token rotation)
    # Re-resolved, never copied from the old token: a membership revoked since
    # the last login must stop being honoured at the next rotation rather than
    # ride along inside a token the client keeps refreshing.
    claims      = _tenant_claims(user_id)
    new_access  = create_access_token(user_id=user_id, role=role, **claims)
    new_refresh = create_refresh_token(user_id=user_id, role=role)

    _set_access_cookie(response, new_access)
    _set_refresh_cookie(response, new_refresh)
    _set_session_hint_cookie(response)

    # Track new access session
    new_payload = decode_access_token(new_access)
    if new_payload:
        await token_blacklist.track_session(
            jti        = new_payload.get("jti", ""),
            user_id    = user_id,
            expires_at = float(new_payload.get("exp", time.time() + 3600)),
        )

    _audit_auth("token_refresh", user_id, "ok")

    return TokenResponse(
        access_token = new_access,
        expires_in   = _EXPIRE_MIN * 60,
        user = {
            "user_id":   user_id,
            "role":      role.upper(),
            "clearance": "LEVEL-5",
        },
    )


@router.post("/logout")
async def logout(
    response:       Response,
    cortex_refresh: Optional[str] = Cookie(default=None),
    current_user:   dict = Depends(get_current_user),
):
    """
    Immediately invalidate the caller's current access token and refresh token.

    - Access token JTI is added to the Redis blacklist (TTL = remaining lifetime).
    - Refresh token JTI is added to the Redis blacklist (TTL = remaining lifetime).
    - httpOnly refresh cookie is cleared.
    - Session tracker entry is removed.

    After this call, reusing either token will return 401.
    """
    user_id = current_user.get("sub", "system")
    jti     = current_user.get("jti", "")
    exp     = float(current_user.get("exp", time.time()))

    # Revoke access token
    if jti:
        try:
            await token_blacklist.revoke_token(
                jti=jti, user_id=user_id, expires_at=exp, token_type="access"
            )
            await token_blacklist.remove_session(jti=jti, user_id=user_id)
        except Exception as exc:
            log.error("logout: access token revocation failed: %s", exc)
            # Still clear the cookie — best effort

    # Revoke the refresh token too
    if cortex_refresh:
        rp = decode_refresh_token(cortex_refresh)
        if rp:
            r_jti = rp.get("jti", "")
            r_exp = float(rp.get("exp", time.time()))
            if r_jti:
                try:
                    await token_blacklist.revoke_token(
                        jti=r_jti, user_id=user_id, expires_at=r_exp,
                        token_type="refresh"
                    )
                except Exception as exc:
                    log.error("logout: refresh token revocation failed: %s", exc)

    _clear_refresh_cookie(response)
    _clear_access_cookie(response)
    _clear_session_hint_cookie(response)
    _audit_auth("logout", user_id, "ok", {"jti": jti[:8] if jti else ""})
    log.info("Logout OK: user=%s jti=%s", user_id[:32], jti[:8] if jti else "none")

    return {
        "status":  "ok",
        "message": "Session terminated — tokens revoked",
    }


@router.get("/me", response_model=UserProfile)
async def me(current_user: dict = Depends(get_current_user)):
    """Return profile for the currently authenticated user."""
    return UserProfile(
        user_id   = current_user.get("sub", "unknown"),
        role      = current_user.get("role", "operator").upper(),
        clearance = "LEVEL-5",
    )


@router.post("/revoke-all")
async def revoke_all_self(current_user: dict = Depends(get_current_user)):
    """
    Revoke ALL tokens for the calling user (e.g. on password change or
    suspicious activity).  The caller's current token is also invalidated —
    they must log in again.
    """
    user_id = current_user.get("sub", "system")
    epoch   = await token_blacklist.revoke_all_user_tokens(user_id)
    _audit_auth("user_revoked", user_id, "ok", {"epoch": epoch})
    log.warning("All tokens revoked: user=%s epoch=%.3f", user_id[:32], epoch)
    return {
        "status":          "ok",
        "message":         "All tokens revoked — please log in again",
        "revoked_at_epoch": epoch,
    }


@router.post("/admin/revoke-user/{target_user_id}")
async def admin_revoke_user(
    target_user_id: str,
    _: dict = Depends(require_permission("admin", "users")),
):
    """
    Admin action: revoke ALL tokens for any user.
    Requires admin permission on users resource.
    """
    actor = _.get("sub", "system")
    epoch   = await token_blacklist.revoke_all_user_tokens(target_user_id)
    _audit_auth(
        "admin_user_revoked", actor, "ok",
        {"target": target_user_id, "epoch": epoch},
    )
    log.warning(
        "Admin revocation: actor=%s target=%s epoch=%.3f",
        actor[:32], target_user_id[:32], epoch,
    )
    return {
        "status":          "ok",
        "message":         f"All tokens revoked for user {target_user_id!r}",
        "revoked_at_epoch": epoch,
    }


# ---------------------------------------------------------------------------
# OAuth 2.0 / SSO Endpoints
# ---------------------------------------------------------------------------

@router.get("/oauth/providers")
async def list_oauth_providers():
    """Return the list of configured OAuth/SSO providers."""
    from backend.identity.providers.registry import get_provider_registry
    registry = get_provider_registry()
    return {
        "providers": registry.list(),
    }


@router.get("/oauth/{provider}")
async def oauth_login(provider: str, redirect_uri: str):
    """Initiate OAuth login by redirecting to the provider's auth page."""
    from backend.identity.providers.registry import get_provider_registry
    registry = get_provider_registry()
    oauth = registry.get(provider)
    if oauth is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OAuth provider '{provider}' is not configured",
        )
    import secrets
    state = secrets.token_urlsafe(32)
    auth_url = await oauth.get_auth_url(redirect_uri, state)
    return {"auth_url": auth_url, "state": state}


@router.get("/oauth/{provider}/callback")
async def oauth_callback(provider: str, code: str, redirect_uri: str):
    """Handle OAuth callback — exchange code for tokens and create session."""
    from backend.identity.providers.registry import get_provider_registry
    registry = get_provider_registry()
    oauth = registry.get(provider)
    if oauth is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"OAuth provider '{provider}' is not configured",
        )

    access_token = await oauth.exchange_code(code, redirect_uri)
    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Failed to exchange authorization code",
        )

    user_info = await oauth.get_user_info(access_token)
    user_id = user_info.email or user_info.sub
    role = "operator"

    from backend.auth.jwt_handler import create_access_token, create_refresh_token, decode_access_token
    jwt_access = create_access_token(user_id=user_id, role=role)
    jwt_refresh = create_refresh_token(user_id=user_id, role=role)

    from starlette.responses import JSONResponse
    resp = JSONResponse({
        "access_token": jwt_access,
        "token_type": "bearer",
        "expires_in": _EXPIRE_MIN * 60,
        "user": {
            "user_id": user_id,
            "email": user_info.email,
            "display_name": user_info.display_name,
            "provider": provider,
            "role": role.upper(),
            "clearance": "LEVEL-5",
        },
    })
    _set_access_cookie(resp, jwt_access)
    _set_refresh_cookie(resp, jwt_refresh)
    _set_session_hint_cookie(resp)

    access_payload = decode_access_token(jwt_access)
    if access_payload:
        import time
        await token_blacklist.track_session(
            jti=access_payload.get("jti", ""),
            user_id=user_id,
            expires_at=float(access_payload.get("exp", time.time() + 3600)),
        )

    _audit_auth(f"oauth_login:{provider}", user_id, "ok")
    log.info("OAuth login OK: provider=%s user=%s", provider, user_id[:32])
    return resp


@router.get("/health")
async def auth_health():
    """
    Auth service health endpoint — no authentication required.

    Returns Redis connectivity, revoked token count, and active sessions.
    """
    bl_status = await token_blacklist.status()
    return {
        "status":               bl_status["status"],
        "auth":                 "jwt",
        "algorithm":            os.getenv("JWT_ALGORITHM", "HS256"),
        "redis_connected":      bl_status["redis_connected"],
        "revoked_token_count":  bl_status["revoked_token_count"],
        "active_sessions":      bl_status["active_sessions"],
        "fail_open":            bl_status["fail_open"],
    }


# ---------------------------------------------------------------------------
# Internal audit helper
# ---------------------------------------------------------------------------

def _audit_auth(
    action:   str,
    user_id:  str,
    outcome:  str,
    metadata: Optional[dict] = None,
) -> None:
    """Fire-and-forget audit log entry for auth events."""
    try:
        from backend.safety.audit_logger import audit_logger
        audit_logger.log(
            execution_id = "auth",
            agent        = "auth_service",
            action       = action,
            target       = user_id[:32],
            risk_level   = "medium" if "revoke" in action else "low",
            outcome      = outcome,
            user         = user_id[:32],
            metadata     = metadata or {},
        )
    except Exception as exc:
        log.debug("_audit_auth non-fatal error: %s", exc)

