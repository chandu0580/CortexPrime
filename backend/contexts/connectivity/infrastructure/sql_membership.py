"""The durable tenant-membership store — Phase 10.9 (ADR-102).

What this is
------------
Phase 10.8 made authority durable and attributed, and left it pointing at
subjects defined by a gitignored JSON file. This is where "who belongs to this
tenant" now lives.

It supplies **storage and attribution**, and no judgement:

* whether a subject may approve, execute or issue is still decided by
  ``resolve_scoped_authority`` against Phase 10.8's grants;
* whether somebody may admit or deactivate a member is decided by
  ``backend.auth.membership``.

Neither is reimplemented here. This module reads rows and writes rows.

Why there is no digest
----------------------
Membership is *intentionally* mutable: activating, deactivating and changing a
role are legitimate operations. A hash over those fields would be recomputed by
every legitimate change and would prove nothing — which is the difference
between this table and ``cp_authority_grant``, whose authority-bearing fields
are immutable once issued. Integrity here comes from the audit trail: who
changed what, when.

Why nothing is ever deleted
---------------------------
A membership row that vanishes leaves every historical grant and approval
pointing at an identity nobody can resolve. Removal is a status change.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Sequence

import sqlalchemy as sa

from backend.database.durable.session import DurableStore
from backend.database.durable.tables import tenant_membership_table as T

__all__ = [
    "SqlMembershipRepository",
    "MembershipRecord",
    "MembershipPersistenceError",
    "ACTIVE",
    "INACTIVE",
    "SCHEMA_VERSION",
]

log = logging.getLogger(__name__)

SCHEMA_VERSION = 1
ACTIVE = "active"
INACTIVE = "inactive"


class MembershipPersistenceError(RuntimeError):
    """A membership could not be persisted (a genuine store failure)."""


class MembershipRecord:
    """One stored membership. A read model that decides nothing."""

    __slots__ = ("membership_id", "tenant_id", "subject_principal_id",
                 "status", "role", "source", "created_by", "created_at",
                 "updated_by", "updated_at")

    def __init__(self, **fields: Any) -> None:
        for name in self.__slots__:
            setattr(self, name, fields.get(name))

    @property
    def is_active(self) -> bool:
        return self.status == ACTIVE

    def to_dict(self) -> dict:
        return {
            "membership_id": self.membership_id,
            "tenant_id": self.tenant_id,
            "subject_principal_id": self.subject_principal_id,
            "status": self.status,
            "role": self.role,
            "source": self.source,
            "created_by": self.created_by,
            "created_at": (self.created_at.isoformat()
                           if self.created_at else None),
            "updated_by": self.updated_by,
            "updated_at": (self.updated_at.isoformat()
                           if self.updated_at else None),
        }


class SqlMembershipRepository:
    """Rows in, rows out. Policy lives in ``backend.auth.membership``."""

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise MembershipPersistenceError(
                "the membership repository requires a DurableStore")
        self._store = store

    # -- writes ------------------------------------------------------------

    def admit(self, *, membership_id: str, tenant_id: str,
              subject_principal_id: str, role: str, created_by: str,
              source: str = "admitted", status: str = ACTIVE,
              now: Optional[datetime] = None) -> MembershipRecord:
        """Create one membership.

        ``created_by`` is a required keyword with no default and the column is
        ``NOT NULL``, so an unattributed membership is a ``TypeError`` rather
        than a row nobody can explain — the same rule Phase 10.8 applies to a
        grant.
        """
        if not created_by or not str(created_by).strip():
            raise MembershipPersistenceError(
                "a membership must name who created it")
        values = {
            "membership_id": membership_id, "tenant_id": tenant_id,
            "subject_principal_id": subject_principal_id,
            "status": status, "role": role, "source": source,
            "created_by": created_by,
            "created_at": now or datetime.now(timezone.utc),
            "schema_version": SCHEMA_VERSION,
        }
        with self._store.atomic() as work:
            work.execute(sa.insert(T).values(**values))
        return MembershipRecord(**values)

    def set_status(self, *, tenant_id: str, membership_id: str, status: str,
                   updated_by: str, now: Optional[datetime] = None) -> bool:
        """Activate or deactivate. Conditional on the status actually changing.

        The ``status != status`` predicate is what makes a second concurrent
        deactivation return ``False`` instead of overwriting who did it first.
        Both callers are right about the outcome; only one is the one that
        happened.
        """
        if status not in (ACTIVE, INACTIVE):
            raise MembershipPersistenceError(
                f"a membership status must be {ACTIVE} or {INACTIVE}")
        with self._store.atomic() as work:
            result = work.execute(
                sa.update(T).where(
                    T.c.membership_id == membership_id,
                    T.c.tenant_id == tenant_id,
                    T.c.status != status,
                ).values(status=status, updated_by=updated_by,
                         updated_at=now or datetime.now(timezone.utc)))
        return bool(getattr(result, "rowcount", 0))

    def set_role(self, *, tenant_id: str, membership_id: str, role: str,
                 updated_by: str, now: Optional[datetime] = None) -> bool:
        """Change the informational role. Confers nothing, by construction."""
        with self._store.atomic() as work:
            result = work.execute(
                sa.update(T).where(
                    T.c.membership_id == membership_id,
                    T.c.tenant_id == tenant_id,
                ).values(role=role, updated_by=updated_by,
                         updated_at=now or datetime.now(timezone.utc)))
        return bool(getattr(result, "rowcount", 0))

    # -- reads -------------------------------------------------------------

    def find(self, *, tenant_id: str,
             subject_principal_id: str) -> Optional[MembershipRecord]:
        """This subject's membership of THIS tenant, active or not.

        Tenant-scoped by predicate, so a membership of another tenant is
        invisible here rather than returned and filtered by a caller who might
        forget to.
        """
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(T).where(
                    T.c.tenant_id == tenant_id,
                    T.c.subject_principal_id == subject_principal_id)
            ).mappings().fetchone()
        return self._record(row) if row else None

    def find_any(self, *, subject_principal_id: str):
        """Any membership this subject holds, in any tenant.

        Used for ONE purpose: telling "you are not a member" apart from "you
        belong to a different tenant", which are different things to tell
        somebody. It is never an authorization input -- every decision uses the
        tenant-scoped ``find``.
        """
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(T).where(
                    T.c.subject_principal_id == subject_principal_id)
                .limit(1)).mappings().fetchone()
        return self._record(row) if row else None

    def get(self, *, tenant_id: str,
            membership_id: str) -> Optional[MembershipRecord]:
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(T).where(T.c.membership_id == membership_id,
                                   T.c.tenant_id == tenant_id)
            ).mappings().fetchone()
        return self._record(row) if row else None

    def list_for_tenant(self, *, tenant_id: str,
                        limit: int = 500) -> Sequence[MembershipRecord]:
        """Every membership in ONE tenant, inactive ones included.

        Inactive rows are returned deliberately: a list that hides them cannot
        answer "who used to belong here", which is what an incident review asks
        when it finds a historical approval by somebody who is gone.
        """
        with self._store.atomic() as work:
            rows = work.execute(
                sa.select(T).where(T.c.tenant_id == tenant_id)
                .order_by(T.c.created_at.desc()).limit(int(limit))
            ).mappings().fetchall()
        return tuple(self._record(row) for row in rows)

    def count_all(self) -> int:
        with self._store.atomic() as work:
            return int(work.execute(
                sa.select(sa.func.count()).select_from(T)).scalar() or 0)

    @staticmethod
    def _record(row) -> MembershipRecord:
        return MembershipRecord(**{n: row[n] for n in MembershipRecord.__slots__})
