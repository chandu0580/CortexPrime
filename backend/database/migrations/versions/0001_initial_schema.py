"""Initial schema — pgvector + all CortexPrime memory tables.

Revision ID: 0001_initial_schema
Revises: (none)
Create Date: 2026-05-24
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic    import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

# revision identifiers
revision: str       = "0001_initial_schema"
down_revision: str | None = None
branch_labels: str | None = None
depends_on:    str | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Extensions
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # ------------------------------------------------------------------
    # missions  (referenced by reflection_history + runtime_analytics)
    # ------------------------------------------------------------------
    op.create_table(
        "missions",
        sa.Column("id",           sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title",        sa.Text,   nullable=False),
        sa.Column("objective",    sa.Text,   nullable=False),
        sa.Column("status",       sa.String(32),  nullable=False, server_default="pending"),
        sa.Column("priority",     sa.Integer,     nullable=True,  server_default="5"),
        sa.Column("result",       sa.Text,   nullable=True),
        sa.Column("metadata",     JSONB,     nullable=True,  server_default="{}"),
        sa.Column("started_at",   TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at",   TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at",   TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint(
            "status IN ('pending','active','completed','failed','cancelled')",
            name="ck_missions_status",
        ),
    )
    op.create_index("idx_missions_status", "missions", ["status", "created_at"])

    # ------------------------------------------------------------------
    # episodic_memory
    # ------------------------------------------------------------------
    op.create_table(
        "episodic_memory",
        sa.Column("id",         sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.String(255),  nullable=False),
        sa.Column("agent",      sa.String(128),  nullable=False),
        sa.Column("event_type", sa.String(64),   nullable=False),
        sa.Column("content",    sa.Text,         nullable=False),
        sa.Column("embedding",  sa.Text,         nullable=True),   # placeholder; real DDL via raw SQL below
        sa.Column("metadata",   JSONB,           nullable=True,  server_default="{}"),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    # Drop the TEXT placeholder and add the real vector column
    op.drop_column("episodic_memory", "embedding")
    op.execute("ALTER TABLE episodic_memory ADD COLUMN embedding vector(1536)")

    op.create_index("idx_ep_session_created", "episodic_memory", ["session_id", "created_at"])
    op.create_index("idx_ep_agent_created",   "episodic_memory", ["agent",      "created_at"])

    # IVFFlat approximate nearest-neighbour index
    op.execute("""
        CREATE INDEX idx_ep_embedding
        ON episodic_memory USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)

    # Full-text GIN index
    op.execute("""
        CREATE INDEX idx_ep_content_fts
        ON episodic_memory
        USING GIN (to_tsvector('english', content))
    """)

    # updated_at trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
        $$
    """)
    op.execute("""
        CREATE TRIGGER trg_episodic_updated_at
        BEFORE UPDATE ON episodic_memory
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    # ------------------------------------------------------------------
    # semantic_memory
    # ------------------------------------------------------------------
    op.create_table(
        "semantic_memory",
        sa.Column("id",         sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("concept",    sa.Text,        nullable=False),
        sa.Column("content",    sa.Text,        nullable=False),
        sa.Column("embedding",  sa.Text,        nullable=True),
        sa.Column("source",     sa.String(512), nullable=True),
        sa.Column("confidence", sa.Float,       nullable=False, server_default="1.0"),
        sa.Column("metadata",   JSONB,          nullable=True,  server_default="{}"),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.drop_column("semantic_memory", "embedding")
    op.execute("ALTER TABLE semantic_memory ADD COLUMN embedding vector(1536)")

    op.create_index("idx_sem_confidence", "semantic_memory", ["confidence"])
    op.execute("""
        CREATE INDEX idx_sem_concept_fts
        ON semantic_memory
        USING GIN (to_tsvector('english', concept || ' ' || content))
    """)
    op.execute("""
        CREATE INDEX idx_sem_embedding
        ON semantic_memory USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
    """)
    op.execute("""
        CREATE TRIGGER trg_semantic_updated_at
        BEFORE UPDATE ON semantic_memory
        FOR EACH ROW EXECUTE FUNCTION set_updated_at()
    """)

    # ------------------------------------------------------------------
    # reflection_history
    # ------------------------------------------------------------------
    op.create_table(
        "reflection_history",
        sa.Column("id",         sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("mission_id", sa.UUID(as_uuid=True), sa.ForeignKey("missions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agent",      sa.String(128), nullable=False),
        sa.Column("reflection", sa.Text,        nullable=False),
        sa.Column("embedding",  sa.Text,        nullable=True),
        sa.Column("score",      sa.Float,       nullable=True),
        sa.Column("metadata",   JSONB,          nullable=True,  server_default="{}"),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.drop_column("reflection_history", "embedding")
    op.execute("ALTER TABLE reflection_history ADD COLUMN embedding vector(1536)")

    op.create_index("idx_refl_agent_created",   "reflection_history", ["agent",      "created_at"])
    op.create_index("idx_refl_mission_created", "reflection_history", ["mission_id", "created_at"])
    op.execute("""
        CREATE INDEX idx_refl_embedding
        ON reflection_history USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 50)
    """)

    # ------------------------------------------------------------------
    # runtime_analytics
    # ------------------------------------------------------------------
    op.create_table(
        "runtime_analytics",
        sa.Column("id",            sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("mission_id",    sa.UUID(as_uuid=True), sa.ForeignKey("missions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("session_id",    sa.String(255),  nullable=True),
        sa.Column("agent",         sa.String(128),  nullable=False),
        sa.Column("event_type",    sa.String(64),   nullable=False),
        sa.Column("model",         sa.String(128),  nullable=True),
        sa.Column("prompt_tokens", sa.Integer,      nullable=True),
        sa.Column("output_tokens", sa.Integer,      nullable=True),
        sa.Column("latency_ms",    sa.Float,        nullable=True),
        sa.Column("cost_usd",      sa.Float,        nullable=True),
        sa.Column("success",       sa.Boolean,      nullable=False, server_default="true"),
        sa.Column("error_message", sa.Text,         nullable=True),
        sa.Column("payload",       JSONB,           nullable=True,  server_default="{}"),
        sa.Column("created_at",    TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at",    TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_analytics_agent_created",   "runtime_analytics", ["agent",      "created_at"])
    op.create_index("idx_analytics_mission_created", "runtime_analytics", ["mission_id", "created_at"])
    op.create_index("idx_analytics_event_type",      "runtime_analytics", ["event_type"])
    op.create_index("idx_analytics_session",         "runtime_analytics", ["session_id"])

    # ------------------------------------------------------------------
    # embedding_cache
    # ------------------------------------------------------------------
    op.create_table(
        "embedding_cache",
        sa.Column("id",           sa.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("text_hash",    sa.String(64),  nullable=False, unique=True),
        sa.Column("model",        sa.String(128), nullable=False),
        sa.Column("text_preview", sa.Text,        nullable=False),
        sa.Column("embedding",    sa.Text,        nullable=False),
        sa.Column("created_at",   TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at",   TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.drop_column("embedding_cache", "embedding")
    # No default needed: this column is added immediately after the table
    # itself is created, so there are no existing rows for NOT NULL to
    # validate against. (A prior version tried to give it a dummy default
    # of '[0]'::vector(1536), which pgvector rejects outright — that
    # literal is a 1-dimensional vector, not a 1536-dimension one.)
    op.execute("ALTER TABLE embedding_cache ADD COLUMN embedding vector(1536) NOT NULL")

    op.create_index("idx_emb_cache_hash", "embedding_cache", ["text_hash"], unique=True)


def downgrade() -> None:
    op.drop_table("embedding_cache")
    op.drop_table("runtime_analytics")
    op.drop_table("reflection_history")
    op.drop_table("semantic_memory")
    op.drop_table("episodic_memory")
    # reflection_log / cognition_events predate this migration chain (bootstrapped
    # by the legacy init.sql, not created by any upgrade() here) but 0003's
    # downgrade() recreates reflection_log with an FK to missions, and
    # cognition_events is created outside Alembic entirely via
    # Base.metadata.create_all() — both must be gone before missions can drop
    # when downgrading all the way to base.
    op.execute("DROP TABLE IF EXISTS reflection_log CASCADE")
    op.execute("DROP TABLE IF EXISTS cognition_events CASCADE")
    op.drop_table("missions")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at() CASCADE")
