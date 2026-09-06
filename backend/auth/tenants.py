"""Governed tenant records — Phase 10.10 (ADR-103).

The gap this closes
-------------------
Phase 10.8 made authority durable and attributed. Phase 10.9 made membership
durable and attributed. Both still rested on ``data/tenants/tenants.json``:
``require_tenant`` read that file on every request and refused when
``is_active`` was false, so an edit to a gitignored file disabled governance for
an entire tenant.

A tenant is a boundary, not a permission
----------------------------------------
A tenant row says exactly one thing: **an authoritative organizational boundary
exists.**

It does not say anybody belongs to it — that is ``cp_tenant_membership``
(Phase 10.9). It does not say anybody may approve, execute or issue — those are
the explicit scoped grants of Phase 10.8. Provisioning a tenant produces a
boundary **nobody can yet access**, which is the correct starting state and is
proven rather than asserted.

What it *is* load-bearing for is the other direction: an inactive tenant makes
membership, approval, execution, issuance and revocation all fail closed.

Who may administer it
---------------------
Nobody, through the product. Deliberately.

The existing authority grammar is capability + environment scoped, and a tenant
is neither. There is no way to express "may create a tenant" without inventing
a new authority action, which Part M of this phase forbids — and Phase 10.8
already established that no role confers authority, so the V1 ``role=admin``
claim is not an answer either.

So tenant provisioning, activation and deactivation are **out-of-band**, via
``bootstrap_tenant`` and ``set_tenant_status`` — the same shape as
``bootstrap_grant`` (10.8) and out-of-band membership seeding (10.9). No system
creates its own root boundary, and pretending otherwise would mean building the
authority model this phase is told not to build.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from backend.contexts.connectivity.infrastructure.sql_tenant import (
    ACTIVE, INACTIVE,
)

__all__ = [
    "TenantOutcome",
    "resolve_tenant",
    "bootstrap_tenant",
    "set_tenant_status",
    "migrate_json_tenants",
    "ACTIVE",
    "INACTIVE",
    "NO_SUCH_TENANT",
    "TENANT_INACTIVE",
    "TENANT_STORE_UNAVAILABLE",
]

log = logging.getLogger(__name__)

NO_SUCH_TENANT = "no_such_tenant"
TENANT_INACTIVE = "tenant_inactive"
TENANT_STORE_UNAVAILABLE = "tenant_store_unavailable"
TENANT_ACTIVE = "tenant_active"
ALREADY_IN_STATE = "tenant_already_in_that_state"
STATUS_CHANGED = "tenant_status_changed"


@dataclass(frozen=True)
class TenantOutcome:
    """What one tenant operation did. Facts, never a permission."""

    accepted: bool
    reason: str
    tenant_id: Optional[str] = None
    previous_state: Optional[str] = None
    new_state: Optional[str] = None

    @property
    def refused(self) -> bool:
        return not self.accepted


def resolve_tenant(*, tenant_id: str, tenants: Any) -> tuple:
    """(tenant, reason) for one tenant id. Fail closed.

    Three distinct answers, kept distinct: the store cannot be read, the tenant
    does not exist, or the tenant exists and is switched off. Collapsing them
    would leave an operator unable to tell a misconfiguration from a deliberate
    deactivation.

    A missing store returns ``tenant_store_unavailable`` rather than "no such
    tenant", because those send somebody to two very different places.
    """
    if tenants is None:
        return None, TENANT_STORE_UNAVAILABLE
    if not tenant_id:
        return None, NO_SUCH_TENANT
    try:
        record = tenants.get(tenant_id=tenant_id)
    except Exception:  # noqa: BLE001 - an unreadable store authorizes nothing
        log.warning("tenant store unavailable", exc_info=True)
        return None, TENANT_STORE_UNAVAILABLE
    if record is None:
        return None, NO_SUCH_TENANT
    if not record.is_active:
        return None, TENANT_INACTIVE
    return record, TENANT_ACTIVE


def bootstrap_tenant(*, repository: Any, slug: str, name: str,
                     tenant_id: Optional[str] = None,
                     status: str = ACTIVE, source: str = "provisioned",
                     created_by: str = "bootstrap") -> Any:
    """Provision one tenant boundary out of band. **The documented root.**

    No system creates its own root boundary, so this exists. What makes it a
    root of trust rather than a backdoor:

    * it is not reachable from any HTTP route — no product route provisions a
      tenant, and the harness asserts that;
    * it is attributed, to ``bootstrap`` by default, so an auditor can tell a
      provisioned tenant from a migrated one at a glance;
    * it creates a boundary and **nothing else** — no membership, no grant, no
      approval, no execution right.

    Anything that can call this can already write to the database.
    """
    return repository.provision(
        tenant_id=tenant_id or f"tenant-{uuid.uuid4().hex[:12]}",
        slug=slug, name=name, created_by=created_by, source=source,
        status=status)


def set_tenant_status(*, repository: Any, tenant_id: str, status: str,
                      actor: str = "bootstrap", audit: Any = None,
                      audit_writer: Any = None,
                      now: Any = None) -> TenantOutcome:
    """Activate or deactivate one tenant. Out-of-band, and audited.

    Deactivation is the operation that matters: when it lands, membership
    resolution, approval, execution, grant issuance and grant revocation all
    fail closed on their next check, because every one of them resolves tenant
    state live rather than trusting a token claim.

    It does **not** delete anything. Approvals, grants, memberships and audit
    records all survive, because an inactive tenant still has a history
    somebody will need to read.
    """
    if repository is None:
        return TenantOutcome(False, TENANT_STORE_UNAVAILABLE)
    record = repository.get(tenant_id=tenant_id)
    if record is None:
        return TenantOutcome(False, NO_SUCH_TENANT, tenant_id=tenant_id)

    previous = record.status
    if not repository.set_status(tenant_id=tenant_id, status=status,
                                 updated_by=actor, now=now):
        return TenantOutcome(False, ALREADY_IN_STATE, tenant_id=tenant_id,
                             previous_state=previous, new_state=previous)

    _audit(audit, audit_writer,
           "tenant_activated" if status == ACTIVE else "tenant_deactivated",
           record=record, actor=actor, previous=previous, new=status)
    log.info("tenant %s: %s -> %s (by %s)", tenant_id, previous, status, actor)
    return TenantOutcome(True, STATUS_CHANGED, tenant_id=tenant_id,
                         previous_state=previous, new_state=status)


def migrate_json_tenants(*, repository: Any, manager: Any,
                         actor: str = "migration:phase-10.10") -> dict:
    """Import the JSON tenant file into the durable store. **Once, read-only.**

    Deterministic: the same file produces the same rows, and a tenant that
    already exists is skipped rather than duplicated, so running it twice is
    safe.

    It preserves ``tenant_id``, ``slug`` and active state — and creates **no**
    membership, grant, approval or execution right. A migration that handed out
    access while moving the boundary would be the quietest possible privilege
    escalation, so the harness measures that as a before/after count rather
    than trusting this docstring.

    Afterwards the JSON file is bootstrap input only. Nothing reads it to decide
    anything, which the harness proves by editing it and showing the answers do
    not move.
    """
    imported = skipped = 0
    for tenant in manager.list_tenants():
        if repository.get(tenant_id=tenant.tenant_id) is not None:
            skipped += 1
            continue
        slug = getattr(tenant, "slug", None) or tenant.tenant_id
        if repository.get_by_slug(slug=slug) is not None:
            # Two JSON tenants sharing a slug: the column is UNIQUE, so the
            # second would fail the insert. Skipping is the honest outcome and
            # it is counted, not hidden.
            log.warning("tenant slug %r already present; skipping %s",
                        slug, tenant.tenant_id)
            skipped += 1
            continue
        repository.provision(
            tenant_id=tenant.tenant_id, slug=slug,
            name=getattr(tenant, "name", None) or slug,
            created_by=actor, source="migrated",
            status=ACTIVE if getattr(tenant, "is_active", True) else INACTIVE)
        imported += 1
    log.info("tenant migration: %d imported, %d already present",
             imported, skipped)
    return {"imported": imported, "skipped": skipped}


def _audit(audit: Any, writer: Any, event: str, *, record: Any, actor: str,
           previous: Optional[str], new: Optional[str]) -> None:
    """Record a tenant mutation on the existing hash-chained ledger.

    ``IDENTITY_EVENT`` already means "authentication, authorization, or
    credential lifecycle" and is ``is_security_relevant``, so it can never be
    sampled away. No new event kind is invented for this phase — the existing
    grammar represents a tenant state change without stretching.

    Carries actor, tenant, previous state and new state. Carries no password,
    token, credential or DSN: there is no field on a tenant that could hold one.
    """
    if audit is None:
        return
    try:
        from backend.auth.grants import _append
        from backend.contracts.audit import AuditEventKind
        from backend.contracts.tenant import TenantRef, TenantScope

        payload = dict(record.to_dict())
        payload.update({"event": event, "actor": actor,
                        "previous_state": previous, "new_state": new})
        _append(audit, writer, AuditEventKind.IDENTITY_EVENT,
                TenantScope(tenant=TenantRef(tenant_id=record.tenant_id)),
                subject_reference=record.tenant_id, detail=payload)
    except Exception:  # noqa: BLE001
        # A failed audit write must never look like a failed mutation, and must
        # never be silent. Phase 10.9 found that the writer lease lapses when a
        # process is quiet, and found it only because this log is loud.
        log.error("tenant %s was not audited (tenant=%s)", event,
                  getattr(record, "tenant_id", None), exc_info=True)
