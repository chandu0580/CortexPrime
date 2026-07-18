"use client"

import { useEffect, useRef, useCallback } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { wsService } from "@/services/websocket"
import { queryKeys } from "@/lib/query"
import type { WSMessage } from "@/types/websocket"

// ============================================================
// Enterprise Event Type Constants
// Mirrors backend backend/events/enterprise_event_types.py
// ============================================================

export const EnterpriseEventTypes = {
  MISSION_LAUNCHED:          "mission.launched",
  MISSION_COMPLETED:         "mission.completed",
  MISSION_FAILED:            "mission.failed",
  MISSION_STEP:              "mission.step",
  MISSION_STEP_FAILED:       "mission.step_failed",

  APPROVAL_REQUIRED:         "approval.required",
  APPROVAL_GRANTED:          "approval.granted",
  APPROVAL_REJECTED:         "approval.rejected",
  APPROVAL_TIMED_OUT:        "approval.timed_out",

  CONNECTOR_ACTION_STARTED:  "connector.action_started",
  CONNECTOR_ACTION_COMPLETED: "connector.action_completed",
  CONNECTOR_ACTION_FAILED:   "connector.action_failed",

  VERIFICATION_STARTED:      "verification.started",
  VERIFICATION_COMPLETED:    "verification.completed",
  VERIFICATION_FAILED:       "verification.failed",

  RECOVERY_RETRY:            "recovery.retry",
  RECOVERY_FALLBACK:         "recovery.fallback",
  RECOVERY_ROLLBACK:         "recovery.rollback",
  RECOVERY_ESCALATION:       "recovery.escalation",

  GRAPH_ENTITY_CREATED:      "graph.entity_created",
  GRAPH_RELATIONSHIP_CREATED: "graph.relationship_created",
  GRAPH_MISSION_UPDATED:     "graph.mission_updated",

  MEMORY_STORED:             "memory.stored",
  MEMORY_RETRIEVED:          "memory.retrieved",

  ANALYTICS_METRICS_UPDATED: "analytics.metrics_updated",
  ANALYTICS_KPI_UPDATED:     "analytics.kpi_updated",

  RUNTIME_METRICS_UPDATED:   "runtime.metrics_updated",
  RUNTIME_STATE_CHANGED:     "runtime.state_changed",

  LEARNING_LESSON_DISCOVERED:       "learning.lesson_discovered",
  LEARNING_PATTERN_UPDATED:         "learning.pattern_updated",
  LEARNING_RECOMMENDATION_GENERATED: "learning.recommendation_generated",
  LEARNING_ANALYSIS_COMPLETED:      "learning.analysis_completed",

  MONITORING_EVENT_DETECTED:          "monitoring.event_detected",
  MONITORING_MISSION_CREATED:         "monitoring.mission_created",
  MONITORING_RECOVERY_STARTED:        "monitoring.recovery_started",
  MONITORING_RECOVERY_COMPLETED:      "monitoring.recovery_completed",
  MONITORING_RECOVERY_FAILED:         "monitoring.recovery_failed",
  MONITORING_APPROVAL_REQUIRED:       "monitoring.approval_required",
  MONITORING_CLOSED:                  "monitoring.closed",
  MONITORING_RULE_CREATED:            "monitoring.rule_created",
  MONITORING_RULE_UPDATED:            "monitoring.rule_updated",
  MONITORING_RULE_DELETED:            "monitoring.rule_deleted",
  MONITORING_WATCHER_HEALTH_CHANGED:  "monitoring.watcher_health_changed",

  RECOMMENDATION_GENERATED:  "recommendation.generated",
  RECOMMENDATION_DISMISSED:  "recommendation.dismissed",
  RECOMMENDATION_EXECUTED:   "recommendation.executed",

  ENGINEERING_REPO_ANALYZED:     "engineering.repo_analyzed",
  ENGINEERING_BUILD_COMPLETED:   "engineering.build_completed",
  ENGINEERING_TEST_COMPLETED:    "engineering.test_completed",
  ENGINEERING_SECURITY_SCANNED:  "engineering.security_scanned",
  ENGINEERING_ARCHITECTURE_REVIEWED: "engineering.architecture_reviewed",
  ENGINEERING_RCA_COMPLETED:     "engineering.rca_completed",
  ENGINEERING_PLAN_GENERATED:    "engineering.plan_generated",
  ENGINEERING_CODE_GENERATED:    "engineering.code_generated",
  ENGINEERING_CODE_REVIEWED:     "engineering.code_reviewed",
  ENGINEERING_MISSION_COMPLETED: "engineering.mission_completed",

  WORKSPACE_CREATED:       "workspace.created",
  WORKSPACE_DESTROYED:     "workspace.destroyed",
  WORKSPACE_BRANCH_CHANGED: "workspace.branch_changed",
  WORKSPACE_SNAPSHOT_CAPTURED: "workspace.snapshot_captured",
  WORKSPACE_ARTIFACT_GENERATED: "workspace.artifact_generated",
  WORKSPACE_LOCKED:        "workspace.locked",
  WORKSPACE_RELEASED:      "workspace.released",
  WORKSPACE_REPO_UPDATED:   "workspace.repo_updated",

  PATCH_CREATED:        "patch.created",
  PATCH_UPDATED:        "patch.updated",
  PATCH_VALIDATED:      "patch.validated",
  PATCH_FAILED:         "patch.failed",
  PATCH_ROLLED_BACK:    "patch.rolled_back",
  PATCH_DIFF_GENERATED:  "patch.diff_generated",
  PATCH_DEPENDENCY_UPDATED: "patch.dependency_updated",

  BUILD_CREATED:             "build.created",
  BUILD_STARTED:             "build.started",
  BUILD_COMPLETED:           "build.completed",
  BUILD_FAILED:              "build.failed",
  BUILD_ARTIFACT_GENERATED:  "build.artifact_generated",

  DEPLOY_CREATED:      "deploy.created",
  DEPLOY_STARTED:      "deploy.started",
  DEPLOY_COMPLETED:    "deploy.completed",
  DEPLOY_FAILED:       "deploy.failed",
  DEPLOY_ROLLED_BACK:  "deploy.rolled_back",
  DEPLOY_ENV_UPDATED:  "deploy.env_updated",

  GOVERNANCE_POLICY_CREATED:   "governance.policy_created",
  GOVERNANCE_POLICY_UPDATED:   "governance.policy_updated",
  GOVERNANCE_POLICY_DELETED:   "governance.policy_deleted",
  GOVERNANCE_COMPLIANCE_CHECK: "governance.compliance_check",
  GOVERNANCE_VIOLATION:        "governance.violation",
    GOVERNANCE_AUDIT_RECORDED:   "governance.audit_recorded",

    // ── Execution Engine ──────────────────────────────────────────────────────
    EXECUTION_CREATED:             "execution.created",
    EXECUTION_STARTED:             "execution.started",
    EXECUTION_STAGE_STARTED:       "execution.stage_started",
    EXECUTION_STAGE_COMPLETED:     "execution.stage_completed",
    EXECUTION_STAGE_FAILED:        "execution.stage_failed",
    EXECUTION_CANCELLED:           "execution.cancelled",
    EXECUTION_ROLLED_BACK:         "execution.rolled_back",
    EXECUTION_COMPLETED:           "execution.completed",
    EXECUTION_FAILED:              "execution.failed",
    EXECUTION_RETRIED:             "execution.retried",

    // ── Continuous Cognition ─────────────────────────────────────────────
    COGNITION_OBSERVATION:              "cognition.observation",
    COGNITION_REPO_ADDED:               "cognition.repo_added",
    COGNITION_REPO_REMOVED:             "cognition.repo_removed",
    COGNITION_ARCHITECTURE_CHANGED:     "cognition.architecture_changed",
    COGNITION_ARCHITECTURE_DRIFT:       "cognition.architecture_drift",
    COGNITION_OWNERSHIP_CHANGED:        "cognition.ownership_changed",
    COGNITION_RISK_CHANGED:             "cognition.risk_changed",
    COGNITION_PREDICTION_REFRESHED:     "cognition.prediction_refreshed",
    COGNITION_CONTEXT_REFRESHED:        "cognition.context_refreshed",
    COGNITION_K8S_HEALTH_CHANGED:       "cognition.k8s_health_changed",
    COGNITION_ARGOCD_SYNC_DRIFT:        "cognition.argocd_sync_drift",
    COGNITION_PROMETHEUS_ALERTS:        "cognition.prometheus_alerts",
    COGNITION_LOKI_ERROR_SPIKE:         "cognition.loki_error_spike",
    COGNITION_OTEL_DEGRADATION:         "cognition.otel_degradation",
    COGNITION_KNOWLEDGE_UPDATED:        "cognition.knowledge_updated",
    COGNITION_EXECUTIVE_MISSION:        "cognition.executive_mission",
    COGNITION_CYCLE_COMPLETED:          "cognition.cycle_completed",
    COGNITION_HIGH_RISK:                "cognition.high_risk",
    COGNITION_LOW_RISK:                 "cognition.low_risk",
} as const

type EnterpriseEventType = string

// ============================================================
// Event → Query Key Invalidation Map
// Maps every enterprise event type to the query keys it should
// invalidate, replacing polling-based refetchInterval.
// ============================================================

type InvalidationEntry = {
  keys: readonly unknown[]
  description: string
}

function buildInvalidationMap(): Map<EnterpriseEventType, InvalidationEntry[]> {
  const m = new Map<EnterpriseEventType, InvalidationEntry[]>()

  // ── Mission lifecycle ──────────────────────────────────────
  const missionInvalidations: InvalidationEntry[] = [
    { keys: queryKeys.missions.all, description: "mission list" },
    { keys: queryKeys.missionControl.missions(), description: "mission control" },
    { keys: queryKeys.dashboard.overview(), description: "dashboard overview" },
    { keys: queryKeys.dashboard.timeline(), description: "dashboard timeline" },
    { keys: queryKeys.dashboard.events(), description: "dashboard events" },
    { keys: queryKeys.executiveDashboard.data(), description: "executive dashboard" },
    { keys: queryKeys.analyticsDashboard.data(), description: "analytics dashboard" },
    { keys: ["workspace"], description: "workspace" },
    { keys: ["enterprise-recent-missions"], description: "enterprise graph" },
    { keys: ["enterprise", "graph", "recent-missions"], description: "enterprise-knowledge" },
  ]

  m.set(EnterpriseEventTypes.MISSION_LAUNCHED, missionInvalidations)
  m.set(EnterpriseEventTypes.MISSION_COMPLETED, missionInvalidations)
  m.set(EnterpriseEventTypes.MISSION_FAILED, missionInvalidations)

  m.set(EnterpriseEventTypes.MISSION_STEP, [
    ...missionInvalidations,
    { keys: queryKeys.missionControl.activity(""), description: "mission activity" },
    { keys: queryKeys.missionControl.timeline(""), description: "mission timeline" },
    { keys: queryKeys.dashboard.header(), description: "dashboard header" },
    { keys: ["connectors", "activity"], description: "connector activity" },
  ])

  // ── Approval lifecycle ─────────────────────────────────────
  const approvalInvalidations: InvalidationEntry[] = [
    { keys: queryKeys.governance.all, description: "governance" },
    { keys: ["approval-center"], description: "approval center" },
    { keys: queryKeys.missionControl.missions(), description: "mission control" },
    { keys: queryKeys.dashboard.events(), description: "dashboard events" },
  ]
  m.set(EnterpriseEventTypes.APPROVAL_REQUIRED, approvalInvalidations)
  m.set(EnterpriseEventTypes.APPROVAL_GRANTED, approvalInvalidations)
  m.set(EnterpriseEventTypes.APPROVAL_REJECTED, approvalInvalidations)
  m.set(EnterpriseEventTypes.APPROVAL_TIMED_OUT, approvalInvalidations)

  // ── Connector lifecycle ────────────────────────────────────
  const connectorInvalidations: InvalidationEntry[] = [
    { keys: queryKeys.connectors.all, description: "connectors" },
    { keys: queryKeys.dashboard.overview(), description: "dashboard overview" },
    { keys: queryKeys.analyticsDashboard.data(), description: "analytics dashboard" },
    { keys: queryKeys.executiveDashboard.data(), description: "executive dashboard" },
  ]
  m.set(EnterpriseEventTypes.CONNECTOR_ACTION_STARTED, connectorInvalidations)
  m.set(EnterpriseEventTypes.CONNECTOR_ACTION_COMPLETED, connectorInvalidations)
  m.set(EnterpriseEventTypes.CONNECTOR_ACTION_FAILED, connectorInvalidations)

  // ── Verification lifecycle ─────────────────────────────────
  const verificationInvalidations: InvalidationEntry[] = [
    { keys: queryKeys.governance.audit(), description: "audit log" },
    { keys: ["governance"], description: "governance center" },
    { keys: queryKeys.dashboard.events(), description: "dashboard events" },
  ]
  m.set(EnterpriseEventTypes.VERIFICATION_STARTED, verificationInvalidations)
  m.set(EnterpriseEventTypes.VERIFICATION_COMPLETED, verificationInvalidations)
  m.set(EnterpriseEventTypes.VERIFICATION_FAILED, verificationInvalidations)

  // ── Recovery lifecycle ─────────────────────────────────────
  const recoveryInvalidations: InvalidationEntry[] = [
    { keys: queryKeys.missionControl.missions(), description: "mission control" },
    { keys: queryKeys.dashboard.overview(), description: "dashboard overview" },
    { keys: ["workspace"], description: "workspace" },
    { keys: queryKeys.governance.all, description: "governance" },
  ]
  m.set(EnterpriseEventTypes.RECOVERY_RETRY, recoveryInvalidations)
  m.set(EnterpriseEventTypes.RECOVERY_FALLBACK, recoveryInvalidations)
  m.set(EnterpriseEventTypes.RECOVERY_ROLLBACK, recoveryInvalidations)
  m.set(EnterpriseEventTypes.RECOVERY_ESCALATION, recoveryInvalidations)

  // ── Knowledge Graph ────────────────────────────────────────
  const graphInvalidations: InvalidationEntry[] = [
    { keys: ["enterprise", "graph"], description: "enterprise graph" },
    { keys: ["enterprise-knowledge"], description: "enterprise knowledge center" },
    { keys: ["enterprise", "search"], description: "enterprise search" },
    { keys: ["enterprise-recent-missions"], description: "recent missions" },
  ]
  m.set(EnterpriseEventTypes.GRAPH_ENTITY_CREATED, graphInvalidations)
  m.set(EnterpriseEventTypes.GRAPH_RELATIONSHIP_CREATED, graphInvalidations)
  m.set(EnterpriseEventTypes.GRAPH_MISSION_UPDATED, graphInvalidations)

  // ── Memory ─────────────────────────────────────────────────
  const memoryInvalidations: InvalidationEntry[] = [
    { keys: queryKeys.memory.all, description: "memory" },
    { keys: ["enterprise", "search"], description: "enterprise search" },
  ]
  m.set(EnterpriseEventTypes.MEMORY_STORED, memoryInvalidations)
  m.set(EnterpriseEventTypes.MEMORY_RETRIEVED, memoryInvalidations)

  // ── Analytics ──────────────────────────────────────────────
  const analyticsInvalidations: InvalidationEntry[] = [
    { keys: queryKeys.analyticsDashboard.data(), description: "analytics dashboard" },
    { keys: queryKeys.analytics.all, description: "analytics" },
    { keys: queryKeys.executiveDashboard.data(), description: "executive dashboard" },
    { keys: queryKeys.dashboard.overview(), description: "dashboard overview" },
  ]
  m.set(EnterpriseEventTypes.ANALYTICS_METRICS_UPDATED, analyticsInvalidations)
  m.set(EnterpriseEventTypes.ANALYTICS_KPI_UPDATED, analyticsInvalidations)

  // ── Runtime ────────────────────────────────────────────────
  const runtimeInvalidations: InvalidationEntry[] = [
    { keys: queryKeys.dashboard.resources(), description: "dashboard resources" },
    { keys: queryKeys.runtime.all, description: "runtime status" },
    { keys: queryKeys.executiveDashboard.data(), description: "executive dashboard" },
    { keys: queryKeys.analyticsDashboard.data(), description: "analytics dashboard" },
  ]
  m.set(EnterpriseEventTypes.RUNTIME_METRICS_UPDATED, runtimeInvalidations)
  m.set(EnterpriseEventTypes.RUNTIME_STATE_CHANGED, runtimeInvalidations)

  // ── Learning ─────────────────────────────────────────────────
  const learningInvalidations: InvalidationEntry[] = [
    { keys: ["enterprise-learning"], description: "enterprise learning" },
    { keys: ["enterprise-learning-dashboard"], description: "learning dashboard" },
    { keys: ["enterprise-learning-lessons"], description: "learning lessons" },
    { keys: ["enterprise-learning-best-practices"], description: "learning best practices" },
    { keys: ["enterprise-learning-failure-patterns"], description: "learning failure patterns" },
    { keys: ["enterprise-learning-recovery-patterns"], description: "learning recovery patterns" },
    { keys: ["enterprise-learning-recommendations"], description: "learning recommendations" },
    { keys: ["enterprise-learning-confidence-trends"], description: "learning confidence trends" },
  ]
  m.set(EnterpriseEventTypes.LEARNING_LESSON_DISCOVERED, learningInvalidations)
  m.set(EnterpriseEventTypes.LEARNING_PATTERN_UPDATED, learningInvalidations)
  m.set(EnterpriseEventTypes.LEARNING_RECOMMENDATION_GENERATED, learningInvalidations)
  m.set(EnterpriseEventTypes.LEARNING_ANALYSIS_COMPLETED, learningInvalidations)

  // ── Monitoring ──────────────────────────────────────────────
  const monitoringInvalidations: InvalidationEntry[] = [
    { keys: ["monitoring-watchers"], description: "monitoring watchers" },
    { keys: ["monitoring-rules"], description: "monitoring rules" },
    { keys: ["monitoring-events"], description: "monitoring events" },
    { keys: ["monitoring-missions"], description: "monitoring missions" },
    { keys: ["monitoring-statistics"], description: "monitoring statistics" },
    { keys: ["monitoring-health"], description: "monitoring health" },
    { keys: ["enterprise-learning"], description: "enterprise learning" },
    { keys: ["enterprise-learning-dashboard"], description: "learning dashboard" },
  ]
  m.set(EnterpriseEventTypes.MONITORING_EVENT_DETECTED, monitoringInvalidations)
  m.set(EnterpriseEventTypes.MONITORING_MISSION_CREATED, monitoringInvalidations)
  m.set(EnterpriseEventTypes.MONITORING_RECOVERY_STARTED, monitoringInvalidations)
  m.set(EnterpriseEventTypes.MONITORING_RECOVERY_COMPLETED, monitoringInvalidations)
  m.set(EnterpriseEventTypes.MONITORING_RECOVERY_FAILED, monitoringInvalidations)
  m.set(EnterpriseEventTypes.MONITORING_APPROVAL_REQUIRED, monitoringInvalidations)
  m.set(EnterpriseEventTypes.MONITORING_CLOSED, monitoringInvalidations)
  m.set(EnterpriseEventTypes.MONITORING_RULE_CREATED, monitoringInvalidations)
  m.set(EnterpriseEventTypes.MONITORING_RULE_UPDATED, monitoringInvalidations)
  m.set(EnterpriseEventTypes.MONITORING_RULE_DELETED, monitoringInvalidations)
  m.set(EnterpriseEventTypes.MONITORING_WATCHER_HEALTH_CHANGED, monitoringInvalidations)

  // ── Recommendation ────────────────────────────────────────────
  const recommendationInvalidations: InvalidationEntry[] = [
    { keys: ["recommendations"], description: "recommendations list" },
    { keys: ["recommendations-dashboard"], description: "recommendations dashboard" },
    { keys: ["recommendations-categories"], description: "recommendations categories" },
    { keys: ["recommendations-history"], description: "recommendations history" },
  ]
  m.set(EnterpriseEventTypes.RECOMMENDATION_GENERATED, recommendationInvalidations)
  m.set(EnterpriseEventTypes.RECOMMENDATION_DISMISSED, recommendationInvalidations)
  m.set(EnterpriseEventTypes.RECOMMENDATION_EXECUTED, recommendationInvalidations)

  // ── Engineering ───────────────────────────────────────────────
  const engineeringInvalidations: InvalidationEntry[] = [
    { keys: ["engineering"], description: "engineering data" },
    { keys: ["engineering-agents"], description: "engineering agents" },
    { keys: ["engineering-ecosystems"], description: "engineering ecosystems" },
    { keys: queryKeys.missions.all, description: "mission list" },
    { keys: ["enterprise", "graph"], description: "enterprise graph" },
  ]
  m.set(EnterpriseEventTypes.ENGINEERING_REPO_ANALYZED, engineeringInvalidations)
  m.set(EnterpriseEventTypes.ENGINEERING_BUILD_COMPLETED, engineeringInvalidations)
  m.set(EnterpriseEventTypes.ENGINEERING_TEST_COMPLETED, engineeringInvalidations)
  m.set(EnterpriseEventTypes.ENGINEERING_SECURITY_SCANNED, engineeringInvalidations)
  m.set(EnterpriseEventTypes.ENGINEERING_ARCHITECTURE_REVIEWED, engineeringInvalidations)
  m.set(EnterpriseEventTypes.ENGINEERING_RCA_COMPLETED, engineeringInvalidations)
  m.set(EnterpriseEventTypes.ENGINEERING_PLAN_GENERATED, engineeringInvalidations)
  m.set(EnterpriseEventTypes.ENGINEERING_CODE_GENERATED, engineeringInvalidations)
  m.set(EnterpriseEventTypes.ENGINEERING_CODE_REVIEWED, engineeringInvalidations)
  m.set(EnterpriseEventTypes.ENGINEERING_MISSION_COMPLETED, engineeringInvalidations)

  // ── Workspace ─────────────────────────────────────────────────
  const workspaceInvalidations: InvalidationEntry[] = [
    { keys: ["workspaces"], description: "workspaces list" },
    { keys: ["engineering-repositories"], description: "engineering repositories" },
    { keys: ["engineering-repository-intelligence"], description: "repository intelligence" },
  ]
  m.set(EnterpriseEventTypes.WORKSPACE_CREATED, workspaceInvalidations)
  m.set(EnterpriseEventTypes.WORKSPACE_DESTROYED, workspaceInvalidations)
  m.set(EnterpriseEventTypes.WORKSPACE_BRANCH_CHANGED, workspaceInvalidations)
  m.set(EnterpriseEventTypes.WORKSPACE_SNAPSHOT_CAPTURED, workspaceInvalidations)
  m.set(EnterpriseEventTypes.WORKSPACE_ARTIFACT_GENERATED, workspaceInvalidations)
  m.set(EnterpriseEventTypes.WORKSPACE_LOCKED, workspaceInvalidations)
  m.set(EnterpriseEventTypes.WORKSPACE_RELEASED, workspaceInvalidations)
  m.set(EnterpriseEventTypes.WORKSPACE_REPO_UPDATED, workspaceInvalidations)

  // ── Patch ─────────────────────────────────────────────────────
  const patchInvalidations: InvalidationEntry[] = [
    { keys: ["patches"], description: "patches list" },
    { keys: ["engineering-repositories"], description: "engineering repositories" },
  ]
  m.set(EnterpriseEventTypes.PATCH_CREATED, patchInvalidations)
  m.set(EnterpriseEventTypes.PATCH_UPDATED, patchInvalidations)
  m.set(EnterpriseEventTypes.PATCH_VALIDATED, patchInvalidations)
  m.set(EnterpriseEventTypes.PATCH_FAILED, patchInvalidations)
  m.set(EnterpriseEventTypes.PATCH_ROLLED_BACK, patchInvalidations)
  m.set(EnterpriseEventTypes.PATCH_DIFF_GENERATED, patchInvalidations)
  m.set(EnterpriseEventTypes.PATCH_DEPENDENCY_UPDATED, patchInvalidations)

  // ── Build ──────────────────────────────────────────────────────
  const buildInvalidations: InvalidationEntry[] = [
    { keys: ["builds"], description: "builds list" },
  ]
  m.set(EnterpriseEventTypes.BUILD_CREATED, buildInvalidations)
  m.set(EnterpriseEventTypes.BUILD_STARTED, buildInvalidations)
  m.set(EnterpriseEventTypes.BUILD_COMPLETED, buildInvalidations)
  m.set(EnterpriseEventTypes.BUILD_FAILED, buildInvalidations)
  m.set(EnterpriseEventTypes.BUILD_ARTIFACT_GENERATED, buildInvalidations)

  // ── Deploy ─────────────────────────────────────────────────────
  const deployInvalidations: InvalidationEntry[] = [
    { keys: ["deployments"], description: "deployments list" },
    { keys: ["environments"], description: "environments list" },
  ]
  m.set(EnterpriseEventTypes.DEPLOY_CREATED, deployInvalidations)
  m.set(EnterpriseEventTypes.DEPLOY_STARTED, deployInvalidations)
  m.set(EnterpriseEventTypes.DEPLOY_COMPLETED, deployInvalidations)
  m.set(EnterpriseEventTypes.DEPLOY_FAILED, deployInvalidations)
  m.set(EnterpriseEventTypes.DEPLOY_ROLLED_BACK, deployInvalidations)
  m.set(EnterpriseEventTypes.DEPLOY_ENV_UPDATED, deployInvalidations)

  // ── Governance ─────────────────────────────────────────────────
  const governanceInvalidations: InvalidationEntry[] = [
    { keys: ["policies"], description: "policies list" },
    { keys: ["governance-dashboard"], description: "governance dashboard" },
    { keys: ["compliance"], description: "compliance checks" },
    { keys: ["audit-log"], description: "audit log" },
  ]
  m.set(EnterpriseEventTypes.GOVERNANCE_POLICY_CREATED, governanceInvalidations)
  m.set(EnterpriseEventTypes.GOVERNANCE_POLICY_UPDATED, governanceInvalidations)
  m.set(EnterpriseEventTypes.GOVERNANCE_POLICY_DELETED, governanceInvalidations)
  m.set(EnterpriseEventTypes.GOVERNANCE_COMPLIANCE_CHECK, governanceInvalidations)
  m.set(EnterpriseEventTypes.GOVERNANCE_VIOLATION, governanceInvalidations)
  m.set(EnterpriseEventTypes.GOVERNANCE_AUDIT_RECORDED, governanceInvalidations)

  // ── Execution Engine ────────────────────────────────────────────────
  const executionInvalidations: InvalidationEntry[] = [
    { keys: queryKeys.execution.all, description: "execution list" },
    { keys: queryKeys.execution.dashboard(), description: "execution dashboard" },
    { keys: queryKeys.execution.detail(""), description: "execution detail" },
    { keys: queryKeys.dashboard.overview(), description: "dashboard overview" },
    { keys: queryKeys.dashboard.events(), description: "dashboard events" },
    { keys: queryKeys.executiveDashboard.data(), description: "executive dashboard" },
    { keys: ["workspaces"], description: "workspaces" },
    { keys: ["patches"], description: "patches" },
    { keys: ["deployments"], description: "deployments" },
    { keys: ["builds"], description: "builds" },
  ]
  m.set(EnterpriseEventTypes.EXECUTION_CREATED, executionInvalidations)
  m.set(EnterpriseEventTypes.EXECUTION_STARTED, executionInvalidations)
  m.set(EnterpriseEventTypes.EXECUTION_STAGE_STARTED, executionInvalidations)
  m.set(EnterpriseEventTypes.EXECUTION_STAGE_COMPLETED, executionInvalidations)
  m.set(EnterpriseEventTypes.EXECUTION_STAGE_FAILED, executionInvalidations)
  m.set(EnterpriseEventTypes.EXECUTION_CANCELLED, executionInvalidations)
  m.set(EnterpriseEventTypes.EXECUTION_ROLLED_BACK, executionInvalidations)
  m.set(EnterpriseEventTypes.EXECUTION_COMPLETED, executionInvalidations)
  m.set(EnterpriseEventTypes.EXECUTION_FAILED, executionInvalidations)
  m.set(EnterpriseEventTypes.EXECUTION_RETRIED, executionInvalidations)

  // ── Continuous Cognition ──────────────────────────────────────────────
  const cognitionInvalidations: InvalidationEntry[] = [
    { keys: queryKeys.enterpriseCognition.all, description: "enterprise cognition" },
    { keys: queryKeys.dashboard.overview(), description: "dashboard overview" },
    { keys: queryKeys.dashboard.events(), description: "dashboard events" },
    { keys: queryKeys.executiveDashboard.data(), description: "executive dashboard" },
  ]
  m.set(EnterpriseEventTypes.COGNITION_OBSERVATION, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_REPO_ADDED, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_REPO_REMOVED, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_ARCHITECTURE_CHANGED, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_ARCHITECTURE_DRIFT, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_OWNERSHIP_CHANGED, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_RISK_CHANGED, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_PREDICTION_REFRESHED, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_CONTEXT_REFRESHED, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_K8S_HEALTH_CHANGED, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_ARGOCD_SYNC_DRIFT, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_PROMETHEUS_ALERTS, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_LOKI_ERROR_SPIKE, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_OTEL_DEGRADATION, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_KNOWLEDGE_UPDATED, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_EXECUTIVE_MISSION, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_CYCLE_COMPLETED, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_HIGH_RISK, cognitionInvalidations)
  m.set(EnterpriseEventTypes.COGNITION_LOW_RISK, cognitionInvalidations)

  return m
}

const invalidationMap = buildInvalidationMap()

// Also handle legacy event types that may come from non-upgraded services
const LEGACY_EVENT_MAP: Record<string, EnterpriseEventType[]> = {
  cognition_event:             [EnterpriseEventTypes.MEMORY_STORED],
  execution_event:             [EnterpriseEventTypes.MISSION_STEP],
  orchestration_update:        [EnterpriseEventTypes.MISSION_STEP],
  agent_status_update:         [EnterpriseEventTypes.RUNTIME_STATE_CHANGED],
  runtime_metrics:             [EnterpriseEventTypes.RUNTIME_METRICS_UPDATED],
  health_update:               [EnterpriseEventTypes.RUNTIME_STATE_CHANGED],
  mission_start:               [EnterpriseEventTypes.MISSION_LAUNCHED],
  mission_complete:            [EnterpriseEventTypes.MISSION_COMPLETED],
  mission_failed:              [EnterpriseEventTypes.MISSION_FAILED],
  execution_state_update:      [EnterpriseEventTypes.MISSION_STEP],
  pipeline_event:              [EnterpriseEventTypes.MISSION_STEP],
}

// ============================================================
// Hook
// ============================================================

export interface EnterpriseEventCallbacks {
  onMissionEvent?:      (msg: WSMessage) => void
  onConnectorEvent?:    (msg: WSMessage) => void
  onApprovalEvent?:     (msg: WSMessage) => void
  onVerificationEvent?: (msg: WSMessage) => void
  onRecoveryEvent?:     (msg: WSMessage) => void
  onGraphEvent?:        (msg: WSMessage) => void
  onMemoryEvent?:       (msg: WSMessage) => void
  onAnalyticsEvent?:    (msg: WSMessage) => void
  onRuntimeEvent?:      (msg: WSMessage) => void
  onLearningEvent?:     (msg: WSMessage) => void
  onMonitoringEvent?:   (msg: WSMessage) => void
  onRecommendationEvent?: (msg: WSMessage) => void
  onEngineeringEvent?:    (msg: WSMessage) => void
  onWorkspaceEvent?:      (msg: WSMessage) => void
  onCognitionEvent?:      (msg: WSMessage) => void
  onExecutionEvent?:      (msg: WSMessage) => void
}

export function useEnterpriseEventStream(enabled = true, callbacks?: EnterpriseEventCallbacks) {
  const queryClient = useQueryClient()
  const subscribed = useRef(false)
  const callbacksRef = useRef(callbacks)
  // eslint-disable-next-line react-hooks/refs
  callbacksRef.current = callbacks

  const handleMessage = useCallback((msg: WSMessage) => {
    const eventType = msg.type ?? msg.event_type ?? msg._topic ?? ""
    if (!eventType) return

    // Resolve event type — check direct map, then legacy map
    let resolvedTypes: EnterpriseEventType[] | undefined

    if (invalidationMap.has(eventType)) {
      resolvedTypes = [eventType]
    } else if (LEGACY_EVENT_MAP[eventType]) {
      resolvedTypes = LEGACY_EVENT_MAP[eventType]
    }

    if (resolvedTypes) {
      // Invalidate all query keys for the resolved event types
      for (const et of resolvedTypes) {
        const entries = invalidationMap.get(et)
        if (entries) {
          for (const entry of entries) {
            queryClient.invalidateQueries({ queryKey: entry.keys as readonly unknown[] })
          }
        }
      }

      // Fire domain-specific callback
      if (callbacksRef.current) {
        if (eventType.startsWith("mission.") || eventType.startsWith("enterprise_mission")) {
          callbacksRef.current.onMissionEvent?.(msg)
        } else if (eventType.startsWith("connector.")) {
          callbacksRef.current.onConnectorEvent?.(msg)
        } else if (eventType.startsWith("approval.") || eventType.startsWith("enterprise_approval")) {
          callbacksRef.current.onApprovalEvent?.(msg)
        } else if (eventType.startsWith("verification.")) {
          callbacksRef.current.onVerificationEvent?.(msg)
        } else if (eventType.startsWith("recovery.") || eventType.startsWith("enterprise_") && (eventType.includes("rollback") || eventType.includes("escalation"))) {
          callbacksRef.current.onRecoveryEvent?.(msg)
        } else if (eventType.startsWith("graph.")) {
          callbacksRef.current.onGraphEvent?.(msg)
        } else if (eventType.startsWith("memory.")) {
          callbacksRef.current.onMemoryEvent?.(msg)
        } else if (eventType.startsWith("analytics.")) {
          callbacksRef.current.onAnalyticsEvent?.(msg)
        } else if (eventType.startsWith("runtime.")) {
          callbacksRef.current.onRuntimeEvent?.(msg)
        } else if (eventType.startsWith("learning.")) {
          callbacksRef.current.onLearningEvent?.(msg)
        } else if (eventType.startsWith("monitoring.")) {
          callbacksRef.current.onMonitoringEvent?.(msg)
        } else if (eventType.startsWith("recommendation.")) {
          callbacksRef.current.onRecommendationEvent?.(msg)
        } else if (eventType.startsWith("engineering.")) {
          callbacksRef.current.onEngineeringEvent?.(msg)
        } else if (eventType.startsWith("workspace.")) {
          callbacksRef.current.onWorkspaceEvent?.(msg)
        } else if (eventType.startsWith("execution.")) {
          callbacksRef.current.onExecutionEvent?.(msg)
        } else if (eventType.startsWith("cognition.")) {
          callbacksRef.current.onCognitionEvent?.(msg)
        }
      }
    }
  }, [queryClient])

  useEffect(() => {
    if (!enabled || subscribed.current) return
    subscribed.current = true

    wsService.connect()
    const unsubscribe = wsService.subscribe(handleMessage)

    return () => {
      unsubscribe()
      subscribed.current = false
    }
  }, [enabled, handleMessage])
}

// ============================================================
// Per-domain convenience hooks
// These wrap useEnterpriseEventStream with domain-specific
// callbacks so individual pages can react to events without
// knowing the full invalidation map.
// ============================================================

export function useMissionEventStream(onMissionEvent?: (msg: WSMessage) => void) {
  useEnterpriseEventStream(true, { onMissionEvent })
}

export function useConnectorEventStream(onConnectorEvent?: (msg: WSMessage) => void) {
  useEnterpriseEventStream(true, { onConnectorEvent })
}

export function useApprovalEventStream(onApprovalEvent?: (msg: WSMessage) => void) {
  useEnterpriseEventStream(true, { onApprovalEvent })
}

export function useGraphEventStream(onGraphEvent?: (msg: WSMessage) => void) {
  useEnterpriseEventStream(true, { onGraphEvent })
}

export function useExecutionEventStream(onExecutionEvent?: (msg: WSMessage) => void) {
  useEnterpriseEventStream(true, { onExecutionEvent })
}
