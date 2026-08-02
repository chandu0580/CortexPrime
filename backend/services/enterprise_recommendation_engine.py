"""
Enterprise Recommendation Engine — continuously analyzes the entire platform
and proactively recommends actions to operators and executives.

Combines signals from:
  - Mission outcomes (ReplayStore, Knowledge Graph)
  - Connector health (WatcherManager)
  - Verification failures (AuditLogger, EventBus)
  - Approval bottlenecks (ApprovalQueue)
  - Workflow delays (RuntimeMetrics, EventBus)
  - Runtime metrics (RuntimeMetrics)
  - Infrastructure health (EventBus, connection states)
  - Learning insights (EnterpriseLearningEngine)
  - Cost metrics (CostEngine)
  - Knowledge graph relationships (EnterpriseGraphService)
  - Governance / audit patterns (AuditLogger)

Every recommendation includes an evidence chain linking back to source systems,
and optional one-click actions that reuse existing APIs.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.events.enterprise_event_types import EnterpriseEventTypes as EET
from backend.events.event_bus import event_bus
from backend.events.event_models import CognitionEvent

log = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_RECOMMENDATIONS_FILE = _DATA_DIR / "recommendations.json"

RECOMMENDATION_CATEGORIES = [
    "operations", "security", "reliability", "performance",
    "connector_health", "workflow_optimization", "cost_optimization",
    "knowledge", "learning", "mission_recovery",
    "governance", "compliance", "infrastructure", "executive_strategy",
]

PRIORITY_LEVELS = ["low", "medium", "high", "critical"]
RISK_LEVELS = ["low", "medium", "high", "critical"]

# Maps a caller-supplied context string (see generate()) to one of
# RECOMMENDATION_CATEGORIES. Unrecognized contexts fall back to
# "operations" — generate() is meant to stay usable by any future caller,
# not just root_cause_analysis (its first real caller).
_CONTEXT_CATEGORIES: Dict[str, str] = {
    "root_cause_analysis": "reliability",
}

RECOMMENDATION_EVENT_GENERATED = "recommendation.generated"
RECOMMENDATION_DISMISSED = "recommendation.dismissed"
RECOMMENDATION_EXECUTED = "recommendation.executed"


class RecommendationAction:
    """An optional action that can be executed for a recommendation."""

    def __init__(
        self,
        action_type: str,
        label: str,
        endpoint: str,
        method: str = "POST",
        description: str = "",
    ) -> None:
        self.action_type = action_type
        self.label = label
        self.endpoint = endpoint
        self.method = method
        self.description = description

    def to_dict(self) -> Dict[str, str]:
        return {
            "action_type": self.action_type,
            "label": self.label,
            "endpoint": self.endpoint,
            "method": self.method,
            "description": self.description,
        }


class Recommendation:
    """A single actionable recommendation with full evidence chain."""

    def __init__(
        self,
        category: str,
        title: str,
        description: str,
        reason: str,
        evidence: Optional[List[Dict[str, Any]]] = None,
        confidence: float = 0.5,
        risk: str = "medium",
        priority: str = "medium",
        estimated_impact: str = "",
        estimated_cost_savings: str = "",
        estimated_time_savings: str = "",
        related_mission: Optional[str] = None,
        related_connector: Optional[str] = None,
        related_workflow: Optional[str] = None,
        learning_references: Optional[List[Dict[str, Any]]] = None,
        replay_references: Optional[List[Dict[str, Any]]] = None,
        knowledge_graph_references: Optional[List[Dict[str, Any]]] = None,
        verification_references: Optional[List[Dict[str, Any]]] = None,
        actions: Optional[List[RecommendationAction]] = None,
        source: str = "auto",
        recommendation_id: Optional[str] = None,
    ) -> None:
        self.id = recommendation_id or str(uuid.uuid4())
        self.category = category
        self.title = title
        self.description = description
        self.reason = reason
        self.evidence = evidence or []
        self.confidence = confidence
        self.risk = risk
        self.priority = priority
        self.estimated_impact = estimated_impact
        self.estimated_cost_savings = estimated_cost_savings
        self.estimated_time_savings = estimated_time_savings
        self.related_mission = related_mission
        self.related_connector = related_connector
        self.related_workflow = related_workflow
        self.learning_references = learning_references or []
        self.replay_references = replay_references or []
        self.knowledge_graph_references = knowledge_graph_references or []
        self.verification_references = verification_references or []
        self.actions = actions or []
        self.source = source
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.dismissed = False
        self.dismissed_at: Optional[str] = None
        self.executed = False
        self.executed_at: Optional[str] = None

    def dismiss(self) -> None:
        self.dismissed = True
        self.dismissed_at = datetime.now(timezone.utc).isoformat()

    def mark_executed(self) -> None:
        self.executed = True
        self.executed_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "reason": self.reason,
            "evidence": self.evidence,
            "confidence": self.confidence,
            "risk": self.risk,
            "priority": self.priority,
            "estimated_impact": self.estimated_impact,
            "estimated_cost_savings": self.estimated_cost_savings,
            "estimated_time_savings": self.estimated_time_savings,
            "related_mission": self.related_mission,
            "related_connector": self.related_connector,
            "related_workflow": self.related_workflow,
            "learning_references": self.learning_references,
            "replay_references": self.replay_references,
            "knowledge_graph_references": self.knowledge_graph_references,
            "verification_references": self.verification_references,
            "actions": [a.to_dict() for a in self.actions],
            "source": self.source,
            "created_at": self.created_at,
            "dismissed": self.dismissed,
            "dismissed_at": self.dismissed_at,
            "executed": self.executed,
            "executed_at": self.executed_at,
        }


class EnterpriseRecommendationEngine:
    """
    Continuous recommendation engine that scans all platform signals and
    generates categorized, evidence-backed recommendations.

    Architecture:
      1. Event-driven — subscribes to EventBus for real-time triggers
      2. Periodic scan — full analysis every SCAN_INTERVAL seconds
      3. Analyzers — modular scan methods per category/signal
      4. Deduplication — prevents identical recommendations
      5. Persistence — recommendations saved to JSON file
    """

    SCAN_INTERVAL = 120

    def __init__(self) -> None:
        self._initialized = False
        self._recommendations: Dict[str, Recommendation] = {}
        self._persisted_ids: set[str] = set()
        self._scan_task: Optional[asyncio.Task] = None
        self._last_full_scan: Optional[str] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._load_persisted()
        event_bus.subscribe(self._on_event)
        self._scan_task = asyncio.create_task(self._periodic_scan())
        self._initialized = True
        log.info("EnterpriseRecommendationEngine initialized — %d persisted recommendations loaded", len(self._recommendations))

    async def shutdown(self) -> None:
        if self._scan_task:
            self._scan_task.cancel()
            try:
                await self._scan_task
            except asyncio.CancelledError:
                pass
        self._persist()
        log.info("EnterpriseRecommendationEngine shutdown — %d recommendations persisted", len(self._recommendations))

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------

    async def _on_event(self, event: CognitionEvent) -> None:
        event_type = event.event_type or ""
        try:
            if event_type in (EET.MISSION_COMPLETED, EET.MISSION_FAILED):
                await self._analyze_mission_outcome(event)
            elif event_type == EET.CONNECTOR_ACTION_FAILED:
                await self._analyze_connector_failure(event)
            elif event_type == EET.VERIFICATION_FAILED:
                await self._analyze_verification_failure(event)
            elif event_type in (EET.APPROVAL_REQUIRED, EET.APPROVAL_TIMED_OUT):
                await self._analyze_approval_event(event)
            elif event_type.startswith("monitoring."):
                await self._analyze_monitoring_event(event)
            elif event_type.startswith("learning."):
                await self._analyze_learning_event(event)
            elif event_type == EET.RUNTIME_HEALTH_UPDATED:
                await self._analyze_runtime_health(event)
        except Exception as exc:
            log.debug("Recommendation engine event handler error: %s", exc)

    # ------------------------------------------------------------------
    # Periodic full scan
    # ------------------------------------------------------------------

    async def _periodic_scan(self) -> None:
        while True:
            try:
                await asyncio.sleep(self.SCAN_INTERVAL)
                await self.full_scan()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.warning("Recommendation periodic scan error: %s", exc)

    async def full_scan(self) -> int:
        """Run all analyzers and return count of new recommendations."""
        before = len(self._recommendations)
        await self._scan_mission_trends()
        await self._scan_connector_health()
        await self._scan_verification_trends()
        await self._scan_approval_bottlenecks()
        await self._scan_runtime_metrics()
        await self._scan_cost_metrics()
        await self._scan_governance()
        await self._scan_workflows()
        await self._scan_infrastructure()
        await self._scan_learning_insights()
        self._last_full_scan = datetime.now(timezone.utc).isoformat()
        self._persist()
        new_count = len(self._recommendations) - before
        if new_count > 0:
            await self._emit_recommendation_event(f"Full scan generated {new_count} new recommendations")
        return new_count

    # ------------------------------------------------------------------
    # Analyzers
    # ------------------------------------------------------------------

    async def _analyze_mission_outcome(self, event: CognitionEvent) -> None:
        execution_id = event.execution_id or event.payload.get("execution_id", "")
        if not execution_id:
            return
        related = await self._get_related_missions(execution_id, 10)
        failures = [m for m in related if m.get("status") == "failed"]
        if len(failures) >= 3:
            self._add_if_new(Recommendation(
                category="reliability",
                title=f"Repeated mission failures detected ({len(failures)} in recent missions)",
                description=f"Execution {execution_id[:12]} and {len(failures) - 1} other recent missions have failed. Review failure patterns and consider adjusting retry policies.",
                reason=f"{len(failures)} of {len(related)} recent missions failed",
                evidence=[{"source": "replay_store", "event_type": event.event_type or "", "execution_id": execution_id, "detail": event.message}],
                confidence=min(0.9, 0.3 + (len(failures) * 0.15)),
                risk="high" if len(failures) >= 5 else "medium",
                priority="high" if len(failures) >= 5 else "medium",
                related_mission=execution_id,
                replay_references=[{"execution_id": execution_id}],
                actions=[
                    RecommendationAction("open_replay", "Open Replay", f"/api/enterprise-replay/{execution_id}", "GET"),
                    RecommendationAction("open_explainability", "Open Explainability", f"/api/explainability/missions/{execution_id}", "GET"),
                    RecommendationAction("retry_mission", "Retry Mission", f"/api/enterprise/missions/retry/{execution_id}", "POST"),
                ],
            ))
            await self._emit_recommendation_event(f"Failure trend: {len(failures)} failures")

    async def _analyze_connector_failure(self, event: CognitionEvent) -> None:
        connector = event.payload.get("connector", event.agent)
        operation = event.payload.get("operation", "unknown")
        recent = await self._get_recent_connector_failures(connector, 5)
        if len(recent) >= 3:
            self._add_if_new(Recommendation(
                category="connector_health",
                title=f"Connector {connector} experiencing repeated failures ({len(recent)} in recent events)",
                description=f"The {connector} connector has failed {len(recent)} times recently (operation: {operation}). Check credentials, API rate limits, and network connectivity.",
                reason=f"{len(recent)} recent failures on {connector}.{operation}",
                evidence=[{"source": "event_bus", "connector": connector, "operation": operation, "detail": event.message}],
                confidence=0.85,
                risk="high" if len(recent) >= 5 else "medium",
                priority="high" if len(recent) >= 5 else "medium",
                related_connector=connector,
                actions=[
                    RecommendationAction("reconnect_connector", "Reconnect", f"/api/connectors/{connector}/reconnect", "POST"),
                    RecommendationAction("notify_teams", "Notify Team", f"/api/connectors/{connector}/notify", "POST"),
                ],
            ))
            await self._emit_recommendation_event(f"Connector issue: {connector} {len(recent)} failures")

    async def _analyze_verification_failure(self, event: CognitionEvent) -> None:
        connector = event.payload.get("connector", event.agent)
        operation = event.payload.get("operation", "unknown")
        self._add_if_new(Recommendation(
            category="reliability",
            title=f"Verification failed for {connector}.{operation}",
            description=f"Verification check failed on {connector}/{operation}. The operation completed but the result could not be verified. Manual review recommended.",
            reason=f"Verification failure for {connector}.{operation}",
            evidence=[{"source": "verification", "connector": connector, "operation": operation, "detail": event.message}],
            confidence=0.7,
            risk="medium",
            priority="medium",
            related_connector=connector,
            verification_references=[{"connector": connector, "operation": operation}],
            actions=[
                RecommendationAction("run_verification", "Re-run Verification", f"/api/verification/{connector}/{operation}/retry", "POST"),
            ],
        ))
        await self._emit_recommendation_event(f"Verification failure: {connector}.{operation}")

    async def _analyze_approval_event(self, event: CognitionEvent) -> None:
        is_timeout = event.event_type == EET.APPROVAL_TIMED_OUT
        execution_id = event.execution_id or event.payload.get("execution_id", "")
        if is_timeout:
            self._add_if_new(Recommendation(
                category="governance",
                title=f"Approval timed out for execution {execution_id[:12] if execution_id else 'unknown'}",
                description="An approval request timed out, which may block mission progress. Consider reducing approval timeout or assigning backup approvers.",
                reason="Approval request timed out without decision",
                evidence=[{"source": "approval_queue", "event_type": event.event_type or "", "detail": event.message, "execution_id": execution_id}],
                confidence=0.9,
                risk="medium",
                priority="high",
                related_mission=execution_id,
                actions=[
                    RecommendationAction("create_approval", "Re-request Approval", "/api/approval-center/requests", "POST"),
                ],
            ))
            await self._emit_recommendation_event(f"Approval timeout: {execution_id[:12] if execution_id else 'unknown'}")

        pending = await self._get_approval_queue_depth()
        if pending > 5:
            self._add_if_new(Recommendation(
                category="governance",
                title=f"Approval backlog: {pending} requests pending",
                description=f"There are {pending} pending approval requests. Consider adding approvers or streamlining approval policies to reduce bottlenecks.",
                reason=f"{pending} pending approvals in queue",
                evidence=[{"source": "approval_queue", "pending_count": pending}],
                confidence=0.8,
                risk="low" if pending < 10 else "medium",
                priority="medium" if pending < 10 else "high",
                actions=[
                    RecommendationAction("review_approvals", "Review Approvals", "/api/approval-center/requests", "GET"),
                ],
            ))

    async def _analyze_monitoring_event(self, event: CognitionEvent) -> None:
        connector = event.payload.get("connector", "")
        severity = event.payload.get("severity", "medium")
        if severity in ("high", "critical") and connector:
            self._add_if_new(Recommendation(
                category="operations",
                title=f"Critical monitoring event from {connector}: {event.message[:80]}",
                description=f"A {severity}-severity monitoring event was detected: {event.message}. Immediate attention recommended.",
                reason=f"{severity} monitoring event from {connector}",
                evidence=[{"source": "monitoring", "connector": connector, "severity": severity, "detail": event.message}],
                confidence=0.9,
                risk=severity,
                priority=severity,
                related_connector=connector,
                actions=[
                    RecommendationAction("launch_recovery", "Launch Recovery", "/api/monitoring/recover", "POST"),
                    RecommendationAction("open_jira", "Open Jira Issue", "/api/connectors/jira/create", "POST"),
                ],
            ))
            await self._emit_recommendation_event(f"Critical monitoring: {connector}")

    async def _analyze_learning_event(self, event: CognitionEvent) -> None:
        if event.event_type == EET.LEARNING_LESSON_DISCOVERED:
            self._add_if_new(Recommendation(
                category="learning",
                title=f"New lesson discovered: {event.message[:80]}",
                description="The learning engine discovered a new lesson from recent mission outcomes. Review and apply to future missions.",
                reason="New lesson extracted from mission data",
                evidence=[{"source": "learning_engine", "event_type": event.event_type or "", "detail": event.message}],
                confidence=0.75,
                risk="low",
                priority="low",
                learning_references=[{"type": "lesson", "summary": event.message}],
            ))

    async def _analyze_runtime_health(self, event: CognitionEvent) -> None:
        payload = event.payload or {}
        metrics = payload.get("metrics", {})
        error_rate = metrics.get("error_rate", 0)
        if isinstance(error_rate, (int, float)) and error_rate > 0.1:
            self._add_if_new(Recommendation(
                category="performance",
                title=f"High runtime error rate ({error_rate * 100:.0f}%)",
                description=f"The runtime error rate is {error_rate * 100:.0f}%, which exceeds the 10% threshold. Investigate recent executions for root cause.",
                reason=f"Error rate {error_rate * 100:.0f}% exceeds 10% threshold",
                evidence=[{"source": "runtime_metrics", "error_rate": error_rate, "detail": event.message}],
                confidence=0.8,
                risk="high",
                priority="high",
                actions=[
                    RecommendationAction("restart_runtime", "Restart Runtime", "/api/runtime/restart", "POST"),
                ],
            ))

    async def _scan_mission_trends(self) -> None:
        try:
            from backend.services.enterprise_graph_service import enterprise_graph

            missions_raw = await enterprise_graph.list_recent_missions(limit=50)
            missions = missions_raw if isinstance(missions_raw, list) else missions_raw.get("missions", [])
            completed = [m for m in missions if m.get("status") == "completed"]
            failed = [m for m in missions if m.get("status") == "failed"]

            if len(missions) >= 10:
                fail_rate = len(failed) / len(missions)
                if fail_rate > 0.3:
                    self._add_if_new(Recommendation(
                        category="reliability",
                        title=f"High mission failure rate ({fail_rate * 100:.0f}%)",
                        description=f"Of the last {len(missions)} missions, {len(failed)} failed ({fail_rate * 100:.0f}%). This exceeds the 30% threshold. Review failure patterns and update recovery strategies.",
                        reason=f"{len(failed)} failures out of {len(missions)} recent missions ({fail_rate * 100:.0f}%)",
                        evidence=[{"source": "knowledge_graph", "total_missions": len(missions), "failed": len(failed), "completed": len(completed)}],
                        confidence=min(0.95, 0.5 + fail_rate),
                        risk="high" if fail_rate > 0.5 else "medium",
                        priority="high" if fail_rate > 0.5 else "medium",
                        actions=[
                            RecommendationAction("open_learning", "View Failure Patterns", "/api/enterprise/learning/failure-patterns", "GET"),
                        ],
                    ))

                if len(completed) >= 5 and fail_rate < 0.1:
                    self._add_if_new(Recommendation(
                        category="executive_strategy",
                        title=f"Strong mission success rate ({len(completed)}/{len(missions)} completed)",
                        description=f"Mission execution is performing well with a {fail_rate * 100:.0f}% failure rate over the last {len(missions)} missions. Consider expanding automation to additional workflows.",
                        reason=f"{(1 - fail_rate) * 100:.0f}% success rate across {len(missions)} missions",
                        evidence=[{"source": "knowledge_graph", "total_missions": len(missions), "completed": len(completed)}],
                        confidence=0.7,
                        risk="low",
                        priority="low",
                        estimated_impact="Expanded automation coverage",
                    ))
        except Exception as exc:
            log.debug("Mission trend scan skipped: %s", exc)

    async def _scan_connector_health(self) -> None:
        try:
            from backend.services.enterprise_watchers import watcher_manager

            health = watcher_manager.get_all_health()
            unhealthy = [name for name, h in health.items() if h.get("status") != "healthy"]
            for conn in unhealthy[:3]:
                self._add_if_new(Recommendation(
                    category="connector_health",
                    title=f"Connector {conn} is unhealthy",
                    description=f"The {conn} watcher reports unhealthy status. This connector may be unavailable or experiencing issues. Check credentials and API access.",
                    reason=f"Watcher health check failed for {conn}",
                    evidence=[{"source": "watcher_manager", "connector": conn, "health": health.get(conn, {})}],
                    confidence=0.9,
                    risk="high",
                    priority="high",
                    related_connector=conn,
                    actions=[
                        RecommendationAction("reconnect_connector", "Reconnect", f"/api/connectors/{conn}/reconnect", "POST"),
                        RecommendationAction("notify_teams", "Notify Team", f"/api/connectors/{conn}/notify", "POST"),
                    ],
                ))
        except Exception as exc:
            log.debug("Connector health scan skipped: %s", exc)

    async def _scan_verification_trends(self) -> None:
        try:
            from backend.safety.audit_logger import audit_logger

            recent = audit_logger.get_recent(limit=100)
            if not isinstance(recent, list):
                recent = recent.get("entries", []) if isinstance(recent, dict) else []
            verifications = [r for r in recent if "verification" in str(r.get("action", "")).lower()]
            failed_verifications = [v for v in verifications if v.get("outcome") == "failed"]
            if len(failed_verifications) >= 5:
                self._add_if_new(Recommendation(
                    category="reliability",
                    title=f"Multiple verification failures ({len(failed_verifications)} in recent audit log)",
                    description=f"There have been {len(failed_verifications)} verification failures in recent audit records. Review verification procedures and connector configurations.",
                    reason=f"{len(failed_verifications)} failed verifications detected",
                    evidence=[{"source": "audit_logger", "total_verifications": len(verifications), "failed": len(failed_verifications)}],
                    confidence=0.8,
                    risk="medium",
                    priority="medium",
                ))
        except Exception as exc:
            log.debug("Verification trend scan skipped: %s", exc)

    async def _scan_approval_bottlenecks(self) -> None:
        try:
            from backend.safety.approval_queue import approval_queue

            pending = approval_queue.get_pending_count() if hasattr(approval_queue, "get_pending_count") else 0
            if pending > 10:
                self._add_if_new(Recommendation(
                    category="governance",
                    title=f"Approval queue overloaded: {pending} pending",
                    description=f"The approval queue has {pending} pending requests. This may indicate insufficient approver capacity or overly restrictive policies.",
                    reason=f"{pending} pending requests in approval queue",
                    evidence=[{"source": "approval_queue", "pending_count": pending}],
                    confidence=0.85,
                    risk="medium" if pending < 20 else "high",
                    priority="medium" if pending < 20 else "high",
                    actions=[
                        RecommendationAction("review_approvals", "Review Approvals", "/api/approval-center/requests", "GET"),
                    ],
                ))
        except Exception as exc:
            log.debug("Approval bottleneck scan skipped: %s", exc)

    async def _scan_runtime_metrics(self) -> None:
        try:
            from backend.runtime.runtime_metrics import runtime_metrics

            metrics = runtime_metrics.export_metrics()
            total = metrics.get("total_executions", 0)
            failed = metrics.get("failed_executions", 0)
            if total > 0:
                fail_rate = failed / total
                if fail_rate > 0.25:
                    self._add_if_new(Recommendation(
                        category="performance",
                        title=f"Runtime failure rate elevated ({fail_rate * 100:.0f}%)",
                        description=f"Runtime metrics show {failed} failed executions out of {total} total ({fail_rate * 100:.0f}%). Investigate recurring failures.",
                        reason=f"{failed} failures out of {total} executions ({fail_rate * 100:.0f}%)",
                        evidence=[{"source": "runtime_metrics", "total_executions": total, "failed": failed}],
                        confidence=0.85,
                        risk="high" if fail_rate > 0.4 else "medium",
                        priority="high" if fail_rate > 0.4 else "medium",
                        actions=[
                            RecommendationAction("restart_runtime", "Restart Runtime", "/api/runtime/restart", "POST"),
                        ],
                    ))
        except Exception as exc:
            log.debug("Runtime metrics scan skipped: %s", exc)

    async def _scan_cost_metrics(self) -> None:
        try:
            from backend.analytics.cost_engine import cost_engine

            cost_data = cost_engine.get_summary() if hasattr(cost_engine, "get_summary") else {}
            if not isinstance(cost_data, dict):
                cost_data = {}
            total_cost = cost_data.get("total_cost", 0)
            cost_trend = cost_data.get("trend", "stable")
            if isinstance(total_cost, (int, float)) and total_cost > 1000 and cost_trend == "increasing":
                self._add_if_new(Recommendation(
                    category="cost_optimization",
                    title=f"Costs increasing: ${total_cost:,.0f} total",
                    description=f"Platform costs are trending upward and currently at ${total_cost:,.0f}. Review cost allocation and optimize high-cost operations.",
                    reason=f"Total cost ${total_cost:,.0f} with increasing trend",
                    evidence=[{"source": "cost_engine", "total_cost": total_cost, "trend": cost_trend}],
                    confidence=0.75,
                    risk="medium",
                    priority="medium",
                    estimated_cost_savings="10-25% reduction possible",
                    actions=[
                        RecommendationAction("view_costs", "View Cost Analytics", "/api/analytics/costs", "GET"),
                    ],
                ))
        except Exception as exc:
            log.debug("Cost metrics scan skipped: %s", exc)

    async def _scan_governance(self) -> None:
        try:
            from backend.safety.audit_logger import audit_logger

            recent = audit_logger.get_recent(limit=200)
            if not isinstance(recent, list):
                recent = recent.get("entries", []) if isinstance(recent, dict) else []
            rejected = [r for r in recent if r.get("outcome") == "rejected"]
            if len(rejected) >= 10:
                self._add_if_new(Recommendation(
                    category="compliance",
                    title=f"High rejection rate in governance ({len(rejected)} recent rejections)",
                    description=f"There have been {len(rejected)} governance rejections in recent audit records. Review governance policies and operator training.",
                    reason=f"{len(rejected)} governance rejections detected",
                    evidence=[{"source": "audit_logger", "total_entries": len(recent), "rejected": len(rejected)}],
                    confidence=0.7,
                    risk="medium",
                    priority="medium",
                ))
        except Exception as exc:
            log.debug("Governance scan skipped: %s", exc)

    async def _scan_workflows(self) -> None:
        try:
            from backend.runtime.runtime_metrics import runtime_metrics

            metrics = runtime_metrics.export_metrics()
            avg_duration = metrics.get("average_duration_ms", 0)
            total = metrics.get("total_executions", 0)
            if total > 20 and avg_duration and avg_duration > 30000:
                self._add_if_new(Recommendation(
                    category="workflow_optimization",
                    title=f"High average execution duration ({avg_duration / 1000:.1f}s)",
                    description=f"The average mission execution time is {avg_duration / 1000:.1f}s across {total} executions. Consider optimizing workflow steps and parallelizing independent operations.",
                    reason=f"Average duration {avg_duration / 1000:.1f}s across {total} executions",
                    evidence=[{"source": "runtime_metrics", "average_duration_ms": avg_duration, "total_executions": total}],
                    confidence=0.7,
                    risk="low",
                    priority="medium",
                    estimated_time_savings=f"~{avg_duration // 2000 * 1000:.0f}ms per execution",
                    actions=[
                        RecommendationAction("view_analytics", "View Analytics", "/api/analytics/performance", "GET"),
                    ],
                ))
        except Exception as exc:
            log.debug("Workflow scan skipped: %s", exc)

    async def _scan_infrastructure(self) -> None:
        infra_issues = []
        try:
            from backend.infrastructure.redis.connection import redis_connection
            if not redis_connection.is_available:
                infra_issues.append("Redis")
        except Exception:
            pass
        try:
            from backend.infrastructure.neo4j.connection import neo4j_connection
            if not neo4j_connection.is_available:
                infra_issues.append("Neo4j")
        except Exception:
            pass
        try:
            from backend.infrastructure.rabbitmq.connection import rabbitmq_connection
            if not rabbitmq_connection.is_available:
                infra_issues.append("RabbitMQ")
        except Exception:
            pass
        try:
            from backend.database.health import check_database_health as dbh
            db_health = await dbh()
            if not db_health.get("status") == "healthy":
                infra_issues.append("PostgreSQL")
        except Exception:
            pass

        if infra_issues:
            self._add_if_new(Recommendation(
                category="infrastructure",
                title=f"Infrastructure component(s) unavailable: {', '.join(infra_issues)}",
                description=f"The following infrastructure components are unavailable: {', '.join(infra_issues)}. This may impact platform functionality.",
                reason=f"Unavailable components: {', '.join(infra_issues)}",
                evidence=[{"source": "health_checks", "unavailable": infra_issues}],
                confidence=1.0,
                risk="critical" if len(infra_issues) >= 2 else "high",
                priority="critical" if len(infra_issues) >= 2 else "high",
                actions=[
                    RecommendationAction("restart_runtime", "Restart Runtime", "/api/runtime/restart", "POST"),
                ],
            ))
            await self._emit_recommendation_event(f"Infrastructure issue: {', '.join(infra_issues)}")

    async def _scan_learning_insights(self) -> None:
        try:
            from backend.services.enterprise_learning_service import enterprise_learning

            patterns = (await enterprise_learning.get_failure_patterns()) if hasattr(enterprise_learning, "get_failure_patterns") else []
            if not isinstance(patterns, list):
                patterns = []
            if len(patterns) >= 3:
                top_pattern = patterns[0] if patterns else {}
                signature = top_pattern.get("error_signature", top_pattern.get("signature", "unknown"))
                frequency = top_pattern.get("frequency", top_pattern.get("count", 0))
                self._add_if_new(Recommendation(
                    category="learning",
                    title=f"Recurring failure pattern: {signature[:60]}",
                    description=f"The learning engine detected a recurring failure pattern '{signature[:60]}' occurring {frequency} times. Apply learned recovery strategies to prevent future failures.",
                    reason=f"Pattern '{signature[:60]}' detected {frequency} times",
                    evidence=[{"source": "learning_engine", "pattern_signature": signature, "frequency": frequency}],
                    confidence=0.8,
                    risk="medium" if frequency > 5 else "low",
                    priority="medium" if frequency > 5 else "low",
                    learning_references=[{"type": "failure_pattern", "signature": signature, "frequency": frequency}],
                    actions=[
                        RecommendationAction("view_patterns", "View Failure Patterns", "/api/enterprise/learning/failure-patterns", "GET"),
                    ],
                ))
        except Exception as exc:
            log.debug("Learning insights scan skipped: %s", exc)

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    async def _get_related_missions(self, execution_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        try:
            from backend.services.enterprise_graph_service import enterprise_graph
            missions_raw = await enterprise_graph.list_recent_missions(limit=limit + 1)
            missions = missions_raw if isinstance(missions_raw, list) else missions_raw.get("missions", [])
            return [m for m in missions if m.get("execution_id") != execution_id][:limit]
        except Exception:
            return []

    async def _get_recent_connector_failures(self, connector: str, limit: int = 5) -> List[Dict[str, Any]]:
        failures = []
        for rec in self._recommendations.values():
            if rec.related_connector == connector and "fail" in rec.title.lower():
                failures.append(rec.to_dict())
                if len(failures) >= limit:
                    break
        return failures

    async def _get_approval_queue_depth(self) -> int:
        try:
            from backend.safety.approval_queue import approval_queue
            count = approval_queue.get_pending_count() if hasattr(approval_queue, "get_pending_count") else 0
            return count if isinstance(count, int) else 0
        except Exception:
            return 0

    def _add_if_new(self, rec: Recommendation) -> bool:
        key = f"{rec.category}:{rec.title[:80]}"
        for existing in self._recommendations.values():
            if existing.dismissed or existing.executed:
                continue
            existing_key = f"{existing.category}:{existing.title[:80]}"
            if existing_key == key:
                return False
        self._recommendations[rec.id] = rec
        return True

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _persist(self) -> None:
        try:
            _DATA_DIR.mkdir(parents=True, exist_ok=True)
            data = [r.to_dict() for r in self._recommendations.values()]
            with open(_RECOMMENDATIONS_FILE, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as exc:
            log.warning("Recommendation persistence failed: %s", exc)

    def _load_persisted(self) -> None:
        try:
            if _RECOMMENDATIONS_FILE.exists():
                with open(_RECOMMENDATIONS_FILE) as f:
                    data = json.load(f)
                for item in data:
                    rec = Recommendation(
                        category=item.get("category", "operations"),
                        title=item.get("title", ""),
                        description=item.get("description", ""),
                        reason=item.get("reason", ""),
                        evidence=item.get("evidence", []),
                        confidence=item.get("confidence", 0.5),
                        risk=item.get("risk", "medium"),
                        priority=item.get("priority", "medium"),
                        estimated_impact=item.get("estimated_impact", ""),
                        estimated_cost_savings=item.get("estimated_cost_savings", ""),
                        estimated_time_savings=item.get("estimated_time_savings", ""),
                        related_mission=item.get("related_mission"),
                        related_connector=item.get("related_connector"),
                        related_workflow=item.get("related_workflow"),
                        learning_references=item.get("learning_references", []),
                        replay_references=item.get("replay_references", []),
                        knowledge_graph_references=item.get("knowledge_graph_references", []),
                        verification_references=item.get("verification_references", []),
                        source=item.get("source", "persisted"),
                        recommendation_id=item.get("id"),
                    )
                    rec.dismissed = item.get("dismissed", False)
                    rec.dismissed_at = item.get("dismissed_at")
                    rec.executed = item.get("executed", False)
                    rec.executed_at = item.get("executed_at")
                    rec.created_at = item.get("created_at", rec.created_at)
                    actions_data = item.get("actions", [])
                    rec.actions = [
                        RecommendationAction(
                            action_type=a.get("action_type", "unknown"),
                            label=a.get("label", ""),
                            endpoint=a.get("endpoint", ""),
                            method=a.get("method", "POST"),
                            description=a.get("description", ""),
                        ) for a in actions_data
                    ]
                    self._recommendations[rec.id] = rec
        except Exception as exc:
            log.warning("Recommendation load failed: %s", exc)

    # ------------------------------------------------------------------
    async def _emit_recommendation_event(self, message: str) -> None:
        try:
            from backend.services.enterprise_event_hub import enterprise_hub
            await enterprise_hub.emit(
                event_type=RECOMMENDATION_EVENT_GENERATED,
                agent="recommendation_engine",
                status="info",
                message=message,
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_active(self, category: Optional[str] = None, priority: Optional[str] = None) -> List[Dict[str, Any]]:
        results = [r.to_dict() for r in self._recommendations.values() if not r.dismissed and not r.executed]
        if category:
            results = [r for r in results if r["category"] == category]
        if priority:
            results = [r for r in results if r["priority"] == priority]
        results.sort(key=lambda r: ["critical", "high", "medium", "low"].index(r.get("priority", "medium")))
        return results

    def get_by_id(self, rec_id: str) -> Optional[Dict[str, Any]]:
        rec = self._recommendations.get(rec_id)
        return rec.to_dict() if rec else None

    async def generate(self, context: str, summary: str, metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """On-demand recommendation for callers that already ran their own
        evidence-gathering (e.g. RootCauseAnalysisService), rather than
        waiting for this engine's own event-driven analyzers to notice
        something independently. Still flows through the same
        Recommendation / _add_if_new / persistence path as every other
        recommendation, so it shows up in get_active()/get_dashboard() like
        any other — not a side-channel bypass.
        """
        metrics = metrics or {}
        category = _CONTEXT_CATEGORIES.get(context, "operations")
        confidence = metrics.get("confidence")
        impacted = metrics.get("impacted_entities")
        elevated = isinstance(impacted, (int, float)) and impacted > 3

        rec = Recommendation(
            category=category,
            title=f"{context.replace('_', ' ').title()}: {summary}"[:200],
            description=summary,
            reason=f"Generated from {context} (metrics: {metrics})",
            evidence=[{"source": context, "metrics": metrics}],
            confidence=confidence if isinstance(confidence, (int, float)) else 0.5,
            risk="high" if elevated else "medium",
            priority="high" if elevated else "medium",
            source=context,
        )
        self._add_if_new(rec)
        self._persist()
        await self._emit_recommendation_event(f"{context}: {summary}")
        return rec.to_dict()

    def dismiss(self, rec_id: str) -> bool:
        rec = self._recommendations.get(rec_id)
        if not rec or rec.dismissed:
            return False
        rec.dismiss()
        self._persist()
        return True

    def mark_executed(self, rec_id: str) -> bool:
        rec = self._recommendations.get(rec_id)
        if not rec or rec.executed:
            return False
        rec.mark_executed()
        self._persist()
        return True

    def get_dashboard(self) -> Dict[str, Any]:
        all_recs = [r.to_dict() for r in self._recommendations.values()]
        active = [r for r in all_recs if not r.get("dismissed") and not r.get("executed")]
        dismissed = [r for r in all_recs if r.get("dismissed")]
        executed = [r for r in all_recs if r.get("executed")]

        by_priority: Dict[str, int] = defaultdict(int)
        by_category: Dict[str, int] = defaultdict(int)
        for r in active:
            by_priority[r.get("priority", "medium")] += 1
            by_category[r.get("category", "unknown")] += 1

        critical = [r for r in active if r.get("priority") == "critical"]
        high = [r for r in active if r.get("priority") == "high"]
        medium = [r for r in active if r.get("priority") == "medium"]
        low = [r for r in active if r.get("priority") == "low"]

        top_risks = [r for r in active if r.get("risk") in ("high", "critical")][:5]
        top_opportunities = [r for r in active if r.get("estimated_cost_savings") or r.get("estimated_time_savings")][:5]

        return {
            "total_recommendations": len(all_recs),
            "active_recommendations": len(active),
            "dismissed_recommendations": len(dismissed),
            "executed_recommendations": len(executed),
            "by_priority": dict(by_priority),
            "by_category": dict(by_category),
            "critical_count": len(critical),
            "high_count": len(high),
            "medium_count": len(medium),
            "low_count": len(low),
            "top_risks": top_risks,
            "top_opportunities": top_opportunities,
            "last_full_scan": self._last_full_scan,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_categories(self) -> List[Dict[str, Any]]:
        by_cat: Dict[str, List[Dict]] = defaultdict(list)
        for r in self._recommendations.values():
            if not r.dismissed and not r.executed:
                by_cat[r.category].append(r.to_dict())
        result = []
        for cat in RECOMMENDATION_CATEGORIES:
            items = by_cat.get(cat, [])
            items.sort(key=lambda x: ["critical", "high", "medium", "low"].index(x.get("priority", "medium")))
            result.append({
                "category": cat,
                "count": len(items),
                "recommendations": items[:10],
                "total": len(items),
            })
        return result

    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        historical = [r.to_dict() for r in self._recommendations.values() if r.dismissed or r.executed]
        historical.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return historical[:limit]


enterprise_recommendation_engine = EnterpriseRecommendationEngine()
