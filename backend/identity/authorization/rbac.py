from __future__ import annotations

from typing import Any, Optional

from backend.identity.interfaces.authorization import (
    AuthorizationProvider,
    AuthorizationRequest,
    AuthorizationResult,
)

BUILTIN_ROLES: dict[str, dict[str, list[str]]] = {
    "viewer": {
        "read": ["*"],
        "write": [],
        "admin": [],
    },
    "member": {
        "read": ["*"],
        "write": ["projects", "missions", "executions"],
        "admin": [],
    },
    "operator": {
        "read": ["*"],
        "write": ["projects", "missions", "executions", "connectors", "settings"],
        "admin": [],
    },
    "admin": {
        "read": ["*"],
        "write": ["*"],
        "admin": ["users", "billing", "tenants", "settings", "connectors"],
    },
    "owner": {
        "read": ["*"],
        "write": ["*"],
        "admin": ["*"],
    },
}


class RBACProvider(AuthorizationProvider):
    def __init__(self, role_definitions: Optional[dict[str, dict[str, list[str]]]] = None):
        self._roles = role_definitions or BUILTIN_ROLES

    async def authorize(self, request: AuthorizationRequest) -> AuthorizationResult:
        role_config = self._roles.get(request.role.lower())
        if role_config is None:
            return AuthorizationResult(allowed=False, reason=f"Unknown role: {request.role}", evaluated_by="rbac")
        allowed_actions = role_config.get(request.action, [])
        if "*" in allowed_actions:
            return AuthorizationResult(allowed=True, evaluated_by="rbac")
        if request.resource in allowed_actions:
            return AuthorizationResult(allowed=True, evaluated_by="rbac")
        return AuthorizationResult(
            allowed=False,
            reason=f"Role '{request.role}' lacks '{request.action}' on '{request.resource}'",
            evaluated_by="rbac",
        )

    async def get_permissions(self, role: str) -> list[str]:
        role_config = self._roles.get(role.lower())
        if role_config is None:
            return []
        result = []
        for action, resources in role_config.items():
            for resource in resources:
                if resource == "*":
                    result.append(f"{action}:*")
                else:
                    result.append(f"{action}:{resource}")
        return result
