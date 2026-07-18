from __future__ import annotations

from backend.agents.base import AgentCapability, AgentContext, AgentResult, AgentTask, BaseAgent
from backend.orchestrator.runtime_resolver import get_mission_intel_service


class PlannerAgent(BaseAgent):
    def __init__(self, agent_id: str = "") -> None:
        super().__init__(agent_id)
        self._capabilities = [
            AgentCapability("task_decomposition", "Break down goals into tasks with dependency graph", ["mission_intel"]),
            AgentCapability("mission_planning", "Create execution plans with ordered steps", ["mission_intel"]),
            AgentCapability("dependency_graph", "Build and resolve task dependency DAGs", []),
            AgentCapability("resource_allocation", "Assign tasks to appropriate agents based on capabilities", []),
        ]

    async def _execute_impl(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        svc = get_mission_intel_service()
        plan_steps = []

        if "decompose" in task.description.lower() or "plan" in task.description.lower():
            input_goal = task.input_data.get("goal", task.description)
            if svc:
                analysis = svc.analyze(goal=input_goal, context=ctx.metadata)
                decomposition = svc.decompose(analysis)
                plan_steps = [
                    {"id": f"step_{i}", "description": str(t)[:100], "agent_type": self._map_agent(t)}
                    for i, t in enumerate(getattr(decomposition, "tasks", []) or [])
                ]
            else:
                plan_steps = [
                    {"id": "step_1", "description": "Research and gather information", "agent_type": "ResearchAgent"},
                    {"id": "step_2", "description": "Design and implement solution", "agent_type": "PlatformEngineerAgent"},
                    {"id": "step_3", "description": "Validate and verify", "agent_type": "QAAgent"},
                ]

        return AgentResult(
            task_id=task.task_id, agent_id=self.agent_id,
            agent_type=self.agent_type, success=True,
            output_data={
                "plan_steps": plan_steps,
                "total_steps": len(plan_steps),
                "estimated_duration_minutes": len(plan_steps) * 5,
            },
        )

    @staticmethod
    def _map_agent(task_desc: str) -> str:
        desc_lower = str(task_desc).lower()
        if any(kw in desc_lower for kw in ("deploy", "configure", "infra", "k8s", "terraform")):
            return "PlatformEngineerAgent"
        if any(kw in desc_lower for kw in ("test", "qa", "validate", "verify")):
            return "QAAgent"
        if any(kw in desc_lower for kw in ("incident", "monitor", "alert", "sre")):
            return "SREAgent"
        if any(kw in desc_lower for kw in ("security", "vulnerability", "scan")):
            return "SecurityAgent"
        if any(kw in desc_lower for kw in ("compliance", "policy", "audit")):
            return "ComplianceAgent"
        if any(kw in desc_lower for kw in ("release", "rollout", "changelog")):
            return "ReleaseAgent"
        if any(kw in desc_lower for kw in ("research", "analyze", "investigate", "root cause")):
            return "ResearchAgent"
        return "PlatformEngineerAgent"
