from __future__ import annotations

from backend.agents.base import AgentCapability, AgentContext, AgentResult, AgentTask, BaseAgent
from backend.orchestrator.runtime_resolver import (get_execution_service, get_knowledge_service, get_learning_service)


class SREAgent(BaseAgent):
    def __init__(self, agent_id: str = "") -> None:
        super().__init__(agent_id)
        self._capabilities = [
            AgentCapability("incident_response", "Respond to incidents with runbook execution", ["execution", "knowledge"]),
            AgentCapability("monitoring_analysis", "Analyze monitoring data and metrics", ["knowledge"]),
            AgentCapability("alert_investigation", "Investigate alerts and determine severity", ["knowledge", "learning"]),
            AgentCapability("runbook_execution", "Execute predefined runbooks for common scenarios", ["execution"]),
        ]

    async def _execute_impl(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        knowledge_svc = get_knowledge_service()
        learning_svc = get_learning_service()
        exec_svc = get_execution_service()

        findings = {}

        if knowledge_svc:
            try:
                from backend.knowledge.models import KnowledgeQuery
                kq = KnowledgeQuery(query=f"incident runbook {task.description}", limit=5)
                result = await knowledge_svc.search(kq)
                entries = getattr(result, "entries", []) or []
                findings["runbooks"] = [str(getattr(e, "title", ""))[:80] for e in entries[:3]]
            except Exception as exc:
                findings["runbooks_error"] = str(exc)

        if learning_svc:
            try:
                patterns = await learning_svc.list_patterns(category="incident", min_confidence=0.5, limit=5)
                findings["similar_incidents"] = len(patterns or [])
            except Exception as exc:
                findings["patterns_error"] = str(exc)

        if exec_svc:
            try:
                await exec_svc.create_execution(
                    command=f"sre: {task.description[:80]}",
                    mission_id=ctx.mission_id,
                    source=f"agent.{self.agent_id}",
                    tags=["agent", "sre", "incident"],
                )
                findings["execution"] = "created"
            except Exception as exc:
                findings["execution_error"] = str(exc)

        severity = "critical" if any(kw in task.description.lower()
                                     for kw in ("down", "outage", "critical", "p0", "sev0")) else "high"

        return AgentResult(
            task_id=task.task_id, agent_id=self.agent_id,
            agent_type=self.agent_type, success=True,
            output_data={
                "task": task.description[:100],
                "severity": severity,
                "findings": findings,
                "recommended_action": "Execute runbook" if findings.get("runbooks") else "Manual investigation required",
            },
        )
