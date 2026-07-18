"""
Role-Based Access Control (RBAC) — permission checking utilities.
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import Depends, HTTPException, status

from backend.auth.dependencies import require_user

# Permission definitions
PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
    "member": {
        "read": ["projects", "missions", "executions", "analytics"],
        "write": ["projects"],
        "admin": [],
    },
    "admin": {
        "read": ["*"],
        "write": ["projects", "missions", "executions", "connectors", "settings"],
        "admin": ["users"],
    },
    "owner": {
        "read": ["*"],
        "write": ["*"],
        "admin": ["*"],
    },
}


def check_permission(user_role: str, action: str, resource: str) -> bool:
    """Check if a user role has permission for a given action on a resource."""
    if user_role not in PERMISSIONS:
        return False
    allowed = PERMISSIONS[user_role].get(action, [])
    if "*" in allowed:
        return True
    return resource in allowed


def require_permission(action: str, resource: str):
    """Dependency factory: returns a FastAPI dependency that checks RBAC."""
    async def _checker(user: Dict[str, Any] = Depends(require_user)):
        role = user.get("role", "member")
        if not check_permission(role, action, resource):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permission: {action}:{resource}",
            )
        return user
    return _checker
