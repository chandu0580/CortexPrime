from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List, Optional

from backend.mission_intel.models import (
    MissionAnalysis,
    MissionDecomposition,
    MissionStep,
    MissionTask,
    TaskGroup,
)

log = logging.getLogger(__name__)

_CATEGORY_TASKS: Dict[str, List[Dict[str, Any]]] = {
    "software_release": [
        {"name": "analyze_release_scope", "desc": "Analyze release scope and changes", "cap": "search", "conn": "github"},
        {"name": "verify_prerequisites", "desc": "Verify pre-deployment checks", "cap": "execute", "conn": "github"},
        {"name": "create_release_branch", "desc": "Create release branch", "cap": "execute", "conn": "github"},
        {"name": "trigger_build", "desc": "Trigger build and deployment", "cap": "build", "conn": "github"},
        {"name": "monitor_deployment", "desc": "Monitor deployment progress", "cap": "observe", "conn": "prometheus"},
        {"name": "notify_stakeholders", "desc": "Notify stakeholders of release", "cap": "notify", "conn": "slack"},
    ],
    "incident_response": [
        {"name": "triage_incident", "desc": "Triage and assess incident severity", "cap": "search", "conn": "prometheus"},
        {"name": "analyze_impact", "desc": "Analyze affected services and impact", "cap": "observe", "conn": "grafana"},
        {"name": "create_incident_ticket", "desc": "Create incident tracking ticket", "cap": "execute", "conn": "jira"},
        {"name": "notify_responders", "desc": "Notify incident responders", "cap": "notify", "conn": "slack"},
        {"name": "document_findings", "desc": "Document initial findings", "cap": "search", "conn": "jira"},
    ],
    "executive_research": [
        {"name": "gather_information", "desc": "Gather research information", "cap": "search", "conn": "github"},
        {"name": "analyze_trends", "desc": "Analyze trends and patterns", "cap": "search", "conn": "jira"},
        {"name": "compile_briefing", "desc": "Compile executive briefing", "cap": "execute", "conn": "jira"},
        {"name": "present_findings", "desc": "Present findings to stakeholders", "cap": "notify", "conn": "slack"},
    ],
    "compliance_audit": [
        {"name": "review_framework", "desc": "Review compliance framework", "cap": "search", "conn": "jira"},
        {"name": "assess_controls", "desc": "Assess each control", "cap": "search", "conn": "jira"},
        {"name": "identify_gaps", "desc": "Identify compliance gaps", "cap": "execute", "conn": "jira"},
        {"name": "generate_report", "desc": "Generate audit report", "cap": "execute", "conn": "jira"},
        {"name": "notify_auditors", "desc": "Notify compliance team", "cap": "notify", "conn": "slack"},
    ],
    "change_management": [
        {"name": "assess_impact", "desc": "Assess change impact", "cap": "search", "conn": "github"},
        {"name": "plan_implementation", "desc": "Document implementation plan", "cap": "execute", "conn": "jira"},
        {"name": "define_rollback", "desc": "Define rollback procedures", "cap": "execute", "conn": "jira"},
        {"name": "submit_cab", "desc": "Submit for CAB approval", "cap": "notify", "conn": "slack"},
        {"name": "schedule_change", "desc": "Schedule change window", "cap": "execute", "conn": "jira"},
    ],
    "infrastructure_deployment": [
        {"name": "design_architecture", "desc": "Design infrastructure architecture", "cap": "search", "conn": "github"},
        {"name": "provision_resources", "desc": "Provision cloud resources", "cap": "deploy", "conn": "kubernetes"},
        {"name": "configure_network", "desc": "Configure networking", "cap": "configure", "conn": "kubernetes"},
        {"name": "verify_deployment", "desc": "Verify deployment health", "cap": "observe", "conn": "prometheus"},
        {"name": "document_setup", "desc": "Document deployment runbook", "cap": "execute", "conn": "github"},
    ],
    "security_investigation": [
        {"name": "analyze_alert", "desc": "Analyze security alert", "cap": "search", "conn": "prometheus"},
        {"name": "trace_attack", "desc": "Trace attack chain", "cap": "observe", "conn": "grafana"},
        {"name": "assess_damage", "desc": "Assess affected systems", "cap": "execute", "conn": "jira"},
        {"name": "contain_threat", "desc": "Contain and isolate threat", "cap": "restart", "conn": "kubernetes"},
        {"name": "document_iocs", "desc": "Document indicators of compromise", "cap": "execute", "conn": "jira"},
    ],
    "knowledge_discovery": [
        {"name": "research_topic", "desc": "Research the topic", "cap": "search", "conn": "github"},
        {"name": "identify_patterns", "desc": "Identify key patterns", "cap": "search", "conn": "jira"},
        {"name": "synthesize_knowledge", "desc": "Synthesize findings", "cap": "execute", "conn": "jira"},
        {"name": "create_document", "desc": "Create knowledge document", "cap": "execute", "conn": "jira"},
    ],
    "customer_escalation": [
        {"name": "analyze_issue", "desc": "Analyze customer issue", "cap": "search", "conn": "jira"},
        {"name": "identify_root_cause", "desc": "Identify root cause", "cap": "observe", "conn": "grafana"},
        {"name": "plan_resolution", "desc": "Plan resolution steps", "cap": "execute", "conn": "jira"},
        {"name": "notify_customer", "desc": "Draft customer communication", "cap": "notify", "conn": "slack"},
        {"name": "document_learnings", "desc": "Document lessons learned", "cap": "execute", "conn": "jira"},
    ],
    "disaster_recovery": [
        {"name": "assess_scenario", "desc": "Assess failure scenario", "cap": "observe", "conn": "prometheus"},
        {"name": "activate_failover", "desc": "Activate failover procedure", "cap": "deploy", "conn": "kubernetes"},
        {"name": "restore_services", "desc": "Restore critical services", "cap": "restart", "conn": "docker"},
        {"name": "verify_recovery", "desc": "Verify recovery success", "cap": "observe", "conn": "prometheus"},
        {"name": "document_dr", "desc": "Document recovery outcome", "cap": "execute", "conn": "jira"},
    ],
}


class MissionDecomposer:

    async def decompose(
        self,
        analysis: MissionAnalysis,
        context: Optional[Dict[str, Any]] = None,
    ) -> MissionDecomposition:
        mission_id = f"mi-{uuid.uuid4().hex[:12]}"
        task_defs = _CATEGORY_TASKS.get(analysis.category, _CATEGORY_TASKS["knowledge_discovery"])
        tasks: List[MissionTask] = []
        steps: List[MissionStep] = []
        groups: List[TaskGroup] = []

        for i, td in enumerate(task_defs):
            task_id = f"t_{i}"
            tasks.append(MissionTask(
                id=task_id,
                name=td["name"],
                description=td["desc"],
                required_capability=td["cap"],
                suggested_connector=td["conn"],
                depends_on=[f"t_{j}" for j in range(i)],
                estimated_duration_seconds=60,
                retry_allowed=True,
                params={},
            ))
            step_id = f"s_{i}"
            connector_type = td.get("connector", td["conn"])
            operation = self._map_task_to_operation(td["name"], td["cap"])
            steps.append(MissionStep(
                id=step_id,
                task_id=task_id,
                name=td["desc"],
                order=i,
                connector_type=connector_type,
                operation=operation,
                params={},
                depends_on=[f"s_{j}" for j in range(i)],
                verification_required=True,
            ))

            if i % 2 == 0:
                group_id = f"g_{i // 2}"
                groups.append(TaskGroup(
                    id=group_id,
                    name=f"Phase {i // 2 + 1}",
                    task_ids=[task_id],
                    parallel=False,
                ))

        critical_path = [s.id for s in steps]
        duration_map = {t.id: t.estimated_duration_seconds for t in tasks}
        estimated_duration = sum(duration_map.get(s.task_id, 60) for s in steps)

        return MissionDecomposition(
            mission_id=mission_id,
            tasks=tasks,
            steps=steps,
            groups=groups,
            critical_path=critical_path,
            estimated_duration_seconds=estimated_duration,
        )

    def _map_task_to_operation(self, task_name: str, capability: str) -> str:
        op_map: Dict[str, str] = {
            "search": "search",
            "execute": "execute",
            "notify": "send_message",
            "observe": "query",
            "deploy": "deploy",
            "build": "build",
            "restart": "restart",
            "scale": "scale",
            "configure": "configure",
        }
        return op_map.get(capability, "execute")


mission_decomposer = MissionDecomposer()
