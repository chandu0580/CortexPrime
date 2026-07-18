from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.infrastructure.redis.runtime_state_manager import runtime_state

log = logging.getLogger(__name__)


# ======================================================================
# DECLARATIVE WORKFLOW DEFINITION MODELS
# ======================================================================


@dataclass
class RetryPolicy:
    """Retry configuration for a workflow step."""

    max_retries: int = 2
    backoff_strategy: str = "exponential"  # exponential | fixed | none
    base_delay_s: float = 1.0


@dataclass
class ApprovalConfig:
    """Approval gate configuration for a workflow step."""

    required: bool = True
    timeout: int = 300
    risk_level: str = "medium"
    description_template: str = ""
    action: str = "approve_step"


@dataclass
class WorkflowStepDef:
    """Declarative definition for a single workflow step.

    Fields
    ------
    id : str
        Unique step identifier.  Referenced by ``$steps.<id>.<field>``
        in subsequent step params.
    name : str
        Human-readable step label.
    connector : str | None
        Connector type to resolve from ConnectorRegistry.  ``None``
        for special steps (approval).
    operation : str
        Connector method name, or ``__approval__`` for the approval gate.
    params : dict
        Parameters passed to the operation.  Supports ``$params.*``
        (mission context) and ``$steps.*`` (prior step results) references.
    retry : RetryPolicy
        Retry strategy when the operation fails.
    timeout : float | None
        Optional per-step timeout in seconds.
    approval : ApprovalConfig | None
        When set, an approval gate runs BEFORE the step.
    condition : str | None
        Optional ``$params.*`` expression; step is skipped when falsy.
    on_failure : str
        Behaviour on failure: ``fail`` (default, raises), ``skip``
        (marks completed), or ``continue`` (marks failed, proceeds).
    outputs : dict | None
        Optional mapping of output field names from the raw result
        (e.g. ``{"branch": "$.ref"}`` or ``{"pr_number": "$.number"}``).
    """

    id: str = ""
    name: str = ""
    connector: Optional[str] = None
    operation: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    timeout: Optional[float] = None
    approval: Optional[ApprovalConfig] = None
    condition: Optional[str] = None
    on_failure: str = "fail"
    outputs: Optional[Dict[str, str]] = None


@dataclass
class WorkflowDefinition:
    """Declarative definition for an entire enterprise workflow.

    Fields
    ------
    skill_type : str
        Unique skill identifier (e.g. ``software_release``).
    description : str
        Human-readable summary of the workflow.
    steps : list[WorkflowStepDef]
        Ordered list of workflow steps.
    """

    skill_type: str = ""
    description: str = ""
    steps: List[WorkflowStepDef] = field(default_factory=list)


@dataclass
class StepResult:
    """Result produced by the engine after executing one step."""

    step_id: str
    success: bool
    output: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    duration_ms: int = 0
    retries: int = 0
    skipped: bool = False


# ======================================================================
# MISSION STATE MODEL  (Redis-persisted workflow progress)
# ======================================================================


class MissionStateModel:
    """
    Redis-persisted workflow state for a multi-step enterprise mission skill.

    Tracks:
      - current_step
      - completed_steps
      - failed_steps
      - step_attempts
      - resources_created
      - approval_state
      - skill_type
      - status

    Persistence uses ``runtime_state.set_execution_state()`` /
    ``runtime_state.get_execution_state()`` with automatic TTL.

    Usage::

        state = await MissionStateModel.load(execution_id)
        state.advance_step("create_release_branch")
        state.add_resource("branch", "release/v1.2.0")
        await state.save()
    """

    def __init__(
        self,
        execution_id: str,
        skill_type: str = "",
    ) -> None:
        self.execution_id: str = execution_id
        self.skill_type: str = skill_type
        self.status: str = "running"
        self.current_step: str = ""
        self.completed_steps: List[str] = []
        self.failed_steps: List[str] = []
        self.step_attempts: Dict[str, int] = {}
        self.resources_created: List[Dict[str, str]] = []
        self.approval_state: Dict[str, Any] = {}
        self.created_at: str = datetime.now(timezone.utc).isoformat()
        self.updated_at: str = self.created_at

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def save(self) -> None:
        self.updated_at = datetime.now(timezone.utc).isoformat()
        try:
            await runtime_state.set_execution_state(
                self.execution_id,
                self._serialize(),
            )
        except Exception as exc:
            log.warning("MissionStateModel.save failed: %s", exc)

    @classmethod
    async def load(cls, execution_id: str) -> Optional["MissionStateModel"]:
        try:
            raw = await runtime_state.get_execution_state(execution_id)
            if raw:
                return cls._deserialize(execution_id, raw)
        except Exception as exc:
            log.warning("MissionStateModel.load failed: %s", exc)
        return None

    # ------------------------------------------------------------------
    # Step tracking
    # ------------------------------------------------------------------

    def advance_step(self, step_id: str) -> None:
        self.current_step = step_id
        self.step_attempts[step_id] = self.step_attempts.get(step_id, 0) + 1

    def complete_step(self, step_id: str) -> None:
        if step_id not in self.completed_steps:
            self.completed_steps.append(step_id)

    def fail_step(self, step_id: str) -> None:
        if step_id not in self.failed_steps:
            self.failed_steps.append(step_id)

    def add_resource(self, resource_type: str, resource_id: str, metadata: Optional[Dict[str, str]] = None) -> None:
        self.resources_created.append({
            "type": resource_type,
            "id": resource_id,
            **(metadata or {}),
        })

    def set_approval(self, step_id: str, status: str, details: Optional[Dict[str, Any]] = None) -> None:
        self.approval_state[step_id] = {
            "status": status,
            "details": details or {},
        }

    def is_last_step_completed(self, step_id: str) -> bool:
        return step_id in self.completed_steps

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def _serialize(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "skill_type": self.skill_type,
            "status": self.status,
            "current_step": self.current_step,
            "completed_steps": self.completed_steps,
            "failed_steps": self.failed_steps,
            "step_attempts": self.step_attempts,
            "resources_created": self.resources_created,
            "approval_state": self.approval_state,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def _deserialize(cls, execution_id: str, data: Dict[str, Any]) -> "MissionStateModel":
        obj = cls(execution_id)
        obj.skill_type = data.get("skill_type", "")
        obj.status = data.get("status", "running")
        obj.current_step = data.get("current_step", "")
        obj.completed_steps = data.get("completed_steps", [])
        obj.failed_steps = data.get("failed_steps", [])
        obj.step_attempts = data.get("step_attempts", {})
        obj.resources_created = data.get("resources_created", [])
        obj.approval_state = data.get("approval_state", {})
        obj.created_at = data.get("created_at", obj.created_at)
        obj.updated_at = data.get("updated_at", obj.updated_at)
        return obj
