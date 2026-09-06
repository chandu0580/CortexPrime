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
    "APPROVE_RESOURCE",
    "APPROVE_REMEDIATION",
    "ApproverAuthority",
    "resolve_approver_authority",
]

#: The permission, in the vocabulary ``rbac.PERMISSIONS`` already uses.
APPROVE_ACTION = "approve"
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

    # The explicit grant. Deliberately NOT satisfied by any role wildcard: the
    # existing PERMISSIONS table gives `owner` "*" for read, write and admin,
    # and a permission reachable through one of those wildcards would be the
    # blanket approval authority this phase exists to prevent.
    granted = APPROVE_REMEDIATION in tuple(getattr(member, "permissions", ()) or ())
    if not granted:
        return ApproverAuthority(False, NOT_AN_APPROVER, principal_id, tenant_id,
                                 member.role)

    return ApproverAuthority(True, GRANTED, principal_id, tenant_id, member.role)
