"""Governed tenant membership — Phase 10.9 (ADR-102).

The gap this closes
-------------------
Phase 10.8 made authority durable, attributed, scoped and audited. Every one of
those grants points at a *subject*, and who that subject was — whether they
belonged to the tenant at all, whether they were still active — was defined by
``data/tenants/tenant_users.json``: gitignored, with no deactivate method, no
delete method, no audit, and one HTTP mutation path that took the tenant from
the URL.

Membership is a primitive, not an authority
-------------------------------------------
A membership says exactly one thing: **this subject belongs to this tenant.**

It does not say they may approve. It does not say they may execute. It does not
say they may issue grants. It does not confer autonomy. Those remain the
explicit scoped grants of Phase 10.8, and nothing in this module creates,
implies or upgrades one. The `role` field is carried and never read by a
decision — Phase 10.5 established that a tenant owner is not an approver, and
that stays true.

What membership *is* load-bearing for is the other direction: an inactive
membership must make every one of those authorities fail, because a grant must
never resurrect a membership that was taken away.

Who may administer it
---------------------
Holding at least one live ``issue`` grant in the tenant — a **presence** check
against Phase 10.8's store, not a scoped match against a capability, because
membership has no capability and forcing one in would be inventing a dimension.

This reuses the existing authority rather than adding a fourth action: an
issuer already holds the strictly more dangerous power of creating approval and
execution authority, and a member-admin who could not issue grants could still
create the principals grants attach to. No new authority, no new action, no new
escalation surface.

The limitation that follows is real and stated rather than hidden: **admission
and issuance are not separable today.**
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from backend.auth.grants import ISSUE_ACTION
from backend.contexts.connectivity.infrastructure.sql_membership import (
    ACTIVE, INACTIVE,
)

__all__ = [
    "MembershipOutcome",
    "admit_member",
    "set_member_status",
    "set_member_role",
    "resolve_membership",
    "may_administer_membership",
    "migrate_json_memberships",
    "ACTIVE",
    "INACTIVE",
]

log = logging.getLogger(__name__)

# Refusal reasons. Each names the thing that actually stopped the caller.
NO_MEMBERSHIP_AUTHORITY = "no_membership_authority"
SELF_ADMISSION = "self_admission_refused"
ALREADY_A_MEMBER = "already_a_member"
NO_SUCH_MEMBERSHIP = "no_such_membership"
ALREADY_IN_STATE = "membership_already_in_that_state"
STORE_UNAVAILABLE = "membership_store_unavailable"
ADMITTED = "member_admitted"
STATUS_CHANGED = "membership_status_changed"
ROLE_CHANGED = "membership_role_changed"

#: Roles a membership may carry. Informational: none of them is read by any
#: authorization decision, and adding one confers nothing.
KNOWN_ROLES = ("member", "admin", "owner")


@dataclass(frozen=True)
class MembershipOutcome:
    """What one membership operation did. Facts, never a permission."""

    accepted: bool
    reason: str
    membership_id: Optional[str] = None
    previous_state: Optional[str] = None
    new_state: Optional[str] = None

    @property
    def refused(self) -> bool:
        return not self.accepted


def may_administer_membership(*, principal_id: str, tenant_id: str,
                              grants: Any, memberships: Any = None) -> bool:
    """Does this caller hold ANY live issue-grant in this tenant?

    A presence check, deliberately. ``resolve_scoped_authority`` answers "may
    you issue THIS capability in THIS environment"; membership names neither,
    and passing an arbitrary capability in order to reuse that function would
    make the answer depend on a value with no meaning here.
    """
    from backend.auth.approver import durable_grants, durable_membership

    # An administrator must be a live member of the tenant they administer.
    # Checking the grant alone would let somebody whose membership was switched
    # off keep admitting people -- exactly the resurrection Part J forbids.
    member, _ = durable_membership(memberships, tenant_id=tenant_id,
                                   principal_id=principal_id)
    if member is None:
        return False
    strings = durable_grants(grants, tenant_id=tenant_id,
                             principal_id=principal_id, action=ISSUE_ACTION)
    return bool(strings)


def resolve_membership(*, principal_id: str, tenant_id: str,
                       memberships: Any) -> Any:
    """This subject's membership of this tenant, or ``None``. Fails closed.

    A store that cannot be read returns ``None``, which every caller treats as
    "not a member" — the honest answer to "we cannot tell whether you belong
    here" is no.
    """
    if memberships is None or not principal_id or not tenant_id:
        return None
    try:
        return memberships.find(tenant_id=tenant_id,
                                subject_principal_id=principal_id)
    except Exception:  # noqa: BLE001 - an unreadable store confers nothing
        log.warning("membership store unavailable", exc_info=True)
        return None


def admit_member(
    *, repository: Any, actor_principal_id: str, tenant_id: str,
    subject_principal_id: str, role: str = "member", grants: Any = None,
    audit: Any = None, audit_writer: Any = None, now: Any = None,
) -> MembershipOutcome:
    """Admit one subject to one tenant.

    ``tenant_id`` is the actor's own tenant, resolved from the verified
    session. There is no parameter through which a caller could name a
    different one, which is why the cross-tenant admission this phase found is
    not merely refused here — it is unrepresentable.
    """
    if repository is None:
        return MembershipOutcome(False, STORE_UNAVAILABLE)
    if not may_administer_membership(principal_id=actor_principal_id,
                                     tenant_id=tenant_id, grants=grants,
                                     memberships=repository):
        return MembershipOutcome(False, NO_MEMBERSHIP_AUTHORITY)

    # Self-admission. An administrator is already a member of the tenant they
    # administer, so this is always either redundant or an attempt to create a
    # principal out of nothing.
    if _same(actor_principal_id, subject_principal_id):
        return MembershipOutcome(False, SELF_ADMISSION)

    if repository.find(tenant_id=tenant_id,
                       subject_principal_id=subject_principal_id) is not None:
        # Idempotent refusal rather than a second row: two memberships for one
        # subject would mean a deactivation could miss one.
        return MembershipOutcome(False, ALREADY_A_MEMBER)

    record = repository.admit(
        membership_id=f"mbr-{uuid.uuid4().hex[:16]}", tenant_id=tenant_id,
        subject_principal_id=subject_principal_id,
        role=role if role in KNOWN_ROLES else "member",
        created_by=actor_principal_id, source="admitted", now=now)
    _audit(audit, "membership_created", tenant_id=tenant_id,
           actor=actor_principal_id, record=record, writer=audit_writer,
           previous=None, new=ACTIVE)
    return MembershipOutcome(True, ADMITTED, membership_id=record.membership_id,
                             previous_state=None, new_state=ACTIVE)


def set_member_status(
    *, repository: Any, actor_principal_id: str, tenant_id: str,
    membership_id: str, status: str, grants: Any = None, audit: Any = None,
    audit_writer: Any = None, now: Any = None,
) -> MembershipOutcome:
    """Activate or deactivate one membership.

    Deactivation is the operation that matters. When it lands, every authority
    that reads membership — approval, execution, grant issuance, grant
    revocation and product access — fails on its next check, because each of
    them resolves membership live rather than trusting a token claim.
    """
    if repository is None:
        return MembershipOutcome(False, STORE_UNAVAILABLE)
    if not may_administer_membership(principal_id=actor_principal_id,
                                     tenant_id=tenant_id, grants=grants,
                                     memberships=repository):
        return MembershipOutcome(False, NO_MEMBERSHIP_AUTHORITY)

    record = repository.get(tenant_id=tenant_id, membership_id=membership_id)
    if record is None:
        # Also the answer for a membership in another tenant: the read is
        # tenant-scoped, so "not here" is all this may disclose.
        return MembershipOutcome(False, NO_SUCH_MEMBERSHIP)

    previous = record.status
    if not repository.set_status(tenant_id=tenant_id,
                                 membership_id=membership_id, status=status,
                                 updated_by=actor_principal_id, now=now):
        return MembershipOutcome(False, ALREADY_IN_STATE,
                                 membership_id=membership_id,
                                 previous_state=previous, new_state=previous)

    _audit(audit,
           "membership_activated" if status == ACTIVE
           else "membership_deactivated",
           tenant_id=tenant_id, actor=actor_principal_id, record=record,
           previous=previous, new=status, writer=audit_writer)
    log.info("membership %s of %s in %s: %s -> %s (by %s)", membership_id,
             record.subject_principal_id, tenant_id, previous, status,
             actor_principal_id)
    return MembershipOutcome(True, STATUS_CHANGED, membership_id=membership_id,
                             previous_state=previous, new_state=status)


def set_member_role(
    *, repository: Any, actor_principal_id: str, tenant_id: str,
    membership_id: str, role: str, grants: Any = None, audit: Any = None,
    audit_writer: Any = None, now: Any = None,
) -> MembershipOutcome:
    """Change the informational role.

    This confers nothing and removes nothing. It is recorded because an auditor
    asking "who was described as the owner in March" deserves an answer, not
    because the answer changes what anybody may do.
    """
    if repository is None:
        return MembershipOutcome(False, STORE_UNAVAILABLE)
    if not may_administer_membership(principal_id=actor_principal_id,
                                     tenant_id=tenant_id, grants=grants,
                                     memberships=repository):
        return MembershipOutcome(False, NO_MEMBERSHIP_AUTHORITY)

    record = repository.get(tenant_id=tenant_id, membership_id=membership_id)
    if record is None:
        return MembershipOutcome(False, NO_SUCH_MEMBERSHIP)
    previous = record.role
    repository.set_role(tenant_id=tenant_id, membership_id=membership_id,
                        role=role if role in KNOWN_ROLES else "member",
                        updated_by=actor_principal_id, now=now)
    _audit(audit, "membership_role_changed", tenant_id=tenant_id,
           actor=actor_principal_id, record=record, writer=audit_writer,
           previous=previous, new=role)
    return MembershipOutcome(True, ROLE_CHANGED, membership_id=membership_id,
                             previous_state=previous, new_state=role)


def migrate_json_memberships(*, repository: Any, manager: Any,
                             actor: str = "migration:phase-10.9") -> dict:
    """Import the JSON tenant store into the durable one. **Once, and read-only.**

    Deterministic: the same file produces the same rows, and a membership that
    already exists is skipped rather than duplicated, so running it twice is
    safe.

    It preserves subject, tenant, active state and role — and creates **no**
    authority grant, no approval and no execution right. A migration that
    handed out authority while moving membership would be the quietest possible
    privilege escalation.

    Afterwards the JSON file is bootstrap input only. Nothing reads it to
    decide anything, which the harness proves by editing it and showing the
    answers do not move.
    """
    imported = skipped = 0
    for tenant in manager.list_tenants():
        for user in manager.get_users(tenant.tenant_id):
            subject = getattr(user, "email", None)
            if not subject:
                continue
            if repository.find(tenant_id=tenant.tenant_id,
                               subject_principal_id=subject) is not None:
                skipped += 1
                continue
            repository.admit(
                membership_id=f"mbr-{uuid.uuid4().hex[:16]}",
                tenant_id=tenant.tenant_id, subject_principal_id=subject,
                role=getattr(user, "role", "member") or "member",
                created_by=actor, source="migrated",
                status=ACTIVE if getattr(user, "is_active", True) else INACTIVE)
            imported += 1
    log.info("membership migration: %d imported, %d already present",
             imported, skipped)
    return {"imported": imported, "skipped": skipped}


def _same(left: Any, right: Any) -> bool:
    """Compare authoritative identities, never display names."""
    return (str(left or "").strip().casefold()
            == str(right or "").strip().casefold())


def _audit(audit: Any, event: str, *, tenant_id: str, actor: str, record: Any,
           previous: Optional[str], new: Optional[str],
           writer: Any = None) -> None:
    """Record a membership mutation on the existing hash-chained ledger.

    ``IDENTITY_EVENT`` already means "authentication, authorization, or
    credential lifecycle" and is ``is_security_relevant``, so it can never be
    sampled away. No new event kind is invented for this phase.

    The detail carries actor, tenant, subject, previous state and new state. It
    carries no password, token, secret, credential or DSN — there is no field
    on a membership that could hold one.
    """
    if audit is None:
        return
    try:
        from backend.contracts.audit import AuditEventKind
        from backend.contracts.tenant import TenantRef, TenantScope

        payload = dict(record.to_dict())
        payload.update({"event": event, "actor": actor,
                        "previous_state": previous, "new_state": new})
        from backend.auth.grants import _append

        _append(audit, writer, AuditEventKind.IDENTITY_EVENT,
                TenantScope(tenant=TenantRef(tenant_id=tenant_id)),
                subject_reference=record.membership_id, detail=payload)
    except Exception:  # noqa: BLE001
        # A failed audit write must never look like a failed mutation, and must
        # never be silent. Phase 10.8 lost every one of its audit events to a
        # swallowed ImportError and found out only because the log was loud.
        log.error("membership %s was not audited (tenant=%s membership=%s)",
                  event, tenant_id, getattr(record, "membership_id", None),
                  exc_info=True)
