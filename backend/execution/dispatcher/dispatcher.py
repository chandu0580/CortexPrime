from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from backend.execution.dispatcher.interfaces import (
    DispatchStepStatus,
    ExecutionDispatcher,
    ExecutionDispatchResult,
    ExecutionDispatchStepResult,
    ExecutionProgressReport,
)

log = logging.getLogger(__name__)


class ExecutionDispatcherImpl(ExecutionDispatcher):
    def __init__(self) -> None:
        self._running: dict[str, asyncio.Task] = {}
        self._cancelled: set[str] = set()
        self._progress: dict[str, ExecutionProgressReport] = {}
        self._results: dict[str, ExecutionDispatchResult] = {}

    async def dispatch(
        self,
        execution_id: str,
        execution_type: str,
        command: str,
        inputs: Optional[dict[str, Any]] = None,
        environment: Optional[dict[str, Any]] = None,
        timeout_seconds: int = 300,
    ) -> ExecutionDispatchResult:
        from backend.execution.sandbox.interfaces import sandbox_registry

        report = ExecutionProgressReport(execution_id=execution_id, total_steps=1)
        self._progress[execution_id] = report

        sandbox = sandbox_registry.get(execution_type)
        if not sandbox:
            result = ExecutionDispatchResult(
                execution_id=execution_id, success=False,
                error=f"Unsupported execution type: {execution_type}",
            )
            self._results[execution_id] = result
            return result

        if execution_id in self._cancelled:
            report.status = "cancelled"
            result = ExecutionDispatchResult(
                execution_id=execution_id, success=False, error="Execution cancelled before start",
            )
            self._results[execution_id] = result
            return result

        step_result = ExecutionDispatchStepResult(
            step_id="main", status=DispatchStepStatus.RUNNING,
        )
        step_result.started_at = datetime.now(timezone.utc)

        task = asyncio.create_task(
            self._run_sandbox(sandbox, command, inputs, environment, timeout_seconds, step_result)
        )
        self._running[execution_id] = task

        try:
            sandbox_result = await task
        except asyncio.CancelledError:
            step_result.status = DispatchStepStatus.FAILED
            step_result.error = "Execution cancelled"
            result = ExecutionDispatchResult(
                execution_id=execution_id, success=False,
                step_results=[step_result], error="Execution cancelled",
                completed_at=datetime.now(timezone.utc),
            )
            self._results[execution_id] = result
            return result

        step_result.outputs = sandbox_result.outputs
        step_result.error = sandbox_result.error
        step_result.duration_ms = sandbox_result.duration_ms
        step_result.completed_at = datetime.now(timezone.utc)

        if sandbox_result.success:
            step_result.status = DispatchStepStatus.COMPLETED
            report.completed_steps = 1
            report.status = "completed"
            result = ExecutionDispatchResult(
                execution_id=execution_id, success=True,
                step_results=[step_result],
                completed_at=datetime.now(timezone.utc),
            )
        else:
            step_result.status = DispatchStepStatus.FAILED
            report.failed_steps = 1
            report.status = "failed"
            result = ExecutionDispatchResult(
                execution_id=execution_id, success=False,
                step_results=[step_result],
                error=sandbox_result.error or "Execution failed",
                completed_at=datetime.now(timezone.utc),
            )

        report.percent = 100.0
        self._results[execution_id] = result
        self._progress[execution_id] = report
        self._running.pop(execution_id, None)
        self._cancelled.discard(execution_id)
        return result

    async def _run_sandbox(self, sandbox, command, inputs, environment, timeout, step_result):
        return await sandbox.execute(
            command=command,
            inputs=inputs,
            environment=environment,
            timeout_seconds=timeout,
        )

    async def cancel(self, execution_id: str) -> bool:
        self._cancelled.add(execution_id)
        if execution_id in self._running:
            self._running[execution_id].cancel()
            del self._running[execution_id]
        if execution_id in self._progress:
            self._progress[execution_id].status = "cancelled"
        log.info("Execution %s cancelled", execution_id)
        return True

    async def get_progress(self, execution_id: str) -> Optional[ExecutionProgressReport]:
        return self._progress.get(execution_id)

    async def is_running(self, execution_id: str) -> bool:
        return execution_id in self._running
