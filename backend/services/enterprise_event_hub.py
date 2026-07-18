"""
Enterprise Event Hub — centralized event routing + cross-service sync.

Subscribes to EventBus and routes every enterprise event to:
  1. WebSocket broadcast (with topic-hints in payload for frontend routing)
  2. Cross-service synchronization triggers (e.g., mission complete → graph refresh)

Also provides convenience methods for emitting standardized enterprise events
so that callers don't need to import CognitionEvent / EventBus directly.

Usage
-----
    from backend.services.enterprise_event_hub import enterprise_hub

    # Emit a standardized enterprise event
    await enterprise_hub.emit_mission_launched(execution_id, template_name, ...)

    # Or emit an arbitrary CognitionEvent (which will also be routed)
    # This happens automatically for events published via event_bus.publish()
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from backend.events.enterprise_event_types import EnterpriseEventTypes as EET
from backend.events.event_bus import event_bus
from backend.events.event_models import CognitionEvent

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Domain → topic mapping for WebSocket routing
# ---------------------------------------------------------------------------

def _topic_for_event(event_type: str) -> str:
    """Map an enterprise event type to a WebSocket topic name."""
    if event_type.startswith("mission."):
        return "enterprise:mission"
    if event_type.startswith("approval."):
        return "enterprise:approval"
    if event_type.startswith("connector."):
        return "enterprise:connector"
    if event_type.startswith("verification."):
        return "enterprise:verification"
    if event_type.startswith("recovery."):
        return "enterprise:recovery"
    if event_type.startswith("graph."):
        return "enterprise:graph"
    if event_type.startswith("memory."):
        return "enterprise:memory"
    if event_type.startswith("analytics."):
        return "enterprise:analytics"
    if event_type.startswith("runtime."):
        return "enterprise:runtime"
    if event_type.startswith("learning."):
        return "enterprise:learning"
    if event_type.startswith("monitoring."):
        return "enterprise:monitoring"
    if event_type.startswith("recommendation."):
        return "enterprise:recommendation"
    if event_type.startswith("engineering."):
        return "enterprise:engineering"
    if event_type.startswith("workspace."):
        return "enterprise:workspace"
    if event_type.startswith("patch."):
        return "enterprise:patch"
    if event_type.startswith("build."):
        return "enterprise:build"
    if event_type.startswith("deploy."):
        return "enterprise:deploy"
    if event_type.startswith("governance."):
        return "enterprise:governance"
    if event_type.startswith("delivery."):
        return "enterprise:delivery"
    if event_type.startswith("trigger."):
        return "enterprise:trigger"
    if event_type.startswith("sandbox."):
        return "enterprise:sandbox"
    if event_type.startswith("code."):
        return "enterprise:code"
    if event_type.startswith("execution."):
        return "enterprise:execution"
    if event_type.startswith("git."):
        return "enterprise:git"
    if event_type.startswith("github."):
        return "enterprise:github"
    if event_type.startswith("pipeline."):
        return "enterprise:pipeline"
    if event_type.startswith("architecture."):
        return "enterprise:architecture"
    if event_type.startswith("cicd."):
        return "enterprise:cicd"
    if event_type.startswith("infra."):
        return "enterprise:infrastructure"
    if event_type.startswith("otel."):
        return "enterprise:infrastructure"
    if event_type.startswith("rca."):
        return "enterprise:rca"
    return "enterprise:general"


# ---------------------------------------------------------------------------
# EventHub
# ---------------------------------------------------------------------------

class EnterpriseEventHub:
    """Central hub for enterprise event routing and cross-service sync."""

    def __init__(self) -> None:
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Subscribe to EventBus and register cross-service handlers."""
        if self._initialized:
            return
        event_bus.subscribe(self._on_event)
        self._initialized = True
        log.info("EnterpriseEventHub initialized — subscribed to EventBus")

    async def _on_event(self, event: CognitionEvent) -> None:
        """Called for every event published to the EventBus."""
        event_type = event.event_type or ""

        # Route to WebSocket with topic-hints for frontend routing
        await self._broadcast_with_topic(event)

        # Cross-service sync triggers
        await self._sync_triggers(event, event_type)

    # ------------------------------------------------------------------
    # WebSocket broadcasting
    # ------------------------------------------------------------------

    async def _broadcast_with_topic(self, event: CognitionEvent) -> None:
        """Broadcast event via connection_pool with topic routing."""
        try:
            from backend.websocket.connection_pool import connection_pool

            event_dict = event.model_dump()

            # Add topic routing hints for the frontend
            topic = _topic_for_event(event.event_type or "")
            event_dict["_topic"] = topic
            event_dict["_schema"] = "enterprise:1"

            # Always broadcast to all connected clients (enterprise events
            # are global by nature). The frontend will filter by topic.
            asyncio.ensure_future(connection_pool.broadcast(event_dict))
        except Exception as exc:
            log.debug("WS broadcast skipped: %s", exc)

    # ------------------------------------------------------------------
    # Cross-service sync triggers
    # ------------------------------------------------------------------

    async def _sync_triggers(
        self, event: CognitionEvent, event_type: str,
    ) -> None:
        """Trigger cross-service synchronisation when relevant events fire."""

        # Mission launched → ensure nothing special needed
        if event_type == EET.MISSION_LAUNCHED:
            pass

        # Mission completed → analytics refresh (fired via event already)
        elif event_type in (EET.MISSION_COMPLETED, EET.MISSION_FAILED):
            pass

        # Connector action completed → update connector activity service
        elif event_type == EET.CONNECTOR_ACTION_COMPLETED:
            pass  # activity service is already updated by BaseConnector._execute

        # Graph update → future: trigger re-indexing
        elif event_type.startswith("graph."):
            pass

    # ------------------------------------------------------------------
    # Convenience emitters
    # ------------------------------------------------------------------

    async def emit(
        self,
        event_type: str,
        agent: str = "system",
        status: str = "info",
        message: str = "",
        execution_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a standardized enterprise event via EventBus."""
        # The EventBus.publish() handles:
        #   - replay store recording
        #   - runtime metrics updates
        #   - WebSocket broadcasting (via _on_event -> _broadcast_with_topic)
        await event_bus.publish(CognitionEvent(
            agent=agent,
            event_type=event_type,
            status=status,
            message=message,
            execution_id=execution_id,
            payload=metadata or {},
        ))

    # ------------------------------------------------------------------
    # Domain-specific emitters
    # ------------------------------------------------------------------

    async def emit_mission_launched(
        self,
        execution_id: str,
        template_name: str,
        objective: str,
        launched_by: str = "system",
    ) -> None:
        await self.emit(
            event_type=EET.MISSION_LAUNCHED,
            agent=template_name,
            status="running",
            message=f"Mission launched: {objective}",
            execution_id=execution_id,
            metadata={
                "execution_id": execution_id,
                "template": template_name,
                "objective": objective,
                "launched_by": launched_by,
                "domain": "mission",
            },
        )

    async def emit_mission_completed(
        self,
        execution_id: str,
        template_name: str,
        step_count: int,
    ) -> None:
        await self.emit(
            event_type=EET.MISSION_COMPLETED,
            agent=template_name,
            status="completed",
            message=f"Mission completed: {template_name} ({step_count} steps)",
            execution_id=execution_id,
            metadata={
                "execution_id": execution_id,
                "step_count": step_count,
                "domain": "mission",
            },
        )

    async def emit_mission_failed(
        self,
        execution_id: str,
        template_name: str,
        error: str,
        step_count: int = 0,
    ) -> None:
        await self.emit(
            event_type=EET.MISSION_FAILED,
            agent=template_name,
            status="failed",
            message=f"Mission failed: {error}",
            execution_id=execution_id,
            metadata={
                "execution_id": execution_id,
                "error": error,
                "step_count": step_count,
                "domain": "mission",
            },
        )

    async def emit_step_completed(
        self,
        execution_id: str,
        template_name: str,
        step_idx: int,
        connector_type: str,
        operation: str,
        description: str,
        action_id: str,
    ) -> None:
        await self.emit(
            event_type=EET.MISSION_STEP,
            agent=template_name,
            status="completed",
            message=f"Step {step_idx}: {description}",
            execution_id=execution_id,
            metadata={
                "execution_id": execution_id,
                "step_idx": step_idx,
                "connector": connector_type,
                "operation": operation,
                "description": description,
                "action_id": action_id,
                "domain": "mission",
            },
        )

    async def emit_approval_required(
        self,
        execution_id: str,
        reason: str,
        step_description: str,
    ) -> None:
        await self.emit(
            event_type=EET.APPROVAL_REQUIRED,
            agent="governance",
            status="pending_approval",
            message=f"Approval required: {reason}",
            execution_id=execution_id,
            metadata={
                "execution_id": execution_id,
                "reason": reason,
                "step": step_description,
                "domain": "approval",
            },
        )

    async def emit_approval_decision(
        self,
        execution_id: str,
        decision: str,
        reason: str,
    ) -> None:
        event_type = EET.APPROVAL_GRANTED if decision == "approved" else EET.APPROVAL_REJECTED
        await self.emit(
            event_type=event_type,
            agent="governance",
            status=decision,
            message=f"Approval {decision}: {reason}",
            execution_id=execution_id,
            metadata={
                "execution_id": execution_id,
                "decision": decision,
                "domain": "approval",
            },
        )

    async def emit_connector_action(
        self,
        execution_id: str,
        connector_type: str,
        operation: str,
        status: str,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        event_type = EET.CONNECTOR_ACTION_STARTED
        if status == "completed":
            event_type = EET.CONNECTOR_ACTION_COMPLETED
        elif status == "failed":
            event_type = EET.CONNECTOR_ACTION_FAILED

        await self.emit(
            event_type=event_type,
            agent=connector_type,
            status=status,
            message=description or f"{connector_type}.{operation} {status}",
            execution_id=execution_id,
            metadata={
                "connector": connector_type,
                "operation": operation,
                "execution_id": execution_id,
                "domain": "connector",
                **(metadata or {}),
            },
        )

    async def emit_verification(
        self,
        execution_id: str,
        connector_type: str,
        operation: str,
        verified: bool,
        status: str = "completed",
    ) -> None:
        event_type = EET.VERIFICATION_COMPLETED if status == "completed" else EET.VERIFICATION_FAILED
        await self.emit(
            event_type=event_type,
            agent=f"verifier:{connector_type}",
            status=status,
            message=f"Verification {'passed' if verified else 'failed'} for {connector_type}.{operation}",
            execution_id=execution_id,
            metadata={
                "connector": connector_type,
                "operation": operation,
                "verified": verified,
                "domain": "verification",
            },
        )

    async def emit_recovery(
        self,
        execution_id: str,
        recovery_type: str,
        description: str,
    ) -> None:
        event_type_map = {
            "retry": EET.RECOVERY_RETRY,
            "alternative": EET.RECOVERY_FALLBACK,
            "fallback": EET.RECOVERY_FALLBACK,
            "rollback": EET.RECOVERY_ROLLBACK,
            "escalation": EET.RECOVERY_ESCALATION,
        }
        et = event_type_map.get(recovery_type, EET.RECOVERY_RETRY)
        await self.emit(
            event_type=et,
            agent="recovery",
            status="warning",
            message=description,
            execution_id=execution_id,
            metadata={
                "recovery_type": recovery_type,
                "execution_id": execution_id,
                "domain": "recovery",
            },
        )

    async def emit_graph_update(
        self,
        entity_type: str,
        entity_id: str,
        action: str = "created",
        execution_id: Optional[str] = None,
    ) -> None:
        event_type = EET.GRAPH_ENTITY_CREATED if action == "created" else EET.GRAPH_MISSION_UPDATED
        await self.emit(
            event_type=event_type,
            agent="knowledge_graph",
            status="info",
            message=f"Graph {action}: {entity_type}/{entity_id}",
            execution_id=execution_id,
            metadata={
                "entity_type": entity_type,
                "entity_id": entity_id,
                "action": action,
                "domain": "graph",
            },
        )

    async def emit_analytics_update(
        self,
        metric_name: str,
        value: Any = None,
    ) -> None:
        await self.emit(
            event_type=EET.ANALYTICS_METRICS_UPDATED,
            agent="analytics",
            status="info",
            message=f"Analytics updated: {metric_name}",
            metadata={
                "metric": metric_name,
                "value": value,
                "domain": "analytics",
            },
        )

    # ------------------------------------------------------------------
    # Learning emitters
    # ------------------------------------------------------------------

    async def emit_learning_event(
        self,
        event_type: str,
        message: str,
        metadata: Optional[Dict[str, Any]] = None,
        execution_id: Optional[str] = None,
    ) -> None:
        """Emit a learning-related event."""
        await self.emit(
            event_type=event_type,
            agent="enterprise_learning",
            status="info",
            message=message,
            execution_id=execution_id,
            metadata={
                "domain": "learning",
                **(metadata or {}),
            },
        )

    async def emit_lesson_discovered(
        self,
        lesson_summary: str,
        execution_id: Optional[str] = None,
    ) -> None:
        await self.emit_learning_event(
            event_type=EET.LEARNING_LESSON_DISCOVERED,
            message=lesson_summary,
            execution_id=execution_id,
            metadata={"subtype": "lesson_discovered"},
        )

    async def emit_pattern_updated(
        self,
        pattern_type: str,
        pattern_key: str,
        execution_id: Optional[str] = None,
    ) -> None:
        await self.emit_learning_event(
            event_type=EET.LEARNING_PATTERN_UPDATED,
            message=f"Pattern updated: {pattern_type}/{pattern_key}",
            execution_id=execution_id,
            metadata={"pattern_type": pattern_type, "pattern_key": pattern_key},
        )

    async def emit_recommendation_generated(
        self,
        recommendation_summary: str,
        priority: str = "medium",
    ) -> None:
        await self.emit_learning_event(
            event_type=EET.LEARNING_RECOMMENDATION_GENERATED,
            message=recommendation_summary,
            metadata={"priority": priority},
        )

    # ------------------------------------------------------------------
    # Monitoring emitters
    # ------------------------------------------------------------------

    async def emit_monitoring_event(
        self,
        event_type: str,
        message: str,
        status: str = "info",
        execution_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit a monitoring-related event."""
        await self.emit(
            event_type=event_type,
            agent="enterprise_monitoring",
            status=status,
            message=message,
            execution_id=execution_id,
            metadata={
                "domain": "monitoring",
                **(metadata or {}),
            },
        )

    async def emit_monitoring_event_detected(
        self,
        connector_type: str,
        event_title: str,
        severity: str = "medium",
        execution_id: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
    ) -> None:
        await self.emit_monitoring_event(
            event_type=EET.MONITORING_EVENT_DETECTED,
            message=f"{connector_type} event detected: {event_title}",
            status=severity,
            execution_id=execution_id,
            metadata={
                "connector": connector_type,
                "event_title": event_title,
                "severity": severity,
                "event_data": event_data or {},
            },
        )

    async def emit_monitoring_mission_created(
        self,
        connector_type: str,
        rule_name: str,
        template_name: str,
        execution_id: str,
        event_title: str,
    ) -> None:
        await self.emit_monitoring_event(
            event_type=EET.MONITORING_MISSION_CREATED,
            message=f"Mission auto-created from {connector_type}: {event_title}",
            status="info",
            execution_id=execution_id,
            metadata={
                "connector": connector_type,
                "rule": rule_name,
                "template": template_name,
                "event_title": event_title,
            },
        )

    async def emit_monitoring_recovery(
        self,
        event_type: str,
        recovery_type: str,
        execution_id: str,
        message: str,
    ) -> None:
        status_map = {
            EET.MONITORING_RECOVERY_STARTED: "recovering",
            EET.MONITORING_RECOVERY_COMPLETED: "recovered",
            EET.MONITORING_RECOVERY_FAILED: "failed",
        }
        await self.emit_monitoring_event(
            event_type=event_type,
            message=message,
            status=status_map.get(event_type, "info"),
            execution_id=execution_id,
            metadata={"recovery_type": recovery_type},
        )

    async def emit_monitoring_rule_event(
        self,
        event_type: str,
        rule_id: str,
        rule_name: str,
    ) -> None:
        action = event_type.split(".")[-1]
        await self.emit_monitoring_event(
            event_type=event_type,
            message=f"Monitoring rule {action}: {rule_name}",
            metadata={"rule_id": rule_id, "rule_name": rule_name},
        )

    async def emit_decision_made(
        self,
        report_id: str,
        risk_score: float,
        risk_level: str,
        execution_plan: str,
        deployment_strategy: str,
        approval_required: bool,
        categories: List[str],
        repository: str = "",
        branch: str = "",
    ) -> None:
        """Emit a decision event from the Engineering Decision Engine."""
        await self.emit(
            event_type=EET.ENGINEERING_DECISION_MADE,
            agent="engineering_decision_engine",
            status="completed",
            message=f"Decision {report_id}: {risk_level} risk, {execution_plan}",
            metadata={
                "domain": "engineering",
                "report_id": report_id,
                "risk_score": risk_score,
                "risk_level": risk_level,
                "execution_plan": execution_plan,
                "deployment_strategy": deployment_strategy,
                "approval_required": approval_required,
                "categories": categories,
                "repository": repository,
                "branch": branch,
            },
        )

    async def emit_runtime_metrics(self) -> None:
        """Emit current runtime metrics snapshot."""
        try:
            from backend.runtime.runtime_metrics import runtime_metrics
            metrics = runtime_metrics.export_metrics()
            await self.emit(
                event_type=EET.RUNTIME_METRICS_UPDATED,
                agent="runtime",
                status="active",
                message="Runtime metrics updated",
                metadata={
                    "domain": "runtime",
                    "metrics": metrics,
                },
            )
        except Exception as exc:
            log.warning("Runtime metrics emission failed: %s", exc)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

enterprise_hub = EnterpriseEventHub()
