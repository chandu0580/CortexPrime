from __future__ import annotations

import hashlib
import hmac
import logging
import os
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.security_center.models import (
    ApiKey,
    AuthProvider,
    Group,
    IdentityType,
    Organization,
    Permission,
    PermissionAction,
    ResourceType,
    Role,
    SecretProvider,
    SecretReference,
    ServiceIdentity,
    User,
    new_id,
)

log = logging.getLogger(__name__)


class IdentityManager:
    """
    Central identity management for CortexPrime.

    Manages users, groups, organizations, roles, and service identities.
    Integrates with the existing JWT auth system, token blacklist, and audit logger.
    """

    def __init__(self) -> None:
        self._users: Dict[str, User] = {}
        self._groups: Dict[str, Group] = {}
        self._organizations: Dict[str, Organization] = {}
        self._roles: Dict[str, Role] = {}
        self._api_keys: Dict[str, ApiKey] = {}
        self._service_identities: Dict[str, ServiceIdentity] = {}
        self._secrets: Dict[str, SecretReference] = {}

        self._init_system_roles()
        self._init_bootstrap_user()

    # ------------------------------------------------------------------
    # System role initialization
    # ------------------------------------------------------------------

    def _init_system_roles(self) -> None:
        system_roles = [
            Role(
                role_id="role_admin",
                name="Administrator",
                description="Full system access with all permissions.",
                permissions=[
                    Permission(ResourceType.SYSTEM, PermissionAction.ADMIN),
                    Permission(ResourceType.MISSION, PermissionAction.EXECUTE),
                    Permission(ResourceType.MISSION, PermissionAction.CREATE),
                    Permission(ResourceType.MISSION, PermissionAction.READ),
                    Permission(ResourceType.MISSION, PermissionAction.UPDATE),
                    Permission(ResourceType.MISSION, PermissionAction.DELETE),
                    Permission(ResourceType.WORKER, PermissionAction.CONFIGURE),
                    Permission(ResourceType.CONNECTOR, PermissionAction.CONFIGURE),
                    Permission(ResourceType.APPROVAL, PermissionAction.APPROVE),
                    Permission(ResourceType.APPROVAL, PermissionAction.OVERRIDE),
                    Permission(ResourceType.APPROVAL, PermissionAction.DELEGATE),
                    Permission(ResourceType.USER, PermissionAction.ADMIN),
                    Permission(ResourceType.SECRET, PermissionAction.ADMIN),
                    Permission(ResourceType.API_KEY, PermissionAction.ADMIN),
                    Permission(ResourceType.GOVERNANCE, PermissionAction.ADMIN),
                    Permission(ResourceType.OBSERVABILITY, PermissionAction.READ),
                    Permission(ResourceType.ANALYTICS, PermissionAction.READ),
                ],
                is_system_role=True,
            ),
            Role(
                role_id="role_operator",
                name="Operator",
                description="Can execute missions, manage approvals, and view all resources.",
                permissions=[
                    Permission(ResourceType.MISSION, PermissionAction.EXECUTE),
                    Permission(ResourceType.MISSION, PermissionAction.CREATE),
                    Permission(ResourceType.MISSION, PermissionAction.READ),
                    Permission(ResourceType.WORKER, PermissionAction.EXECUTE),
                    Permission(ResourceType.CONNECTOR, PermissionAction.EXECUTE),
                    Permission(ResourceType.APPROVAL, PermissionAction.APPROVE),
                    Permission(ResourceType.APPROVAL, PermissionAction.DELEGATE),
                    Permission(ResourceType.USER, PermissionAction.READ),
                    Permission(ResourceType.OBSERVABILITY, PermissionAction.READ),
                    Permission(ResourceType.ANALYTICS, PermissionAction.READ),
                    Permission(ResourceType.MEMORY, PermissionAction.READ),
                    Permission(ResourceType.KNOWLEDGE_GRAPH, PermissionAction.READ),
                ],
                is_system_role=True,
            ),
            Role(
                role_id="role_security_officer",
                name="Security Officer",
                description="Can manage security policies, approve critical actions, and view audit logs.",
                permissions=[
                    Permission(ResourceType.MISSION, PermissionAction.READ),
                    Permission(ResourceType.APPROVAL, PermissionAction.APPROVE),
                    Permission(ResourceType.APPROVAL, PermissionAction.OVERRIDE),
                    Permission(ResourceType.USER, PermissionAction.READ),
                    Permission(ResourceType.GOVERNANCE, PermissionAction.READ),
                    Permission(ResourceType.GOVERNANCE, PermissionAction.UPDATE),
                    Permission(ResourceType.OBSERVABILITY, PermissionAction.READ),
                    Permission(ResourceType.ANALYTICS, PermissionAction.READ),
                    Permission(ResourceType.SECRET, PermissionAction.READ),
                ],
                is_system_role=True,
            ),
            Role(
                role_id="role_compliance_officer",
                name="Compliance Officer",
                description="Can view audit logs, analytics, and governance reports.",
                permissions=[
                    Permission(ResourceType.MISSION, PermissionAction.READ),
                    Permission(ResourceType.GOVERNANCE, PermissionAction.READ),
                    Permission(ResourceType.OBSERVABILITY, PermissionAction.READ),
                    Permission(ResourceType.ANALYTICS, PermissionAction.READ),
                    Permission(ResourceType.USER, PermissionAction.READ),
                    Permission(ResourceType.APPROVAL, PermissionAction.READ),
                ],
                is_system_role=True,
            ),
            Role(
                role_id="role_engineer",
                name="Engineer",
                description="Can execute missions and view resources but cannot approve or manage secrets.",
                permissions=[
                    Permission(ResourceType.MISSION, PermissionAction.EXECUTE),
                    Permission(ResourceType.MISSION, PermissionAction.CREATE),
                    Permission(ResourceType.MISSION, PermissionAction.READ),
                    Permission(ResourceType.WORKER, PermissionAction.EXECUTE),
                    Permission(ResourceType.OBSERVABILITY, PermissionAction.READ),
                    Permission(ResourceType.MEMORY, PermissionAction.READ),
                    Permission(ResourceType.KNOWLEDGE_GRAPH, PermissionAction.READ),
                ],
                is_system_role=True,
            ),
            Role(
                role_id="role_viewer",
                name="Viewer",
                description="Read-only access to all resources.",
                permissions=[
                    Permission(ResourceType.MISSION, PermissionAction.READ),
                    Permission(ResourceType.USER, PermissionAction.READ),
                    Permission(ResourceType.OBSERVABILITY, PermissionAction.READ),
                    Permission(ResourceType.ANALYTICS, PermissionAction.READ),
                    Permission(ResourceType.MEMORY, PermissionAction.READ),
                    Permission(ResourceType.KNOWLEDGE_GRAPH, PermissionAction.READ),
                    Permission(ResourceType.GOVERNANCE, PermissionAction.READ),
                    Permission(ResourceType.WORKER, PermissionAction.READ),
                    Permission(ResourceType.CONNECTOR, PermissionAction.READ),
                ],
                is_system_role=True,
            ),
        ]
        for role in system_roles:
            self._roles[role.role_id] = role

    def _init_bootstrap_user(self) -> None:
        admin_user = User(
            user_id="user_admin",
            username=os.getenv("CORTEX_USER", "admin"),
            email="admin@cortexprime.local",
            display_name="Platform Administrator",
            role_ids=["role_admin"],
            attributes={"type": "bootstrap"},
        )
        self._users[admin_user.user_id] = admin_user
        log.info("Bootstrap admin user initialized: %s", admin_user.username)

    # ------------------------------------------------------------------
    # User management
    # ------------------------------------------------------------------

    def create_user(
        self,
        username: str,
        email: str,
        display_name: str,
        role_ids: Optional[List[str]] = None,
        group_ids: Optional[List[str]] = None,
        organization_id: Optional[str] = None,
        attributes: Optional[Dict[str, str]] = None,
    ) -> User:
        user = User(
            user_id=new_id("usr"),
            username=username,
            email=email,
            display_name=display_name,
            role_ids=role_ids or [],
            group_ids=group_ids or [],
            organization_id=organization_id,
            attributes=attributes or {},
        )
        self._users[user.user_id] = user
        self._audit("user_created", user_id=user.user_id, username=username)
        return user

    def get_user(self, user_id: str) -> Optional[User]:
        return self._users.get(user_id)

    def get_user_by_username(self, username: str) -> Optional[User]:
        for user in self._users.values():
            if user.username == username:
                return user
        return None

    def get_user_by_email(self, email: str) -> Optional[User]:
        for user in self._users.values():
            if user.email == email:
                return user
        return None

    def list_users(self, active_only: bool = True) -> List[User]:
        if active_only:
            return [u for u in self._users.values() if u.is_active]
        return list(self._users.values())

    def update_user(self, user_id: str, **kwargs: Any) -> Optional[User]:
        user = self.get_user(user_id)
        if user is None:
            return None
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        user.updated_at = datetime.now(timezone.utc).isoformat()
        self._audit("user_updated", user_id=user_id)
        return user

    def deactivate_user(self, user_id: str) -> Optional[User]:
        return self.update_user(user_id, is_active=False)

    # ------------------------------------------------------------------
    # Group management
    # ------------------------------------------------------------------

    def create_group(
        self,
        name: str,
        description: str,
        organization_id: Optional[str] = None,
        role_ids: Optional[List[str]] = None,
    ) -> Group:
        group = Group(
            group_id=new_id("grp"),
            name=name,
            description=description,
            organization_id=organization_id,
            role_ids=role_ids or [],
        )
        self._groups[group.group_id] = group
        self._audit("group_created", group_id=group.group_id, name=name)
        return group

    def get_group(self, group_id: str) -> Optional[Group]:
        return self._groups.get(group_id)

    def list_groups(self) -> List[Group]:
        return list(self._groups.values())

    def add_user_to_group(self, user_id: str, group_id: str) -> bool:
        user = self.get_user(user_id)
        group = self.get_group(group_id)
        if user is None or group is None:
            return False
        if user_id not in group.member_user_ids:
            group.member_user_ids.append(user_id)
        if group_id not in user.group_ids:
            user.group_ids.append(group_id)
        self._audit("user_added_to_group", user_id=user_id, group_id=group_id)
        return True

    def remove_user_from_group(self, user_id: str, group_id: str) -> bool:
        user = self.get_user(user_id)
        group = self.get_group(group_id)
        if user is None or group is None:
            return False
        group.member_user_ids = [uid for uid in group.member_user_ids if uid != user_id]
        user.group_ids = [gid for gid in user.group_ids if gid != group_id]
        self._audit("user_removed_from_group", user_id=user_id, group_id=group_id)
        return True

    # ------------------------------------------------------------------
    # Organization management
    # ------------------------------------------------------------------

    def create_organization(self, name: str, domain: Optional[str] = None) -> Organization:
        org = Organization(
            organization_id=new_id("org"),
            name=name,
            domain=domain,
        )
        self._organizations[org.organization_id] = org
        self._audit("organization_created", org_id=org.organization_id, name=name)
        return org

    def get_organization(self, org_id: str) -> Optional[Organization]:
        return self._organizations.get(org_id)

    def list_organizations(self) -> List[Organization]:
        return list(self._organizations.values())

    # ------------------------------------------------------------------
    # Role management
    # ------------------------------------------------------------------

    def create_role(
        self,
        name: str,
        description: str,
        permissions: Optional[List[Permission]] = None,
        parent_role_id: Optional[str] = None,
    ) -> Role:
        role = Role(
            role_id=new_id("role"),
            name=name,
            description=description,
            permissions=permissions or [],
            parent_role_id=parent_role_id,
        )
        self._roles[role.role_id] = role
        self._audit("role_created", role_id=role.role_id, name=name)
        return role

    def get_role(self, role_id: str) -> Optional[Role]:
        return self._roles.get(role_id)

    def list_roles(self) -> List[Role]:
        return list(self._roles.values())

    def get_effective_permissions(self, role_ids: List[str]) -> List[Permission]:
        all_perms: List[Permission] = []
        seen: set = set()
        for rid in role_ids:
            role = self.get_role(rid)
            if role is None:
                continue
            for perm in role.permissions:
                key = (perm.resource_type.value, perm.action.value, perm.resource_id)
                if key not in seen:
                    seen.add(key)
                    all_perms.append(perm)
            if role.parent_role_id:
                parent_perms = self.get_effective_permissions([role.parent_role_id])
                for perm in parent_perms:
                    key = (perm.resource_type.value, perm.action.value, perm.resource_id)
                    if key not in seen:
                        seen.add(key)
                        all_perms.append(perm)
        return all_perms

    def assign_user_role(self, user_id: str, role_id: str) -> bool:
        user = self.get_user(user_id)
        if user is None or role_id not in self._roles:
            return False
        if role_id not in user.role_ids:
            user.role_ids.append(role_id)
        self._audit("role_assigned", user_id=user_id, role_id=role_id)
        return True

    def remove_user_role(self, user_id: str, role_id: str) -> bool:
        user = self.get_user(user_id)
        if user is None:
            return False
        user.role_ids = [rid for rid in user.role_ids if rid != role_id]
        self._audit("role_removed", user_id=user_id, role_id=role_id)
        return True

    # ------------------------------------------------------------------
    # API Key management
    # ------------------------------------------------------------------

    def create_api_key(
        self,
        name: str,
        user_id: str,
        role_ids: Optional[List[str]] = None,
        permissions: Optional[List[Permission]] = None,
        allowed_ips: Optional[List[str]] = None,
    ) -> tuple[ApiKey, str]:
        raw_key = f"cp_{secrets.token_hex(32)}"
        hashed = self._hash_api_key(raw_key)
        api_key = ApiKey(
            key_id=new_id("key"),
            key_prefix=raw_key[:12],
            name=name,
            hashed_key=hashed,
            user_id=user_id,
            role_ids=role_ids or [],
            permissions=permissions or [],
            allowed_ips=allowed_ips or [],
        )
        self._api_keys[api_key.key_id] = api_key
        self._audit("api_key_created", key_id=api_key.key_id, name=name, user_id=user_id)
        return api_key, raw_key

    def validate_api_key(self, raw_key: str, ip_address: Optional[str] = None) -> Optional[ApiKey]:
        hashed = self._hash_api_key(raw_key)
        for api_key in self._api_keys.values():
            if not api_key.is_active:
                continue
            if not hmac.compare_digest(api_key.hashed_key, hashed):
                continue
            if api_key.expires_at:
                exp = datetime.fromisoformat(api_key.expires_at)
                if datetime.now(timezone.utc) > exp:
                    continue
            if ip_address and api_key.allowed_ips:
                if ip_address not in api_key.allowed_ips:
                    continue
            api_key.last_used_at = datetime.now(timezone.utc).isoformat()
            return api_key
        return None

    def revoke_api_key(self, key_id: str) -> bool:
        api_key = self._api_keys.get(key_id)
        if api_key is None:
            return False
        api_key.is_active = False
        self._audit("api_key_revoked", key_id=key_id)
        return True

    def rotate_api_key(self, key_id: str) -> Optional[tuple[ApiKey, str]]:
        api_key = self._api_keys.get(key_id)
        if api_key is None:
            return None
        new_key, raw = self.create_api_key(
            name=api_key.name,
            user_id=api_key.user_id,
            role_ids=api_key.role_ids,
            permissions=api_key.permissions,
            allowed_ips=api_key.allowed_ips,
        )
        new_key.rotated_from = key_id
        api_key.is_active = False
        self._audit("api_key_rotated", key_id=key_id, new_key_id=new_key.key_id)
        return new_key, raw

    def list_api_keys(self, user_id: Optional[str] = None) -> List[ApiKey]:
        if user_id:
            return [k for k in self._api_keys.values() if k.user_id == user_id]
        return list(self._api_keys.values())

    # ------------------------------------------------------------------
    # Service identity management
    # ------------------------------------------------------------------

    def create_service_identity(
        self,
        name: str,
        identity_type: IdentityType,
        role_ids: Optional[List[str]] = None,
        permissions: Optional[List[Permission]] = None,
        attributes: Optional[Dict[str, str]] = None,
    ) -> ServiceIdentity:
        si = ServiceIdentity(
            identity_id=new_id("sid"),
            name=name,
            identity_type=identity_type,
            role_ids=role_ids or [],
            permissions=permissions or [],
            attributes=attributes or {},
        )
        self._service_identities[si.identity_id] = si
        self._audit("service_identity_created", identity_id=si.identity_id, name=name)
        return si

    def get_service_identity(self, identity_id: str) -> Optional[ServiceIdentity]:
        return self._service_identities.get(identity_id)

    def list_service_identities(self) -> List[ServiceIdentity]:
        return list(self._service_identities.values())

    # ------------------------------------------------------------------
    # Secrets management (metadata only, values stored in provider)
    # ------------------------------------------------------------------

    def register_secret(
        self,
        name: str,
        provider: SecretProvider,
        provider_path: str,
        description: Optional[str] = None,
        rotation_days: int = 90,
    ) -> SecretReference:
        secret = SecretReference(
            secret_id=new_id("sec"),
            name=name,
            provider=provider,
            provider_path=provider_path,
            description=description,
            rotation_days=rotation_days,
        )
        self._secrets[secret.secret_id] = secret
        self._audit("secret_registered", secret_id=secret.secret_id, name=name)
        return secret

    def get_secret(self, secret_id: str) -> Optional[SecretReference]:
        return self._secrets.get(secret_id)

    def list_secrets(self) -> List[SecretReference]:
        return list(self._secrets.values())

    def mark_secret_rotated(self, secret_id: str) -> bool:
        secret = self._secrets.get(secret_id)
        if secret is None:
            return False
        secret.last_rotated_at = datetime.now(timezone.utc).isoformat()
        self._audit("secret_rotated", secret_id=secret_id)
        return True

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _hash_api_key(self, raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode()).hexdigest()

    def _audit(self, action: str, **kwargs: Any) -> None:
        try:
            from backend.safety.audit_logger import audit_logger
            audit_logger.log(
                execution_id=f"identity:{action}",
                agent="security_center",
                action=action,
                risk_level="low",
                outcome="completed",
                reason=action.replace("_", " "),
                metadata=kwargs,
            )
        except Exception as exc:
            log.debug("Identity audit failed: %s", exc)

    # ------------------------------------------------------------------
    # Session tracking
    # ------------------------------------------------------------------

    def _track_session(
        self,
        user_id: str,
        provider: AuthProvider,
        access_jti: str,
        refresh_jti: Optional[str] = None,
        ip: Optional[str] = None,
        ua: Optional[str] = None,
    ) -> None:
        try:
            from backend.auth.token_blacklist import token_blacklist
            token_blacklist.track_session(user_id, access_jti)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def status(self) -> Dict[str, Any]:
        return {
            "users": len(self._users),
            "active_users": sum(1 for u in self._users.values() if u.is_active),
            "groups": len(self._groups),
            "organizations": len(self._organizations),
            "roles": len(self._roles),
            "system_roles": sum(1 for r in self._roles.values() if r.is_system_role),
            "api_keys": len(self._api_keys),
            "active_api_keys": sum(1 for k in self._api_keys.values() if k.is_active),
            "service_identities": len(self._service_identities),
            "secrets": len(self._secrets),
        }


identity_manager = IdentityManager()
