-- ==============================================================
-- CORTEXPRIME — PostgreSQL Initialization
-- Database: cortexdb
-- Extension: pgvector
--
-- Runs automatically on first container start via
-- /docker-entrypoint-initdb.d/
-- ==============================================================

-- --------------------------------------------------------------
-- EXTENSIONS
-- --------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;   -- trigram search for semantic fuzzy match

-- --------------------------------------------------------------
-- EPISODIC MEMORY
-- Long-term storage of agent interactions and mission history
-- --------------------------------------------------------------

CREATE TABLE IF NOT EXISTS episodic_memory (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id      TEXT        NOT NULL,
    agent           TEXT        NOT NULL,
    event_type      TEXT        NOT NULL,
    content         TEXT        NOT NULL,
    embedding       vector(1536),              -- OpenAI text-embedding-3-small
    metadata        JSONB       DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_episodic_session
    ON episodic_memory (session_id);

CREATE INDEX IF NOT EXISTS idx_episodic_agent
    ON episodic_memory (agent);

CREATE INDEX IF NOT EXISTS idx_episodic_created
    ON episodic_memory (created_at DESC);

-- IVFFlat vector index for approximate nearest-neighbour search
-- Lists count: sqrt(total_rows) is a good starting point; tune after data load
CREATE INDEX IF NOT EXISTS idx_episodic_embedding
    ON episodic_memory USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- --------------------------------------------------------------
-- SEMANTIC MEMORY
-- Factual knowledge extracted and stored with vector embeddings
-- --------------------------------------------------------------

CREATE TABLE IF NOT EXISTS semantic_memory (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    concept         TEXT        NOT NULL,
    content         TEXT        NOT NULL,
    embedding       vector(1536),
    source          TEXT,
    confidence      FLOAT       DEFAULT 1.0,
    metadata        JSONB       DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_semantic_concept
    ON semantic_memory USING GIN (to_tsvector('english', concept || ' ' || content));

CREATE INDEX IF NOT EXISTS idx_semantic_embedding
    ON semantic_memory USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- --------------------------------------------------------------
-- MISSIONS
-- Tracks autonomous mission state and execution history
-- --------------------------------------------------------------

CREATE TABLE IF NOT EXISTS missions (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    title           TEXT        NOT NULL,
    objective       TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'pending',
    priority        INT         DEFAULT 5,
    result          TEXT,
    metadata        JSONB       DEFAULT '{}',
    started_at      TIMESTAMPTZ,
    completed_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT missions_status_check CHECK (
        status IN ('pending', 'active', 'completed', 'failed', 'cancelled')
    )
);

CREATE INDEX IF NOT EXISTS idx_missions_status
    ON missions (status, created_at DESC);

-- --------------------------------------------------------------
-- COGNITION EVENTS
-- Persistent log of all agent cognition events
-- --------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cognition_events (
    id              BIGSERIAL   PRIMARY KEY,
    mission_id      UUID        REFERENCES missions (id) ON DELETE SET NULL,
    agent           TEXT        NOT NULL,
    event_type      TEXT        NOT NULL,
    phase           TEXT,
    message         TEXT        NOT NULL,
    payload         JSONB       DEFAULT '{}',
    stream_chunk    TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cognition_mission
    ON cognition_events (mission_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_cognition_agent
    ON cognition_events (agent, created_at DESC);

-- Partition by month for large-scale deployments (optional future step)

-- --------------------------------------------------------------
-- AGENT SESSIONS
-- Active and historical agent runtime sessions
-- --------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_sessions (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_key     TEXT        UNIQUE NOT NULL,
    agent           TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'active',
    context         JSONB       DEFAULT '{}',
    started_at      TIMESTAMPTZ DEFAULT NOW(),
    last_active_at  TIMESTAMPTZ DEFAULT NOW(),
    ended_at        TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_sessions_key
    ON agent_sessions (session_key);

CREATE INDEX IF NOT EXISTS idx_sessions_agent_status
    ON agent_sessions (agent, status);

-- --------------------------------------------------------------
-- REFLECTION_HISTORY  (single canonical reflection table)
-- All reflection reads and writes use this table.
-- The legacy reflection_log table has been removed — migration
-- 0003_consolidate_reflection_tables copies any existing rows here.
-- --------------------------------------------------------------

CREATE TABLE IF NOT EXISTS reflection_history (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    mission_id      UUID        REFERENCES missions (id) ON DELETE SET NULL,
    agent           TEXT        NOT NULL,
    reflection      TEXT        NOT NULL,
    embedding       vector(1536),
    score           FLOAT,
    metadata        JSONB       DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_refl_hist_agent_created
    ON reflection_history (agent, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_refl_hist_mission
    ON reflection_history (mission_id);

CREATE INDEX IF NOT EXISTS idx_refl_hist_embedding
    ON reflection_history USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 50);

-- --------------------------------------------------------------
-- RUNTIME_ANALYTICS
-- Per-agent, per-mission performance and cost telemetry
-- --------------------------------------------------------------

CREATE TABLE IF NOT EXISTS runtime_analytics (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    mission_id      UUID        REFERENCES missions (id) ON DELETE SET NULL,
    session_id      TEXT,
    agent           TEXT        NOT NULL,
    event_type      TEXT        NOT NULL,
    model           TEXT,
    prompt_tokens   INT,
    output_tokens   INT,
    latency_ms      FLOAT,
    cost_usd        FLOAT,
    success         BOOLEAN     NOT NULL DEFAULT TRUE,
    error_message   TEXT,
    payload         JSONB       DEFAULT '{}',
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analytics_agent_created
    ON runtime_analytics (agent, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analytics_mission_created
    ON runtime_analytics (mission_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_analytics_event_type
    ON runtime_analytics (event_type);

CREATE INDEX IF NOT EXISTS idx_analytics_session
    ON runtime_analytics (session_id);

-- --------------------------------------------------------------
-- EMBEDDING_CACHE
-- Persistent cross-restart cache for computed embeddings
-- --------------------------------------------------------------

CREATE TABLE IF NOT EXISTS embedding_cache (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    text_hash       TEXT        NOT NULL UNIQUE,
    model           TEXT        NOT NULL,
    text_preview    TEXT        NOT NULL,
    embedding       vector(1536) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_emb_cache_hash
    ON embedding_cache (text_hash);

-- ==============================================================
-- UPDATED_AT trigger function
-- ==============================================================

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_episodic_updated_at
    BEFORE UPDATE ON episodic_memory
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_semantic_updated_at
    BEFORE UPDATE ON semantic_memory
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_missions_updated_at
    BEFORE UPDATE ON missions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_reflection_history_updated_at
    BEFORE UPDATE ON reflection_history
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_runtime_analytics_updated_at
    BEFORE UPDATE ON runtime_analytics
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_embedding_cache_updated_at
    BEFORE UPDATE ON embedding_cache
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ==============================================================
-- GRANT permissions (default user has full access to cortexdb)
-- ==============================================================

GRANT ALL PRIVILEGES ON ALL TABLES    IN SCHEMA public TO cortex;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO cortex;
GRANT USAGE ON SCHEMA public TO cortex;
