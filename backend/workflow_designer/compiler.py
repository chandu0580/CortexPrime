from __future__ import annotations

import logging
from typing import Any, Dict

from backend.workflow_designer.models import Workflow, WorkflowNodeType

log = logging.getLogger(__name__)


class WorkflowCompiler:
    def compile(self, workflow: Workflow) -> Dict[str, Any]:
        mission_def = {
            "name": workflow.name,
            "description": workflow.description,
            "tags": workflow.tags,
            "version": workflow.version,
            "steps": [],
            "branches": [],
            "parallel_groups": [],
            "approval_gates": [],
        }

        for node in workflow.nodes:
            step = {
                "id": node.id,
                "type": node.node_type.value,
                "label": node.label,
                "config": node.config,
            }
            mission_def["steps"].append(step)

            if node.node_type == WorkflowNodeType.APPROVAL:
                mission_def["approval_gates"].append(node.id)

            if node.node_type == WorkflowNodeType.CONDITION:
                outgoing = [e for e in workflow.edges if e.source_node_id == node.id]
                branch = {
                    "condition_node_id": node.id,
                    "branches": [
                        {"edge_id": e.id, "condition": e.condition or "true", "target_id": e.target_node_id}
                        for e in outgoing
                    ],
                }
                mission_def["branches"].append(branch)

        return mission_def
