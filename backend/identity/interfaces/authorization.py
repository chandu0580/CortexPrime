from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class AuthorizationRequest:
    user_id: str
    role: str
    action: str
    resource: str
    resource_id: Optional[str] = None
    tenant_id: Optional[str] = None
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuthorizationResult:
    allowed: bool
    reason: Optional[str] = None
    evaluated_by: str = "rbac"


class AuthorizationProvider(ABC):
    @abstractmethod
    async def authorize(self, request: AuthorizationRequest) -> AuthorizationResult:
        ...

    @abstractmethod
    async def get_permissions(self, role: str) -> list[str]:
        ...


class PermissionEvaluator(ABC):
    @abstractmethod
    async def has_permission(self, user_id: str, action: str, resource: str, tenant_id: Optional[str] = None) -> bool:
        ...

    @abstractmethod
    async def has_all_permissions(self, user_id: str, actions: list[str], resource: str) -> bool:
        ...

    @abstractmethod
    async def has_any_permission(self, user_id: str, actions: list[str], resource: str) -> bool:
        ...

    @abstractmethod
    async def filter_by_permission(self, user_id: str, action: str, resources: list[str]) -> list[str]:
        ...
