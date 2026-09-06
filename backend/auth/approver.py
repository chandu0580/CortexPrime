"""Approver authority — Phase 10.5 (ADR-098).

The distinction this module exists to make
------------------------------------------
Until now, tenant membership was sufficient to approve an irreversible action.
That was survivable while approvals were reachable only from the investigation
that raised them. Phase 10.4 put every pending decision in one queue, which
hands every member of a tenant a list of every irreversible action awaiting
authorization -- so **tenant member != approver** has to become structural.

What this module is
-------------------
One question, answered from the authoritative store:

    may this authenticated human decide an approval in this tenant?

It is not an approval system. It does not decide *what* an approval covers
(``ApprovalFacts.is_valid_for`` does), it does not decide whether an action may
run (the authorization service does), and it does not execute anything. It runs
**before** the existing approval authority and adds nothing after it.

Why authority is read from the store and not from the token
-----------------------------------------------------------
Phase 10.2 mints the tenant membership role into the JWT. A check against that
claim would keep honouring a grant that had been revoked, until the token
expired -- a real revocation window nobody asked for. So the token establishes
*who is calling* and *which tenant*; this module asks the store *what they may
do*, on every request. Revocation therefore takes effect on the next request,
and that is proven with a token minted before the revocation rather than
asserted.

The cost is one store read per decision. The alternative is a window in which a
removed approver can still authorize an irreversible write.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

log = logging.getLogger(__name__)

__all__ = [
    "APPROVE_ACTION",
    "EXECUTE_ACTION",
    "ScopedGrant",
    "parse_grants",
    "resolve_scoped_authority",
    "OUT_OF_SCOPE_CAPABILITY",
    "OUT_OF_SCOPE_ENVIRONMENT",
    "OUT_OF_SCOPE_RISK",
    "UNSCOPED_GRANT",
    "SeparationVerdict",
    "SEPARATION_OF_DUTIES",
    "decision_separation",
    "APPROVE_RESOURCE",
    "APPROVE_REMEDIATION",
    "ApproverAuthority",
    "resolve_approver_authority",
]

#: The permission, in the vocabulary ``rbac.PERMISSIONS`` already uses.
APPROVE_ACTION = "approve"
#: Executing an already-approved action is a THIRD thing, distinct from
#: requesting it and from allowing it. Phase 10.5 gave approving its own grant;
#: until now executing needed only tenant membership plus a granted approval.
EXECUTE_ACTION = "execute"
APPROVE_RESOURCE = "remediation"

#: The single grant string stored on a tenant membership. It means exactly one
#: thing: *may make a decision on an existing approval request in this tenant*.
#: It does NOT mean "may execute" -- execution stays behind the execute route,
#: the gateway and the worker, none of which this module can reach.
APPROVE_REMEDIATION = f"{APPROVE_ACTION}:{APPROVE_RESOURCE}"


@dataclass(frozen=True)
class ApproverAuthority:
    """Whether this human may decide, and why.

    ``reason`` is a stable machine code, not prose, so a refusal can be
    attributed to the layer that made it rather than collapsed into "denied".
    """

    permitted: bool
    reason: str
    principal_id: str = ""
    tenant_id: str = ""
    membership_role: Optional[str] = None

    @property
    def denied(self) -> bool:
        return not self.permitted


#: Every refusal this module can produce. Named so the harness can assert WHICH
#: check refused, and so a UI can say something true rather than "forbidden".
NO_MEMBERSHIP = "no_tenant_membership"
MEMBERSHIP_INACTIVE = "membership_inactive"
WRONG_TENANT = "membership_in_another_tenant"
TENANT_INACTIVE = "tenant_inactive"
NOT_AN_APPROVER = "no_approver_authority"
STORE_UNAVAILABLE = "authority_store_unavailable"
GRANTED = "approver_authority_granted"


def resolve_approver_authority(
    *, principal_id: str, tenant_id: str
) -> ApproverAuthority:
    """May this human decide approvals in this tenant? Read live, fail closed.

    Both arguments come from the **verified session**. There is no parameter
    through which a request body, header or query string could reach this
    function, which is why a forged ``role`` or ``actor`` field is not ignored
    here -- it is unrepresentable.

    Every failure path denies. A store that cannot be read does not grant
    authority: the honest answer to "we cannot tell whether you may approve" is
    no, and an approval is exactly the wrong place to fail open.
    """
    if not principal_id or not tenant_id:
        return ApproverAuthority(False, NO_MEMBERSHIP, principal_id, tenant_id)

    try:
        from backend.auth.tenant import get_tenant_manager

        manager = get_tenant_manager()
        member = manager.get_user_by_email(principal_id)
        tenant = manager.get_tenant(tenant_id)
    except Exception:  # noqa: BLE001 - an unreadable store grants nothing
        log.warning("approver authority store unavailable", exc_info=True)
        return ApproverAuthority(False, STORE_UNAVAILABLE, principal_id, tenant_id)

    if member is None:
        return ApproverAuthority(False, NO_MEMBERSHIP, principal_id, tenant_id)
    if not getattr(member, "is_active", False):
        return ApproverAuthority(False, MEMBERSHIP_INACTIVE, principal_id, tenant_id,
                                 getattr(member, "role", None))
    # The membership must be in the tenant the SESSION resolved, not merely in
    # some tenant. A member of tenant B holding an approver grant there has no
    # authority over tenant A's queue.
    if member.tenant_id != tenant_id:
        return ApproverAuthority(False, WRONG_TENANT, principal_id, tenant_id,
                                 member.role)
    if tenant is None or not tenant.is_active:
        return ApproverAuthority(False, TENANT_INACTIVE, principal_id, tenant_id,
                                 member.role)

    # Does this membership hold ANY approver grant?
    #
    # Deliberately NOT satisfied by a role wildcard: the existing PERMISSIONS
    # table gives `owner` "*" for read, write and admin, and a permission
    # reachable through one of those would be the blanket approval authority
    # Phase 10.5 exists to prevent.
    #
    # Deliberately NOT an exact-string match either, since Phase 10.7. A grant
    # may now carry scope (`approve:remediation:capability=…,environment=…`),
    # and this layer answers only "are you an approver at all?". Whether the
    # grant covers a PARTICULAR action is a separate question answered by
    # ``resolve_scoped_authority`` against the stored approval -- so the two
    # refusals stay distinct: "you are not an approver" and "your grant does not
    # cover this".
    granted = bool(parse_grants(getattr(member, "permissions", ()) or (),
                                action=APPROVE_ACTION))
    if not granted:
        return ApproverAuthority(False, NOT_AN_APPROVER, principal_id, tenant_id,
                                 member.role)

    return ApproverAuthority(True, GRANTED, principal_id, tenant_id, member.role)

# ----------------------------------------------------------------------
# Separation of duties — Phase 10.6 (ADR-099)
# ----------------------------------------------------------------------

#: The reason a self-decision is refused. Taken from the EXISTING
#: ``DenialReason`` enum rather than invented here, so a refusal on this path
#: and a refusal in the capability policy -- where a capability owner may not be
#: the one who makes it live -- are the same named thing, and a reviewer
#: grepping for that reason finds both.
SEPARATION_OF_DUTIES = "separation_of_duties"


@dataclass(frozen=True)
class SeparationVerdict:
    """Whether these two identities may be the decider and the requester."""

    permitted: bool
    reason: str
    requested_by: str = ""
    actor: str = ""

    @property
    def denied(self) -> bool:
        return not self.permitted


def _canonical(reference: Optional[str]) -> str:
    """One identity reference, normalised for comparison.

    Whitespace and case only. Nothing here parses or rebuilds the reference:
    both sides are minted by the same helper from the same verified session, so
    they are already the same shape, and a comparison that had to *interpret* an
    identity would be a comparison that could be fooled by a different spelling
    of one.
    """
    return (reference or "").strip().casefold()


def decision_separation(
    *, requested_by: Optional[str], actor: Optional[str]
) -> SeparationVerdict:
    """The human who asked for an action may not be the one who allows it.

    Why this exists
    ---------------
    Until Phase 10.6 one person could raise an irreversible remediation and
    approve it alone. Phase 10.5 established that approving requires an explicit
    grant -- but the requester can hold that grant, so authority alone did not
    make a second human necessary.

    What it compares
    ----------------
    The two stored, namespaced identity references. Both are produced by the
    same helper from the verified session, so this is never a comparison of
    display names, browser-supplied usernames or free text -- and there is no
    parameter through which a caller could supply either side.

    Fail closed
    -----------
    An **absent or unreadable** requester reference denies. An approval whose
    requester cannot be established is exactly the one where nobody can say the
    decision was independent, and the honest answer to "we cannot tell whether
    this is a self-decision" is no.

    What it does NOT do
    -------------------
    It answers ALLOWED or REFUSED. It does not decide whether the approval is
    valid, whether the action may run, or what the action is -- and it cannot
    rewrite any of them. In particular the requester is already inside
    ``canonical_approval_digest``; this reads that identity and never touches
    the digest.
    """
    requester = _canonical(requested_by)
    decider = _canonical(actor)

    if not requester or not decider:
        return SeparationVerdict(False, SEPARATION_OF_DUTIES,
                                 requested_by or "", actor or "")
    if requester == decider:
        return SeparationVerdict(False, SEPARATION_OF_DUTIES,
                                 requested_by or "", actor or "")
    return SeparationVerdict(True, "independent_decision",
                             requested_by or "", actor or "")


def separation_denial_reason():
    """The platform's own denial reason for this refusal.

    Imported lazily and returned rather than hard-coded, so the string this
    module reports and the one the capability policy reports cannot drift apart.
    """
    from backend.contexts.connectivity.domain.authorization import DenialReason

    return DenialReason.SEPARATION_OF_DUTIES

# ----------------------------------------------------------------------
# Scoped authority — Phase 10.7 (ADR-100)
# ----------------------------------------------------------------------

#: Refusals this layer can produce, each naming the dimension that failed. A
#: caller told only "forbidden" cannot tell a wrong capability from a wrong
#: environment, and an operator debugging a grant needs to know which.
OUT_OF_SCOPE_CAPABILITY = "out_of_scope_capability"
OUT_OF_SCOPE_ENVIRONMENT = "out_of_scope_environment"
OUT_OF_SCOPE_RISK = "risk_exceeds_grant_ceiling"
UNSCOPED_GRANT = "grant_is_not_scoped"
NO_EXECUTOR_AUTHORITY = "no_executor_authority"
SCOPED_GRANT_MATCHED = "scoped_grant_matched"

#: The risk ladder, by the platform's own ordering. Not a score -- a rank over
#: the existing RiskLevel members, used only to compare a declared risk against
#: a grant's declared ceiling.
_RISK_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


@dataclass(frozen=True)
class ScopedGrant:
    """One parsed grant from a tenant membership.

    The grammar is deliberately small and categorical::

        <action>:remediation:capability=<ref>,environment=<env>[,max_risk=<level>]

    There are **no wildcards**. A grant names one capability; two capabilities
    means two grants. The existing role table already demonstrates what a
    wildcard does to an authority surface, and Phase 10.5 established that no
    wildcard may confer approval.
    """

    action: str
    resource: str
    capability_ref: str = ""
    environment: str = ""
    max_risk: Optional[str] = None

    @property
    def is_scoped(self) -> bool:
        """A grant naming neither a capability nor an environment is not a
        narrower grant -- it is the tenant-wide one this phase replaced."""
        return bool(self.capability_ref and self.environment)


def parse_grants(permissions: Any, *, action: str) -> tuple:
    """Every grant a membership holds for one action, parsed.

    Unparseable entries are skipped rather than guessed at. A grant that cannot
    be read is not a grant: the honest answer to "what does this string permit?"
    when it does not parse is nothing.
    """
    grants = []
    for raw in tuple(permissions or ()):
        if not isinstance(raw, str):
            continue
        parts = raw.split(":", 2)
        if len(parts) < 2 or parts[0] != action or parts[1] != APPROVE_RESOURCE:
            continue
        grant = ScopedGrant(action=parts[0], resource=parts[1])
        if len(parts) == 3 and parts[2]:
            fields = {}
            for pair in parts[2].split(","):
                key, _, value = pair.partition("=")
                key, value = key.strip(), value.strip()
                if key and value:
                    fields[key] = value
            grant = ScopedGrant(
                action=parts[0], resource=parts[1],
                capability_ref=fields.get("capability", ""),
                environment=fields.get("environment", ""),
                max_risk=fields.get("max_risk"),
            )
        grants.append(grant)
    return tuple(grants)


@dataclass(frozen=True)
class ScopedAuthority:
    """Whether this human may take this action ON THIS APPROVAL."""

    permitted: bool
    reason: str
    action: str = ""
    matched_grant: Optional[str] = None
    principal_id: str = ""
    tenant_id: str = ""

    @property
    def denied(self) -> bool:
        return not self.permitted


def resolve_scoped_authority(
    *, principal_id: str, tenant_id: str, action: str,
    capability_ref: str, environment: str, risk: str,
) -> ScopedAuthority:
    """May this human take ``action`` on an approval with these properties?

    Every argument after ``action`` describes the **stored approval and its
    capability contract** -- the capability it names, the environment it was
    raised in, and the risk the platform derives from the declared effect. None
    of them is ever read from a request: the request models forbid extra fields,
    so an attempt to supply one is a 422 rather than a silent ignore.

    Read live from the store, like the unscoped check it extends, so a revoked
    or re-scoped grant stops working on the next request rather than at token
    expiry.

    Fail closed at every step, including the one that used to pass: a grant with
    no capability and no environment is refused as ``grant_is_not_scoped``. That
    is the Phase 10.5 form, and leaving it working would leave tenant-wide
    authority in place beside the narrower scope that replaced it.
    """
    if not principal_id or not tenant_id:
        return ScopedAuthority(False, NO_MEMBERSHIP, action,
                               principal_id=principal_id, tenant_id=tenant_id)

    try:
        from backend.auth.tenant import get_tenant_manager

        manager = get_tenant_manager()
        member = manager.get_user_by_email(principal_id)
        tenant = manager.get_tenant(tenant_id)
    except Exception:  # noqa: BLE001 - an unreadable store grants nothing
        log.warning("scoped authority store unavailable", exc_info=True)
        return ScopedAuthority(False, STORE_UNAVAILABLE, action,
                               principal_id=principal_id, tenant_id=tenant_id)

    if member is None:
        return ScopedAuthority(False, NO_MEMBERSHIP, action,
                               principal_id=principal_id, tenant_id=tenant_id)
    if not getattr(member, "is_active", False):
        return ScopedAuthority(False, MEMBERSHIP_INACTIVE, action,
                               principal_id=principal_id, tenant_id=tenant_id)
    if member.tenant_id != tenant_id:
        return ScopedAuthority(False, WRONG_TENANT, action,
                               principal_id=principal_id, tenant_id=tenant_id)
    if tenant is None or not tenant.is_active:
        return ScopedAuthority(False, TENANT_INACTIVE, action,
                               principal_id=principal_id, tenant_id=tenant_id)

    grants = parse_grants(getattr(member, "permissions", ()), action=action)
    if not grants:
        reason = (NOT_AN_APPROVER if action == APPROVE_ACTION
                  else NO_EXECUTOR_AUTHORITY)
        return ScopedAuthority(False, reason, action,
                               principal_id=principal_id, tenant_id=tenant_id)

    # The most specific refusal wins, so an operator is told the dimension that
    # actually failed rather than the first one checked.
    refusal = UNSCOPED_GRANT
    declared_rank = _RISK_RANK.get((risk or "").strip().casefold(), 3)

    for grant in grants:
        if not grant.is_scoped:
            continue
        if grant.capability_ref != capability_ref:
            refusal = OUT_OF_SCOPE_CAPABILITY
            continue
        if grant.environment != environment:
            refusal = OUT_OF_SCOPE_ENVIRONMENT
            continue
        if grant.max_risk is not None:
            ceiling = _RISK_RANK.get(grant.max_risk.strip().casefold())
            # An unrecognised ceiling does not widen the grant. A ceiling
            # nobody can rank is a ceiling nobody agreed to.
            if ceiling is None or declared_rank > ceiling:
                refusal = OUT_OF_SCOPE_RISK
                continue
        return ScopedAuthority(
            True, SCOPED_GRANT_MATCHED, action,
            matched_grant=(f"{grant.action}:{grant.resource}:"
                           f"capability={grant.capability_ref},"
                           f"environment={grant.environment}"
                           + (f",max_risk={grant.max_risk}"
                              if grant.max_risk else "")),
            principal_id=principal_id, tenant_id=tenant_id)

    return ScopedAuthority(False, refusal, action,
                           principal_id=principal_id, tenant_id=tenant_id)
