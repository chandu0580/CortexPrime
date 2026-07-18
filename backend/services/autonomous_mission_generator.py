"""
Autonomous Mission Generator — creates enterprise missions from monitoring events.

When a watcher detects an event and a rule matches, this service:
  1. Maps the event+rule to an enterprise mission template
  2. Consults the Enterprise Learning Engine for recovery strategy context
  3. Launches the mission via EnterpriseMissionOrchestrator
  4. Emits monitoring lifecycle events through EnterpriseEventHub

Reuses the entire existing mission infrastructure.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.events.enterprise_event_types import EnterpriseEventTypes as EET
from backend.services.enterprise_event_hub import enterprise_hub

log = logging.getLogger(__name__)

# Map event types to mission template names
_EVENT_TO_TEMPLATE: Dict[str, str] = {
    "pipeline_failure":  "incident_response",
    "p1_incident":       "incident_response",
    "high_incident":     "incident_response",
    "alert_message":     "incident_response",
    "critical_issue":    "bug_triage",
    "critical_work_item":"bug_triage",
    "page_updated":      "knowledge_publishing",
}

# Map connector types to template names (fallback)
_CONNECTOR_TO_TEMPLATE: Dict[str, str] = {
    "github":       "incident_response",
    "jira":         "bug_triage",
    "slack":        "incident_response",
    "teams":        "incident_response",
    "azure_devops": "incident_response",
    "servicenow":   "incident_response",
    "confluence":   "knowledge_publishing",
    "notion":       "knowledge_publishing",
}


class AutonomousMissionGenerator:
    """Generates missions from detected monitoring events."""

    def __init__(self) -> None:
        self._initialized = False
        self._auto_generated_missions: List[Dict[str, Any]] = []
        self._active_recoveries: Dict[str, Dict[str, Any]] = {}

    async def initialize(self) -> None:
        """Prepare the generator."""
        self._initialized = True
        log.info("AutonomousMissionGenerator initialized")

    async def shutdown(self) -> None:
        self._initialized = False
        log.info("AutonomousMissionGenerator shutdown")

    # ------------------------------------------------------------------
    # Mission creation from monitoring event
    # ------------------------------------------------------------------

    async def create_mission(
        self,
        rule: Any,
        event: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """
        Create an enterprise mission from a matched monitoring event.

        Returns the mission result dict or None if creation failed.
        """
        connector_type = event.get("connector_type", "unknown")
        event_type = event.get("event_type", "unknown")
        severity = event.get("severity", "medium")
        title = event.get("title", "Untitled event")
        description = event.get("description", "")

        # Determine mission template
        template_name = (
            rule.mission_template
            if hasattr(rule, "mission_template") and rule.mission_template
            else _EVENT_TO_TEMPLATE.get(event_type)
            or _CONNECTOR_TO_TEMPLATE.get(connector_type)
            or "incident_response"
        )

        # Consult enterprise learning engine for context
        learning_context = await self._consult_learning(connector_type, event_type)

        # Build mission parameters
        execution_id = str(uuid4())
        params = {
            "title": f"[Auto] {title}",
            "description": description,
            "severity": severity,
            "source": f"monitoring:{connector_type}",
            "connector_type": connector_type,
            "event_type": event_type,
            "rule_name": rule.name if hasattr(rule, "name") else "unknown",
            "rule_id": rule.rule_id if hasattr(rule, "rule_id") else "unknown",
            "detected_at": event.get("detected_at", ""),
            "learning_context": learning_context,
        }

        # Get the orchestrator and launch
        try:
            from backend.services.enterprise_mission_orchestrator import enterprise_orchestrator
            from backend.services.mission_templates import template_registry

            # Find the template
            templates = template_registry.get_all()
            template = next(
                (t for t in templates if t.name.lower().replace(" ", "_") == template_name.lower()),
                None,
            )
            if not template:
                # Fall back to first available template
                template = templates[0] if templates else None
            if not template:
                log.warning("No mission template available for %s", template_name)
                return None

            # Check if approval is required
            requires_approval = (
                hasattr(rule, "requires_approval") and rule.requires_approval
            )
            if requires_approval:
                params["requires_approval"] = True
                await enterprise_hub.emit_monitoring_event(
                    event_type=EET.MONITORING_APPROVAL_REQUIRED,
                    message=f"Approval required for auto-generated mission: {title}",
                    status="pending_approval",
                    execution_id=execution_id,
                    metadata={"rule": rule.name if hasattr(rule, "name") else "unknown", "title": title},
                )

            # Launch the mission
            result = await enterprise_orchestrator.launch(
                template=template,
                params=params,
                launched_by="enterprise_monitoring",
            )

            mission_info = {
                "execution_id": result.get("execution_id", execution_id),
                "template": template_name,
                "status": result.get("status", "running"),
                "event_title": title,
                "connector": connector_type,
                "rule_name": rule.name if hasattr(rule, "name") else "unknown",
                "severity": severity,
                "created_at": result.get("started_at", ""),
            }

            self._auto_generated_missions.append(mission_info)
            if len(self._auto_generated_missions) > 500:
                self._auto_generated_missions = self._auto_generated_missions[-500:]

            # Emit monitoring mission created event
            await enterprise_hub.emit_monitoring_mission_created(
                connector_type=connector_type,
                rule_name=rule.name if hasattr(rule, "name") else "unknown",
                template_name=template_name,
                execution_id=result.get("execution_id", execution_id),
                event_title=title,
            )

            log.info(
                "Auto mission created: %s (template=%s, execution=%s)",
                title, template_name, result.get("execution_id", "?"),
            )
            return mission_info

        except ImportError as exc:
            log.warning("Mission creation failed (import): %s", exc)
        except Exception as exc:
            log.error("Mission creation failed: %s", exc)

        return None

    # ------------------------------------------------------------------
    # Learning consultation
    # ------------------------------------------------------------------

    async def _consult_learning(
        self,
        connector_type: str,
        event_type: str,
    ) -> Dict[str, Any]:
        """
        Consult the enterprise learning engine for context about similar past events.
        Returns relevant lessons, patterns, and recommendations.
        """
        try:
            from backend.services.enterprise_learning_service import enterprise_learning

            # Get relevant lessons (filter by domain matching connector)
            lessons = await enterprise_learning.get_lessons(
                limit=5, domain=connector_type,
            )

            # Get failure patterns for this connector
            patterns = await enterprise_learning.get_failure_patterns(limit=5)
            connector_patterns = [
                p for p in patterns
                if p.get("metadata", {}).get("source_type") == connector_type
                or p.get("metadata", {}).get("operation", "").startswith(connector_type)
            ]

            # Get recommendations
            recommendations = await enterprise_learning.recommend(limit=5, priority="high")

            # Get recovery patterns
            recovery = await enterprise_learning.get_recovery_patterns()

            return {
                "lessons_count": len(lessons),
                "relevant_lessons": [
                    {"content": lesson.get("content", "")[:200], "confidence": lesson.get("confidence", 0)}
                    for lesson in lessons[:3]
                ],
                "failure_patterns": [
                    {"signature": p.get("signature", ""), "count": p.get("metadata", {}).get("count", 0)}
                    for p in connector_patterns[:3]
                ],
                "recovery_strategies": [
                    {"type": r.get("recovery_type", ""), "count": r.get("metadata", {}).get("count", 0)}
                    for r in recovery
                ],
                "recommendations": [
                    {"content": r.get("content", "")[:200]}
                    for r in recommendations[:3]
                ],
            }
        except ImportError:
            return {"error": "learning_engine_unavailable"}
        except Exception as exc:
            log.debug("Learning consultation failed: %s", exc)
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Recovery tracking
    # ------------------------------------------------------------------

    def track_recovery(
        self,
        execution_id: str,
        recovery_type: str,
        status: str,
    ) -> None:
        """Track a recovery event for the monitoring dashboard."""
        if execution_id not in self._active_recoveries:
            self._active_recoveries[execution_id] = {
                "execution_id": execution_id,
                "recoveries": [],
            }
        self._active_recoveries[execution_id]["recoveries"].append({
            "type": recovery_type,
            "status": status,
            "timestamp": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        })

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_missions(
        self,
        limit: int = 50,
        connector: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get auto-generated missions with optional filtering."""
        missions = list(self._auto_generated_missions)
        if connector:
            missions = [m for m in missions if m.get("connector") == connector]
        missions.reverse()
        return missions[:limit]

    def get_active_recoveries(self) -> List[Dict[str, Any]]:
        """Get currently tracked recoveries."""
        return list(self._active_recoveries.values())

    def get_mission_statistics(self) -> Dict[str, Any]:
        """Aggregated mission statistics."""
        total = len(self._auto_generated_missions)
        by_connector: Dict[str, int] = {}
        by_template: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        for m in self._auto_generated_missions:
            conn = m.get("connector", "unknown")
            by_connector[conn] = by_connector.get(conn, 0) + 1
            tmpl = m.get("template", "unknown")
            by_template[tmpl] = by_template.get(tmpl, 0) + 1
            sev = m.get("severity", "unknown")
            by_severity[sev] = by_severity.get(sev, 0) + 1

        return {
            "total_missions": total,
            "missions_by_connector": by_connector,
            "missions_by_template": by_template,
            "missions_by_severity": by_severity,
            "active_recoveries": len(self._active_recoveries),
        }


# Singleton
auto_mission_generator = AutonomousMissionGenerator()
