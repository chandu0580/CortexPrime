from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

import jwt
from jwt import InvalidTokenError

from backend.identity.interfaces.authentication import TokenClaims
from backend.identity.jwt.key_store import KeyStore

log = logging.getLogger(__name__)


class AccessTokenProvider:
    def __init__(self, key_store: KeyStore):
        self._key_store = key_store

    async def create(self, claims: TokenClaims) -> str:
        signing_key = await self._key_store.get_signing_key()
        if signing_key is None:
            raise RuntimeError("No valid signing key available")

        payload: dict[str, Any] = {
            "sub": claims.sub,
            "role": claims.role,
            "type": "access",
            "jti": claims.jti or secrets.token_hex(16),
            "iat": claims.iat,
            "exp": claims.exp,
        }
        if claims.tenant_id:
            payload["tenant_id"] = claims.tenant_id
        if claims.tenant_slug:
            payload["tenant_slug"] = claims.tenant_slug
        if claims.user_role:
            payload["user_role"] = claims.user_role
        if claims.email:
            payload["email"] = claims.email
        if claims.permissions:
            payload["permissions"] = claims.permissions

        headers = {"kid": signing_key.kid}
        return jwt.encode(payload, signing_key.secret, algorithm=signing_key.algorithm, headers=headers)

    async def validate(self, token: str) -> Optional[TokenClaims]:
        try:
            headers = jwt.get_unverified_header(token)
            kid = headers.get("kid", "")
            if not kid:
                log.debug("Access token missing kid header")
                return None

            signing_key = await self._key_store.get_verification_key(kid)
            if signing_key is None:
                log.debug("No verification key found for kid=%s", kid[:8])
                return None

            payload = jwt.decode(token, signing_key.secret, algorithms=[signing_key.algorithm])
            if payload.get("type") != "access":
                log.debug("Token type is not access: %s", payload.get("type"))
                return None

            exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
            if exp < datetime.now(timezone.utc):
                log.debug("Access token expired")
                return None

            return TokenClaims(
                sub=payload["sub"],
                role=payload.get("role", "member"),
                type="access",
                jti=payload.get("jti", ""),
                iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
                exp=exp,
                tenant_id=payload.get("tenant_id"),
                tenant_slug=payload.get("tenant_slug"),
                user_role=payload.get("user_role"),
                email=payload.get("email"),
                permissions=payload.get("permissions", []),
            )
        except InvalidTokenError as exc:
            log.debug("Access token validation failed: %s", exc)
            return None
        except Exception as exc:
            log.error("Access token validation error: %s", exc)
            return None

    async def get_expiry(self, token: str) -> Optional[datetime]:
        try:
            payload = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
            exp = payload.get("exp")
            return datetime.fromtimestamp(exp, tz=timezone.utc) if exp else None
        except Exception:
            return None
