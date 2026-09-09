"""Mission replay events: migration coverage for the replay store's durable layer.

Revision ID: 0025_mission_replay_events
Revises: 0024_approval_store
Create Date: 2026-09-08

Phase 10.26 (ADR-118). ``backend/services/mission_replay_store.py`` is a
dual-layer store: Redis holds a 72-hour hot window, PostgreSQL is documented as
the "cold / permanent" layer that answers once the window has expired. The
model ``backend/database/models/mission_replay.py`` has existed since the GA
commit, but no migration ever created its table and the model was imported only
inside the store's functions -- so Alembic never saw it, ``event_bus.publish``
wrote to it on every event, and the failing insert was swallowed at DEBUG.

The schema below is the model's own contract, column for column, reviewed
against ``CreateTable(MissionReplayEvent.__table__)`` -- not autogenerate
output. ``sequence``, ``status`` and ``message`` carry Python-side defaults in
the model and therefore no server default here; ``id``, ``created_at`` and
``updated_at`` carry the mixins' server defaults. The two single-column indexes
are the model's ``index=True`` markers under the names SQLAlchemy assigns them;
the three composite ``idx_replay_*`` indexes are declared explicitly. No
uniqueness is added: the model declares none, and ``sequence`` is assigned by a
Redis counter that can restart (documented in ADR-118) -- inventing a
constraint here would turn that into write failures.

Development databases built by ``create_all`` already have this table, so the
table and every index are guarded by existence checks, as in 0023 and 0024.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP, UUID

revision: str = "0025_mission_replay_events"
down_revision: str | None = "0024_approval_store"
branch_labels = None
depends_on = None

_TS = TIMESTAMP(timezone=True)
_DOC = JSONB().with_variant(sa.JSON(), "sqlite")

_TABLE = "mission_replay_events"
_INDEXES = (
    ("ix_mission_replay_events_execution_id", ["execution_id"]),
    ("ix_mission_replay_events_agent", ["agent"]),
    ("idx_replay_exec_seq", ["execution_id", "sequence"]),
    ("idx_replay_exec_type", ["execution_id", "event_type"]),
    ("idx_replay_exec_agent", ["execution_id", "agent"]),
)


def _table_present() -> bool:
    return _TABLE in sa.inspect(op.get_bind()).get_table_names()


def _index_present(name: str) -> bool:
    return any(ix["name"] == name for ix in sa.inspect(op.get_bind()).get_indexes(_TABLE))


def upgrade() -> None:
    if not _table_present():
        op.create_table(
            _TABLE,
            sa.Column("id", UUID(as_uuid=True), primary_key=True,
                      server_default=sa.text("gen_random_uuid()")),
            # Grouping key: every event of one mission run shares it.
            sa.Column("execution_id", sa.String(255), nullable=False),
            # Store-assigned, monotonically increasing per execution; playback
            # orders by it.
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(64), nullable=False),
            sa.Column("agent", sa.String(128), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            # Wall-clock ISO timestamp when the agent emitted the event;
            # created_at below is when the row was written.
            sa.Column("event_ts", sa.String(64), nullable=True),
            sa.Column("latency_ms", sa.Float(), nullable=True),
            sa.Column("payload", _DOC, nullable=True),
            sa.Column("created_at", _TS, nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", _TS, nullable=False, server_default=sa.text("NOW()")),
        )
    for name, columns in _INDEXES:
        if not _index_present(name):
            op.create_index(name, _TABLE, columns)


def downgrade() -> None:
    if not _table_present():
        return
    for name, _columns in _INDEXES:
        if _index_present(name):
            op.drop_index(name, table_name=_TABLE)
    op.drop_table(_TABLE)
