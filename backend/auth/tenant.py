"""Read-only import of the legacy tenant JSON — Phase 10.11 (ADR-104).

**This is no longer a store. It is an importer.**

Phases 10.8, 10.9 and 10.10 moved authority, membership and the tenant boundary
into PostgreSQL (``cp_authority_grant``, ``cp_tenant_membership``,
``cp_tenant``). Those are authoritative; nothing here decides anything.

What was removed, and why
-------------------------
Every mutator -- ``create_tenant``, ``add_user``, ``update_user_role``,
``deactivate_tenant``, ``grant_permission``, ``revoke_permission`` -- and the
``_save`` that backed them. They were the only code in the repository that
**wrote** ``tenants.json`` or ``tenant_users.json``, and by Phase 10.11 every
one of them was either unreachable or a silent no-op: a write that appeared to
work and changed nothing the governed paths read.

Removing them is what lets both filenames leave the frozen
``GRANDFATHERED_STORES`` inventory, which may only shrink. The inventory
shrinks because the writes are gone -- not because the list was edited.
``FileStateRule`` flags a module that *writes* a state file; reading one is
explicitly fine, which is why the loader below stays.

What remains
------------
Reads, for exactly one purpose: ``migrate_json_tenants`` and
``migrate_json_memberships`` import these files **once** into the durable
stores. After that first import the files are inert, and the harness proves it
by mutating them, then removing them, and showing no governed answer moves.

If the files are absent the importer yields nothing, the migrations import
nothing, and the durable stores stay as they are. That is correct behaviour,
not a failure -- a fresh installation has no legacy data to import.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class Tenant:
    tenant_id: str
    name: str
    slug: str
    domain: Optional[str] = None
    plan: str = "free"
    is_active: bool = True
    settings: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class TenantUser:
    user_id: str
    tenant_id: str
    email: str
    role: str = "member"  # member, admin, owner
    is_active: bool = True
    permissions: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TenantManager:
    """Reads the legacy tenant JSON. **No mutator, and no ``_save``.**

    Every method here is a read. There is deliberately no way to create,
    modify or delete anything through this class: the durable stores own
    that, and a write here would produce a row no governed path consults.
    """

    def __init__(self, storage_path: str = "data/tenants"):
        from pathlib import Path
        self._tenants: Dict[str, Tenant] = {}
        self._tenant_users: Dict[str, List[TenantUser]] = {}
        # A reader creates nothing. The directory may be absent -- on a
        # fresh installation there is no legacy data to import, and
        # ``_load`` treats that as the empty import it is.
        self._storage_path = Path(storage_path)
        self._load()

    def _load(self):
        import json
        tenants_file = self._storage_path / "tenants.json"
        users_file = self._storage_path / "tenant_users.json"
        if tenants_file.exists():
            data = json.loads(tenants_file.read_text())
            for t in data:
                self._tenants[t["tenant_id"]] = Tenant(**t)
        if users_file.exists():
            data = json.loads(users_file.read_text())
            for tenant_id, users in data.items():
                self._tenant_users[tenant_id] = [TenantUser(**u) for u in users]

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        return self._tenants.get(tenant_id)

    def get_tenant_by_slug(self, slug: str) -> Optional[Tenant]:
        for t in self._tenants.values():
            if t.slug == slug:
                return t
        return None

    def list_tenants(self) -> List[Tenant]:
        return list(self._tenants.values())

    def get_users(self, tenant_id: str) -> List[TenantUser]:
        return self._tenant_users.get(tenant_id, [])

    def get_user_by_email(self, email: str) -> Optional[TenantUser]:
        for users in self._tenant_users.values():
            for u in users:
                if u.email == email:
                    return u
        return None

# Singleton
_tenant_manager: Optional[TenantManager] = None


def get_tenant_manager() -> TenantManager:
    global _tenant_manager
    if _tenant_manager is None:
        _tenant_manager = TenantManager()
    return _tenant_manager
