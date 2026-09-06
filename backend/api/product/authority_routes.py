"""Governed grant issuance over the product API — Phase 10.8 (ADR-101).

Why these routes exist at all
-----------------------------
Phase 10.8 could have stopped at a Python function. It did not, for one reason:
**attribution needs an authenticated issuer.** A service callable only from a
script takes its issuer identity from whoever happens to run the script, which
is the same unattributed write this phase exists to close. The session is what
makes ``issued_by`` mean something.

So the surface is the minimum that makes issuance real, and no more:

    POST   /api/v1/authority/grants                     issue
    POST   /api/v1/authority/grants/{grant_id}/revocation   revoke
    GET    /api/v1/authority/grants                     list

What these routes do NOT do
---------------------------
They decide nothing. The issuer's entitlement is resolved by
``resolve_scoped_authority`` -- the same function that decides approval and
execution authority -- and the policy that validates what may be issued lives
in ``backend.auth.grants``. These handlers translate HTTP to that call and its
answer back to a status code.

Nothing authority-bearing is read from the request. The tenant and the issuer
come from the verified session; the capability's version, supported
environments and implied risk come from the catalog. A body that tries to
supply any of them is a 422, because the models forbid extra fields -- rejected
rather than ignored.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from backend.api.product.context import ProductContext, product_context

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["authority"])

#: Every mutating route this module adds, enumerated so a test can assert the
#: product's write surface is exactly what was intended -- the same technique
#: Phase 10.3 used, and the reason a fourth mutating route cannot appear here
#: unnoticed.
MUTATING_ROUTES = (
    ("POST", "/api/v1/authority/grants"),
    ("POST", "/api/v1/authority/grants/{grant_id}/revocation"),
)


class IssueGrantBody(BaseModel):
    """What an issuer may say. Note what is absent.

    There is no tenant, no issuer, no role, no capability version, no risk
    ceiling for the *capability*, and no scope object. Those are either
    resolved from the session or read from the catalog. ``extra="forbid"``
    turns an attempt to supply one into a 422 rather than a silently ignored
    field -- an ignored authority field is indistinguishable from an accepted
    one to whoever sent it.
    """

    model_config = ConfigDict(extra="forbid")

    subject: str = Field(
        min_length=1, max_length=256,
        description="The human who will hold this authority. Checked against "
                    "real membership of the caller's own tenant.")
    authority_type: str = Field(
        pattern="^(approve|execute)$",
        description="approve or execute. Never both, never 'issue' (which "
                    "would be transitive delegation) and never autonomy.")
    capability_ref: str = Field(min_length=1, max_length=512)
    environment: str = Field(min_length=1, max_length=32)
    max_risk: Optional[str] = Field(
        default=None, pattern="^(low|medium|high|critical)$",
        description="Optional ceiling. It may not exceed the risk the "
                    "capability itself declares.")
    reason: str = Field(
        min_length=8, max_length=1000,
        description="Why this authority is being granted. Stored on the row "
                    "and on the audit event; a grant nobody explained is a "
                    "grant nobody reviewed.")


class RevokeGrantBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=8, max_length=1000)


class GrantView(BaseModel):
    """One grant as the product presents it. A projection, never a decision."""

    grant_id: str
    tenant_id: str
    subject: str
    authority_type: str
    capability_ref: str
    capability_version: str
    environment: str
    max_risk: Optional[str] = None
    issued_by: str
    issued_at: Optional[str] = None
    revoked_at: Optional[str] = None
    revoked_by: Optional[str] = None
    #: True when this row still hashes to the identity it was issued with. A
    #: false value is an integrity finding, surfaced rather than hidden: a
    #: tampered grant already stops authorizing, and an operator needs to know
    #: the difference between that and a grant nobody ever created.
    intact: bool = True
    digest: str


class GrantList(BaseModel):
    grants: List[GrantView]
    tenant_id: str


class IssuedGrant(BaseModel):
    grant_id: str
    digest: str
    reason: str
    issuer_grant: Optional[str] = None


_ERRORS = {401: {"description": "unauthenticated"},
           403: {"description": "refused, with the reason named"},
           404: {"description": "no such grant in this tenant"},
           409: {"description": "already revoked"},
           503: {"description": "the grant store is unavailable"}}


def _engine():
    from backend.api.product.app import current_engine

    engine = current_engine()
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="the product engine is not composed")
    return engine


def _capability_facts(engine, capability_ref: str):
    """What the CATALOG says about this capability. Never what a body says.

    An unknown capability yields facts that fail ``known``, so issuance refuses
    rather than storing a grant for something that does not exist -- authority
    over a capability nobody commissioned is authority nobody can reason about.
    """
    from backend.auth.grants import CapabilityFacts
    from backend.contexts.connectivity.domain.authorization import implied_risk_for

    definitions = getattr(getattr(engine, "remediation", None),
                          "_definitions", {}) or {}
    for definition in definitions.values():
        reference = getattr(getattr(definition, "reference", None), "value", "")
        if reference != capability_ref:
            continue
        contract = getattr(definition, "contract", None)
        risk = implied_risk_for(
            getattr(contract, "effect_semantics", None),
            getattr(contract, "side_effect_class", None)).value
        return CapabilityFacts(
            capability_ref=reference,
            # The reference is already versioned ("...rollout_restart@1"), so
            # the version is read from it rather than unwrapped from a
            # CapabilityVersion -- one source, and the same one a grant pins.
            capability_version=(reference.rsplit("@", 1)[-1]
                                if "@" in reference else "1"),
            supported_environments=frozenset(
                str(e.value if hasattr(e, "value") else e)
                for e in (getattr(contract, "supported_environments", ()) or ())),
            implied_risk=risk)
    return CapabilityFacts(capability_ref="", capability_version="",
                           supported_environments=frozenset(), implied_risk="critical")


def _view(record: Any) -> GrantView:
    return GrantView(
        grant_id=record.grant_id, tenant_id=record.tenant_id,
        subject=record.subject_principal_id,
        authority_type=record.authority_type,
        capability_ref=record.capability_ref,
        capability_version=record.capability_version,
        environment=record.environment, max_risk=record.max_risk,
        issued_by=record.issued_by,
        issued_at=record.issued_at.isoformat() if record.issued_at else None,
        revoked_at=record.revoked_at.isoformat() if record.revoked_at else None,
        revoked_by=record.revoked_by,
        intact=record.digest_matches(),
        digest=record.digest)


@router.post("/authority/grants", response_model=IssuedGrant,
             responses=_ERRORS, status_code=status.HTTP_201_CREATED,
             summary="Issue one scoped authority grant")
def issue(body: IssueGrantBody,
          ctx: ProductContext = Depends(product_context)) -> IssuedGrant:
    """Create one grant, or refuse and name the check that stopped it.

    The issuer is ``ctx.principal`` -- the verified session -- and the tenant is
    ``ctx.tenant_id``. Neither is reachable from the body.
    """
    from backend.auth.grants import issue_grant
    from backend.auth.tenant import get_tenant_manager

    engine = _engine()
    outcome = issue_grant(
        repository=getattr(engine, "grants", None),
        issuer_principal_id=ctx.principal.principal_id,
        tenant_id=ctx.tenant_id,
        subject_principal_id=body.subject,
        authority_type=body.authority_type,
        capability=_capability_facts(engine, body.capability_ref),
        environment=body.environment,
        max_risk=body.max_risk,
        reason=body.reason,
        members=get_tenant_manager(),
        audit=getattr(getattr(engine, "runtime", None), "audit", None))

    if outcome.refused:
        if outcome.reason == "grant_store_unavailable":
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=outcome.reason)
        # 403 for every authority refusal, with the reason NAMED. A flat
        # "forbidden" would leave an issuer unable to tell a missing
        # entitlement from a self-grant from an environment the capability
        # does not support -- three different things to go and fix.
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=outcome.reason)
    return IssuedGrant(grant_id=outcome.grant_id, digest=outcome.digest,
                       reason=outcome.reason, issuer_grant=outcome.issuer_grant)


@router.post("/authority/grants/{grant_id}/revocation",
             response_model=IssuedGrant, responses=_ERRORS,
             summary="Revoke one grant")
def revoke(grant_id: str, body: RevokeGrantBody,
           ctx: ProductContext = Depends(product_context)) -> IssuedGrant:
    """Withdraw a grant. Tenant-scoped, so another tenant's grant is a 404."""
    from backend.auth.grants import revoke_grant

    engine = _engine()
    outcome = revoke_grant(
        repository=getattr(engine, "grants", None),
        revoker_principal_id=ctx.principal.principal_id,
        tenant_id=ctx.tenant_id, grant_id=grant_id, reason=body.reason,
        audit=getattr(getattr(engine, "runtime", None), "audit", None))

    if outcome.refused:
        if outcome.reason == "grant_store_unavailable":
            raise HTTPException(status_code=503, detail=outcome.reason)
        if outcome.reason == "no_such_grant":
            # Also the answer for a grant in another tenant. The read is
            # tenant-scoped, so "does not exist here" is all this may say.
            raise HTTPException(status_code=404, detail=outcome.reason)
        if outcome.reason == "grant_already_revoked":
            raise HTTPException(status_code=409, detail=outcome.reason)
        raise HTTPException(status_code=403, detail=outcome.reason)
    return IssuedGrant(grant_id=outcome.grant_id, digest=outcome.digest,
                       reason=outcome.reason)


@router.get("/authority/grants", response_model=GrantList, responses=_ERRORS,
            summary="Every grant in this tenant")
def list_grants(ctx: ProductContext = Depends(product_context)) -> GrantList:
    """A read. **No audit event is written** -- looking is not an action.

    Revoked grants are included deliberately: a list that hides them cannot
    answer "who used to be able to approve this", which is the question an
    incident review actually asks.
    """
    engine = _engine()
    grants = getattr(engine, "grants", None)
    if grants is None:
        raise HTTPException(status_code=503, detail="grant_store_unavailable")
    records = grants.list_for_tenant(tenant_id=ctx.tenant_id)
    return GrantList(grants=[_view(r) for r in records],
                     tenant_id=ctx.tenant_id)
