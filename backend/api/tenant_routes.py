"""
Tenant management REST API.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.auth.dependencies import require_admin
from backend.auth.tenant import Tenant, TenantUser, get_tenant_manager

router = APIRouter(prefix="/api/tenants", tags=["Tenants"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class CreateTenantRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    slug: str = Field(..., min_length=1, max_length=128, pattern=r"^[a-z0-9\-]+$")
    domain: Optional[str] = None
    plan: str = "free"


class TenantResponse(BaseModel):
    tenant_id: str
    name: str
    slug: str
    domain: Optional[str] = None
    plan: str
    is_active: bool
    settings: dict
    created_at: str


class AddUserRequest(BaseModel):
    email: str = Field(..., min_length=1, max_length=256)
    role: str = "member"


class UpdateUserRoleRequest(BaseModel):
    role: str = Field(..., min_length=1, max_length=64)


class TenantUserResponse(BaseModel):
    user_id: str
    tenant_id: str
    email: str
    role: str
    is_active: bool
    permissions: List[str]
    created_at: str


#: Phase 10.10. Tenant records are authoritative in ``cp_tenant``, and tenant
#: administration is deliberately OUT-OF-BAND: the authority grammar is
#: capability+environment scoped, a tenant is neither, and inventing a
#: tenant-admin action would be building the second authority model this phase
#: is told not to build.
#:
#: These mutation routes are therefore refused rather than repointed at the
#: durable store. Repointing them would hand tenant-state authority to an
#: unscoped V1 ``role=admin`` claim over a now-authoritative store, which is
#: worse than the hole they had. Leaving them writing the JSON would be worse
#: still: they would appear to work and change nothing.
TENANT_ADMIN_IS_OUT_OF_BAND = (
    "tenant administration is out-of-band: tenant records are authoritative in "
    "the durable store and are provisioned by an operator, not through this API"
)


def _same_tenant_or_refuse(current_user: dict, tenant_id: str) -> None:
    """The path tenant must be the caller's OWN tenant. **Phase 10.9.**

    Before this, these routes took ``tenant_id`` from the URL and guarded it
    with ``require_admin``, which checks a JWT ``role == "admin"`` claim and
    nothing else -- no tenant. An admin of tenant A could therefore admit
    members to tenant B, relabel them, list them, and deactivate tenant B
    outright, which stops every approval and execution in it.

    The claim is the caller's own tenant, and a mismatch is a 404 rather than a
    403: a tenant may not learn that another tenant exists.

    These routes are also no longer authoritative for membership. The durable
    store (``cp_tenant_membership``) is, and the governed path is
    ``/api/v1/tenants/members`` on the product API, where the tenant cannot be
    named by a caller at all.
    """
    claimed = current_user.get("tenant_id")
    if not claimed or claimed != tenant_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )


def _tenant_to_response(t: Tenant) -> TenantResponse:
    return TenantResponse(
        tenant_id=t.tenant_id,
        name=t.name,
        slug=t.slug,
        domain=t.domain,
        plan=t.plan,
        is_active=t.is_active,
        settings=t.settings,
        created_at=t.created_at,
    )


def _user_to_response(u: TenantUser) -> TenantUserResponse:
    return TenantUserResponse(
        user_id=u.user_id,
        tenant_id=u.tenant_id,
        email=u.email,
        role=u.role,
        is_active=u.is_active,
        permissions=u.permissions,
        created_at=u.created_at,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: CreateTenantRequest,
    current_user: dict = Depends(require_admin),
):
    """Refused. **Phase 10.10: tenant creation is out-of-band.**

    Until this phase any token carrying ``role == "admin"`` could create a
    tenant here, with no relationship to the governed authority model at all.
    """
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=TENANT_ADMIN_IS_OUT_OF_BAND,
    )
    tm = get_tenant_manager()
    existing = tm.get_tenant_by_slug(request.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant with slug '{request.slug}' already exists",
        )
    tenant = tm.create_tenant(
        name=request.name,
        slug=request.slug,
        domain=request.domain,
        plan=request.plan,
    )
    return _tenant_to_response(tenant)


@router.get("", response_model=List[TenantResponse])
async def list_tenants(
    current_user: dict = Depends(require_admin),
):
    """The caller's OWN tenant. **Phase 10.10 closed a disclosure here.**

    This route returned every tenant in the system -- id, slug, domain, plan
    and state -- to any token carrying ``role == "admin"``. That is the map an
    attacker uses to pick the next target, and Phase 10.9's path-tenant guard
    could not reach it because there is no tenant in the path to compare.
    """
    claimed = current_user.get("tenant_id")
    if not claimed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tenant association in token",
        )
    tm = get_tenant_manager()
    own = tm.get_tenant(claimed)
    return [_tenant_to_response(own)] if own else []


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    current_user: dict = Depends(require_admin),
):
    """Get tenant details (admin only)."""
    _same_tenant_or_refuse(current_user, tenant_id)
    tm = get_tenant_manager()
    tenant = tm.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return _tenant_to_response(tenant)


@router.post("/{tenant_id}/users", response_model=TenantUserResponse, status_code=status.HTTP_201_CREATED)
async def add_user_to_tenant(
    tenant_id: str,
    request: AddUserRequest,
    current_user: dict = Depends(require_admin),
):
    """Add a user to a tenant (admin only)."""
    _same_tenant_or_refuse(current_user, tenant_id)
    tm = get_tenant_manager()
    tenant = tm.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    existing = tm.get_user_by_email(request.email)
    if existing and existing.tenant_id == tenant_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists in this tenant",
        )
    user = tm.add_user(tenant_id, request.email, request.role)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to add user",
        )
    return _user_to_response(user)


@router.get("/{tenant_id}/users", response_model=List[TenantUserResponse])
async def list_tenant_users(
    tenant_id: str,
    current_user: dict = Depends(require_admin),
):
    """List users in a tenant (admin only)."""
    _same_tenant_or_refuse(current_user, tenant_id)
    tm = get_tenant_manager()
    tenant = tm.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return [_user_to_response(u) for u in tm.get_users(tenant_id)]


@router.patch("/{tenant_id}/users/{user_id}", response_model=TenantUserResponse)
async def update_user_role(
    tenant_id: str,
    user_id: str,
    request: UpdateUserRoleRequest,
    current_user: dict = Depends(require_admin),
):
    """Update a user's role within a tenant (admin only)."""
    _same_tenant_or_refuse(current_user, tenant_id)
    tm = get_tenant_manager()
    tenant = tm.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    success = tm.update_user_role(tenant_id, user_id, request.role)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found in tenant",
        )
    users = tm.get_users(tenant_id)
    for u in users:
        if u.user_id == user_id:
            return _user_to_response(u)
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Failed to retrieve updated user",
    )


@router.post("/{tenant_id}/deactivate", response_model=TenantResponse)
async def deactivate_tenant(
    tenant_id: str,
    current_user: dict = Depends(require_admin),
):
    """Refused. **Phase 10.10: tenant state is out-of-band.**

    Deactivating a tenant stops every approval and execution inside it. That is
    not something an unscoped admin claim may do to a now-authoritative store.
    """
    _same_tenant_or_refuse(current_user, tenant_id)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=TENANT_ADMIN_IS_OUT_OF_BAND,
    )
    tm = get_tenant_manager()
    tenant = tm.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    if not tenant.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tenant is already inactive",
        )
    tm.deactivate_tenant(tenant_id)
    return _tenant_to_response(tm.get_tenant(tenant_id))
