from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from backend.mission.dispatcher.interfaces import (
    DispatchResult,
    DispatchStepResult,
    MissionDispatcher,
    ProgressReport,
    StepStatus,
)
from backend.mission.planner.interfaces import MissionStep

log = logging.getLogger(__name__)


class MissionDispatcherImpl(MissionDispatcher):
    def __init__(self, execution_service: Optional[Any] = None) -> None:
        self._execution_service = execution_service
        self._running: dict[str, asyncio.Task] = {}
        self._cancelled: set[str] = set()
        self._progress: dict[str, ProgressReport] = {}
        self._results: dict[str, DispatchResult] = {}

    async def dispatch(self, mission_id: str, plan_id: str,
                       steps: list[MissionStep]) -> DispatchResult:
        result = DispatchResult(mission_id=mission_id, success=True)
        report = ProgressReport(
            mission_id=mission_id,
            total_steps=len(steps),
            completed_steps=0,
            failed_steps=0,
        )
        self._progress[mission_id] = report
        completed: set[str] = set()

        for step in steps:
            if mission_id in self._cancelled:
                report.status = "cancelled"
                report.message = "Mission cancelled"
                result.success = False
                break

            if not self._dependencies_met(step, completed):
                log.warning("Dependencies not met for step %s, skipping", step.step_id)
                continue

            report.current_step = step.step_id
            step_result = await self._execute_step(mission_id, step)
            result.step_results.append(step_result)
            result.started_at = datetime.now(timezone.utc)

            if step_result.status == StepStatus.COMPLETED:
                completed.add(step.step_id)
                report.completed_steps += 1
            elif step_result.status in (StepStatus.FAILED, StepStatus.TIMEOUT):
                report.failed_steps += 1
                if step.retry_count < step.max_retries:
                    step.retry_count += 1
                    log.info("Retrying step %s (attempt %d/%d)",
                             step.step_id, step.retry_count, step.max_retries)
                    retry_result = await self._execute_step(mission_id, step)
                    result.step_results.append(retry_result)
                    if retry_result.status == StepStatus.COMPLETED:
                        completed.add(step.step_id)
                        report.completed_steps += 1
                        report.failed_steps -= 1
                    else:
                        result.success = False
                        result.error = f"Step {step.step_id} failed after retries"
                        report.status = "failed"
                        break
                else:
                    result.success = False
                    result.error = f"Step {step.step_id} failed: {step_result.error}"
                    report.status = "failed"
                    break

            report.percent = (report.completed_steps / max(report.total_steps, 1)) * 100.0

        result.completed_at = datetime.now(timezone.utc)
        self._results[mission_id] = result
        self._progress[mission_id] = report
        self._cancelled.discard(mission_id)
        return result

    async def cancel(self, mission_id: str) -> bool:
        self._cancelled.add(mission_id)
        if mission_id in self._running:
            self._running[mission_id].cancel()
            del self._running[mission_id]
        if mission_id in self._progress:
            self._progress[mission_id].status = "cancelled"
        log.info("Mission %s cancelled", mission_id)
        return True

    async def get_progress(self, mission_id: str) -> Optional[ProgressReport]:
        return self._progress.get(mission_id)

    async def is_running(self, mission_id: str) -> bool:
        return mission_id in self._running

    def _dependencies_met(self, step: MissionStep, completed: set[str]) -> bool:
        if not step.dependencies:
            return True
        return all(dep in completed for dep in step.dependencies)

    async def _execute_step(self, mission_id: str, step: MissionStep) -> DispatchStepResult:
        step_result = DispatchStepResult(step_id=step.step_id, status=StepStatus.RUNNING)
        step_result.started_at = datetime.now(timezone.utc)

        if self._execution_service is not None:
            try:
                entity = await self._execution_service.run_execution(
                    command=step.name,
                    execution_type=self._infer_execution_type(step),
                    mission_id=mission_id,
                    mission_step_id=step.step_id,
                    agent=step.agent,
                    inputs=step.inputs or {},
                    timeout_seconds=step.timeout_seconds,
                    max_retries=step.max_retries,
                    tags=step.name.lower().replace(" ", "_"),
                )
                if entity and entity.status.value == "SUCCEEDED":
                    step_result.status = StepStatus.COMPLETED
                    step_result.outputs = entity.result
                else:
                    step_result.status = StepStatus.FAILED
                    step_result.error = entity.error_message if entity else "Execution returned no entity"
                step_result.completed_at = datetime.now(timezone.utc)
                if step_result.started_at and step_result.completed_at:
                    step_result.duration_ms = (step_result.completed_at - step_result.started_at).total_seconds() * 1000
                return step_result
            except asyncio.CancelledError:
                step_result.status = StepStatus.FAILED
                step_result.error = "Step cancelled"
            except Exception as exc:
                step_result.status = StepStatus.FAILED
                step_result.error = str(exc)
            step_result.completed_at = datetime.now(timezone.utc)
            if step_result.started_at and step_result.completed_at:
                step_result.duration_ms = (step_result.completed_at - step_result.started_at).total_seconds() * 1000
            return step_result

        try:
            await asyncio.sleep(0.1)
            step_result.status = StepStatus.COMPLETED
            step_result.completed_at = datetime.now(timezone.utc)
            if step_result.started_at and step_result.completed_at:
                step_result.duration_ms = (step_result.completed_at - step_result.started_at).total_seconds() * 1000
        except asyncio.CancelledError:
            step_result.status = StepStatus.FAILED
            step_result.error = "Step cancelled"
        except Exception as exc:
            step_result.status = StepStatus.FAILED
            step_result.error = str(exc)
        return step_result

    def _infer_execution_type(self, step: MissionStep) -> str:
        name_lower = step.name.lower()
        if name_lower.startswith("http") or "request" in name_lower or "api" in name_lower:
            return "http"
        if name_lower.endswith(".py") or "script" in name_lower or "execute" in name_lower:
            return "script"
        return "shell"
