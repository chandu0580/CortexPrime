from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional


_now = lambda: datetime.now(timezone.utc)


@dataclass
class Session:
    session_id: str
    user_id: str
    tenant_id: Optional[str] = None
    jti: str = ""
    created_at: datetime = field(default_factory=_now)
    expires_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    is_revoked: bool = False

    @property
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return _now() > self.expires_at

    @property
    def is_active(self) -> bool:
        return not self.is_revoked and not self.is_expired


@dataclass
class SessionCreateRequest:
    user_id: str
    tenant_id: Optional[str] = None
    jti: str = ""
    expires_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionProvider(ABC):
    @abstractmethod
    async def create_session(self, request: SessionCreateRequest) -> Session:
        ...

    @abstractmethod
    async def get_session(self, session_id: str) -> Optional[Session]:
        ...

    @abstractmethod
    async def validate_session(self, session_id: str) -> bool:
        ...

    @abstractmethod
    async def revoke_session(self, session_id: str) -> bool:
        ...

    @abstractmethod
    async def revoke_all_user_sessions(self, user_id: str) -> int:
        ...

    @abstractmethod
    async def touch_session(self, session_id: str) -> bool:
        ...

    @abstractmethod
    async def list_active_sessions(self, user_id: str) -> list[Session]:
        ...

    @abstractmethod
    async def count_active_sessions(self) -> int:
        ...
