"""The durable tenant store — Phase 10.10 (ADR-103).

What this is
------------
Phases 10.8 and 10.9 made authority and membership durable, and left both
resting on a gitignored JSON file that ``require_tenant`` read on every request.
This is where "does this tenant exist, and is it live" now lives.

It supplies **storage and attribution**, and no judgement:

* whether a subject belongs to the tenant is still decided by
  ``cp_tenant_membership``;
* whether they may approve, execute or issue is still decided by
  ``cp_authority_grant``.

Neither is reimplemented here. This module reads rows and writes rows.

Why there is no digest
----------------------
Tenant state is *intentionally* mutable — activating and deactivating are
legitimate operations — so a hash over it would be recomputed by every
legitimate change and prove nothing. That is the same reasoning Phase 10.9
applied to membership, and the reason Phase 10.8's grant digest does work: a
grant's authority-bearing fields are immutable once issued.

Tenant state also stays **out of** the capability, approval and grant digests.
Those are historical bindings; folding mutable state into them would mean
deactivating a tenant silently invalidated every approval ever bound in it.

Why nothing is ever deleted
---------------------------
A tenant row that vanishes leaves every historical approval, grant and
membership pointing at a boundary nobody can resolve. Removal is a status
change.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

import sqlalchemy as sa

from backend.database.durable.session import DurableStore
from backend.database.durable.tables import tenant_table as T

__all__ = [
    "SqlTenantRepository",
    "TenantRecord",
    "TenantPersistenceError",
    "ACTIVE",
    "INACTIVE",
    "SCHEMA_VERSION",
]

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
ACTIVE = "active"
INACTIVE = "inactive"


class TenantPersistenceError(RuntimeError):
    """A tenant could not be persisted (a genuine store failure)."""


class TenantRecord:
    """One stored tenant. A read model that decides nothing."""

    __slots__ = ("tenant_id", "slug", "name", "status", "source",
                 "created_by", "created_at", "updated_by", "updated_at")

    def __init__(self, **fields: Any) -> None:
        for name in self.__slots__:
            setattr(self, name, fields.get(name))

    @property
    def is_active(self) -> bool:
        return self.status == ACTIVE

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "slug": self.slug,
            "name": self.name,
            "status": self.status,
            "source": self.source,
            "created_by": self.created_by,
            "created_at": (self.created_at.isoformat()
                           if self.created_at else None),
            "updated_by": self.updated_by,
            "updated_at": (self.updated_at.isoformat()
                           if self.updated_at else None),
        }


class SqlTenantRepository:
    """Rows in, rows out. Policy lives in ``backend.auth.tenants``."""

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise TenantPersistenceError(
                "the tenant repository requires a DurableStore")
        self._store = store

    # -- writes ------------------------------------------------------------

    def provision(self, *, tenant_id: str, slug: str, name: str,
                  created_by: str, source: str = "provisioned",
                  status: str = ACTIVE,
                  now: Optional[datetime] = None) -> TenantRecord:
        """Create one tenant boundary.

        ``created_by`` is a required keyword with no default and the column is
        ``NOT NULL``, so an unattributed tenant is a ``TypeError`` rather than a
        row nobody can explain — the same rule Phases 10.8 and 10.9 apply to a
        grant and a membership.

        This creates a boundary and **nothing else**: no membership, no grant,
        no approval, no execution right. A freshly provisioned tenant is one
        nobody can yet access, which is the correct starting state.
        """
        if not created_by or not str(created_by).strip():
            raise TenantPersistenceError("a tenant must name who created it")
        values = {
            "tenant_id": tenant_id, "slug": slug, "name": name,
            "status": status, "source": source, "created_by": created_by,
            "created_at": now or datetime.now(timezone.utc),
            "schema_version": SCHEMA_VERSION,
        }
        with self._store.atomic() as work:
            work.execute(sa.insert(T).values(**values))
        return TenantRecord(**values)

    def set_status(self, *, tenant_id: str, status: str, updated_by: str,
                   now: Optional[datetime] = None) -> bool:
        """Activate or deactivate. Conditional on the status actually changing.

        The ``status != status`` predicate makes a second concurrent
        deactivation return ``False`` instead of overwriting who did it first.
        """
        if status not in (ACTIVE, INACTIVE):
            raise TenantPersistenceError(
                f"a tenant status must be {ACTIVE} or {INACTIVE}")
        with self._store.atomic() as work:
            result = work.execute(
                sa.update(T).where(T.c.tenant_id == tenant_id,
                                   T.c.status != status)
                .values(status=status, updated_by=updated_by,
                        updated_at=now or datetime.now(timezone.utc)))
        return bool(getattr(result, "rowcount", 0))

    # -- reads -------------------------------------------------------------

    def get(self, *, tenant_id: str) -> Optional[TenantRecord]:
        """One tenant by its authority-bearing identity. Fails closed."""
        if not tenant_id:
            return None
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(T).where(T.c.tenant_id == tenant_id)
            ).mappings().fetchone()
        return self._record(row) if row else None

    def get_by_slug(self, *, slug: str) -> Optional[TenantRecord]:
        """Lookup by the display identifier.

        Present because provisioning and migration need it. It is **not** used
        by any authorization decision: those key on ``tenant_id``, which is
        what every membership, grant, approval and audit record stores.
        """
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(T).where(T.c.slug == slug)).mappings().fetchone()
        return self._record(row) if row else None

    def list_all(self, *, limit: int = 500) -> Sequence[TenantRecord]:
        """Every tenant. **Administrative only.**

        No product route exposes this: Phase 10.10 found that the V1 route
        which did handed the entire system's tenant list to any single tenant's
        admin, which is the map an attacker uses to pick the next target.
        """
        with self._store.atomic() as work:
            rows = work.execute(
                sa.select(T).order_by(T.c.created_at.desc()).limit(int(limit))
            ).mappings().fetchall()
        return tuple(self._record(row) for row in rows)

    def count_all(self) -> int:
        with self._store.atomic() as work:
            return int(work.execute(
                sa.select(sa.func.count()).select_from(T)).scalar() or 0)

    @staticmethod
    def _record(row) -> TenantRecord:
        return TenantRecord(**{n: row[n] for n in TenantRecord.__slots__})
