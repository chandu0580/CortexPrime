from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict

from backend.mission_skills.engine import skill_engine
from backend.mission_skills.models import WorkflowDefinition

log = logging.getLogger(__name__)


class BaseMissionSkill(ABC):
    """
    Abstract base for an enterprise mission skill.

    Subclasses define ``skill_type`` and implement ``get_definition()``
    which returns a declarative ``WorkflowDefinition``.  The engine
    handles execution, persistence, retry, approval, replay, audit,
    and telemetry automatically.

    Usage::

        class MySkill(BaseMissionSkill):
            skill_type = "my_workflow"

            def get_definition(self):
                return WorkflowDefinition(
                    skill_type=self.skill_type,
                    steps=[...],
                )
    """

    skill_type: str = ""

    # ------------------------------------------------------------------
    # Lifecycle  (uses engine internally)
    # ------------------------------------------------------------------

    async def execute_all(
        self,
        execution_id: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Execute the workflow definition via ``MissionSkillEngine``.

        Delegates to ``skill_engine.execute()`` with the definition
        returned by ``get_definition()``.  All execution, persistence,
        retry, approval, replay, and audit logic is handled by the engine.
        """
        definition = self.get_definition()
        return await skill_engine.execute(
            definition=definition,
            execution_id=execution_id,
            context=context,
        )

    # ------------------------------------------------------------------
    # Workflow definition  (subclass must implement)
    # ------------------------------------------------------------------

    @abstractmethod
    def get_definition(self) -> WorkflowDefinition:
        ...
