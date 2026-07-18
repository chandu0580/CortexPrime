from __future__ import annotations

import logging
import os
import secrets
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Optional

log = logging.getLogger(__name__)


class SigningKey:
    def __init__(self, kid: str, secret: str, algorithm: str, created_at: datetime, expires_at: Optional[datetime] = None):
        self.kid = kid
        self.secret = secret
        self.algorithm = algorithm
        self.created_at = created_at
        self.expires_at = expires_at

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def is_valid(self) -> bool:
        return not self.is_expired


class KeyStore(ABC):
    @abstractmethod
    async def get_signing_key(self, kid: Optional[str] = None) -> Optional[SigningKey]:
        ...

    @abstractmethod
    async def get_verification_key(self, kid: str) -> Optional[SigningKey]:
        ...

    @abstractmethod
    async def rotate_key(self) -> str:
        ...

    @abstractmethod
    async def get_active_kid(self) -> str:
        ...

    @abstractmethod
    async def health(self) -> dict:
        ...


class InMemoryKeyStore(KeyStore):
    def __init__(
        self,
        access_secret: Optional[str] = None,
        refresh_secret: Optional[str] = None,
        access_algorithm: str = "HS256",
        refresh_algorithm: str = "HS256",
        access_expire_minutes: int = 60,
        refresh_expire_hours: int = 168,
        key_rotation_interval_days: int = 90,
    ):
        self._access_secret = access_secret or os.getenv("JWT_SECRET_KEY", "") or secrets.token_hex(32)
        self._refresh_secret = refresh_secret or os.getenv("JWT_REFRESH_SECRET", "") or self._access_secret
        self._access_algorithm = access_algorithm
        self._refresh_algorithm = refresh_algorithm
        self._access_expire_minutes = access_expire_minutes
        self._refresh_expire_hours = refresh_expire_hours
        self._key_rotation_interval = timedelta(days=key_rotation_interval_days)

        now = datetime.now(timezone.utc)
        self._keys: dict[str, SigningKey] = {}
        self._key_order: list[str] = []

        access_kid = self._generate_kid("access")
        self._keys[access_kid] = SigningKey(
            kid=access_kid,
            secret=self._access_secret,
            algorithm=self._access_algorithm,
            created_at=now,
            expires_at=now + self._key_rotation_interval,
        )
        self._key_order.append(access_kid)

        refresh_kid = self._generate_kid("refresh")
        self._keys[refresh_kid] = SigningKey(
            kid=refresh_kid,
            secret=self._refresh_secret,
            algorithm=self._refresh_algorithm,
            created_at=now,
            expires_at=now + self._key_rotation_interval,
        )
        self._key_order.append(refresh_kid)

        self._active_kid = access_kid
        log.info(
            "KeyStore initialised: access_kid=%s refresh_kid=%s algo=%s/%s",
            access_kid[:8], refresh_kid[:8],
            self._access_algorithm, self._refresh_algorithm,
        )

    def _generate_kid(self, prefix: str) -> str:
        return f"{prefix}_{secrets.token_hex(8)}"

    async def get_signing_key(self, kid: Optional[str] = None) -> Optional[SigningKey]:
        if kid is None:
            kid = self._active_kid
        key = self._keys.get(kid)
        if key and key.is_valid:
            return key
        return None

    async def get_verification_key(self, kid: str) -> Optional[SigningKey]:
        key = self._keys.get(kid)
        if key and key.is_valid:
            return key
        return None

    async def rotate_key(self) -> str:
        now = datetime.now(timezone.utc)
        new_secret = secrets.token_hex(32)
        new_kid = self._generate_kid("access")

        self._keys[new_kid] = SigningKey(
            kid=new_kid,
            secret=new_secret,
            algorithm=self._access_algorithm,
            created_at=now,
            expires_at=now + self._key_rotation_interval,
        )
        self._key_order.append(new_kid)
        self._active_kid = new_kid

        expired = [kid for kid in self._key_order if kid != new_kid and self._keys[kid].is_expired]
        for kid in expired:
            self._keys.pop(kid, None)
            self._key_order.remove(kid)

        log.info("Key rotated: new_kid=%s expired_keys=%d", new_kid[:8], len(expired))
        return new_kid

    async def get_active_kid(self) -> str:
        return self._active_kid

    @property
    def access_expire_minutes(self) -> int:
        return self._access_expire_minutes

    @property
    def refresh_expire_hours(self) -> int:
        return self._refresh_expire_hours

    async def health(self) -> dict:
        datetime.now(timezone.utc)
        active_keys = sum(1 for k in self._keys.values() if k.is_valid)
        expired_keys = sum(1 for k in self._keys.values() if k.is_expired)
        return {
            "active_keys": active_keys,
            "expired_keys": expired_keys,
            "active_kid": self._active_kid[:8] if self._active_kid else None,
            "access_algorithm": self._access_algorithm,
            "refresh_algorithm": self._refresh_algorithm,
            "access_expire_minutes": self._access_expire_minutes,
            "refresh_expire_hours": self._refresh_expire_hours,
            "healthy": active_keys > 0,
        }
