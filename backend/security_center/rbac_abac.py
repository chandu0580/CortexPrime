from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.security_center.identity import identity_manager
from backend.security_center.models import (
    ApiKey,
    Permission,
    PermissionAction,
    ResourceType,
    User,
)

log = logging.getLogger(__name__)


class AccessControl:
    """
    Combined RBAC + ABAC access control for CortexPrime.

    Reuses and extends the existing PermissionEngine with:
    - Database-backed role resolution with inheritance
    - Attribute-Based Access Control (ABAC) for fine-grained decisions
    - Scoped permissions for missions, workers, connectors, and approvals
    - Least-privilege enforcement
    """

    def __init__(self) -> None:
        self._abac_rules: List[ABACRule] = []

    # ------------------------------------------------------------------
    # Permission check
    # ------------------------------------------------------------------

    def check_permission(
        self,
        user: User,
        resource_type: ResourceType,
        action: PermissionAction,
        resource_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if not user.is_active:
            return False

        effective_perms = identity_manager.get_effective_permissions(user.role_ids)

        # Check RBAC permissions
        for perm in effective_perms:
            if perm.matches(resource_type, action, resource_id):
                return True

        # Check ABAC rules if attributes are provided
        if attributes:
            for rule in self._abac_rules:
                if rule.matches(user, resource_type, action, resource_id, attributes):
                    if rule.effect == "deny":
                        return False
                    return True

        return False

    def check_api_key_permission(
        self,
        api_key: ApiKey,
        resource_type: ResourceType,
        action: PermissionAction,
        resource_id: Optional[str] = None,
    ) -> bool:
        if not api_key.is_active:
            return False

        for perm in api_key.permissions:
            if perm.matches(resource_type, action, resource_id):
                return True

        effective_perms = identity_manager.get_effective_permissions(api_key.role_ids)
        for perm in effective_perms:
            if perm.matches(resource_type, action, resource_id):
                return True

        return False

    def check_mission_permission(
        self,
        user: User,
        action: PermissionAction,
        mission_id: Optional[str] = None,
    ) -> bool:
        return self.check_permission(user, ResourceType.MISSION, action, mission_id)

    def check_worker_permission(
        self,
        user: User,
        action: PermissionAction,
        worker_type: Optional[str] = None,
    ) -> bool:
        return self.check_permission(user, ResourceType.WORKER, action, worker_type)

    def check_connector_permission(
        self,
        user: User,
        action: PermissionAction,
        connector_type: Optional[str] = None,
    ) -> bool:
        return self.check_permission(user, ResourceType.CONNECTOR, action, connector_type)

    def check_approval_permission(
        self,
        user: User,
        action: PermissionAction,
    ) -> bool:
        return self.check_permission(user, ResourceType.APPROVAL, action)

    def check_system_permission(
        self,
        user: User,
        action: PermissionAction,
    ) -> bool:
        if action == PermissionAction.ADMIN:
            return self.check_permission(user, ResourceType.SYSTEM, PermissionAction.ADMIN)
        return self.check_permission(user, ResourceType.SYSTEM, action)

    def enforce(
        self,
        user: User,
        resource_type: ResourceType,
        action: PermissionAction,
        resource_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.check_permission(user, resource_type, action, resource_id, attributes):
            self._audit_denied(user, resource_type, action, resource_id)
            raise PermissionError(
                f"Access denied: {user.user_id} cannot {action.value} {resource_type.value}"
                + (f"/{resource_id}" if resource_id else "")
            )

    # ------------------------------------------------------------------
    # ABAC rule management
    # ------------------------------------------------------------------

    def add_abac_rule(self, rule: ABACRule) -> None:
        self._abac_rules.append(rule)

    def clear_abac_rules(self) -> None:
        self._abac_rules.clear()

    # ------------------------------------------------------------------
    # Utility: resolve user from JWT or API key
    # ------------------------------------------------------------------

    def resolve_user(self, user_id: str) -> Optional[User]:
        return identity_manager.get_user(user_id)

    def can_user_access_mission(
        self, user: User, mission_id: str, organization_id: Optional[str] = None
    ) -> bool:
        if self.check_system_permission(user, PermissionAction.ADMIN):
            return True
        if organization_id and user.organization_id:
            if user.organization_id != organization_id:
                return False
        return self.check_mission_permission(user, PermissionAction.EXECUTE, mission_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _audit_denied(
        self,
        user: User,
        resource_type: ResourceType,
        action: PermissionAction,
        resource_id: Optional[str] = None,
    ) -> None:
        try:
            from backend.safety.audit_logger import audit_logger
            audit_logger.log(
                execution_id=f"access:denied:{user.user_id}",
                agent="access_control",
                action="permission_denied",
                target=f"{resource_type.value}/{resource_id}" if resource_id else resource_type.value,
                risk_level="medium",
                outcome="denied",
                reason=f"{user.user_id} lacks {action.value} on {resource_type.value}",
                metadata={
                    "user_id": user.user_id,
                    "roles": user.role_ids,
                    "resource_type": resource_type.value,
                    "action": action.value,
                    "resource_id": resource_id,
                },
            )
        except Exception:
            pass

    def status(self) -> Dict[str, Any]:
        return {
            "rbac_roles": len(identity_manager.list_roles()),
            "abac_rules": len(self._abac_rules),
            "total_users": len(identity_manager.list_users()),
        }


@staticmethod
def check_scope(scopes: List[str], required_scope: str) -> bool:
    return required_scope in scopes or "admin" in scopes


# ---------------------------------------------------------------------------
# ABAC Rule
# ---------------------------------------------------------------------------


class ABACRule:
    """
    Attribute-Based Access Control rule.

    Evaluates user attributes and resource attributes to grant or deny access.
    Rules are evaluated after RBAC permissions.
    """

    def __init__(
        self,
        name: str,
        effect: str,
        resource_types: List[ResourceType],
        actions: List[PermissionAction],
        conditions: Optional[List[Dict[str, Any]]] = None,
    ):
        self.name = name
        self.effect = effect
        self.resource_types = resource_types
        self.actions = actions
        self.conditions = conditions or []

    def matches(
        self,
        user: User,
        resource_type: ResourceType,
        action: PermissionAction,
        resource_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None,
    ) -> bool:
        if resource_type not in self.resource_types:
            return False
        if action not in self.actions:
            return False
        if not attributes:
            return bool(self.conditions) is False
        for condition in self.conditions:
            attr_key = condition.get("attribute", "")
            expected = condition.get("value")
            actual = attributes.get(attr_key)
            if actual != expected:
                return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "effect": self.effect,
            "resource_types": [r.value for r in self.resource_types],
            "actions": [a.value for a in self.actions],
            "conditions": self.conditions,
        }


access_control = AccessControl()