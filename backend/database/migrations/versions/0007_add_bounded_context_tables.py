"""Create bounded context domain tables — IAM, Missions, Executions, Knowledge,
Learning, Digital Twin, Governance, Connectors, AI Agents, Platform, Billing.

Revision ID: 0007_add_bounded_context_tables
Revises: 0006_fix_cost_tracking_id_type
Create Date: 2026-07-17
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision: str = "0007_add_bounded_context_tables"
down_revision: str | None = "0006_fix_cost_tracking_id_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # IAM
    # ------------------------------------------------------------------
    op.create_table(
        "iam_users",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("display_name", sa.String(256), nullable=False),
        sa.Column("password_hash", sa.String(256), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("is_sso", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("sso_provider", sa.String(64), nullable=True),
        sa.Column("sso_subject", sa.String(256), nullable=True),
        sa.Column("roles", JSONB, nullable=False, server_default="[]"),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_iam_users_email", "iam_users", ["email"], unique=True)
    op.create_index("idx_iam_users_status", "iam_users", ["status"])
    op.create_index("idx_iam_users_sso", "iam_users", ["sso_provider", "sso_subject"])

    op.create_table(
        "iam_roles",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.String(1024), nullable=True),
        sa.Column("permissions", JSONB, nullable=False, server_default="[]"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_iam_roles_name", "iam_roles", ["name"], unique=True)

    op.create_table(
        "iam_api_keys",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("iam_users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("key_hash", sa.String(256), nullable=False),
        sa.Column("last_prefix", sa.String(8), nullable=False),
        sa.Column("expires_at", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_iam_ak_user", "iam_api_keys", ["user_id"])
    op.create_index("idx_iam_ak_hash", "iam_api_keys", ["key_hash"], unique=True)

    # ------------------------------------------------------------------
    # Missions
    # ------------------------------------------------------------------
    op.create_table(
        "missions_bc",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("objective", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("category", sa.String(128), nullable=True),
        sa.Column("owner", sa.String(256), nullable=True),
        sa.Column("execution_id", sa.String(128), nullable=True),
        sa.Column("context", JSONB, nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("started_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_missions_bc_status", "missions_bc", ["status", "created_at"])
    op.create_index("idx_missions_bc_category", "missions_bc", ["category"])
    op.create_index("idx_missions_bc_owner", "missions_bc", ["owner"])

    op.create_table(
        "mission_steps",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("mission_id", sa.Uuid(), sa.ForeignKey("missions_bc.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("agent", sa.String(128), nullable=True),
        sa.Column("input_data", JSONB, nullable=True),
        sa.Column("output_data", JSONB, nullable=True),
        sa.Column("started_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_mission_steps_mission", "mission_steps", ["mission_id", "step_order"])
    op.create_index("idx_mission_steps_status", "mission_steps", ["status"])

    # ------------------------------------------------------------------
    # Executions
    # ------------------------------------------------------------------
    op.create_table(
        "executions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("mission_id", sa.Uuid(), sa.ForeignKey("missions_bc.id", ondelete="SET NULL"), nullable=True),
        sa.Column("execution_id", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("agent", sa.String(128), nullable=True),
        sa.Column("trigger", sa.String(64), nullable=False, server_default="manual"),
        sa.Column("context", JSONB, nullable=True),
        sa.Column("result", JSONB, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Float(), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_exec_mission", "executions", ["mission_id"])
    op.create_index("idx_exec_status", "executions", ["status", "created_at"])
    op.create_index("idx_exec_agent", "executions", ["agent"])
    op.create_index("idx_exec_trigger", "executions", ["trigger"])
    op.create_index("idx_exec_id", "executions", ["execution_id"], unique=True)

    op.create_table(
        "execution_events",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("execution_id", sa.String(128), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("phase", sa.String(64), nullable=True),
        sa.Column("agent", sa.String(128), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("payload", JSONB, nullable=True),
        sa.Column("timestamp", TIMESTAMP(timezone=True), nullable=False),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_exec_events_exec", "execution_events", ["execution_id", "timestamp"])
    op.create_index("idx_exec_events_type", "execution_events", ["event_type"])

    # ------------------------------------------------------------------
    # Knowledge
    # ------------------------------------------------------------------
    op.create_table(
        "knowledge_entries",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("source", sa.String(256), nullable=True),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("embedding", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    # Replace TEXT embedding placeholder with real vector column
    op.drop_column("knowledge_entries", "embedding")
    op.execute("ALTER TABLE knowledge_entries ADD COLUMN embedding vector(1536)")
    op.create_index("idx_knowledge_category", "knowledge_entries", ["category"])
    op.create_index("idx_knowledge_confidence", "knowledge_entries", ["confidence"])
    op.create_index("idx_knowledge_created", "knowledge_entries", ["created_at"])

    op.create_table(
        "knowledge_relationships",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column("relationship_type", sa.String(64), nullable=False),
        sa.Column("strength", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_knowledge_rel_source", "knowledge_relationships", ["source_id", "relationship_type"])
    op.create_index("idx_knowledge_rel_target", "knowledge_relationships", ["target_id", "relationship_type"])

    # ------------------------------------------------------------------
    # Learning
    # ------------------------------------------------------------------
    op.create_table(
        "learning_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("session_id", sa.String(128), nullable=False),
        sa.Column("mission_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("outcome", sa.String(64), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("patterns_extracted", JSONB, nullable=True),
        sa.Column("lessons_learned", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_learn_session_sid", "learning_sessions", ["session_id"], unique=True)
    op.create_index("idx_learn_session_mission", "learning_sessions", ["mission_type"])
    op.create_index("idx_learn_session_status", "learning_sessions", ["status"])

    op.create_table(
        "learning_patterns",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("occurrences", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("pattern_data", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_learn_patterns_name", "learning_patterns", ["name"], unique=True)
    op.create_index("idx_learn_patterns_category", "learning_patterns", ["category"])
    op.create_index("idx_learn_patterns_confidence", "learning_patterns", ["confidence"])

    # ------------------------------------------------------------------
    # Digital Twin
    # ------------------------------------------------------------------
    op.create_table(
        "digital_twin_models",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("region", sa.String(128), nullable=True),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("properties", JSONB, nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="unknown"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_dt_model_type", "digital_twin_models", ["resource_type", "provider"])
    op.create_index("idx_dt_model_status", "digital_twin_models", ["status"])
    op.create_index("idx_dt_model_active", "digital_twin_models", ["is_active"])

    op.create_table(
        "digital_twin_relationships",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", sa.String(128), nullable=False),
        sa.Column("target_id", sa.String(128), nullable=False),
        sa.Column("relationship_type", sa.String(64), nullable=False),
        sa.Column("properties", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_dt_rel_source", "digital_twin_relationships", ["source_id", "relationship_type"])
    op.create_index("idx_dt_rel_target", "digital_twin_relationships", ["target_id", "relationship_type"])

    op.create_table(
        "digital_twin_metrics",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("resource_id", sa.String(128), nullable=False),
        sa.Column("metric_name", sa.String(64), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("tags", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_dt_metrics_resource", "digital_twin_metrics", ["resource_id", "metric_name", "created_at"])

    # ------------------------------------------------------------------
    # Governance
    # ------------------------------------------------------------------
    op.create_table(
        "governance_policies",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(32), nullable=False, server_default="medium"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("conditions", JSONB, nullable=True),
        sa.Column("actions", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_gov_policies_name", "governance_policies", ["name"], unique=True)
    op.create_index("idx_gov_policies_category", "governance_policies", ["category"])
    op.create_index("idx_gov_policies_enabled", "governance_policies", ["enabled"])

    op.create_table(
        "governance_compliance_rules",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("framework", sa.String(64), nullable=False),
        sa.Column("control_id", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("severity", sa.String(32), nullable=False, server_default="medium"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("check_type", sa.String(64), nullable=False),
        sa.Column("check_config", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_gov_compliance_framework", "governance_compliance_rules", ["framework", "control_id"])
    op.create_index("idx_gov_compliance_enabled", "governance_compliance_rules", ["enabled"])

    op.create_table(
        "governance_approval_requests",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("request_id", sa.String(128), nullable=False),
        sa.Column("requester", sa.String(256), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("reviewers", JSONB, nullable=False, server_default="[]"),
        sa.Column("approved_by", sa.String(256), nullable=True),
        sa.Column("approved_at", sa.String(64), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_gov_approval_rid", "governance_approval_requests", ["request_id"], unique=True)
    op.create_index("idx_gov_approval_status", "governance_approval_requests", ["status", "created_at"])

    # ------------------------------------------------------------------
    # Connectors
    # ------------------------------------------------------------------
    op.create_table(
        "connector_configs",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("connector_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(32), nullable=False, server_default="1.0"),
        sa.Column("endpoint", sa.String(1024), nullable=True),
        sa.Column("auth_type", sa.String(64), nullable=True),
        sa.Column("config", JSONB, nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_connector_name", "connector_configs", ["name"], unique=True)
    op.create_index("idx_connector_configs_type", "connector_configs", ["connector_type"])
    op.create_index("idx_connector_configs_active", "connector_configs", ["is_active"])

    op.create_table(
        "connector_activity_bc",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("connector_name", sa.String(128), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="success"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("request_summary", sa.Text(), nullable=True),
        sa.Column("response_summary", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_connector_activity_name", "connector_activity_bc", ["connector_name", "created_at"])
    op.create_index("idx_connector_activity_status", "connector_activity_bc", ["status"])

    # ------------------------------------------------------------------
    # AI Agents
    # ------------------------------------------------------------------
    op.create_table(
        "agent_configs",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("agent_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("provider", sa.String(64), nullable=False, server_default="openai"),
        sa.Column("model", sa.String(128), nullable=False, server_default="gpt-4o"),
        sa.Column("system_prompt", sa.Text(), nullable=True),
        sa.Column("capabilities", JSONB, nullable=True),
        sa.Column("config", JSONB, nullable=True),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_agent_name", "agent_configs", ["name"], unique=True)
    op.create_index("idx_agent_configs_type", "agent_configs", ["agent_type"])
    op.create_index("idx_agent_configs_active", "agent_configs", ["is_active"])

    op.create_table(
        "agent_states",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("agent_name", sa.String(128), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="idle"),
        sa.Column("current_mission", sa.String(128), nullable=True),
        sa.Column("current_execution", sa.String(128), nullable=True),
        sa.Column("last_heartbeat", sa.String(64), nullable=True),
        sa.Column("metrics", JSONB, nullable=True),
        sa.Column("memory_snapshot", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_agent_states_name", "agent_states", ["agent_name"], unique=True)
    op.create_index("idx_agent_states_status", "agent_states", ["status"])

    # ------------------------------------------------------------------
    # Platform
    # ------------------------------------------------------------------
    op.create_table(
        "platform_feature_flags",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_platform_ff_name", "platform_feature_flags", ["name"], unique=True)
    op.create_index("idx_platform_ff_enabled", "platform_feature_flags", ["enabled"])

    op.create_table(
        "platform_settings",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.String(256), nullable=False),
        sa.Column("value", JSONB, nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(64), nullable=False, server_default="general"),
        sa.Column("is_encrypted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_platform_settings_key", "platform_settings", ["key"], unique=True)
    op.create_index("idx_platform_settings_category", "platform_settings", ["category"])

    # ------------------------------------------------------------------
    # Billing
    # ------------------------------------------------------------------
    op.create_table(
        "billing_usage_records",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("mission_id", sa.String(128), nullable=True),
        sa.Column("user_id", sa.String(128), nullable=True),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False, server_default="requests"),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_billing_usage_org", "billing_usage_records", ["organization_id", "created_at"])
    op.create_index("idx_billing_usage_resource", "billing_usage_records", ["resource_type"])

    op.create_table(
        "billing_invoices",
        sa.Column("id", sa.Uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", sa.String(128), nullable=False),
        sa.Column("invoice_number", sa.String(64), nullable=False),
        sa.Column("period_start", sa.String(32), nullable=False),
        sa.Column("period_end", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("total_usd", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(8), nullable=False, server_default="USD"),
        sa.Column("line_items", JSONB, nullable=True),
        sa.Column("metadata", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("idx_billing_invoices_number", "billing_invoices", ["invoice_number"], unique=True)
    op.create_index("idx_billing_invoices_org", "billing_invoices", ["organization_id", "status"])
    op.create_index("idx_billing_invoices_status", "billing_invoices", ["status"])


def downgrade() -> None:
    tables = [
        "billing_invoices",
        "billing_usage_records",
        "platform_settings",
        "platform_feature_flags",
        "agent_states",
        "agent_configs",
        "connector_activity_bc",
        "connector_configs",
        "governance_approval_requests",
        "governance_compliance_rules",
        "governance_policies",
        "digital_twin_metrics",
        "digital_twin_relationships",
        "digital_twin_models",
        "learning_patterns",
        "learning_sessions",
        "knowledge_relationships",
        "knowledge_entries",
        "execution_events",
        "executions",
        "mission_steps",
        "missions_bc",
        "iam_api_keys",
        "iam_roles",
        "iam_users",
    ]
    for t in tables:
        op.drop_table(t)
