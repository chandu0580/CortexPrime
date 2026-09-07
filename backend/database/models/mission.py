"""
ORM model: missions

The mapping for a table that has existed since migration ``0001`` and that no
model has ever declared. Two live models carry foreign keys to it --
``reflection_history.mission_id`` and ``runtime_analytics.mission_id`` -- so
without this mapping ``Base.metadata`` was not closed under its own foreign
keys and ``sorted_tables`` raised ``NoReferencedTableError``. That broke
``create_all`` and, more importantly, ``alembic check`` and
``alembic revision --autogenerate``.

This file adds a mapping and nothing else. It creates no table, no migration,
no repository, no route and no authority.

Source of truth
---------------
**Migration ``0001_initial_schema.py`` lines 31-49, copied column for column.**

Deliberately NOT copied from ``infra/postgres/init.sql``, which defines a
*different* ``missions`` (``TEXT`` status, nullable timestamps,
``uuid_generate_v4()``, ``missions_status_check``, a ``DESC`` index) and which
Phase 10.18 unmounted precisely because it was a competing authority (ADR-109,
ADR-110).

What this is NOT
----------------
This is not ``missions_bc``. That is a different table, created by migration
``0007``, mapped by ``MissionModel`` in ``repositories/missions.py``, and used
by ``backend/mission/service.py``. ``mission_steps`` and ``executions``
reference *it*, not this.

It is also not the in-memory mission in ``backend/contexts/mission``, which the
mission runtime routes use and which touches no SQL at all.

Nothing reads or writes this table. Its only role today is to be the referent
of two foreign keys, which is exactly why the mapping was missing and why
adding it changes no runtime behaviour.

A name collision, deliberately left in place
--------------------------------------------
``backend/services/enterprise_executive_runtime.py:90`` defines its own
``MissionRecord`` -- an unrelated frozen dataclass held in an in-memory dict. It
does not import this one and this one does not import it; they never appear in
the same module. The name here follows the sibling convention
(``ReflectionHistoryRecord``, ``RuntimeAnalyticsRecord``,
``EpisodicMemoryRecord``), so it is kept -- but a text search for
``MissionRecord`` will find both, and that is worth knowing before assuming a
hit is this class.

Why no mixins
-------------
``UUIDPrimaryKeyMixin`` and ``TimestampMixin`` would look natural here and are
used by every sibling model, but both add Python-side semantics that migration
``0001`` does not specify -- ``default=uuid.uuid4`` and ``onupdate=_utcnow``.
This model must represent ``0001``, not the house convention, so the columns are
declared explicitly.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, Optional

import sqlalchemy as sa
from sqlalchemy import CheckConstraint, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column

from backend.database.base import Base


class MissionRecord(Base):
    """One row of the ``missions`` table, exactly as migration ``0001`` defines it."""

    __tablename__ = "missions"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    title:     Mapped[str]           = mapped_column(Text, nullable=False)
    objective: Mapped[str]           = mapped_column(Text, nullable=False)
    status:    Mapped[str]           = mapped_column(String(32), nullable=False,
                                                     server_default="pending")
    priority:  Mapped[Optional[int]] = mapped_column(Integer, nullable=True,
                                                     server_default="5")
    result:    Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # The database column is named ``metadata``. The ATTRIBUTE cannot be:
    # SQLAlchemy raises "Attribute name 'metadata' is reserved when using the
    # Declarative API". ``reflection_history`` resolves this the same way, so
    # the column name is preserved exactly and only the Python attribute
    # differs.
    meta: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        "metadata", JSONB, nullable=True, server_default="{}")

    started_at:   Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True)
    created_at:   Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()"))
    updated_at:   Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()"))

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','active','completed','failed','cancelled')",
            name="ck_missions_status",
        ),
        Index("idx_missions_status", "status", "created_at"),
    )
