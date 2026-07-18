from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from backend.auth.dependencies import require_user
from backend.security_center.auth_providers import auth_providers
from backend.security_center.identity import identity_manager
from backend.security_center.models import (
    IdentityType,
    Permission,
    PermissionAction,
    ResourceType,
    SecretProvider,
)
from backend.security_center.rbac_abac import access_control

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/security", tags=["Security Center"], dependencies=[Depends(require_user)])


# ------------------------------------------------------------------
# Users
# ------------------------------------------------------------------

@router.get("/users")
async def list_users(active_only: bool = True):
    users = identity_manager.list_users(active_only=active_only)
    return {"users": [u.to_dict() for u in users], "total": len(users)}


@router.get("/users/{user_id}")
async def get_user(user_id: str):
    user = identity_manager.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User not found: {user_id}")
    return {"user": user.to_dict()}


@router.post("/users")
async def create_user(
    username: str,
    email: str,
    display_name: str,
    role_ids: Optional[List[str]] = None,
    organization_id: Optional[str] = None,
):
    user = identity_manager.create_user(
        username=username,
        email=email,
        display_name=display_name,
        role_ids=role_ids,
        organization_id=organization_id,
    )
    return {"status": "created", "user": user.to_dict()}


@router.post("/users/{user_id}/deactivate")
async def deactivate_user(user_id: str):
    user = identity_manager.deactivate_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deactivated", "user_id": user_id}


# ------------------------------------------------------------------
# Roles
# ------------------------------------------------------------------

@router.get("/roles")
async def list_roles():
    roles = identity_manager.list_roles()
    return {"roles": [r.to_dict() for r in roles], "total": len(roles)}


@router.get("/roles/{role_id}")
async def get_role(role_id: str):
    role = identity_manager.get_role(role_id)
    if role is None:
        raise HTTPException(status_code=404, detail=f"Role not found: {role_id}")
    return {"role": role.to_dict()}


@router.post("/roles")
async def create_role(
    name: str,
    description: str,
    parent_role_id: Optional[str] = None,
    permissions: Optional[List[Dict[str, Any]]] = None,
):
    perm_objs = []
    if permissions:
        for p in permissions:
            perm_objs.append(Permission(
                resource_type=ResourceType(p.get("resource_type", "system")),
                action=PermissionAction(p.get("action", "read")),
                resource_id=p.get("resource_id"),
            ))
    role = identity_manager.create_role(
        name=name,
        description=description,
        permissions=perm_objs,
        parent_role_id=parent_role_id,
    )
    return {"status": "created", "role": role.to_dict()}


@router.post("/users/{user_id}/roles/{role_id}")
async def assign_user_role(user_id: str, role_id: str):
    ok = identity_manager.assign_user_role(user_id, role_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to assign role")
    return {"status": "assigned", "user_id": user_id, "role_id": role_id}


@router.delete("/users/{user_id}/roles/{role_id}")
async def remove_user_role(user_id: str, role_id: str):
    ok = identity_manager.remove_user_role(user_id, role_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to remove role")
    return {"status": "removed", "user_id": user_id, "role_id": role_id}


# ------------------------------------------------------------------
# Groups
# ------------------------------------------------------------------

@router.get("/groups")
async def list_groups():
    groups = identity_manager.list_groups()
    return {"groups": [g.to_dict() for g in groups], "total": len(groups)}


@router.post("/groups")
async def create_group(
    name: str,
    description: str,
    organization_id: Optional[str] = None,
    role_ids: Optional[List[str]] = None,
):
    group = identity_manager.create_group(
        name=name, description=description,
        organization_id=organization_id, role_ids=role_ids,
    )
    return {"status": "created", "group": group.to_dict()}


@router.post("/groups/{group_id}/members/{user_id}")
async def add_user_to_group(group_id: str, user_id: str):
    ok = identity_manager.add_user_to_group(user_id, group_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to add user to group")
    return {"status": "added", "group_id": group_id, "user_id": user_id}


@router.delete("/groups/{group_id}/members/{user_id}")
async def remove_user_from_group(group_id: str, user_id: str):
    ok = identity_manager.remove_user_from_group(user_id, group_id)
    if not ok:
        raise HTTPException(status_code=400, detail="Failed to remove user from group")
    return {"status": "removed", "group_id": group_id, "user_id": user_id}


# ------------------------------------------------------------------
# Organizations
# ------------------------------------------------------------------

@router.get("/organizations")
async def list_organizations():
    orgs = identity_manager.list_organizations()
    return {"organizations": [o.to_dict() for o in orgs], "total": len(orgs)}


@router.post("/organizations")
async def create_organization(name: str, domain: Optional[str] = None):
    org = identity_manager.create_organization(name=name, domain=domain)
    return {"status": "created", "organization": org.to_dict()}


# ------------------------------------------------------------------
# API Keys
# ------------------------------------------------------------------

@router.get("/api-keys")
async def list_api_keys(user_id: Optional[str] = None):
    keys = identity_manager.list_api_keys(user_id=user_id)
    return {"api_keys": [k.to_dict() for k in keys], "total": len(keys)}


@router.post("/api-keys")
async def create_api_key(
    name: str,
    user_id: str,
    role_ids: Optional[List[str]] = None,
):
    api_key, raw_key = identity_manager.create_api_key(
        name=name, user_id=user_id, role_ids=role_ids,
    )
    return {
        "status": "created",
        "api_key": api_key.to_dict(),
        "raw_key": raw_key,
        "warning": "Store this key securely - it will not be shown again.",
    }


@router.post("/api-keys/{key_id}/revoke")
async def revoke_api_key(key_id: str):
    ok = identity_manager.revoke_api_key(key_id)
    if not ok:
        raise HTTPException(status_code=404, detail="API key not found")
    return {"status": "revoked", "key_id": key_id}


@router.post("/api-keys/{key_id}/rotate")
async def rotate_api_key(key_id: str):
    result = identity_manager.rotate_api_key(key_id)
    if result is None:
        raise HTTPException(status_code=404, detail="API key not found")
    new_key, raw = result
    return {
        "status": "rotated",
        "api_key": new_key.to_dict(),
        "raw_key": raw,
        "warning": "Store this key securely - it will not be shown again.",
    }


# ------------------------------------------------------------------
# Service Identities
# ------------------------------------------------------------------

@router.get("/service-identities")
async def list_service_identities():
    identities = identity_manager.list_service_identities()
    return {"identities": [i.to_dict() for i in identities], "total": len(identities)}


@router.post("/service-identities")
async def create_service_identity(
    name: str,
    identity_type: str = "service_account",
    role_ids: Optional[List[str]] = None,
):
    si = identity_manager.create_service_identity(
        name=name,
        identity_type=IdentityType(identity_type),
        role_ids=role_ids,
    )
    return {"status": "created", "identity": si.to_dict()}


# ------------------------------------------------------------------
# Secrets
# ------------------------------------------------------------------

@router.get("/secrets")
async def list_secrets():
    secrets = identity_manager.list_secrets()
    return {"secrets": [s.to_dict() for s in secrets], "total": len(secrets)}


@router.post("/secrets")
async def register_secret(
    name: str,
    provider: str = "env",
    provider_path: str = "",
    description: Optional[str] = None,
    rotation_days: int = 90,
):
    secret = identity_manager.register_secret(
        name=name,
        provider=SecretProvider(provider),
        provider_path=provider_path or name,
        description=description,
        rotation_days=rotation_days,
    )
    return {"status": "registered", "secret": secret.to_dict()}


# ------------------------------------------------------------------
# Auth Providers
# ------------------------------------------------------------------

@router.get("/auth-providers")
async def list_auth_providers():
    return {
        "providers": auth_providers.status(),
        "configured": len(auth_providers.list_configured()),
    }


@router.get("/auth/oauth2/login")
async def oauth2_login(state: str = "default"):
    url = auth_providers.get_oauth2_authorization_url(state)
    if url is None:
        raise HTTPException(status_code=501, detail="OAuth 2.0 not configured")
    return {"authorization_url": url}


@router.post("/auth/oauth2/callback")
async def oauth2_callback(code: str, redirect_uri: str):
    result = await auth_providers.exchange_oauth2_code(code, redirect_uri)
    if not result.success:
        raise HTTPException(status_code=401, detail=result.error)
    return {"result": {
        "success": True,
        "provider": result.provider.value,
        "user_id": result.user_id,
        "email": result.email,
        "display_name": result.display_name,
    }}


@router.get("/auth/oidc/login")
async def oidc_login(state: str = "default"):
    url = auth_providers.get_oidc_authorization_url(state)
    if url is None:
        raise HTTPException(status_code=501, detail="OpenID Connect not configured")
    return {"authorization_url": url}


@router.post("/auth/oidc/callback")
async def oidc_callback(code: str, redirect_uri: str):
    result = await auth_providers.exchange_oidc_code(code, redirect_uri)
    if not result.success:
        raise HTTPException(status_code=401, detail=result.error)
    return {"result": {
        "success": True,
        "provider": result.provider.value,
        "user_id": result.user_id,
        "email": result.email,
        "display_name": result.display_name,
    }}


@router.get("/auth/saml/login")
async def saml_login():
    url = auth_providers.get_saml_login_url()
    if url is None:
        raise HTTPException(status_code=501, detail="SAML 2.0 not configured")
    return {"sso_url": url}


@router.post("/auth/saml/callback")
async def saml_callback(saml_response: str):
    result = await auth_providers.process_saml_response(saml_response)
    if not result.success:
        raise HTTPException(status_code=401, detail=result.error)
    return {"result": {
        "success": True,
        "provider": result.provider.value,
        "user_id": result.user_id,
        "email": result.email,
        "display_name": result.display_name,
    }}


# ------------------------------------------------------------------
# Access Control
# ------------------------------------------------------------------

@router.post("/access/check")
async def check_access(
    user_id: str,
    resource_type: str,
    action: str,
    resource_id: Optional[str] = None,
):
    user = identity_manager.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    allowed = access_control.check_permission(
        user=user,
        resource_type=ResourceType(resource_type),
        action=PermissionAction(action),
        resource_id=resource_id,
    )
    return {
        "allowed": allowed,
        "user_id": user_id,
        "resource_type": resource_type,
        "action": action,
        "resource_id": resource_id,
    }


@router.get("/access/effective-permissions/{user_id}")
async def get_effective_permissions(user_id: str):
    user = identity_manager.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    perms = identity_manager.get_effective_permissions(user.role_ids)
    return {
        "user_id": user_id,
        "role_ids": user.role_ids,
        "permissions": [p.to_dict() for p in perms],
        "total": len(perms),
    }


# ------------------------------------------------------------------
# Status
# ------------------------------------------------------------------

@router.get("/status")
async def security_status():
    return {
        "identity": identity_manager.status(),
        "auth_providers_configured": len(auth_providers.list_configured()),
        "auth_providers": [p["provider"] for p in auth_providers.list_configured()],
        "access_control": access_control.status(),
    }
