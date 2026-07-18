from __future__ import annotations

from backend.agents.base import AgentCapability, AgentContext, AgentResult, AgentTask, BaseAgent
from backend.orchestrator.runtime_resolver import get_knowledge_service, get_learning_service


class ResearchAgent(BaseAgent):
    def __init__(self, agent_id: str = "") -> None:
        super().__init__(agent_id)
        self._capabilities = [
            AgentCapability("knowledge_search", "Search indexed knowledge base for relevant information", ["knowledge"]),
            AgentCapability("pattern_discovery", "Discover patterns from learning runtime", ["learning"]),
            AgentCapability("root_cause_analysis", "Analyze incident data to determine root cause", ["knowledge", "learning"]),
            AgentCapability("information_gathering", "Collect and synthesize information from multiple sources", []),
        ]

    async def _execute_impl(self, task: AgentTask, ctx: AgentContext) -> AgentResult:
        query = task.input_data.get("query", task.description)
        knowledge_svc = get_knowledge_service()
        learning_svc = get_learning_service()

        findings = []

        if knowledge_svc:
            try:
                from backend.knowledge.models import KnowledgeQuery
                kq = KnowledgeQuery(query=query, limit=10)
                result = await knowledge_svc.search(kq)
                entries = getattr(result, "entries", []) or []
                findings.append({
                    "source": "knowledge",
                    "count": len(entries),
                    "entries": [str(getattr(e, "title", ""))[:80] for e in entries[:5]],
                })
            except Exception as exc:
                findings.append({"source": "knowledge", "error": str(exc)})

        if learning_svc:
            try:
                patterns = await learning_svc.list_patterns(category="mission", min_confidence=0.3, limit=10)
                findings.append({
                    "source": "learning",
                    "count": len(patterns),
                    "patterns": [str(getattr(p, "name", ""))[:80] for p in (patterns or [])[:5]],
                })
            except Exception as exc:
                findings.append({"source": "learning", "error": str(exc)})

        return AgentResult(
            task_id=task.task_id, agent_id=self.agent_id,
            agent_type=self.agent_type, success=True,
            output_data={
                "query": query,
                "findings": findings,
                "total_sources": len(findings),
            },
        )
