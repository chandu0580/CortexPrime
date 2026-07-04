"""Consolidate reflection_log into reflection_history.

Audit finding: two tables existed for the same domain.
- reflection_log       (asyncpg path — ReflectionStore writes here)
- reflection_history   (SQLAlchemy ORM path — ReflectionRepository reads here)

This migration makes reflection_history the single source of truth:
  1. Copies all existing rows from reflection_log → reflection_history
     (IF reflection_log exists — safe for fresh databases).
  2. Drops reflection_log.

After this migration:
  - ReflectionStore writes to reflection_history (code updated separately)
  - ReflectionRepository reads from reflection_history (already correct)
  - No split write/read path.

Revision ID: 0003_consolidate_reflection_tables
Revises    : 0002_add_audit_logs
Create Date: 2026-06-06
"""
from __future__ import annotations

from alembic import op

revision: str       = "0003_consolidate_reflection_tables"
down_revision: str | None = "0002_add_audit_logs"
branch_labels: str | None = None
depends_on:    str | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Copy rows from reflection_log into reflection_history.
    #    Wrapped in a DO block so it silently skips on fresh databases
    #    that never had reflection_log (e.g. after init.sql is cleaned up).
    #    ON CONFLICT (id) DO NOTHING makes it idempotent if run twice.
    # ------------------------------------------------------------------
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name   = 'reflection_log'
            ) THEN
                INSERT INTO reflection_history
                    (id, mission_id, agent, reflection, embedding,
                     score, metadata, created_at, updated_at)
                SELECT
                    id,
                    mission_id,
                    agent,
                    reflection,
                    embedding,
                    score,
                    COALESCE(metadata, '{}'::jsonb),
                    created_at,
                    COALESCE(updated_at, created_at, NOW())
                FROM reflection_log
                ON CONFLICT (id) DO NOTHING;

                -- 2. Drop reflection_log (and its indexes/triggers) once safe
                DROP TABLE reflection_log CASCADE;
            END IF;
        END;
        $$
    """)


def downgrade() -> None:
    # Recreate reflection_log and copy data back from reflection_history.
    # This restores the split-table state for rollback safety.
    op.execute("""
        CREATE TABLE IF NOT EXISTS reflection_log (
            id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
            mission_id  UUID        REFERENCES missions (id) ON DELETE SET NULL,
            agent       TEXT        NOT NULL,
            reflection  TEXT        NOT NULL,
            embedding   vector(1536),
            score       FLOAT,
            metadata    JSONB       DEFAULT '{}',
            created_at  TIMESTAMPTZ DEFAULT NOW(),
            updated_at  TIMESTAMPTZ DEFAULT NOW()
        )
    """)

    op.execute("""
        INSERT INTO reflection_log
            (id, mission_id, agent, reflection, embedding,
             score, metadata, created_at, updated_at)
        SELECT
            id, mission_id, agent, reflection, embedding,
            score, metadata, created_at, updated_at
        FROM reflection_history
        ON CONFLICT (id) DO NOTHING
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_reflection_mission
            ON reflection_log (mission_id)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_refl_agent_created
            ON reflection_log (agent, created_at DESC)
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_reflection_embedding
            ON reflection_log USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 50)
    """)
