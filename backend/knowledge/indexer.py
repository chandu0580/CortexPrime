from __future__ import annotations

import logging
from typing import Any, Optional

try:
    from backend.database.repositories.factory import RepositoryFactory
    from backend.database.repositories.factory import repo_factory as _repo_factory
except ImportError:
    _repo_factory = None
from backend.knowledge.events import KnowledgeEvent, KnowledgeEventPublisher, knowledge_event_publisher
from backend.knowledge.manager import KnowledgeManager
from backend.knowledge.models import IndexRequest, KnowledgeDocument, RelationshipType

log = logging.getLogger(__name__)


class KnowledgeIndexer:
    def __init__(
        self,
        manager: Optional[KnowledgeManager] = None,
        events: Optional[KnowledgeEventPublisher] = None,
        repo_factory: Optional[RepositoryFactory] = None,
    ) -> None:
        self._manager = manager or KnowledgeManager(events=events, repo_factory=repo_factory)
        self._events = events or knowledge_event_publisher
        self._repo_factory = repo_factory or _repo_factory or RepositoryFactory()

    async def index_mission(self, mission_id: str, title: str, objective: str,
                             status: str, owner: str, result: Optional[str] = None,
                             metadata: Optional[dict[str, Any]] = None) -> Optional[KnowledgeDocument]:
        request = IndexRequest(
            title=f"Mission: {title}",
            content=objective,
            summary=f"Mission '{title}' ({status})",
            category="mission",
            tags=["mission", status.lower()],
            source="mission_runtime",
            source_url=f"/api/missions/{mission_id}",
            confidence=1.0,
            metadata={
                "mission_id": mission_id,
                "status": status,
                "owner": owner,
                **(metadata or {}),
            },
        )
        doc = await self._manager.create_entry(request)
        if doc:
            await self._events.publish(KnowledgeEvent(
                event_type="knowledge.indexed", knowledge_id=doc.id,
                title=doc.title, category=doc.category, source="mission_runtime",
                message=f"Mission indexed: {doc.title}",
            ))
        return doc

    async def index_execution(self, execution_id: str, mission_id: Optional[str],
                               agent: str, status: str, trigger: str,
                               result_data: Optional[dict[str, Any]] = None,
                               error: Optional[str] = None) -> Optional[KnowledgeDocument]:
        content = f"Execution {execution_id} by {agent}: {status}"
        if error:
            content += f" — Error: {error}"

        request = IndexRequest(
            title=f"Execution: {execution_id}",
            content=content,
            summary=f"Execution '{execution_id}' ({status}) by {agent}",
            category="execution",
            tags=["execution", status.lower(), agent.lower() if agent else ""],
            source="execution_runtime",
            source_url=f"/api/executions/{execution_id}",
            confidence=1.0,
            metadata={
                "execution_id": execution_id,
                "mission_id": mission_id or "",
                "agent": agent or "",
                "status": status,
                "trigger": trigger,
                "error": error or "",
                **(result_data or {}),
            },
        )
        doc = await self._manager.create_entry(request)
        if doc:
            await self._events.publish(KnowledgeEvent(
                event_type="knowledge.indexed", knowledge_id=doc.id,
                title=doc.title, category=doc.category, source="execution_runtime",
                message=f"Execution indexed: {doc.title}",
            ))
        if doc and mission_id:
            await self._manager.create_relationship(
                source_id=mission_id,
                target_id=doc.id,
                relationship_type=RelationshipType.PRODUCED_BY.value,
                strength=1.0,
                metadata={"execution_id": execution_id},
            )
        return doc

    async def index_governance_decision(self, decision_id: str, policy_name: str,
                                         decision: str, resource_type: str,
                                         resource_id: str, action: str,
                                         reason: str) -> Optional[KnowledgeDocument]:
        request = IndexRequest(
            title=f"Governance: {policy_name}",
            content=f"Decision '{decision}' on {resource_type}/{resource_id} for '{action}': {reason}",
            summary=f"Governance decision: {decision} for {resource_type}",
            category="policy",
            tags=["governance", decision.lower(), policy_name.lower()],
            source="governance_runtime",
            source_url="",
            confidence=1.0,
            metadata={
                "decision_id": decision_id,
                "policy_name": policy_name,
                "decision": decision,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "action": action,
                "reason": reason,
            },
        )
        doc = await self._manager.create_entry(request)
        if doc:
            await self._events.publish(KnowledgeEvent(
                event_type="knowledge.indexed", knowledge_id=doc.id,
                title=doc.title, category=doc.category, source="governance_runtime",
                message=f"Governance decision indexed: {doc.title}",
            ))
        return doc

    async def index_connector(self, connector_id: str, name: str, connector_type: str,
                               status: str, metadata: Optional[dict[str, Any]] = None) -> Optional[KnowledgeDocument]:
        request = IndexRequest(
            title=f"Connector: {name}",
            content=f"Connector '{name}' of type {connector_type} — status: {status}",
            summary=f"Connector {name} ({connector_type})",
            category="connector",
            tags=["connector", connector_type.lower(), status.lower()],
            source="connector_runtime",
            source_url=f"/api/connectors/{connector_id}",
            confidence=1.0,
            metadata={
                "connector_id": connector_id,
                "name": name,
                "connector_type": connector_type,
                "status": status,
                **(metadata or {}),
            },
        )
        doc = await self._manager.create_entry(request)
        if doc:
            await self._events.publish(KnowledgeEvent(
                event_type="knowledge.indexed", knowledge_id=doc.id,
                title=doc.title, category=doc.category, source="connector_runtime",
                message=f"Connector indexed: {doc.title}",
            ))
        return doc

    async def index_artifact(self, name: str, description: str,
                              source: str, tags: Optional[list[str]] = None,
                              metadata: Optional[dict[str, Any]] = None) -> Optional[KnowledgeDocument]:
        request = IndexRequest(
            title=f"Artifact: {name}",
            content=description,
            summary=f"Artifact '{name}' from {source}",
            category="artifact",
            tags=["artifact"] + (tags or []),
            source=source,
            source_url="",
            confidence=1.0,
            metadata=metadata or {},
        )
        return await self._manager.create_entry(request)
