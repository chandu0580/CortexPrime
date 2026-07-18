from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.workflow_designer.compiler import WorkflowCompiler
from backend.workflow_designer.models import (
    Workflow,
    WorkflowNodeType,
    WorkflowStatus,
)

log = logging.getLogger(__name__)


class WorkflowEngine:
    def __init__(self):
        self._workflows: Dict[str, Workflow] = {}
        self._compiler = WorkflowCompiler()

    async def create_workflow(
        self,
        name: str,
        org_id: str,
        description: str = "",
        tags: Optional[List[str]] = None,
    ) -> Workflow:
        workflow = Workflow(
            name=name,
            org_id=org_id,
            description=description,
            tags=tags,
        )
        self._workflows[workflow.id] = workflow
        log.info("Workflow created: %s (%s)", workflow.name, workflow.id)
        return workflow

    async def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        return self._workflows.get(workflow_id)

    async def list_workflows(self, org_id: Optional[str] = None) -> List[Workflow]:
        if org_id:
            return [w for w in self._workflows.values() if w.org_id == org_id]
        return list(self._workflows.values())

    async def delete_workflow(self, workflow_id: str) -> bool:
        if workflow_id in self._workflows:
            self._workflows.pop(workflow_id)
            log.info("Workflow deleted: %s", workflow_id)
            return True
        return False

    async def add_node(
        self,
        workflow_id: str,
        node_type: str,
        label: str,
        config: Optional[Dict[str, Any]] = None,
        position: Optional[Dict[str, float]] = None,
    ) -> Optional[Dict[str, Any]]:
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return None
        try:
            nt = WorkflowNodeType(node_type)
        except ValueError:
            return None
        node = workflow.add_node(nt, label, config, position)
        return node.to_dict()

    async def add_edge(
        self,
        workflow_id: str,
        source_node_id: str,
        target_node_id: str,
        label: Optional[str] = None,
        condition: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return None
        edge = workflow.add_edge(source_node_id, target_node_id, label, condition)
        return edge.to_dict()

    async def compile_workflow(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        workflow = self._workflows.get(workflow_id)
        if not workflow:
            return None
        return self._compiler.compile(workflow)

    async def health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "workflow_count": len(self._workflows),
        }


workflow_engine = WorkflowEngine()
