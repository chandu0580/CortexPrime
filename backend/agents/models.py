from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4


class RunMissionRequest:
    def __init__(
        self,
        goal: str,
        mission_id: str = "",
        tenant_id: str = "",
        user_id: str = "",
        permissions: Optional[List[str]] = None,
        tasks: Optional[List[Dict[str, Any]]] = None,
        mode: str = "dependency",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.goal = goal
        self.mission_id = mission_id or uuid4().hex[:12]
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.permissions = permissions or []
        self.tasks = tasks or []
        self.mode = mode
        self.metadata = metadata or {}


class DelegateRequest:
    def __init__(
        self,
        mission_id: str,
        task_id: str,
        description: str,
        target_agent_type: str,
        input_data: Optional[Dict[str, Any]] = None,
        tenant_id: str = "",
        user_id: str = "",
    ) -> None:
        self.mission_id = mission_id
        self.task_id = task_id
        self.description = description
        self.target_agent_type = target_agent_type
        self.input_data = input_data or {}
        self.tenant_id = tenant_id
        self.user_id = user_id
