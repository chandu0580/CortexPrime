"""
Enterprise Pipeline Orchestrator — DEPRECATED compatibility wrapper.

All functionality has been merged into EnterpriseDeliveryOrchestrator.
This module is kept for backward compatibility and delegates all calls
to the delivery orchestrator singleton.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.core.shared import load_json as _delivery_load_json
from backend.core.shared import now
from backend.core.shared import save_json as _delivery_save_json
from backend.events.enterprise_event_types import EnterpriseEventTypes as EET
from backend.services.enterprise_delivery_orchestrator import (
    delivery_orchestrator,
)

log = logging.getLogger(__name__)


# Re-export constants for backward compatibility
PIPELINE_STAGES = [
    "trigger",
    "sandbox",
    "code_intel",
    "patch",
    "git",
    "approval",
    "complete",
]

PIPELINE_EVENTS = {
    "created": EET.PIPELINE_CREATED,
    "started": EET.PIPELINE_STARTED,
    "stage_started": EET.PIPELINE_STAGE_STARTED,
    "stage_completed": EET.PIPELINE_STAGE_COMPLETED,
    "stage_failed": EET.PIPELINE_STAGE_FAILED,
    "completed": EET.PIPELINE_COMPLETED,
    "failed": EET.PIPELINE_FAILED,
    "cancelled": EET.PIPELINE_CANCELLED,
    "patch_to_pr": EET.PIPELINE_PATCH_TO_PR,
    "pr_created": EET.PIPELINE_PR_CREATED,
    "artifact_passed": EET.PIPELINE_ARTIFACT_PASSED,
}


class PipelineStateMachine:
    """DEPRECATED — kept for backward compatibility."""

    _VALID_TRANSITIONS: Dict[str, List[str]] = {
        "pending":   ["running", "cancelled"],
        "running":   ["paused", "completed", "failed", "cancelled"],
        "paused":    ["running", "cancelled"],
        "completed": [],
        "failed":    [],
        "cancelled": [],
    }

    @staticmethod
    def can_transition(current: str, target: str) -> bool:
        allowed = PipelineStateMachine._VALID_TRANSITIONS.get(current, [])
        return target in allowed

    @staticmethod
    def is_terminal(state: str) -> bool:
        return state in ("completed", "failed", "cancelled")


class EnterprisePipelineOrchestrator:
    """
    DEPRECATED — delegates to EnterpriseDeliveryOrchestrator.
    All pipeline orchestration functionality is now in delivery_orchestrator.
    """

    def __init__(self) -> None:
        self._pipelines: Dict[str, Dict[str, Any]] = {}
        self._pipeline_json_path = (Path(__file__).resolve().parent.parent / "data" / "pipelines.json")

    async def create_pipeline(self, **kwargs: Any) -> Dict[str, Any]:
        result = await delivery_orchestrator.create_pipeline(**kwargs)
        if result and result.get("pipeline_id"):
            self._pipelines[result["pipeline_id"]] = result
        return result

    async def get_pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        return await delivery_orchestrator.get_pipeline(pipeline_id)

    async def list_pipelines(self, status: str = "", limit: int = 50) -> List[Dict[str, Any]]:
        return await delivery_orchestrator.list_pipelines(status=status, limit=limit)

    async def update_pipeline(self, pipeline_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        result = await delivery_orchestrator.update_pipeline(pipeline_id, updates)
        if result and result.get("pipeline_id"):
            self._pipelines[result["pipeline_id"]] = result
        return result

    async def delete_pipeline(self, pipeline_id: str) -> bool:
        result = await delivery_orchestrator.delete_pipeline(pipeline_id)
        if result:
            self._pipelines.pop(pipeline_id, None)
        return result

    async def start_pipeline(self, pipeline_id: str) -> Dict[str, Any]:
        return await delivery_orchestrator.start_pipeline(pipeline_id)

    async def pause_pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        return await delivery_orchestrator.pause_pipeline(pipeline_id)

    async def resume_pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        return await delivery_orchestrator.resume_pipeline(pipeline_id)

    async def cancel_pipeline(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        return await delivery_orchestrator.cancel_pipeline(pipeline_id)

    async def get_dashboard_stats(self) -> Dict[str, Any]:
        return await delivery_orchestrator.pipeline_dashboard_stats()

    async def patch_to_pr(self, **kwargs: Any) -> Dict[str, Any]:
        return await delivery_orchestrator.patch_to_pr(**kwargs)

    # ── Private delegate methods (for backward compatibility with tests) ──

    async def _transition(self, pipeline_id: str, target: str) -> Optional[Dict[str, Any]]:
        await self._ensure_in_memory_synced(pipeline_id)
        result = await delivery_orchestrator._pipeline_transition(pipeline_id, target)
        if result and result.get("pipeline_id"):
            self._pipelines[result["pipeline_id"]] = result
        return result

    async def _execute_stages(self, pipeline_id: str) -> Dict[str, Any]:
        """Execute pipeline stages. Calls self._execute_stage per stage
        so that monkey-patching by tests works correctly."""
        await self._ensure_in_memory_synced(pipeline_id)
        pipeline = await self.get_pipeline(pipeline_id)
        if not pipeline:
            raise ValueError(f"Pipeline not found: {pipeline_id}")

        completed = set(pipeline.get("stages_completed", []))
        start_index = 0
        for i, stage in enumerate(PIPELINE_STAGES):
            if stage in completed:
                start_index = i + 1
            else:
                break

        for i in range(start_index, len(PIPELINE_STAGES)):
            stage = PIPELINE_STAGES[i]

            pipeline = await self.get_pipeline(pipeline_id)
            if not pipeline or pipeline.get("status") in ("completed", "failed", "cancelled"):
                break
            if pipeline["status"] == "paused":
                break

            # Update current stage
            await self.update_pipeline(pipeline_id, {
                "current_stage": stage,
                "current_stage_index": i,
            })

            await self._emit(PIPELINE_EVENTS["stage_started"], pipeline_id, {"stage": stage})

            try:
                await self._execute_stage(pipeline_id, stage)
                pipeline = await self.get_pipeline(pipeline_id)
                if pipeline:
                    completed_list = pipeline.get("stages_completed", [])
                    if stage not in completed_list:
                        completed_list.append(stage)
                    await self.update_pipeline(pipeline_id, {
                        "stages_completed": completed_list,
                        "current_stage": stage,
                    })
                await self._emit(PIPELINE_EVENTS["stage_completed"], pipeline_id, {"stage": stage})
            except Exception as exc:
                pipeline = await self.get_pipeline(pipeline_id)
                if pipeline:
                    failed_list = pipeline.get("stages_failed", [])
                    if stage not in failed_list:
                        failed_list.append(stage)
                    await self.update_pipeline(pipeline_id, {
                        "stages_failed": failed_list,
                        "error": str(exc),
                    })
                await self._emit(PIPELINE_EVENTS["stage_failed"], pipeline_id, {"stage": stage, "error": str(exc)})

                if stage in ("trigger", "sandbox", "patch", "git"):
                    await self.update_pipeline(pipeline_id, {
                        "status": "failed",
                        "completed_at": now(),
                    })
                    raise RuntimeError(f"Stage '{stage}' failed: {exc}")

        pipeline = await self.get_pipeline(pipeline_id)
        if pipeline:
            current = pipeline.get("status", "")
            if current not in ("completed", "failed", "cancelled") and current != "paused":
                await self._transition(pipeline_id, "completed")
                await self.update_pipeline(pipeline_id, {"completed_at": now()})
                pipeline = await self.get_pipeline(pipeline_id)
                await self._emit(PIPELINE_EVENTS["completed"], pipeline_id, pipeline)
        return pipeline or {}

    async def _execute_stage(self, pipeline_id: str, stage: str) -> None:
        await self._ensure_in_memory_synced(pipeline_id)
        return await delivery_orchestrator._pipeline_execute_stage(pipeline_id, stage)

    async def _emit(self, event_type: str, entity_id: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        return await delivery_orchestrator._pipeline_emit(event_type, entity_id, metadata)

    def _persist(self) -> None:
        self._flush_in_memory_to_json()

    async def _ensure_in_memory_synced(self, pipeline_id: str) -> None:
        """Before delegating to delivery_orchestrator, sync the in-memory
        pipeline state for the given pipeline_id to the JSON store so the
        delivery orchestrator sees it."""
        if pipeline_id in self._pipelines:

            self._pipeline_json_path.parent.mkdir(parents=True, exist_ok=True)
            current = _delivery_load_json(self._pipeline_json_path)
            updated = False
            for i, p in enumerate(current):
                if p["pipeline_id"] == pipeline_id:
                    current[i] = self._pipelines[pipeline_id]
                    updated = True
                    break
            if not updated:
                current.insert(0, self._pipelines[pipeline_id])
            _delivery_save_json(self._pipeline_json_path, current)

    def _reload_in_memory(self) -> None:
        """Reload the in-memory _pipelines dict from the JSON store."""
        self._pipelines.clear()
        try:
            if self._pipeline_json_path.exists():
                with open(self._pipeline_json_path) as f:
                    import json
                    data = json.load(f)
                    for item in data:
                        self._pipelines[item["pipeline_id"]] = item
        except Exception:
            pass

    def _flush_in_memory_to_json(self) -> None:
        """Write all in-memory pipelines to the JSON store."""
        import json
        self._pipeline_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._pipeline_json_path, "w") as f:
            json.dump(list(self._pipelines.values()), f, indent=2, default=str)


# Singleton — kept for backward compatibility
pipeline_orchestrator = EnterprisePipelineOrchestrator()
