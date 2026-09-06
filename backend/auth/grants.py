"""Governed grant issuance — Phase 10.8 (ADR-101).

The gap this closes
-------------------
Phases 10.5-10.7 made authority *enforcement* governed: an approver's grant is
scoped to a capability, an environment and a risk ceiling, executing needs its
own grant, and the requester of an action may not approve it.

Every one of those decisions read a grant that anybody could create. There was
no issuer parameter on ``grant_permission`` at all -- not a weak check, an
absent concept -- no validation beyond ``":" in permission``, no audit event,
and the store was a gitignored JSON file. Authority enforcement was governed;
authority creation was not.

This module is the issuance side. It is the *only* thing that produces a
matching set of arguments for ``SqlAuthorityGrantRepository.issue``, whose
``issued_by`` and ``issue_reason`` are required keywords with no defaults --
so routing around this policy does not yield an unattributed grant, it yields a
``TypeError``.

One authority model, not two
----------------------------
There is no second engine here. The issuer's own entitlement is resolved by
``resolve_scoped_authority`` -- the *same* function that decides whether a human
may approve or execute -- with ``action="issue"``. That is deliberate and it is
also what makes non-escalation free: asking "may this issuer issue a grant for
capability C in environment E at ceiling R" is exactly the question "does this
issuer hold issue-authority scoped to C, E and R", which the existing matcher
already answers by strict equality with no wildcards.

What cannot be issued, structurally
-----------------------------------
``issue`` itself. An issuer may create ``approve`` and ``execute`` grants and
nothing else, so holding issuance authority never confers the power to spread
it. Transitive delegation is therefore impossible rather than merely forbidden,
and Part P's rule -- authority to *use* a capability is not authority to
*delegate* it -- holds without a separate check.

``autonomy`` likewise. It is not an issuable authority type, and the grant
grammar has no autonomy action for the enforcement side to read even if a row
somehow named one.

Precedence, inherited rather than chosen
----------------------------------------
``CapabilityPolicy.evaluate`` orders authorization, then separation of duties,
then state; Phase 10.7 inserted scope inside authorization. This module keeps
that order: issuer authority (which includes scope), then separation of duties,
then the validity of what was asked for. A caller is told the thing that is
actually stopping them.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from backend.auth.approver import (
    APPROVE_ACTION,
    EXECUTE_ACTION,
    NO_ISSUER_AUTHORITY,
    _RISK_RANK,
    render_grant,
    resolve_scoped_authority,
)

__all__ = [
    "ISSUE_ACTION",
    "ISSUABLE_AUTHORITIES",
    "CapabilityFacts",
    "GrantOutcome",
    "issue_grant",
    "revoke_grant",
    "bootstrap_grant",
]

log = logging.getLogger(__name__)

ISSUE_ACTION = "issue"
"""A third action beside ``approve`` and ``execute``, in the same grammar and
read by the same parser. Phase 10.7 added ``execute`` beside ``approve`` the
same way; this is not a new authority model."""

ISSUABLE_AUTHORITIES = (APPROVE_ACTION, EXECUTE_ACTION)
"""What an issuer may create. Note the absence of ``issue`` and of anything
resembling autonomy: this tuple is the whole of the escalation surface."""

# Refusal reasons. Each names the thing that actually stopped the caller --
# "forbidden" would leave an operator unable to tell a missing entitlement from
# a self-grant from a capability that does not support the environment.
SELF_GRANT = "self_grant_refused"
SUBJECT_NOT_A_MEMBER = "subject_not_a_member"
SUBJECT_OTHER_TENANT = "subject_in_another_tenant"
NOT_ISSUABLE = "authority_type_not_issuable"
UNKNOWN_CAPABILITY = "unknown_capability"
ENVIRONMENT_UNSUPPORTED = "environment_not_supported_by_capability"
RISK_ABOVE_CAPABILITY = "risk_ceiling_exceeds_capability"
STORE_UNAVAILABLE = "grant_store_unavailable"
ISSUED = "grant_issued"
REVOKED = "grant_revoked"
NO_SUCH_GRANT = "no_such_grant"
ALREADY_REVOKED = "grant_already_revoked"


@dataclass(frozen=True)
class CapabilityFacts:
    """What the capability catalog says about the capability being granted.

    Supplied by the caller rather than looked up here, so this module imports no
    bounded context and the architecture's one-context-per-module rule keeps
    holding. It is also the reason the values cannot be spoofed by a request:
    the composition resolves them from the catalog, and the request models
    forbid extra fields.
    """

    capability_ref: str
    capability_version: str
    supported_environments: frozenset
    implied_risk: str

    @property
    def known(self) -> bool:
        return bool(self.capability_ref and self.supported_environments)


@dataclass(frozen=True)
class GrantOutcome:
    """What one issuance or revocation did. Facts, never a permission."""

    accepted: bool
    reason: str
    grant_id: Optional[str] = None
    digest: Optional[str] = None
    issuer_grant: Optional[str] = None

    @property
    def refused(self) -> bool:
        return not self.accepted


def _rank(level: Optional[str]) -> Optional[int]:
    return _RISK_RANK.get((level or "").strip().casefold())


def issue_grant(
    *,
    repository: Any,
    issuer_principal_id: str,
    tenant_id: str,
    subject_principal_id: str,
    authority_type: str,
    capability: CapabilityFacts,
    environment: str,
    max_risk: Optional[str],
    reason: str,
    members: Any = None,
    audit: Any = None,
    now: Any = None,
) -> GrantOutcome:
    """Issue one scoped authority grant, or refuse and say which check stopped it.

    ``issuer_principal_id`` is the **authenticated** issuer. Nothing in this
    signature may come from a request body: the tenant is resolved from the
    verified session, the capability facts from the catalog, and the subject is
    checked against real membership in *this* tenant.
    """
    if repository is None:
        return GrantOutcome(False, STORE_UNAVAILABLE)

    # 1. Issuer authority, including scope. The same resolver that answers
    #    "may you approve this" answers "may you issue this", so there is one
    #    authority model and non-escalation costs nothing extra: an issuer whose
    #    issue-grant names a different capability, a different environment or a
    #    lower ceiling simply does not match.
    effective_risk = max_risk or capability.implied_risk
    issuer = resolve_scoped_authority(
        principal_id=issuer_principal_id, tenant_id=tenant_id,
        action=ISSUE_ACTION, capability_ref=capability.capability_ref,
        environment=environment, risk=effective_risk,
        grants=repository)
    if issuer.denied:
        # The scoped reason is more useful than a flat refusal -- it says
        # whether the issuer holds nothing, or holds something narrower.
        # ``resolve_scoped_authority`` already names the dimension that
        # failed -- no issue-grant at all, wrong capability, wrong environment,
        # or a ceiling below what is being issued. All four are non-escalation
        # refusals and each says which.
        return GrantOutcome(False, issuer.reason)

    # 2. Separation of duties. An issuer never grants themselves authority,
    #    whatever else they hold. This is the loop Part J exists to prevent:
    #    without it, one issue-grant is a path to every other authority.
    if _same_identity(issuer_principal_id, subject_principal_id):
        return GrantOutcome(False, SELF_GRANT, issuer_grant=issuer.matched_grant)

    # 3. What is being asked for must be a real, issuable authority.
    if authority_type not in ISSUABLE_AUTHORITIES:
        # Catches "issue" (transitive delegation) and "autonomy" (which the
        # grant grammar cannot express) in one place, by allow-list.
        return GrantOutcome(False, NOT_ISSUABLE,
                            issuer_grant=issuer.matched_grant)

    # 4. The subject must be a real member of THIS tenant. A grant to somebody
    #    who is not here is authority nobody can revoke through the product.
    if members is not None:
        member = _member(members, subject_principal_id)
        if member is None:
            return GrantOutcome(False, SUBJECT_NOT_A_MEMBER,
                                issuer_grant=issuer.matched_grant)
        if getattr(member, "tenant_id", None) != tenant_id:
            return GrantOutcome(False, SUBJECT_OTHER_TENANT,
                                issuer_grant=issuer.matched_grant)

    # 5. The grant may not exceed the capability. This is the check Phase 10.7
    #    left open: a grant naming environment=production was accepted for a
    #    capability that supports only development.
    if not capability.known:
        return GrantOutcome(False, UNKNOWN_CAPABILITY,
                            issuer_grant=issuer.matched_grant)
    if environment not in capability.supported_environments:
        return GrantOutcome(False, ENVIRONMENT_UNSUPPORTED,
                            issuer_grant=issuer.matched_grant)
    if max_risk is not None:
        ceiling, declared = _rank(max_risk), _rank(capability.implied_risk)
        # An unrecognised ceiling does not widen anything: a level nobody can
        # rank is a level nobody agreed to.
        if ceiling is None or declared is None or ceiling > declared:
            return GrantOutcome(False, RISK_ABOVE_CAPABILITY,
                                issuer_grant=issuer.matched_grant)

    record = repository.issue(
        grant_id=f"grant-{uuid.uuid4().hex[:16]}",
        tenant_id=tenant_id,
        subject_principal_id=subject_principal_id,
        authority_type=authority_type,
        capability_ref=capability.capability_ref,
        capability_version=capability.capability_version,
        environment=environment,
        max_risk=max_risk,
        issued_by=issuer_principal_id,
        issue_reason=reason,
        now=now,
    )
    _audit(audit, "grant_issued", tenant_id=tenant_id,
           actor=issuer_principal_id, record=record,
           detail={"issuer_grant": issuer.matched_grant, "reason": reason})
    log.info("authority granted: %s may %s %s in %s (issued by %s)",
             subject_principal_id, authority_type, capability.capability_ref,
             environment, issuer_principal_id)
    return GrantOutcome(True, ISSUED, grant_id=record.grant_id,
                        digest=record.digest,
                        issuer_grant=issuer.matched_grant)


def revoke_grant(
    *, repository: Any, revoker_principal_id: str, tenant_id: str,
    grant_id: str, reason: str, audit: Any = None, now: Any = None,
) -> GrantOutcome:
    """Withdraw one grant. Tenant-scoped, attributed, and fail-closed.

    Revoking needs the same issue-authority that creating did, resolved against
    the grant's **stored** scope rather than anything supplied by the caller.
    Deliberately *not* subject to separation of duties: revoking your own
    authority is giving something up, and refusing it would mean an issuer who
    discovers they hold too much cannot put it down.
    """
    if repository is None:
        return GrantOutcome(False, STORE_UNAVAILABLE)

    record = repository.get(tenant_id=tenant_id, grant_id=grant_id)
    if record is None:
        # Also the answer for a grant in another tenant: the read is
        # tenant-scoped, so a cross-tenant revocation is indistinguishable from
        # a grant that does not exist -- which is the correct thing to leak.
        return GrantOutcome(False, NO_SUCH_GRANT)
    if record.revoked:
        return GrantOutcome(False, ALREADY_REVOKED, grant_id=grant_id)

    # Scoped to the grant's capability and environment, and deliberately NOT to
    # its risk ceiling.
    #
    # Revocation only ever REMOVES authority, so a ceiling comparison here buys
    # no safety -- and it costs something real: an issuer whose own ceiling is
    # `high` could create a grant and then be unable to take it back, stranding
    # authority nobody can retract. A revocation that is harder than the
    # issuance it undoes is not fail-closed, it is a one-way door.
    issuer = resolve_scoped_authority(
        principal_id=revoker_principal_id, tenant_id=tenant_id,
        action=ISSUE_ACTION, capability_ref=record.capability_ref,
        environment=record.environment, risk="low", grants=repository)
    if issuer.denied:
        return GrantOutcome(False, NO_ISSUER_AUTHORITY, grant_id=grant_id)

    if not repository.revoke(tenant_id=tenant_id, grant_id=grant_id,
                             revoked_by=revoker_principal_id, reason=reason,
                             now=now):
        # Lost a race with another revocation. Both callers are right about the
        # outcome; only one of them is the one that happened.
        return GrantOutcome(False, ALREADY_REVOKED, grant_id=grant_id)

    _audit(audit, "grant_revoked", tenant_id=tenant_id,
           actor=revoker_principal_id, record=record,
           detail={"reason": reason})
    return GrantOutcome(True, REVOKED, grant_id=grant_id, digest=record.digest)


def bootstrap_grant(
    *, repository: Any, tenant_id: str, subject_principal_id: str,
    authority_type: str, capability_ref: str, capability_version: str,
    environment: str, max_risk: Optional[str] = None,
    reason: str = "bootstrap: out-of-band root of trust",
) -> Any:
    """Provision a grant with no issuer. **The documented root of trust.**

    No system can issue its own first grant, so this exists. What makes it a
    root of trust rather than a backdoor:

    * it is not reachable from any HTTP route -- the product API has no path
      that calls it, and the boundary test asserts that;
    * it is attributed, to ``bootstrap``, so an auditor reading the store can
      tell a provisioned grant from an issued one at a glance;
    * it validates nothing about an issuer because there is no issuer, and it
      says so in its name rather than accepting an empty string.

    Anything that can call this can already write to the database.
    """
    return repository.issue(
        grant_id=f"grant-{uuid.uuid4().hex[:16]}", tenant_id=tenant_id,
        subject_principal_id=subject_principal_id,
        authority_type=authority_type, capability_ref=capability_ref,
        capability_version=capability_version, environment=environment,
        max_risk=max_risk, issued_by="bootstrap", issue_reason=reason)


def _same_identity(left: Any, right: Any) -> bool:
    """Compare authoritative identities, never display names."""
    return (str(left or "").strip().casefold()
            == str(right or "").strip().casefold())


def _member(members: Any, principal_id: str) -> Any:
    try:
        return members.get_user_by_email(principal_id)
    except Exception:  # noqa: BLE001 - an unreadable store grants nothing
        log.warning("membership lookup failed during issuance", exc_info=True)
        return None


def _audit(audit: Any, event: str, *, tenant_id: str, actor: str,
           record: Any, detail: dict) -> None:
    """Record issuance or revocation on the existing hash-chained ledger.

    ``IDENTITY_EVENT`` already means "authentication, authorization, or
    credential lifecycle" and is ``is_security_relevant``, so it can never be
    sampled or truncated away. No new event kind is invented for this phase.

    The detail carries the grant's authority-bearing fields and its digest. It
    carries no token, secret, credential or DSN -- there is no field on a grant
    that could hold one.
    """
    if audit is None:
        return
    try:
        from backend.contracts.audit import AuditEventKind

        payload = dict(record.to_dict())
        payload.update(detail)
        payload["event"] = event
        audit.record(AuditEventKind.IDENTITY_EVENT,
                     _scope_for(audit, tenant_id),
                     subject_reference=record.grant_id,
                     detail=payload)
    except Exception:  # noqa: BLE001 - see below
        # A failed audit write must never look like a failed grant, and must
        # never be silent. The grant is already durable at this point; losing
        # the event is a real gap and it is logged as one.
        log.error("authority %s was not audited (tenant=%s grant=%s)",
                  event, tenant_id, getattr(record, "grant_id", None),
                  exc_info=True)


def _scope_for(audit: Any, tenant_id: str) -> Any:
    from backend.contracts.tenant import TenantRef, TenantScope

    return TenantScope(tenant=TenantRef(tenant_id=tenant_id))
