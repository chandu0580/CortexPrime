from __future__ import annotations

from typing import Optional

from backend.identity.authorization.abac import ABACEvaluator
from backend.identity.authorization.rbac import RBACProvider
from backend.identity.interfaces.authorization import (
    AuthorizationRequest,
    PermissionEvaluator,
)


class DefaultPermissionEvaluator(PermissionEvaluator):
    def __init__(self, rbac_provider: RBACProvider, abac_evaluator: Optional[ABACEvaluator] = None):
        self._rbac = rbac_provider
        self._abac = abac_evaluator

    async def has_permission(self, user_id: str, action: str, resource: str, tenant_id: Optional[str] = None) -> bool:
        result = await self._rbac.authorize(
            AuthorizationRequest(user_id=user_id, role="member", action=action, resource=resource, tenant_id=tenant_id)
        )
        return result.allowed

    async def has_all_permissions(self, user_id: str, actions: list[str], resource: str) -> bool:
        for action in actions:
            if not await self.has_permission(user_id, action, resource):
                return False
        return True

    async def has_any_permission(self, user_id: str, actions: list[str], resource: str) -> bool:
        for action in actions:
            if await self.has_permission(user_id, action, resource):
                return True
        return False

    async def filter_by_permission(self, user_id: str, action: str, resources: list[str]) -> list[str]:
        result = []
        for resource in resources:
            if await self.has_permission(user_id, action, resource):
                result.append(resource)
        return result
