"""
Enterprise Event Types — standardized event type constants for the
event-driven CortexPrime platform.

Every domain (mission, connector, verification, recovery, approval,
knowledge graph, memory, analytics, runtime) has a set of standardised
event types that the frontend useEnterpriseEventStream hook recognizes
to invalidate the correct query keys.

Convention: domain.event_name (e.g. "mission.launched", "connector.action_completed")
"""
from __future__ import annotations


class EnterpriseEventTypes:
    """Standardized enterprise event types organized by domain."""

    # ------------------------------------------------------------------
    # Mission lifecycle
    # ------------------------------------------------------------------
    MISSION_LAUNCHED: str          = "mission.launched"
    MISSION_COMPLETED: str         = "mission.completed"
    MISSION_FAILED: str            = "mission.failed"
    MISSION_STEP: str              = "mission.step"
    MISSION_STEP_FAILED: str       = "mission.step_failed"

    # ------------------------------------------------------------------
    # Approval lifecycle
    # ------------------------------------------------------------------
    APPROVAL_REQUIRED: str         = "approval.required"
    APPROVAL_GRANTED: str          = "approval.granted"
    APPROVAL_REJECTED: str         = "approval.rejected"
    APPROVAL_TIMED_OUT: str        = "approval.timed_out"

    # ------------------------------------------------------------------
    # Connector lifecycle
    # ------------------------------------------------------------------
    CONNECTOR_ACTION_STARTED: str  = "connector.action_started"
    CONNECTOR_ACTION_COMPLETED: str = "connector.action_completed"
    CONNECTOR_ACTION_FAILED: str   = "connector.action_failed"

    # ------------------------------------------------------------------
    # Verification lifecycle
    # ------------------------------------------------------------------
    VERIFICATION_STARTED: str      = "verification.started"
    VERIFICATION_COMPLETED: str    = "verification.completed"
    VERIFICATION_FAILED: str       = "verification.failed"

    # ------------------------------------------------------------------
    # Recovery lifecycle
    # ------------------------------------------------------------------
    RECOVERY_RETRY: str            = "recovery.retry"
    RECOVERY_FALLBACK: str         = "recovery.fallback"
    RECOVERY_ROLLBACK: str         = "recovery.rollback"
    RECOVERY_ESCALATION: str       = "recovery.escalation"

    # ------------------------------------------------------------------
    # Knowledge Graph lifecycle
    # ------------------------------------------------------------------
    GRAPH_ENTITY_CREATED: str      = "graph.entity_created"
    GRAPH_RELATIONSHIP_CREATED: str = "graph.relationship_created"
    GRAPH_MISSION_UPDATED: str     = "graph.mission_updated"

    # ------------------------------------------------------------------
    # Memory lifecycle
    # ------------------------------------------------------------------
    MEMORY_STORED: str             = "memory.stored"
    MEMORY_RETRIEVED: str          = "memory.retrieved"

    # ------------------------------------------------------------------
    # Analytics lifecycle
    # ------------------------------------------------------------------
    ANALYTICS_METRICS_UPDATED: str = "analytics.metrics_updated"
    ANALYTICS_KPI_UPDATED: str     = "analytics.kpi_updated"

    # ------------------------------------------------------------------
    # Runtime lifecycle
    # ------------------------------------------------------------------
    RUNTIME_METRICS_UPDATED: str   = "runtime.metrics_updated"
    RUNTIME_STATE_CHANGED: str     = "runtime.state_changed"
    RUNTIME_HEALTH_UPDATED: str    = "runtime.health_updated"

    # ------------------------------------------------------------------
    # Learning lifecycle
    # ------------------------------------------------------------------
    LEARNING_LESSON_DISCOVERED: str       = "learning.lesson_discovered"
    LEARNING_PATTERN_UPDATED: str         = "learning.pattern_updated"
    LEARNING_RECOMMENDATION_GENERATED: str = "learning.recommendation_generated"
    LEARNING_ANALYSIS_COMPLETED: str      = "learning.analysis_completed"

    # ------------------------------------------------------------------
    # Monitoring lifecycle
    # ------------------------------------------------------------------
    MONITORING_EVENT_DETECTED: str         = "monitoring.event_detected"
    MONITORING_MISSION_CREATED: str        = "monitoring.mission_created"
    MONITORING_RECOVERY_STARTED: str       = "monitoring.recovery_started"
    MONITORING_RECOVERY_COMPLETED: str     = "monitoring.recovery_completed"
    MONITORING_RECOVERY_FAILED: str        = "monitoring.recovery_failed"
    MONITORING_APPROVAL_REQUIRED: str      = "monitoring.approval_required"
    MONITORING_CLOSED: str                = "monitoring.closed"
    MONITORING_RULE_CREATED: str           = "monitoring.rule_created"
    MONITORING_RULE_UPDATED: str           = "monitoring.rule_updated"
    MONITORING_RULE_DELETED: str           = "monitoring.rule_deleted"
    MONITORING_WATCHER_HEALTH_CHANGED: str = "monitoring.watcher_health_changed"

    # ------------------------------------------------------------------
    # Recommendation lifecycle
    # ------------------------------------------------------------------
    RECOMMENDATION_GENERATED: str  = "recommendation.generated"
    RECOMMENDATION_DISMISSED: str  = "recommendation.dismissed"
    RECOMMENDATION_EXECUTED: str   = "recommendation.executed"

    # ------------------------------------------------------------------
    # Engineering lifecycle
    # ------------------------------------------------------------------
    ENGINEERING_REPO_ANALYZED: str     = "engineering.repo_analyzed"
    ENGINEERING_BUILD_COMPLETED: str   = "engineering.build_completed"
    ENGINEERING_TEST_COMPLETED: str    = "engineering.test_completed"
    ENGINEERING_SECURITY_SCANNED: str  = "engineering.security_scanned"
    ENGINEERING_ARCHITECTURE_REVIEWED: str = "engineering.architecture_reviewed"
    ENGINEERING_RCA_COMPLETED: str     = "engineering.rca_completed"
    ENGINEERING_PLAN_GENERATED: str    = "engineering.plan_generated"
    ENGINEERING_CODE_GENERATED: str    = "engineering.code_generated"
    ENGINEERING_CODE_REVIEWED: str     = "engineering.code_reviewed"
    ENGINEERING_MISSION_COMPLETED: str  = "engineering.mission_completed"

    # ------------------------------------------------------------------
    # Workspace lifecycle
    # ------------------------------------------------------------------
    WORKSPACE_CREATED: str       = "workspace.created"
    WORKSPACE_DESTROYED: str     = "workspace.destroyed"
    WORKSPACE_BRANCH_CHANGED: str = "workspace.branch_changed"
    WORKSPACE_SNAPSHOT_CAPTURED: str = "workspace.snapshot_captured"
    WORKSPACE_ARTIFACT_GENERATED: str = "workspace.artifact_generated"
    WORKSPACE_LOCKED: str        = "workspace.locked"
    WORKSPACE_RELEASED: str      = "workspace.released"
    WORKSPACE_REPO_UPDATED: str   = "workspace.repo_updated"

    # ------------------------------------------------------------------
    # Patch lifecycle
    # ------------------------------------------------------------------
    PATCH_CREATED: str        = "patch.created"
    PATCH_UPDATED: str        = "patch.updated"
    PATCH_VALIDATED: str      = "patch.validated"
    PATCH_FAILED: str         = "patch.failed"
    PATCH_ROLLED_BACK: str    = "patch.rolled_back"
    PATCH_DIFF_GENERATED: str  = "patch.diff_generated"
    PATCH_DEPENDENCY_UPDATED: str = "patch.dependency_updated"
    PATCH_PLANNED: str             = "patch.planned"
    PATCH_GENERATED: str           = "patch.generated"
    PATCH_REJECTED: str            = "patch.rejected"
    PATCH_SELECTED: str            = "patch.selected"
    PATCH_REFACTOR_SUGGESTED: str  = "patch.refactor_suggested"
    PATCH_REFACTOR_APPLIED: str    = "patch.refactor_applied"

    # ------------------------------------------------------------------
    # Build lifecycle
    # ------------------------------------------------------------------
    BUILD_CREATED: str             = "build.created"
    BUILD_STARTED: str             = "build.started"
    BUILD_COMPLETED: str           = "build.completed"
    BUILD_FAILED: str              = "build.failed"
    BUILD_ARTIFACT_GENERATED: str   = "build.artifact_generated"

    # ------------------------------------------------------------------
    # Deployment lifecycle
    # ------------------------------------------------------------------
    DEPLOY_CREATED: str      = "deploy.created"
    DEPLOY_STARTED: str      = "deploy.started"
    DEPLOY_COMPLETED: str    = "deploy.completed"
    DEPLOY_FAILED: str       = "deploy.failed"
    DEPLOY_ROLLED_BACK: str  = "deploy.rolled_back"
    DEPLOY_ENV_UPDATED: str  = "deploy.env_updated"

    # ------------------------------------------------------------------
    # Governance lifecycle
    # ------------------------------------------------------------------
    GOVERNANCE_POLICY_CREATED: str   = "governance.policy_created"
    GOVERNANCE_POLICY_UPDATED: str   = "governance.policy_updated"
    GOVERNANCE_POLICY_DELETED: str   = "governance.policy_deleted"
    GOVERNANCE_COMPLIANCE_CHECK: str  = "governance.compliance_check"
    GOVERNANCE_VIOLATION: str        = "governance.violation"
    GOVERNANCE_AUDIT_RECORDED: str   = "governance.audit_recorded"

    # ------------------------------------------------------------------
    # Trigger lifecycle
    # ------------------------------------------------------------------
    TRIGGER_DETECTED: str            = "trigger.detected"
    TRIGGER_POLICY_MATCHED: str      = "trigger.policy_matched"
    TRIGGER_MISSION_GENERATED: str   = "trigger.mission_generated"
    TRIGGER_MISSION_STARTED: str     = "trigger.mission_started"
    TRIGGER_MISSION_SUPPRESSED: str  = "trigger.mission_suppressed"

    # ------------------------------------------------------------------
    # Delivery lifecycle
    # ------------------------------------------------------------------
    DELIVERY_STARTED: str            = "delivery.started"
    DELIVERY_STAGE_STARTED: str      = "delivery.stage_started"
    DELIVERY_STAGE_COMPLETED: str    = "delivery.stage_completed"
    DELIVERY_STAGE_FAILED: str       = "delivery.stage_failed"
    DELIVERY_PAUSED: str             = "delivery.paused"
    DELIVERY_RESUMED: str            = "delivery.resumed"
    DELIVERY_ROLLED_BACK: str        = "delivery.rolled_back"
    DELIVERY_COMPLETED: str          = "delivery.completed"
    DELIVERY_CANCELLED: str          = "delivery.cancelled"
    DELIVERY_FAILED: str             = "delivery.failed"

    # ------------------------------------------------------------------
    # Execution Engine lifecycle
    # ------------------------------------------------------------------
    EXECUTION_CREATED: str             = "execution.created"
    EXECUTION_STARTED: str             = "execution.started"
    EXECUTION_STAGE_STARTED: str       = "execution.stage_started"
    EXECUTION_STAGE_COMPLETED: str     = "execution.stage_completed"
    EXECUTION_STAGE_FAILED: str        = "execution.stage_failed"
    EXECUTION_CANCELLED: str           = "execution.cancelled"
    EXECUTION_ROLLED_BACK: str         = "execution.rolled_back"
    EXECUTION_COMPLETED: str           = "execution.completed"
    EXECUTION_FAILED: str              = "execution.failed"
    EXECUTION_RETRIED: str             = "execution.retried"

    # ------------------------------------------------------------------
    # Sandbox lifecycle
    # ------------------------------------------------------------------
    SANDBOX_CREATED: str             = "sandbox.created"
    SANDBOX_STARTED: str             = "sandbox.started"
    SANDBOX_PAUSED: str              = "sandbox.paused"
    SANDBOX_RESUMED: str             = "sandbox.resumed"
    SANDBOX_EXECUTION_STARTED: str   = "sandbox.execution_started"
    SANDBOX_EXECUTION_COMPLETED: str = "sandbox.execution_completed"
    SANDBOX_EXECUTION_FAILED: str    = "sandbox.execution_failed"
    SANDBOX_ARTIFACTS_GENERATED: str = "sandbox.artifacts_generated"
    SANDBOX_DESTROYED: str           = "sandbox.destroyed"

    # ------------------------------------------------------------------
    # Code Intelligence lifecycle
    # ------------------------------------------------------------------
    CODE_REPOSITORY_SCANNED: str     = "code.repository_scanned"
    CODE_GRAPH_UPDATED: str          = "code.graph_updated"
    CODE_DEPENDENCY_UPDATED: str     = "code.dependency_updated"
    CODE_IMPACT_COMPUTED: str        = "code.impact_computed"
    CODE_ANALYSIS_COMPLETED: str     = "code.analysis_completed"

    # ------------------------------------------------------------------
    # Git Operations lifecycle
    # ------------------------------------------------------------------
    GIT_BRANCH_CREATED: str          = "git.branch_created"
    GIT_COMMIT_CREATED: str          = "git.commit_created"
    GIT_PULL_REQUEST_OPENED: str     = "git.pull_request_opened"
    GIT_PULL_REQUEST_UPDATED: str    = "git.pull_request_updated"
    GIT_PULL_REQUEST_MERGED: str     = "git.pull_request_merged"
    GIT_ISSUE_SYNCHRONIZED: str      = "git.issue_synchronized"

    # ------------------------------------------------------------------
    # Pipeline lifecycle
    # ------------------------------------------------------------------
    PIPELINE_CREATED: str            = "pipeline.created"
    PIPELINE_STARTED: str            = "pipeline.started"
    PIPELINE_STAGE_STARTED: str      = "pipeline.stage_started"
    PIPELINE_STAGE_COMPLETED: str    = "pipeline.stage_completed"
    PIPELINE_STAGE_FAILED: str       = "pipeline.stage_failed"
    PIPELINE_COMPLETED: str          = "pipeline.completed"
    PIPELINE_FAILED: str             = "pipeline.failed"
    PIPELINE_CANCELLED: str          = "pipeline.cancelled"
    PIPELINE_PATCH_TO_PR: str        = "pipeline.patch_to_pr"
    PIPELINE_PR_CREATED: str         = "pipeline.pr_created"
    PIPELINE_ARTIFACT_PASSED: str    = "pipeline.artifact_passed"

    # ------------------------------------------------------------------
    # Architecture Intelligence lifecycle
    # ------------------------------------------------------------------
    ARCHITECTURE_ANALYSIS_STARTED: str    = "architecture.analysis_started"
    ARCHITECTURE_ANALYSIS_COMPLETED: str  = "architecture.analysis_completed"
    ARCHITECTURE_DOMAIN_GENERATED: str    = "architecture.domain_generated"
    ARCHITECTURE_SERVICES_GENERATED: str  = "architecture.services_generated"
    ARCHITECTURE_DATABASE_GENERATED: str  = "architecture.database_generated"
    ARCHITECTURE_API_GENERATED: str       = "architecture.api_generated"
    ARCHITECTURE_EVENTS_GENERATED: str    = "architecture.events_generated"
    ARCHITECTURE_PLAN_GENERATED: str      = "architecture.plan_generated"
    ARCHITECTURE_MISSIONS_GENERATED: str  = "architecture.missions_generated"
    ARCHITECTURE_TECHNOLOGY_SELECTED: str = "architecture.technology_selected"
    ARCHITECTURE_DECISION_RECORDED: str   = "architecture.decision_recorded"

    # ------------------------------------------------------------------
    # Engineering Executive lifecycle
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # CI/CD Intelligence lifecycle
    # ------------------------------------------------------------------
    CICD_PIPELINE_CREATED: str            = "cicd.pipeline_created"
    CICD_PIPELINE_STARTED: str            = "cicd.pipeline_started"
    CICD_PIPELINE_COMPLETED: str          = "cicd.pipeline_completed"
    CICD_PIPELINE_FAILED: str             = "cicd.pipeline_failed"
    CICD_BUILD_STARTED: str               = "cicd.build_started"
    CICD_BUILD_COMPLETED: str             = "cicd.build_completed"
    CICD_BUILD_FAILED: str                = "cicd.build_failed"
    CICD_DEPLOYMENT_STARTED: str          = "cicd.deployment_started"
    CICD_DEPLOYMENT_COMPLETED: str        = "cicd.deployment_completed"
    CICD_DEPLOYMENT_FAILED: str           = "cicd.deployment_failed"
    CICD_DEPLOYMENT_RECOVERED: str        = "cicd.deployment_recovered"
    CICD_ARTIFACT_PUBLISHED: str          = "cicd.artifact_published"
    CICD_FAILURE_ANALYZED: str            = "cicd.failure_analyzed"
    CICD_RECOVERY_STARTED: str            = "cicd.recovery_started"
    CICD_RECOVERY_COMPLETED: str          = "cicd.recovery_completed"
    CICD_TIMELINE_BUILT: str              = "cicd.timeline_built"

    # ------------------------------------------------------------------
    # GitHub Integration lifecycle
    # ------------------------------------------------------------------
    GITHUB_WEBHOOK_RECEIVED: str              = "github.webhook_received"
    GITHUB_WEBHOOK_VERIFIED: str              = "github.webhook_verified"
    GITHUB_PUSH_RECEIVED: str                 = "github.push_received"
    GITHUB_WORKFLOW_RUN_STARTED: str          = "github.workflow_run_started"
    GITHUB_WORKFLOW_RUN_COMPLETED: str        = "github.workflow_run_completed"
    GITHUB_WORKFLOW_RUN_FAILED: str           = "github.workflow_run_failed"
    GITHUB_PR_OPENED: str                     = "github.pr_opened"
    GITHUB_PR_UPDATED: str                    = "github.pr_updated"
    GITHUB_PR_REVIEWED: str                   = "github.pr_reviewed"
    GITHUB_PR_CHECKS_PASSED: str              = "github.pr_checks_passed"
    GITHUB_PR_MERGED: str                     = "github.pr_merged"
    GITHUB_ISSUE_OPENED: str                  = "github.issue_opened"
    GITHUB_ISSUE_CLOSED: str                  = "github.issue_closed"
    GITHUB_RELEASE_PUBLISHED: str             = "github.release_published"
    GITHUB_DEPLOYMENT_STARTED: str            = "github.deployment_started"
    GITHUB_DEPLOYMENT_COMPLETED: str          = "github.deployment_completed"
    GITHUB_DEPLOYMENT_FAILED: str             = "github.deployment_failed"
    GITHUB_BRANCH_UPDATED: str                = "github.branch_updated"
    GITHUB_BRANCH_DELETED: str                = "github.branch_deleted"
    GITHUB_MISSION_LAUNCHED: str              = "github.mission_launched"

    ENGINEERING_DECISION_MADE: str                   = "engineering.decision_made"
    ENGINEERING_CONTEXT_COLLECTED: str               = "engineering.context_collected"
    ENGINEERING_EXPERIENCE_BUILT: str                = "engineering.experience_built"

    # ------------------------------------------------------------------
    # Simulation / Predictive lifecycle
    # ------------------------------------------------------------------
    SIMULATION_PREDICTION_COMPLETED: str             = "simulation.prediction_completed"
    SIMULATION_PREDICTION_FAILED: str                = "simulation.prediction_failed"
    SIMULATION_PREDICTION_FEEDBACK: str              = "simulation.prediction_feedback"
    SIMULATION_STRATEGY_COMPARED: str                = "simulation.strategy_compared"

    # ------------------------------------------------------------------
    # Verification lifecycle
    # ------------------------------------------------------------------
    ENGINEERING_VERIFICATION_COMPLETED: str          = "engineering.verification_completed"
    ENGINEERING_VERIFICATION_FAILED: str             = "engineering.verification_failed"
    ENGINEERING_VERIFICATION_REPORT_GENERATED: str   = "engineering.verification_report_generated"

    # ------------------------------------------------------------------
    # Executive Runtime lifecycle
    # ------------------------------------------------------------------
    ENGINEERING_MISSION_CREATED: str                 = "engineering.mission_created"
    ENGINEERING_MISSION_PLANNED: str                 = "engineering.mission_planned"
    ENGINEERING_MISSION_RUNNING: str                 = "engineering.mission_running"
    ENGINEERING_MISSION_COMPLETED: str               = "engineering.mission_completed"
    ENGINEERING_MISSION_FAILED: str                  = "engineering.mission_failed"
    ENGINEERING_MISSION_CANCELLED: str               = "engineering.mission_cancelled"
    ENGINEERING_MISSION_INTERVENTION: str            = "engineering.mission_intervention"
    ENGINEERING_EXECUTIVE_TASK_CREATED: str          = "engineering.executive.task_created"
    ENGINEERING_EXECUTIVE_TASK_CLASSIFIED: str       = "engineering.executive.task_classified"
    ENGINEERING_EXECUTIVE_PLAN_CREATED: str          = "engineering.executive.plan_created"
    ENGINEERING_EXECUTIVE_MISSION_LAUNCHED: str      = "engineering.executive.mission_launched"
    ENGINEERING_EXECUTIVE_STAGE_STARTED: str         = "engineering.executive.stage_started"
    ENGINEERING_EXECUTIVE_STAGE_COMPLETED: str       = "engineering.executive.stage_completed"
    ENGINEERING_EXECUTIVE_STAGE_FAILED: str          = "engineering.executive.stage_failed"
    ENGINEERING_EXECUTIVE_RECOVERY_ATTEMPTED: str    = "engineering.executive.recovery_attempted"
    ENGINEERING_EXECUTIVE_ESCALATED: str             = "engineering.executive.escalated"
    ENGINEERING_EXECUTIVE_APPROVAL_REQUESTED: str    = "engineering.executive.approval_requested"
    ENGINEERING_EXECUTIVE_STOPPED: str               = "engineering.executive.stopped"
    ENGINEERING_EXECUTIVE_COMPLETED: str             = "engineering.executive.completed"
    ENGINEERING_EXECUTIVE_REPORT_GENERATED: str      = "engineering.executive.report_generated"

    # ------------------------------------------------------------------
    # Infrastructure Intelligence lifecycle
    # ------------------------------------------------------------------
    INFRA_CLUSTER_HEALTH_CHANGED: str            = "infra.cluster_health_changed"
    INFRA_POD_STATUS_CHANGED: str                = "infra.pod_status_changed"
    INFRA_NODE_STATUS_CHANGED: str               = "infra.node_status_changed"
    INFRA_NODE_UTILIZATION_UPDATED: str          = "infra.node_utilization_updated"
    INFRA_DEPLOYMENT_ROLLOUT_UPDATED: str        = "infra.deployment_rollout_updated"
    INFRA_DEPLOYMENT_ROLLBACK_DETECTED: str      = "infra.deployment_rollback_detected"
    INFRA_CONTAINER_RESTARTED: str               = "infra.container_restarted"
    INFRA_CONTAINER_OOMKILLED: str               = "infra.container_oomkilled"
    INFRA_CONTAINER_CRASHLOOP: str               = "infra.container_crashloop"
    INFRA_PVC_HEALTH_CHANGED: str                = "infra.pvc_health_changed"
    INFRA_NETWORK_FAILURE_DETECTED: str          = "infra.network_failure_detected"
    INFRA_DOCKER_CONTAINER_TRACKED: str          = "infra.docker_container_tracked"
    INFRA_HELM_RELEASE_TRACKED: str              = "infra.helm_release_tracked"
    INFRA_PROMETHEUS_ALERT_CORRELATED: str       = "infra.prometheus_alert_correlated"
    INFRA_GRAFANA_DASHBOARD_DISCOVERED: str      = "infra.grafana_dashboard_discovered"
    INFRA_LOKI_LOG_ANALYSIS_COMPLETED: str       = "infra.loki_log_analysis_completed"
    INFRA_OPENTELEMETRY_TRACE_ANALYZED: str      = "infra.opentelemetry_trace_analyzed"

    # ------------------------------------------------------------------
    # Root Cause Analysis lifecycle
    # ------------------------------------------------------------------
    RCA_INCIDENT_DETECTED: str                 = "rca.incident_detected"
    RCA_ANALYSIS_STARTED: str                  = "rca.analysis_started"
    RCA_CORRELATION_COMPLETED: str             = "rca.correlation_completed"
    RCA_EVIDENCE_COLLECTED: str                = "rca.evidence_collected"
    RCA_ROOT_CAUSE_IDENTIFIED: str             = "rca.root_cause_identified"
    RCA_ANALYSIS_COMPLETED: str                = "rca.analysis_completed"
    RCA_ENGINEERING_STORY_GENERATED: str       = "rca.engineering_story_generated"

    # ------------------------------------------------------------------
    # Continuous Cognition lifecycle
    # ------------------------------------------------------------------
    COGNITION_OBSERVATION: str              = "cognition.observation"
    COGNITION_REPO_ADDED: str               = "cognition.repo_added"
    COGNITION_REPO_REMOVED: str             = "cognition.repo_removed"
    COGNITION_ARCHITECTURE_CHANGED: str     = "cognition.architecture_changed"
    COGNITION_ARCHITECTURE_DRIFT: str       = "cognition.architecture_drift"
    COGNITION_OWNERSHIP_CHANGED: str        = "cognition.ownership_changed"
    COGNITION_RISK_CHANGED: str             = "cognition.risk_changed"
    COGNITION_PREDICTION_REFRESHED: str     = "cognition.prediction_refreshed"
    COGNITION_CONTEXT_REFRESHED: str        = "cognition.context_refreshed"
    COGNITION_K8S_HEALTH_CHANGED: str       = "cognition.k8s_health_changed"
    COGNITION_ARGOCD_SYNC_DRIFT: str        = "cognition.argocd_sync_drift"
    COGNITION_PROMETHEUS_ALERTS: str        = "cognition.prometheus_alerts"
    COGNITION_LOKI_ERROR_SPIKE: str         = "cognition.loki_error_spike"
    COGNITION_OTEL_DEGRADATION: str         = "cognition.otel_degradation"
    COGNITION_KNOWLEDGE_UPDATED: str        = "cognition.knowledge_updated"
    COGNITION_EXECUTIVE_MISSION: str        = "cognition.executive_mission"
    COGNITION_CYCLE_COMPLETED: str          = "cognition.cycle_completed"
    COGNITION_HIGH_RISK: str                = "cognition.high_risk"
    COGNITION_LOW_RISK: str                 = "cognition.low_risk"
