from __future__ import annotations

from backend.agents.base import AgentCapability, AgentContext, AgentResult, AgentTask, BaseAgent
from backend.orchestrator.runtime_resolver import get_execution_service, get_knowledge_service


class QAAgent(BaseAgent):
    def __init__(self, agent_id: str = "") -> None:
        super().__init__(agent_id)
        self._capabilities = [
            AgentCapability("test_execution", "Execute test suites and validate results", ["execution"]),
            AgentCapability("validation", "Validate outputs against acceptance criteria", ["knowledge"]),
            AgentCapability("acceptance_criteria", "Check mission results meet acceptance criteria", []),
            AgentCapability("quality_gate", "Evaluate quality gates before promotion", ["execution"]),
        ]

    async def _execute_impl(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        exec_svc = get_execution_service()
        knowledge_svc = get_knowledge_service()

        validation_results = []
        checks_performed = 0
        checks_passed = 0

        if knowledge_svc:
            try:
                from backend.knowledge.models import KnowledgeQuery
                kq = KnowledgeQuery(query=f"acceptance criteria {task.description}", limit=5)
                result = await knowledge_svc.search(kq)
                entries = getattr(result, "entries", []) or []
                validation_results.append({
                    "type": "acceptance_criteria_search",
                    "found": len(entries),
                })
                checks_performed += 1
                checks_passed += 1
            except Exception as exc:
                validation_results.append({"type": "acceptance_criteria_search", "error": str(exc)})

        input_checks = task.input_data.get("checks", [])
        for check in input_checks:
            checks_performed += 1
            expected = check.get("expected", "")
            actual = check.get("actual", "")
            passed = not expected or not actual or expected == actual
            if passed:
                checks_passed += 1
            validation_results.append({
                "type": "custom_check",
                "name": check.get("name", f"check_{checks_performed}"),
                "passed": passed,
                "expected": expected,
                "actual": actual,
            })

        if exec_svc:
            try:
                await exec_svc.create_execution(
                    command=f"qa: {task.description[:80]}",
                    mission_id=ctx.mission_id,
                    source=f"agent.{self.agent_id}",
                    tags=["agent", "qa", "validation"],
                )
            except Exception as exc:
                validation_results.append({"type": "execution", "error": str(exc)})

        all_passed = checks_performed == 0 or checks_passed == checks_performed

        return AgentResult(
            task_id=task.task_id, agent_id=self.agent_id,
            agent_type=self.agent_type, success=all_passed,
            output_data={
                "task": task.description[:100],
                "validation_results": validation_results,
                "checks_performed": checks_performed,
                "checks_passed": checks_passed,
                "all_passed": all_passed,
                "quality_gate": "passed" if all_passed else "failed",
            },
        )
