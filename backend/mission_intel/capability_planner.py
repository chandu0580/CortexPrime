from __future__ import annotations

import logging
from typing import Any, Dict, List

from backend.mission_intel.models import (
    CapabilityPlan,
    MissionDecomposition,
)

log = logging.getLogger(__name__)

_KNOWN_CONNECTOR_CAPABILITIES: Dict[str, List[str]] = {
    "github": ["build", "deploy", "search", "execute", "observe", "notify"],
    "jira": ["search", "execute", "notify"],
    "slack": ["notify", "search", "execute"],
    "kubernetes": ["observe", "deploy", "scale", "restart", "execute"],
    "docker": ["observe", "execute", "restart", "deploy"],
    "prometheus": ["observe", "search"],
    "grafana": ["observe", "search"],
}


class CapabilityPlanner:

    async def plan(
        self,
        decomposition: MissionDecomposition,
        connector_registry: Any = None,
    ) -> CapabilityPlan:
        task_mappings: Dict[str, str] = {}
        connector_mappings: Dict[str, str] = {}
        available_connectors: List[str] = []
        capability_gaps: List[str] = []

        if connector_registry is not None:
            registry_list = None
            if hasattr(connector_registry, "list_adapters"):
                try:
                    registry_list = connector_registry.list_adapters()
                except Exception:
                    pass
            elif hasattr(connector_registry, "list"):
                try:
                    registry_list = connector_registry.list()
                except Exception:
                    pass
            if registry_list is not None and isinstance(registry_list, (list, tuple)):
                available_connectors = [
                    r.get("connector_type", "") if isinstance(r, dict) else str(r)
                    for r in registry_list
                ]
            else:
                available_connectors = list(_KNOWN_CONNECTOR_CAPABILITIES.keys())
        else:
            available_connectors = list(_KNOWN_CONNECTOR_CAPABILITIES.keys())

        for task in decomposition.tasks:
            task_mappings[task.id] = task.required_capability
            suggested = task.suggested_connector
            if suggested in available_connectors:
                connector_mappings[task.id] = suggested
            else:
                for conn_type in available_connectors:
                    caps = _KNOWN_CONNECTOR_CAPABILITIES.get(conn_type, [])
                    if task.required_capability in caps:
                        connector_mappings[task.id] = conn_type
                        break
                if task.id not in connector_mappings:
                    capability_gaps.append(
                        f"{task.name} requires '{task.required_capability}' "
                        f"(suggested: {suggested})"
                    )
                    connector_mappings[task.id] = suggested

        return CapabilityPlan(
            task_mappings=task_mappings,
            connector_mappings=connector_mappings,
            capability_gaps=capability_gaps,
            available_connectors=available_connectors,
        )


capability_planner = CapabilityPlanner()
