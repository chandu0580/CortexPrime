from __future__ import annotations

from backend.agents.base import AgentCapability, AgentContext, AgentResult, AgentTask, BaseAgent
from backend.orchestrator.runtime_resolver import get_connector_service, get_execution_service


class PlatformEngineerAgent(BaseAgent):
    def __init__(self, agent_id: str = "") -> None:
        super().__init__(agent_id)
        self._capabilities = [
            AgentCapability("infrastructure_as_code", "Generate and apply IaC configurations", ["execution", "connector"]),
            AgentCapability("config_management", "Manage configuration files and secrets", ["execution"]),
            AgentCapability("deployment_planning", "Plan deployment strategies with rollback support", ["execution", "knowledge"]),
            AgentCapability("resource_provisioning", "Provision cloud and infrastructure resources", ["execution", "connector"]),
        ]

    async def _execute_impl(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        exec_svc = get_execution_service()
        conn_svc = get_connector_service()

        operations = []

        if exec_svc:
            try:
                entity = await exec_svc.create_execution(
                    command=task.description,
                    mission_id=ctx.mission_id,
                    source=f"agent.{self.agent_id}",
                    tags=["agent", "platform_engineer"],
                )
                exec_id = getattr(entity, "execution_id", None) or getattr(entity, "id", None)
                operations.append({"type": "execution", "id": str(exec_id) if exec_id else "created"})
            except Exception as exc:
                operations.append({"type": "execution", "error": str(exc)})

        if conn_svc:
            try:
                connectors = await conn_svc.list_connectors()
                available = [str(getattr(c, "connector_type", getattr(c, "name", "")))
                             for c in (connectors or [])[:5]]
                operations.append({"type": "connectors_available", "count": len(available), "list": available})
            except Exception as exc:
                operations.append({"type": "connectors", "error": str(exc)})

        return AgentResult(
            task_id=task.task_id, agent_id=self.agent_id,
            agent_type=self.agent_type, success=True,
            output_data={
                "task": task.description[:100],
                "operations": operations,
                "operation_count": len(operations),
            },
        )
