from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class IdentityType(str, Enum):
    USER = "user"
    GROUP = "group"
    ORGANIZATION = "organization"
    SERVICE_ACCOUNT = "service_account"
    MISSION_IDENTITY = "mission_identity"
    CONNECTOR_IDENTITY = "connector_identity"


class AuthProvider(str, Enum):
    JWT = "jwt"
    OAUTH2 = "oauth2"
    OIDC = "oidc"
    SAML = "saml"
    API_KEY = "api_key"


class SecretProvider(str, Enum):
    ENV = "env"
    HASHICORP_VAULT = "hashicorp_vault"
    AZURE_KEY_VAULT = "azure_key_vault"
    AWS_SECRETS_MANAGER = "aws_secrets_manager"


class PermissionAction(str, Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    APPROVE = "approve"
    DELEGATE = "delegate"
    OVERRIDE = "override"
    CONFIGURE = "configure"
    ADMIN = "admin"


class ResourceType(str, Enum):
    MISSION = "mission"
    WORKER = "worker"
    CONNECTOR = "connector"
    APPROVAL = "approval"
    USER = "user"
    GROUP = "group"
    ROLE = "role"
    SECRET = "secret"
    API_KEY = "api_key"
    WORKSPACE = "workspace"
    MEMORY = "memory"
    KNOWLEDGE_GRAPH = "knowledge_graph"
    OBSERVABILITY = "observability"
    ANALYTICS = "analytics"
    GOVERNANCE = "governance"
    SYSTEM = "system"


@dataclass
class Permission:
    resource_type: ResourceType
    action: PermissionAction
    resource_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_type": self.resource_type.value,
            "action": self.action.value,
            "resource_id": self.resource_id,
        }

    def matches(self, resource_type: ResourceType, action: PermissionAction, resource_id: Optional[str] = None) -> bool:
        if self.resource_type != resource_type:
            return False
        if self.action != action:
            return False
        if self.resource_id is not None and resource_id is not None and self.resource_id != resource_id:
            return False
        return True


@dataclass
class Role:
    role_id: str
    name: str
    description: str
    permissions: List[Permission] = field(default_factory=list)
    parent_role_id: Optional[str] = None
    is_system_role: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_id": self.role_id,
            "name": self.name,
            "description": self.description,
            "permissions": [p.to_dict() for p in self.permissions],
            "parent_role_id": self.parent_role_id,
            "is_system_role": self.is_system_role,
        }


@dataclass
class User:
    user_id: str
    username: str
    email: str
    display_name: str
    role_ids: List[str] = field(default_factory=list)
    group_ids: List[str] = field(default_factory=list)
    organization_id: Optional[str] = None
    attributes: Dict[str, str] = field(default_factory=dict)
    is_active: bool = True
    identity_type: IdentityType = IdentityType.USER
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "display_name": self.display_name,
            "role_ids": self.role_ids,
            "group_ids": self.group_ids,
            "organization_id": self.organization_id,
            "attributes": self.attributes,
            "is_active": self.is_active,
            "identity_type": self.identity_type.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass
class Group:
    group_id: str
    name: str
    description: str
    organization_id: Optional[str] = None
    role_ids: List[str] = field(default_factory=list)
    member_user_ids: List[str] = field(default_factory=list)
    attributes: Dict[str, str] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "group_id": self.group_id,
            "name": self.name,
            "description": self.description,
            "organization_id": self.organization_id,
            "role_ids": self.role_ids,
            "member_count": len(self.member_user_ids),
            "attributes": self.attributes,
            "created_at": self.created_at,
        }


@dataclass
class Organization:
    organization_id: str
    name: str
    domain: Optional[str] = None
    attributes: Dict[str, str] = field(default_factory=dict)
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "name": self.name,
            "domain": self.domain,
            "attributes": self.attributes,
            "is_active": self.is_active,
            "created_at": self.created_at,
        }


@dataclass
class ApiKey:
    key_id: str
    key_prefix: str
    name: str
    hashed_key: str
    user_id: str
    role_ids: List[str] = field(default_factory=list)
    permissions: List[Permission] = field(default_factory=list)
    allowed_ips: List[str] = field(default_factory=list)
    is_active: bool = True
    expires_at: Optional[str] = None
    last_used_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    rotated_from: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": self.key_id,
            "key_prefix": self.key_prefix,
            "name": self.name,
            "user_id": self.user_id,
            "role_ids": self.role_ids,
            "permissions": [p.to_dict() for p in self.permissions],
            "allowed_ips": self.allowed_ips,
            "is_active": self.is_active,
            "expires_at": self.expires_at,
            "last_used_at": self.last_used_at,
            "created_at": self.created_at,
        }


@dataclass
class ServiceIdentity:
    identity_id: str
    name: str
    identity_type: IdentityType
    role_ids: List[str] = field(default_factory=list)
    permissions: List[Permission] = field(default_factory=list)
    attributes: Dict[str, str] = field(default_factory=dict)
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "identity_id": self.identity_id,
            "name": self.name,
            "identity_type": self.identity_type.value,
            "role_ids": self.role_ids,
            "permissions": [p.to_dict() for p in self.permissions],
            "attributes": self.attributes,
            "is_active": self.is_active,
            "created_at": self.created_at,
        }


@dataclass
class AuthSession:
    session_id: str
    user_id: str
    provider: AuthProvider
    expires_at: str
    access_token_jti: Optional[str] = None
    refresh_token_jti: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_activity: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "provider": self.provider.value,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
            "last_activity": self.last_activity,
            "is_active": self.is_active,
        }


@dataclass
class SecretReference:
    secret_id: str
    name: str
    provider: SecretProvider
    provider_path: str
    description: Optional[str] = None
    rotation_days: int = 90
    last_rotated_at: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "secret_id": self.secret_id,
            "name": self.name,
            "provider": self.provider.value,
            "provider_path": self.provider_path,
            "description": self.description,
            "rotation_days": self.rotation_days,
            "last_rotated_at": self.last_rotated_at,
            "created_at": self.created_at,
            "tags": self.tags,
        }


def new_id(prefix: str = "sec") -> str:
    return f"{prefix}_{uuid4().hex[:16]}"
