from __future__ import annotations

from backend.agents.base import AgentCapability, AgentContext, AgentResult, AgentTask, BaseAgent
from backend.orchestrator.runtime_resolver import get_governance_service, get_knowledge_service


class SecurityAgent(BaseAgent):
    def __init__(self, agent_id: str = "") -> None:
        super().__init__(agent_id)
        self._capabilities = [
            AgentCapability("vulnerability_assessment", "Assess security vulnerabilities in configurations", ["governance", "knowledge"]),
            AgentCapability("access_review", "Review access controls and permissions", ["governance"]),
            AgentCapability("compliance_scan", "Scan for security compliance violations", ["governance"]),
            AgentCapability("threat_analysis", "Analyze potential security threats", ["knowledge"]),
        ]

    async def _execute_impl(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        gov_svc = get_governance_service()
        get_knowledge_service()

        checks = []

        if gov_svc:
            try:
                from datetime import datetime, timezone

                from backend.governance.models import DecisionRequest
                request = DecisionRequest(
                    request_id=f"sec_{task.task_id}",
                    requester=ctx.agent_id,
                    user=ctx.user_id or "security-agent",
                    role="security",
                    tenant=ctx.tenant_id,
                    mission_id=ctx.mission_id,
                    resource_type="security_check",
                    resource_id=task.task_id,
                    action="scan",
                    scope="security",
                    risk_level=task.input_data.get("risk_level", "medium"),
                    context={"task": task.description, **task.input_data},
                    metadata={"agent": self.agent_type, "task": task.task_id},
                    timestamp=datetime.now(timezone.utc),
                )
                response = await gov_svc.evaluate_mission(request)
                decision = getattr(response, "decision", None)
                decision_str = str(decision.value) if hasattr(decision, 'value') else str(decision)
                checks.append({
                    "type": "governance",
                    "decision": decision_str,
                    "message": getattr(response, "message", ""),
                })
            except Exception as exc:
                checks.append({"type": "governance", "error": str(exc)})

        return AgentResult(
            task_id=task.task_id, agent_id=self.agent_id,
            agent_type=self.agent_type, success=True,
            output_data={
                "task": task.description[:100],
                "security_checks": checks,
                "check_count": len(checks),
                "risk_level": task.input_data.get("risk_level", "low"),
            },
        )
