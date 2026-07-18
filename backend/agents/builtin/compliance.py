from __future__ import annotations

from backend.agents.base import AgentCapability, AgentContext, AgentResult, AgentTask, BaseAgent
from backend.orchestrator.runtime_resolver import get_governance_service


class ComplianceAgent(BaseAgent):
    def __init__(self, agent_id: str = "") -> None:
        super().__init__(agent_id)
        self._capabilities = [
            AgentCapability("policy_evaluation", "Evaluate actions against organizational policies", ["governance"]),
            AgentCapability("audit_trail", "Generate audit trail for compliance reporting", ["governance"]),
            AgentCapability("governance_check", "Check governance requirements before execution", ["governance"]),
        ]

    async def _execute_impl(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        gov_svc = get_governance_service()

        evaluations = []

        if gov_svc:
            try:
                from datetime import datetime, timezone

                from backend.governance.models import DecisionRequest
                request = DecisionRequest(
                    request_id=f"comp_{task.task_id}",
                    requester=ctx.agent_id,
                    user=ctx.user_id or "compliance-agent",
                    role="compliance",
                    tenant=ctx.tenant_id,
                    mission_id=ctx.mission_id,
                    resource_type="compliance_check",
                    resource_id=task.task_id,
                    action="evaluate",
                    scope="compliance",
                    risk_level=task.input_data.get("risk_level", "medium"),
                    context={"task": task.description, "agent_type": self.agent_type},
                    metadata={"agent": self.agent_type, "source": "compliance_agent"},
                    timestamp=datetime.now(timezone.utc),
                )
                response = await gov_svc.evaluate_mission(request)
                decision = getattr(response, "decision", None)
                decision_str = str(decision.value) if hasattr(decision, 'value') else str(decision)
                denied = getattr(response, "denied", False)
                evaluations.append({
                    "type": "governance",
                    "decision": decision_str,
                    "denied": denied,
                    "message": getattr(response, "message", ""),
                })
            except Exception as exc:
                evaluations.append({"type": "governance", "error": str(exc)})

        all_approved = all(e.get("denied") is False for e in evaluations if "denied" in e)

        return AgentResult(
            task_id=task.task_id, agent_id=self.agent_id,
            agent_type=self.agent_type, success=all_approved,
            output_data={
                "task": task.description[:100],
                "evaluations": evaluations,
                "all_approved": all_approved,
                "compliant": all_approved,
            },
        )
