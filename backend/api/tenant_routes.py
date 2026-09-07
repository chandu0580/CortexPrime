"""
Tenant management REST API.
"""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.auth.dependencies import require_admin

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


#: Phase 10.13. **Nothing here reads a tenant any more.** The three GET routes
#: that projected durable rows into the legacy shape were deleted after Phase
#: 10.12 proved they had no consumer anywhere -- not in the backend, and not in
#: the compiled browser bundle -- and that their shape actively misled: three
#: fields had no authoritative source, four real provenance columns were
#: dropped, ``permissions`` was empty by construction, and ``user_id`` had
#: silently become a membership id while keeping its name.
#:
#: What remains is four refusals, deliberately. Each names where the governed
#: operation moved, so an operator following an old runbook gets an explanation
#: rather than a 404. The response models stay because these four still declare
#: them.
#:
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


MEMBERSHIP_IS_GOVERNED = (
    "membership administration moved to the governed product API: "
    "POST /api/v1/tenants/members. This route wrote a file no governed path "
    "reads, so it returned 201 and granted nothing"
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


@router.post("/{tenant_id}/users", response_model=TenantUserResponse, status_code=status.HTTP_201_CREATED)
async def add_user_to_tenant(
    tenant_id: str,
    request: AddUserRequest,
    current_user: dict = Depends(require_admin),
):
    """Refused. **Phase 10.11: this route granted nothing.**

    It wrote a member into ``tenant_users.json``, which stopped being
    authoritative in Phase 10.9. An operator called it, received **201**, and
    the person had no governed membership at all -- no product access, no
    authority, nothing. A write that appears to work and changes nothing is
    worse than one that refuses, so it refuses.
    """
    _same_tenant_or_refuse(current_user, tenant_id)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=MEMBERSHIP_IS_GOVERNED,
    )


@router.patch("/{tenant_id}/users/{user_id}", response_model=TenantUserResponse)
async def update_user_role(
    tenant_id: str,
    user_id: str,
    request: UpdateUserRoleRequest,
    current_user: dict = Depends(require_admin),
):
    """Refused. **Phase 10.11: this route granted nothing.**

    Same reason as adding a member: it rewrote a role in a file no governed
    path reads. The governed route is
    ``POST /api/v1/tenants/members/{id}/role`` -- and even there the role is
    informational, because Phase 10.5 established that no role confers
    authority.
    """
    _same_tenant_or_refuse(current_user, tenant_id)
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=MEMBERSHIP_IS_GOVERNED,
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
