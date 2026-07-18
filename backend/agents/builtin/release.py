from __future__ import annotations

from backend.agents.base import AgentCapability, AgentContext, AgentResult, AgentTask, BaseAgent
from backend.orchestrator.runtime_resolver import get_execution_service, get_governance_service


class ReleaseAgent(BaseAgent):
    def __init__(self, agent_id: str = "") -> None:
        super().__init__(agent_id)
        self._capabilities = [
            AgentCapability("release_coordination", "Coordinate multi-service release process", ["execution", "governance"]),
            AgentCapability("changelog_generation", "Generate changelog from execution history", ["execution"]),
            AgentCapability("rollback_planning", "Plan and execute rollback procedures", ["execution"]),
        ]

    async def _execute_impl(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        exec_svc = get_execution_service()
        gov_svc = get_governance_service()

        release_plan = {
            "version": task.input_data.get("version", "1.0.0"),
            "environment": task.input_data.get("environment", "production"),
            "steps": [],
            "rollback_procedure": [],
        }

        if gov_svc:
            try:
                from backend.governance.models import DecisionRequest
                from datetime import datetime, timezone
                request = DecisionRequest(
                    request_id=f"rel_{task.task_id}",
                    requester=ctx.agent_id,
                    user=ctx.user_id or "release-agent",
                    role="release",
                    tenant=ctx.tenant_id,
                    mission_id=ctx.mission_id,
                    resource_type="release",
                    resource_id=task.task_id,
                    action="release",
                    scope="release",
                    risk_level=task.input_data.get("risk_level", "high"),
                    context={"task": task.description, "version": release_plan["version"]},
                    metadata={"agent": self.agent_type},
                    timestamp=datetime.now(timezone.utc),
                )
                response = await gov_svc.evaluate_mission(request)
                decision = getattr(response, "decision", None)
                decision_str = str(decision.value) if hasattr(decision, 'value') else str(decision)
                release_plan["governance_decision"] = decision_str
                release_plan["governance_message"] = getattr(response, "message", "")
                if getattr(response, "denied", False):
                    return AgentResult(
                        task_id=task.task_id, agent_id=self.agent_id,
                        agent_type=self.agent_type, success=False,
                        error=f"Release denied by governance: {release_plan['governance_message']}",
                        output_data=release_plan,
                    )
            except Exception as exc:
                release_plan["governance_error"] = str(exc)

        steps = [
            {"step": 1, "action": "Pre-deployment validation", "status": "pending"},
            {"step": 2, "action": f"Deploy to {release_plan['environment']}", "status": "pending"},
            {"step": 3, "action": "Post-deployment health check", "status": "pending"},
            {"step": 4, "action": "Smoke tests", "status": "pending"},
            {"step": 5, "action": "Traffic migration", "status": "pending"},
        ]
        release_plan["steps"] = steps

        rollback = [
            {"step": 1, "action": "Revert traffic to previous version"},
            {"step": 2, "action": "Roll back deployment"},
            {"step": 3, "action": "Verify rollback success"},
        ]
        release_plan["rollback_procedure"] = rollback

        if exec_svc:
            try:
                await exec_svc.create_execution(
                    command=f"release: {release_plan['version']} to {release_plan['environment']}",
                    mission_id=ctx.mission_id,
                    source=f"agent.{self.agent_id}",
                    tags=["agent", "release", release_plan["environment"]],
                )
            except Exception as exc:
                release_plan["execution_error"] = str(exc)

        return AgentResult(
            task_id=task.task_id, agent_id=self.agent_id,
            agent_type=self.agent_type, success=True,
            output_data=release_plan,
        )
