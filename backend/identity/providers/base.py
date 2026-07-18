from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class OAuthUserInfo:
    sub: str
    email: str
    display_name: str
    provider: str
    raw: dict[str, Any]


class OAuthProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @abstractmethod
    async def get_auth_url(self, redirect_uri: str, state: str) -> str:
        ...

    @abstractmethod
    async def exchange_code(self, code: str, redirect_uri: str) -> str:
        ...

    @abstractmethod
    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        ...

    @abstractmethod
    async def refresh_token(self, refresh_token: str) -> str:
        ...
