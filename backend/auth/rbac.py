"""
Role-Based Access Control (RBAC) — permission checking utilities.
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import Depends, HTTPException, status

from backend.auth.dependencies import require_user

# Permission definitions
PERMISSIONS: Dict[str, Dict[str, List[str]]] = {
    # Phase 10.5: note that NO role below carries an "approve" action, and that
    # is the point. Approver authority is an explicit per-membership grant
    # (backend/auth/approver.py), never something a role wildcard confers --
    # `owner` holds "*" for read, write and admin, and a permission reachable
    # through one of those would be the blanket approval authority the approval
    # system exists to prevent. `PERMISSIONS[role].get("approve", [])` is empty
    # for every role here, and the Phase 10.5 harness asserts it rather than
    # assuming it.
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
    """Check if a user role has permission for a given action on a resource.

    Role-based only. It has no view of a membership's explicit grants, which is
    why approver authority does not go through here -- see
    ``backend.auth.approver.resolve_approver_authority``, which reads the
    authoritative store rather than a role name.
    """
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
