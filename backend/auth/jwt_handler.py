"""
JWT Handler — Phase 2
=====================
Access tokens + refresh tokens + bcrypt password hashing.

Configuration (backend/.env):
  JWT_SECRET_KEY        — required, min 32 chars
  JWT_REFRESH_SECRET    — separate secret for refresh tokens (fallback: JWT_SECRET_KEY)
  JWT_ALGORITHM         — default HS256
  JWT_EXPIRE_MINUTES    — access token lifetime, default 60 minutes
  JWT_REFRESH_EXPIRE_H  — refresh token lifetime, default 168 hours (7 days)
  CORTEX_USER           — login username (default: admin)
  CORTEX_PASSWORD_HASH  — bcrypt hash of the password (see notes below)
  CORTEX_PASSWORD       — plaintext fallback used only when hash not set

Generating a password hash for .env:
  python -c "import bcrypt; print(bcrypt.hashpw(b'YourPassword', bcrypt.gensalt()).decode())"
"""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from jwt import InvalidTokenError

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config from environment
# ---------------------------------------------------------------------------

def _require_secret(env_var: str, fallback_var: str = "") -> str:
    secret = os.getenv(env_var, "")
    if not secret and fallback_var:
        secret = os.getenv(fallback_var, "")
    if not secret or len(secret) < 32:
        generated = secrets.token_hex(32)
        log.warning(
            "%s not set or too short — generated ephemeral key. "
            "Set %s in backend/.env (tokens will reset on restart).",
            env_var, env_var,
        )
        return generated
    return secret


_SECRET:         str = _require_secret("JWT_SECRET_KEY")
_REFRESH_SECRET: str = _require_secret("JWT_REFRESH_SECRET", "JWT_SECRET_KEY")
_ALGORITHM:      str = os.getenv("JWT_ALGORITHM", "HS256")
_EXPIRE_MIN:     int = int(os.getenv("JWT_EXPIRE_MINUTES", str(
                              int(os.getenv("JWT_EXPIRE_HOURS", "1")) * 60
                          )))
_REFRESH_EXPIRE_H: int = int(os.getenv("JWT_REFRESH_EXPIRE_H", "168"))  # 7 days


# ---------------------------------------------------------------------------
# Token creation
# ---------------------------------------------------------------------------

def create_access_token(user_id: str, role: str = "operator") -> str:
    """Return a signed short-lived access JWT."""
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub":  user_id,
        "role": role,
        "type": "access",
        "jti":  secrets.token_hex(16),   # unique ID for blacklist revocation
        "iat":  now,
        "exp":  now + timedelta(minutes=_EXPIRE_MIN),
    }
    return jwt.encode(payload, _SECRET, algorithm=_ALGORITHM)


def create_refresh_token(user_id: str, role: str = "operator") -> str:
    """Return a signed long-lived refresh JWT."""
    now = datetime.now(timezone.utc)
    payload: Dict[str, Any] = {
        "sub":  user_id,
        "role": role,
        "type": "refresh",
        "jti":  secrets.token_hex(16),   # unique ID — allows future revocation
        "iat":  now,
        "exp":  now + timedelta(hours=_REFRESH_EXPIRE_H),
    }
    return jwt.encode(payload, _REFRESH_SECRET, algorithm=_ALGORITHM)


# ---------------------------------------------------------------------------
# Token decoding
# ---------------------------------------------------------------------------

def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate an access JWT. Returns payload or None."""
    try:
        payload = jwt.decode(token, _SECRET, algorithms=[_ALGORITHM])
        if payload.get("type") != "access":
            return None
        return payload
    except InvalidTokenError as exc:
        log.debug("Access token invalid: %s", exc)
        return None


def decode_refresh_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a refresh JWT. Returns payload or None."""
    try:
        payload = jwt.decode(token, _REFRESH_SECRET, algorithms=[_ALGORITHM])
        if payload.get("type") != "refresh":
            return None
        return payload
    except InvalidTokenError as exc:
        log.debug("Refresh token invalid: %s", exc)
        return None


def get_token_expiry(token: str) -> Optional[datetime]:
    """Return the expiry datetime of any token without full validation."""
    try:
        payload = jwt.decode(
            token, options={"verify_signature": False, "verify_exp": False},
            algorithms=[_ALGORITHM],
        )
        exp = payload.get("exp")
        return datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Password verification (bcrypt)
# ---------------------------------------------------------------------------

def verify_credentials(username: str, password: str) -> bool:
    """
    Verify username + password.

    Checks against CORTEX_PASSWORD_HASH (bcrypt) first.
    Falls back to constant-time comparison against CORTEX_PASSWORD plaintext
    (for backwards compat during migration).

    To generate a hash for .env:
        python -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PASS', bcrypt.gensalt()).decode())"
    """
    expected_user: str = os.getenv("CORTEX_USER", "admin")

    if not secrets.compare_digest(username.strip(), expected_user):
        return False

    pw_hash: str = os.getenv("CORTEX_PASSWORD_HASH", "")
    if pw_hash:
        try:
            return bcrypt.checkpw(password.encode(), pw_hash.encode())
        except Exception as exc:
            log.error("bcrypt check failed: %s", exc)
            return False

    # Plaintext fallback (no hash configured — warn loudly)
    pw_plain: str = os.getenv("CORTEX_PASSWORD", "")
    if not pw_plain:
        log.warning(
            "Neither CORTEX_PASSWORD_HASH nor CORTEX_PASSWORD is set — "
            "all logins will fail. Configure credentials in backend/.env."
        )
        return False

    log.warning(
        "CORTEX_PASSWORD_HASH not set — using plaintext comparison. "
        "Run: python -c \"import bcrypt; print(bcrypt.hashpw(b'PASSWORD', bcrypt.gensalt()).decode())\" "
        "and set CORTEX_PASSWORD_HASH in backend/.env."
    )
    return secrets.compare_digest(password, pw_plain)
