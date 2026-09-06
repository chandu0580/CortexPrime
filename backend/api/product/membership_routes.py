"""Governed tenant membership over the product API — Phase 10.9 (ADR-102).

The surface is the minimum that makes membership administrable, and no more:

    POST  /api/v1/tenants/members                      admit
    POST  /api/v1/tenants/members/{id}/status          activate / deactivate
    POST  /api/v1/tenants/members/{id}/role            relabel (confers nothing)
    GET   /api/v1/tenants/members                      list

**There is no tenant in any of those paths.** That is the point. The V1 route
this phase replaces took the tenant from the URL and guarded it with a JWT
`role == "admin"` claim that carried no tenant at all, so an admin of one
tenant could admit members to another, relabel them, list them and deactivate
the whole tenant. Here the tenant comes from the verified session and cannot be
named by a caller, so cross-tenant administration is unrepresentable rather
than refused.

These routes decide nothing. Whether the caller may administer membership is
answered by ``backend.auth.membership``, which asks Phase 10.8's grant store.
Whether a member may approve, execute or issue is still answered by their
explicit scoped grants — no field here maps to any of them.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from backend.api.product.context import ProductContext, product_context

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["membership"])

#: Enumerated so a test can assert the product's write surface is exactly what
#: was intended, the same technique Phases 10.3 and 10.8 used.
MUTATING_ROUTES = (
    ("POST", "/api/v1/tenants/members"),
    ("POST", "/api/v1/tenants/members/{membership_id}/status"),
    ("POST", "/api/v1/tenants/members/{membership_id}/role"),
)


class AdmitBody(BaseModel):
    """Note what is absent: no tenant, no actor, no active flag, no authority.

    ``extra="forbid"`` makes an attempt to supply one a 422 rather than a
    silently ignored field — an ignored authority field is indistinguishable
    from an accepted one to whoever sent it.
    """

    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=1, max_length=256,
                         description="The human to admit to the caller's own "
                                     "tenant.")
    role: str = Field(default="member", pattern="^(member|admin|owner)$",
                      description="Informational only. No role confers "
                                  "approval, execution or issuance authority.")


class StatusBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern="^(active|inactive)$")


class RoleBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str = Field(pattern="^(member|admin|owner)$")


class MemberView(BaseModel):
    """One membership as the product presents it. A projection, not a decision."""

    membership_id: str
    tenant_id: str
    subject: str
    status: str
    role: str
    source: str
    created_by: str
    created_at: Optional[str] = None
    updated_by: Optional[str] = None
    updated_at: Optional[str] = None
    #: Deliberately says what membership does NOT confer, because a list of
    #: people with an "owner" beside a name invites exactly the wrong reading.
    confers_authority: bool = False


class MemberList(BaseModel):
    members: List[MemberView]
    tenant_id: str
    #: Restated on every listing: what a member may DO lives in the grant store.
    authority_note: str = ("Membership means this subject belongs to this "
                           "tenant. Approval, execution and issuance authority "
                           "are separate explicit grants.")


class MembershipChange(BaseModel):
    membership_id: str
    reason: str
    previous_state: Optional[str] = None
    new_state: Optional[str] = None


_ERRORS = {401: {"description": "unauthenticated"},
           403: {"description": "refused, with the reason named"},
           404: {"description": "no such membership in this tenant"},
           409: {"description": "already in that state"},
           503: {"description": "the membership store is unavailable"}}


def _engine():
    from backend.api.product.app import current_engine

    engine = current_engine()
    if engine is None:
        raise HTTPException(status_code=503,
                            detail="the product engine is not composed")
    return engine


def _view(record: Any) -> MemberView:
    return MemberView(
        membership_id=record.membership_id, tenant_id=record.tenant_id,
        subject=record.subject_principal_id, status=record.status,
        role=record.role, source=record.source, created_by=record.created_by,
        created_at=record.created_at.isoformat() if record.created_at else None,
        updated_by=record.updated_by,
        updated_at=record.updated_at.isoformat() if record.updated_at else None)


def _refuse(outcome) -> None:
    if outcome.reason == "membership_store_unavailable":
        raise HTTPException(status_code=503, detail=outcome.reason)
    if outcome.reason == "no_such_membership":
        # Also the answer for a membership in another tenant: the read is
        # tenant-scoped, so "not here" is all this may disclose.
        raise HTTPException(status_code=404, detail=outcome.reason)
    if outcome.reason in ("membership_already_in_that_state",
                          "already_a_member"):
        raise HTTPException(status_code=409, detail=outcome.reason)
    raise HTTPException(status_code=403, detail=outcome.reason)


@router.post("/tenants/members", response_model=MembershipChange,
             responses=_ERRORS, status_code=status.HTTP_201_CREATED,
             summary="Admit one subject to the caller's tenant")
def admit(body: AdmitBody,
          ctx: ProductContext = Depends(product_context)) -> MembershipChange:
    from backend.auth.membership import admit_member

    engine = _engine()
    outcome = admit_member(
        repository=getattr(engine, "memberships", None),
        actor_principal_id=ctx.principal.principal_id,
        tenant_id=ctx.tenant_id, subject_principal_id=body.subject,
        role=body.role, grants=getattr(engine, "grants", None),
        audit=getattr(getattr(engine, "runtime", None), "audit", None),
        audit_writer=getattr(getattr(engine, "runtime", None),
                             "audit_writer", None))
    if outcome.refused:
        _refuse(outcome)
    return MembershipChange(membership_id=outcome.membership_id,
                            reason=outcome.reason,
                            previous_state=outcome.previous_state,
                            new_state=outcome.new_state)


@router.post("/tenants/members/{membership_id}/status",
             response_model=MembershipChange, responses=_ERRORS,
             summary="Activate or deactivate one membership")
def set_status(membership_id: str, body: StatusBody,
               ctx: ProductContext = Depends(product_context)) -> MembershipChange:
    """Deactivation is the operation that matters.

    When it lands, approval, execution, grant issuance, grant revocation and
    product access all fail on their next check — each resolves membership live
    rather than trusting a token claim, so a grant cannot resurrect a
    membership somebody took away.
    """
    from backend.auth.membership import set_member_status

    engine = _engine()
    outcome = set_member_status(
        repository=getattr(engine, "memberships", None),
        actor_principal_id=ctx.principal.principal_id,
        tenant_id=ctx.tenant_id, membership_id=membership_id,
        status=body.status, grants=getattr(engine, "grants", None),
        audit=getattr(getattr(engine, "runtime", None), "audit", None),
        audit_writer=getattr(getattr(engine, "runtime", None),
                             "audit_writer", None))
    if outcome.refused:
        _refuse(outcome)
    return MembershipChange(membership_id=outcome.membership_id,
                            reason=outcome.reason,
                            previous_state=outcome.previous_state,
                            new_state=outcome.new_state)


@router.post("/tenants/members/{membership_id}/role",
             response_model=MembershipChange, responses=_ERRORS,
             summary="Relabel one membership (confers nothing)")
def set_role(membership_id: str, body: RoleBody,
             ctx: ProductContext = Depends(product_context)) -> MembershipChange:
    from backend.auth.membership import set_member_role

    engine = _engine()
    outcome = set_member_role(
        repository=getattr(engine, "memberships", None),
        actor_principal_id=ctx.principal.principal_id,
        tenant_id=ctx.tenant_id, membership_id=membership_id, role=body.role,
        grants=getattr(engine, "grants", None),
        audit=getattr(getattr(engine, "runtime", None), "audit", None),
        audit_writer=getattr(getattr(engine, "runtime", None),
                             "audit_writer", None))
    if outcome.refused:
        _refuse(outcome)
    return MembershipChange(membership_id=outcome.membership_id,
                            reason=outcome.reason,
                            previous_state=outcome.previous_state,
                            new_state=outcome.new_state)


@router.get("/tenants/members", response_model=MemberList, responses=_ERRORS,
            summary="Every membership in the caller's tenant")
def list_members(ctx: ProductContext = Depends(product_context)) -> MemberList:
    """A read. **No audit event is written** — looking is not an action.

    Inactive memberships are included deliberately: a list that hides them
    cannot answer "who used to belong here", which is what an incident review
    asks when it finds a historical approval by somebody who is gone.
    """
    engine = _engine()
    memberships = getattr(engine, "memberships", None)
    if memberships is None:
        raise HTTPException(status_code=503,
                            detail="membership_store_unavailable")
    return MemberList(
        members=[_view(r) for r in
                 memberships.list_for_tenant(tenant_id=ctx.tenant_id)],
        tenant_id=ctx.tenant_id)
