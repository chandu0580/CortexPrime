"""Out-of-band grant provisioning for harnesses — Phase 10.8.

Why this exists
---------------
Before Phase 10.8 a harness provisioned authority by calling
``TenantManager.grant_permission``, which wrote a bare string into a gitignored
JSON file. That path no longer confers authority: ``resolve_scoped_authority``
reads ``cp_authority_grant``, where every row names who issued it.

So harnesses now provision through ``bootstrap_grant`` — the documented root of
trust. That is deliberately the *same* function a real operator would use to
seed the first issuer, not a test-only shortcut: if the bootstrap path were
weaker than the real one, the harness would be proving something nobody ships.

This module only translates. It parses the grant grammar the earlier phases
already speak and writes the equivalent durable row; it makes no authority
decision and grants nothing the grammar does not already say.
"""

from __future__ import annotations

from typing import Iterable, Optional

import sqlalchemy as sa


def parse_grant_string(text: str) -> Optional[dict]:
    """One grant string in, its authority-bearing fields out.

    Returns ``None`` for anything that does not parse. A grant that cannot be
    read is not a grant, which is the same rule ``parse_grants`` applies on the
    enforcement side.
    """
    parts = str(text).split(":", 2)
    if len(parts) < 2:
        return None
    action, resource = parts[0], parts[1]
    fields = {}
    if len(parts) == 3 and parts[2]:
        for pair in parts[2].split(","):
            key, _, value = pair.partition("=")
            if key.strip() and value.strip():
                fields[key.strip()] = value.strip()
    return {
        "authority_type": action,
        "resource": resource,
        "capability_ref": fields.get("capability", ""),
        "environment": fields.get("environment", ""),
        "max_risk": fields.get("max_risk"),
    }


def clear_grants(store, *, tenant_id: str, principal_id: str) -> int:
    """Delete this subject's grants outright.

    A *test fixture* reset, not a revocation: revoking would leave rows that
    ``live_grants_for`` correctly ignores but a later assertion about "how many
    grants exist" would still count. Production has no equivalent -- there is no
    route, and no function in ``backend.auth.grants``, that deletes a grant.
    """
    from backend.database.durable.tables import authority_grant_table as G

    with store.atomic() as work:
        result = work.execute(
            sa.delete(G).where(G.c.tenant_id == tenant_id,
                               G.c.subject_principal_id == principal_id))
    return int(getattr(result, "rowcount", 0) or 0)



def ensure_membership(store, *, tenant_id: str, principal_id: str,
                      role: str = "member", status: str = "active") -> str:
    """Give one subject a live durable membership of one tenant.

    Phase 10.9. Authority resolution and product access both now require an
    active membership row, so a harness persona needs one before any of the
    earlier phases' checks can even be attempted. This is the out-of-band
    provisioning path -- the same shape as ``bootstrap_grant``: a real operator
    seeding a tenant's first member does exactly this, because a tenant with no
    members has nobody who could admit one.
    """
    import uuid

    from backend.contexts.connectivity.infrastructure.sql_membership import (
        SqlMembershipRepository)

    repo = SqlMembershipRepository(store)
    existing = repo.find(tenant_id=tenant_id, subject_principal_id=principal_id)
    if existing is not None:
        if existing.status != status:
            repo.set_status(tenant_id=tenant_id,
                            membership_id=existing.membership_id,
                            status=status, updated_by="harness:provisioning")
        return existing.membership_id
    record = repo.admit(
        membership_id=f"mbr-{uuid.uuid4().hex[:16]}", tenant_id=tenant_id,
        subject_principal_id=principal_id, role=role,
        created_by="harness:provisioning", source="migrated", status=status)
    return record.membership_id


def provision(repository, store, *, tenant_id: str, principal_id: str,
              grants: Iterable[str], capability_version: str = "1",
              reason: str = "harness provisioning: out-of-band root of trust",
              clear: bool = True) -> int:
    """Give one subject exactly these grants, durably and attributably.

    Unscoped strings (the Phase 10.5 form, ``approve:remediation``) are written
    with empty capability and environment on purpose: the enforcement side must
    keep refusing them as ``grant_is_not_scoped``, and a harness that quietly
    declined to store them would be hiding the case it means to prove.
    """
    from backend.auth.grants import bootstrap_grant

    if clear:
        clear_grants(store, tenant_id=tenant_id, principal_id=principal_id)
    written = 0
    for text in grants or ():
        parsed = parse_grant_string(text)
        if parsed is None:
            continue
        bootstrap_grant(
            repository=repository, tenant_id=tenant_id,
            subject_principal_id=principal_id,
            authority_type=parsed["authority_type"],
            capability_ref=parsed["capability_ref"],
            capability_version=capability_version,
            environment=parsed["environment"],
            max_risk=parsed["max_risk"], reason=reason)
        written += 1
    return written
