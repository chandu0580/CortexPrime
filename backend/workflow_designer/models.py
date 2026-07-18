from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class WorkflowStatus(str, Enum):
    DRAFT = "draft"
    VALIDATED = "validated"
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class WorkflowNodeType(str, Enum):
    START = "start"
    END = "end"
    TASK = "task"
    CONDITION = "condition"
    PARALLEL = "parallel"
    APPROVAL = "approval"
    SUB_WORKFLOW = "sub_workflow"
    WAIT = "wait"
    TOOL = "tool"


class WorkflowNode:
    def __init__(
        self,
        workflow_id: str,
        node_type: WorkflowNodeType,
        label: str,
        config: Optional[Dict[str, Any]] = None,
        position: Optional[Dict[str, float]] = None,
    ):
        self.id: str = str(uuid4())
        self.workflow_id: str = workflow_id
        self.node_type: WorkflowNodeType = node_type
        self.label: str = label
        self.config: Dict[str, Any] = config or {}
        self.position: Dict[str, float] = position or {"x": 0.0, "y": 0.0}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "node_type": self.node_type.value,
            "label": self.label,
            "config": self.config,
            "position": self.position,
        }


class WorkflowEdge:
    def __init__(
        self,
        workflow_id: str,
        source_node_id: str,
        target_node_id: str,
        label: Optional[str] = None,
        condition: Optional[str] = None,
    ):
        self.id: str = str(uuid4())
        self.workflow_id: str = workflow_id
        self.source_node_id: str = source_node_id
        self.target_node_id: str = target_node_id
        self.label: Optional[str] = label
        self.condition: Optional[str] = condition

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "source_node_id": self.source_node_id,
            "target_node_id": self.target_node_id,
            "label": self.label,
            "condition": self.condition,
        }


class Workflow:
    def __init__(
        self,
        name: str,
        org_id: str,
        description: str = "",
        tags: Optional[List[str]] = None,
    ):
        self.id: str = str(uuid4())
        self.name: str = name
        self.org_id: str = org_id
        self.description: str = description
        self.tags: List[str] = tags or []
        self.status: WorkflowStatus = WorkflowStatus.DRAFT
        self.version: int = 1
        self.nodes: List[WorkflowNode] = []
        self.edges: List[WorkflowEdge] = []
        self.created_at: datetime = datetime.now(timezone.utc)
        self.updated_at: datetime = datetime.now(timezone.utc)

    def add_node(
        self,
        node_type: WorkflowNodeType,
        label: str,
        config: Optional[Dict[str, Any]] = None,
        position: Optional[Dict[str, float]] = None,
    ) -> WorkflowNode:
        node = WorkflowNode(
            workflow_id=self.id,
            node_type=node_type,
            label=label,
            config=config,
            position=position,
        )
        self.nodes.append(node)
        self.updated_at = datetime.now(timezone.utc)
        return node

    def add_edge(
        self,
        source_node_id: str,
        target_node_id: str,
        label: Optional[str] = None,
        condition: Optional[str] = None,
    ) -> WorkflowEdge:
        edge = WorkflowEdge(
            workflow_id=self.id,
            source_node_id=source_node_id,
            target_node_id=target_node_id,
            label=label,
            condition=condition,
        )
        self.edges.append(edge)
        self.updated_at = datetime.now(timezone.utc)
        return edge

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "org_id": self.org_id,
            "description": self.description,
            "tags": self.tags,
            "status": self.status.value,
            "version": self.version,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
