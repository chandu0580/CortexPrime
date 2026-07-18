from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


@dataclass
class TokenClaims:
    sub: str
    role: str
    type: str
    jti: str
    iat: datetime
    exp: datetime
    tenant_id: Optional[str] = None
    tenant_slug: Optional[str] = None
    user_role: Optional[str] = None
    email: Optional[str] = None
    permissions: list[str] = field(default_factory=list)


@dataclass
class TokenResult:
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    refresh_expires_at: datetime
    claims: TokenClaims


@dataclass
class Identity:
    user_id: str
    email: str
    display_name: str
    role: str
    tenant_id: Optional[str] = None
    tenant_slug: Optional[str] = None
    user_role: Optional[str] = None
    permissions: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_authenticated(self) -> bool:
        return True


class AuthenticationProvider(ABC):
    @abstractmethod
    async def authenticate(self, identifier: str, secret: str, tenant_id: Optional[str] = None) -> Optional[Identity]:
        ...

    @abstractmethod
    async def get_identity(self, user_id: str) -> Optional[Identity]:
        ...


class TokenProvider(ABC):
    @abstractmethod
    async def create_token_pair(self, identity: Identity) -> TokenResult:
        ...

    @abstractmethod
    async def validate_access_token(self, token: str) -> Optional[TokenClaims]:
        ...

    @abstractmethod
    async def validate_refresh_token(self, token: str) -> Optional[TokenClaims]:
        ...

    @abstractmethod
    async def refresh_access_token(self, refresh_token: str) -> Optional[TokenResult]:
        ...

    @abstractmethod
    async def revoke_token(self, jti: str, user_id: str, expires_at: datetime) -> None:
        ...

    @abstractmethod
    async def revoke_all_user_tokens(self, user_id: str) -> float:
        ...

    @abstractmethod
    async def is_token_revoked(self, jti: str, user_id: str, issued_at: datetime) -> bool:
        ...


class IdentityProvider(ABC):
    @abstractmethod
    async def resolve_identity(self, token: str) -> Optional[Identity]:
        ...

    @abstractmethod
    async def get_current_identity(self) -> Optional[Identity]:
        ...
