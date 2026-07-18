from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from backend.database.repositories.factory import RepositoryFactory
    from backend.database.repositories.factory import repo_factory as _repo_factory
except ImportError:
    _repo_factory = None
from backend.database.repositories.executions import ExecutionEventModel, ExecutionModel
from backend.execution.dispatcher.dispatcher import ExecutionDispatcherImpl
from backend.execution.dispatcher.interfaces import ExecutionDispatcher
from backend.execution.events import ExecutionEvent, ExecutionEventPublisher, execution_event_publisher
from backend.execution.models import (
    ExecutionContext,
    ExecutionEntity,
    ExecutionMetadata,
    ExecutionStatus,
    ExecutionTrigger,
    ExecutionType,
)
from backend.execution.state_machine import is_terminal, is_valid_transition, validate_transition
from backend.governance.models import DecisionRequest

log = logging.getLogger(__name__)


class ExecutionService:
    def __init__(
        self,
        dispatcher: Optional[ExecutionDispatcher] = None,
        events: Optional[ExecutionEventPublisher] = None,
        repo_factory: Optional[RepositoryFactory] = None,
        governance_service: Optional[Any] = None,
        knowledge_service: Optional[Any] = None,
    ) -> None:
        self._dispatcher = dispatcher or ExecutionDispatcherImpl()
        self._events = events or execution_event_publisher
        self._repo_factory = repo_factory or _repo_factory or RepositoryFactory()
        self._governance_service = governance_service
        self._knowledge_service = knowledge_service

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_execution(
        self,
        command: str,
        execution_type: ExecutionType = ExecutionType.SHELL,
        trigger: ExecutionTrigger = ExecutionTrigger.MANUAL,
        mission_id: Optional[str] = None,
        mission_step_id: Optional[str] = None,
        parent_execution_id: Optional[str] = None,
        agent: Optional[str] = None,
        inputs: Optional[dict[str, Any]] = None,
        environment: Optional[dict[str, Any]] = None,
        parameters: Optional[dict[str, Any]] = None,
        timeout_seconds: int = 300,
        max_retries: int = 3,
        tags: Optional[list[str]] = None,
        source: str = "api",
    ) -> ExecutionEntity:
        execution_id = str(uuid.uuid4())
        datetime.now(timezone.utc)
        correlation_id = str(uuid.uuid4())

        model = ExecutionModel(
            id=uuid.uuid4(),
            execution_id=execution_id,
            status=ExecutionStatus.CREATED.value,
            agent=agent,
            trigger=trigger.value,
            context={
                "execution_type": execution_type.value,
                "command": command,
                "inputs": inputs or {},
                "environment": environment or {},
                "parameters": parameters or {},
                "mission_id": mission_id,
                "mission_step_id": mission_step_id,
                "parent_execution_id": parent_execution_id,
                "correlation_id": correlation_id,
                "tags": tags or [],
                "source": source,
                "timeout_seconds": timeout_seconds,
                "max_retries": max_retries,
            },
        )
        repo = await self._repo_factory.execution_repo()
        model = await repo.create(model)

        entity = self._model_to_entity(model)
        entity.metadata.correlation_id = correlation_id
        entity.metadata.timeout_seconds = timeout_seconds
        entity.metadata.max_retries = max_retries

        await self._publish_event(entity, "execution.created",
                                   to_status="CREATED", actor=agent)
        return entity

    # ------------------------------------------------------------------
    # State transitions
    # ------------------------------------------------------------------

    async def queue_execution(self, execution_id: str, actor: Optional[str] = None) -> Optional[ExecutionEntity]:
        entity = await self._get_entity(execution_id)
        if not entity:
            return None
        if not is_valid_transition(entity.status, ExecutionStatus.QUEUED):
            raise ValueError(f"Cannot queue execution in status {entity.status.value}")

        await self._transition(entity, ExecutionStatus.QUEUED, actor)
        await self._publish_event(entity, "execution.queued",
                                   to_status="QUEUED", actor=actor)
        return entity

    async def start_execution(self, execution_id: str, actor: Optional[str] = None) -> Optional[ExecutionEntity]:
        entity = await self._get_entity(execution_id)
        if not entity:
            return None
        if not is_valid_transition(entity.status, ExecutionStatus.STARTING):
            raise ValueError(f"Cannot start execution in status {entity.status.value}")

        await self._transition(entity, ExecutionStatus.STARTING, actor)
        await self._publish_event(entity, "execution.started",
                                   to_status="STARTING", actor=actor)

        entity = await self._transition(entity, ExecutionStatus.RUNNING, actor)
        return entity

    async def complete_execution(self, execution_id: str, result: Optional[dict[str, Any]] = None,
                                  actor: Optional[str] = None) -> Optional[ExecutionEntity]:
        entity = await self._get_entity(execution_id)
        if not entity:
            return None
        if not is_valid_transition(entity.status, ExecutionStatus.SUCCEEDED):
            raise ValueError(f"Cannot complete execution in status {entity.status.value}")

        await self._transition(entity, ExecutionStatus.SUCCEEDED, actor)
        entity.completed_at = datetime.now(timezone.utc)
        entity.duration_ms = (entity.completed_at - entity.started_at).total_seconds() * 1000 if entity.started_at else None
        entity.result = result or {}
        await self._publish_event(entity, "execution.completed",
                                   to_status="SUCCEEDED", actor=actor,
                                   payload={"duration_ms": entity.duration_ms})
        await self._persist_result(entity)
        await self._index_execution_knowledge(entity, "completed")
        return entity

    async def fail_execution(self, execution_id: str, error: str,
                              actor: Optional[str] = None) -> Optional[ExecutionEntity]:
        entity = await self._get_entity(execution_id)
        if not entity:
            return None
        if not is_valid_transition(entity.status, ExecutionStatus.FAILED):
            raise ValueError(f"Cannot fail execution in status {entity.status.value}")

        await self._transition(entity, ExecutionStatus.FAILED, actor)
        entity.completed_at = datetime.now(timezone.utc)
        entity.duration_ms = (entity.completed_at - entity.started_at).total_seconds() * 1000 if entity.started_at else None
        entity.error_message = error
        await self._publish_event(entity, "execution.failed",
                                   to_status="FAILED", actor=actor,
                                   payload={"error": error})
        await self._persist_result(entity)
        await self._index_execution_knowledge(entity, "failed")
        return entity

    async def cancel_execution(self, execution_id: str, reason: Optional[str] = None,
                                actor: Optional[str] = None) -> Optional[ExecutionEntity]:
        entity = await self._get_entity(execution_id)
        if not entity:
            return None
        if is_terminal(entity.status):
            raise ValueError(f"Cannot cancel execution in terminal status {entity.status.value}")

        await self._dispatcher.cancel(execution_id)
        await self._transition(entity, ExecutionStatus.CANCELLED, actor)
        entity.completed_at = datetime.now(timezone.utc)
        entity.error_message = reason
        await self._publish_event(entity, "execution.cancelled",
                                   to_status="CANCELLED", actor=actor,
                                   payload={"reason": reason or ""})
        await self._persist_result(entity)
        await self._index_execution_knowledge(entity, "cancelled")
        return entity

    async def retry_execution(self, execution_id: str, actor: Optional[str] = None) -> Optional[ExecutionEntity]:
        entity = await self._get_entity(execution_id)
        if not entity:
            return None
        if entity.status not in (ExecutionStatus.FAILED, ExecutionStatus.TIMED_OUT):
            raise ValueError(f"Cannot retry execution in status {entity.status.value}")

        entity.metadata.retry_count += 1
        await self._transition(entity, ExecutionStatus.QUEUED, actor)
        await self._publish_event(entity, "execution.retried",
                                   to_status="QUEUED", actor=actor,
                                   payload={"retry_count": entity.metadata.retry_count})
        return entity

    async def pause_execution(self, execution_id: str, actor: Optional[str] = None) -> Optional[ExecutionEntity]:
        entity = await self._get_entity(execution_id)
        if not entity:
            return None
        if not is_valid_transition(entity.status, ExecutionStatus.PAUSED):
            raise ValueError(f"Cannot pause execution in status {entity.status.value}")

        await self._transition(entity, ExecutionStatus.PAUSED, actor)
        await self._publish_event(entity, "execution.paused",
                                   to_status="PAUSED", actor=actor)
        return entity

    # ------------------------------------------------------------------
    # Run (create + queue + transition through lifecycle)
    # ------------------------------------------------------------------

    async def run_execution(
        self,
        command: str,
        execution_type: ExecutionType = ExecutionType.SHELL,
        trigger: ExecutionTrigger = ExecutionTrigger.MANUAL,
        mission_id: Optional[str] = None,
        mission_step_id: Optional[str] = None,
        agent: Optional[str] = None,
        inputs: Optional[dict[str, Any]] = None,
        environment: Optional[dict[str, Any]] = None,
        parameters: Optional[dict[str, Any]] = None,
        timeout_seconds: int = 300,
        max_retries: int = 3,
        tags: Optional[list[str]] = None,
        source: str = "api",
    ) -> ExecutionEntity:
        entity = await self.create_execution(
            command=command, execution_type=execution_type,
            trigger=trigger, mission_id=mission_id,
            mission_step_id=mission_step_id, agent=agent,
            inputs=inputs, environment=environment,
            parameters=parameters, timeout_seconds=timeout_seconds,
            max_retries=max_retries, tags=tags, source=source,
        )

        entity = await self.queue_execution(entity.execution_id, actor=agent)
        if not entity:
            return entity

        entity = await self.start_execution(entity.execution_id, actor=agent)
        if not entity:
            return entity

        if self._governance_service is not None:
            try:
                gov_request = DecisionRequest(
                    requester=agent or "",
                    user=agent or "",
                    role="",
                    tenant="",
                    mission_id=mission_id,
                    execution_id=entity.execution_id,
                    execution_type=execution_type.value if isinstance(execution_type, ExecutionType) else str(execution_type),
                    action="execute",
                    resource_type="execution",
                    resource_id=entity.execution_id,
                    risk_level=entity.metadata.custom.get("risk_level", "low") if entity.metadata else "low",
                    context={"command": command},
                )
                gov_response = await self._governance_service.evaluate(gov_request)
                if gov_response.denied:
                    entity = await self.fail_execution(
                        entity.execution_id,
                        error=f"Governance denied: {gov_response.message}",
                        actor=agent,
                    )
                    return entity
            except Exception as exc:
                log.warning("Governance evaluation failed (proceeding without): %s", exc)

        dispatch_result = await self._dispatcher.dispatch(
            execution_id=entity.execution_id,
            execution_type=execution_type.value if isinstance(execution_type, ExecutionType) else execution_type,
            command=command,
            inputs=inputs,
            environment=environment,
            timeout_seconds=timeout_seconds,
        )

        if dispatch_result.success:
            entity = await self.complete_execution(
                entity.execution_id,
                result=dispatch_result.step_results[0].outputs if dispatch_result.step_results else {},
                actor=agent,
            )
        else:
            entity = await self.fail_execution(
                entity.execution_id,
                error=dispatch_result.error or "Execution failed",
                actor=agent,
            )

        return entity

    # ------------------------------------------------------------------
    # Read / Query
    # ------------------------------------------------------------------

    async def get_execution(self, execution_id: str) -> Optional[ExecutionEntity]:
        repo = await self._repo_factory.execution_repo()
        model = await repo.get_by_execution_id(execution_id)
        return self._model_to_entity(model) if model else None

    async def get_execution_by_uuid(self, pk: uuid.UUID) -> Optional[ExecutionEntity]:
        repo = await self._repo_factory.execution_repo()
        model = await repo.get(pk)
        return self._model_to_entity(model) if model else None

    async def list_executions(
        self,
        status: Optional[str] = None,
        agent: Optional[str] = None,
        trigger: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExecutionEntity]:
        repo = await self._repo_factory.execution_repo()
        models = await repo.search(status=status, agent=agent, trigger=trigger, limit=limit, offset=offset)
        return [self._model_to_entity(m) for m in models]

    async def list_by_mission(self, mission_id: str, limit: int = 50, offset: int = 0) -> list[ExecutionEntity]:
        repo = await self._repo_factory.execution_repo()
        models = await repo.search_by_mission(mission_id, limit=limit, offset=offset)
        return [self._model_to_entity(m) for m in models]

    async def get_execution_events(self, execution_id: str, limit: int = 200, offset: int = 0) -> list[ExecutionEventModel]:
        repo = await self._repo_factory.execution_event_repo()
        return await repo.list_for_execution(execution_id, limit=limit, offset=offset)

    async def get_progress(self, execution_id: str) -> Any:
        return await self._dispatcher.get_progress(execution_id)

    async def get_in_memory_events(self, execution_id: str) -> Any:
        return await self._events.get_events(execution_id)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _get_entity(self, execution_id: str) -> Optional[ExecutionEntity]:
        repo = await self._repo_factory.execution_repo()
        model = await repo.get_by_execution_id(execution_id)
        return self._model_to_entity(model) if model else None

    async def _transition(self, entity: ExecutionEntity, target: ExecutionStatus,
                           actor: Optional[str] = None) -> ExecutionEntity:
        validate_transition(entity.status, target)
        entity.status = target
        repo = await self._repo_factory.execution_repo()
        model = await repo.get_by_execution_id(entity.execution_id)
        if model:
            model.status = target.value
            if target == ExecutionStatus.STARTING:
                model.started_at = model.started_at or datetime.now(timezone.utc)
                entity.started_at = model.started_at
            elif target in (ExecutionStatus.SUCCEEDED, ExecutionStatus.FAILED,
                            ExecutionStatus.CANCELLED, ExecutionStatus.TIMED_OUT):
                model.completed_at = datetime.now(timezone.utc)
                entity.completed_at = model.completed_at
                if entity.started_at:
                    entity.duration_ms = (model.completed_at - model.started_at).total_seconds() * 1000
                    model.duration_ms = entity.duration_ms
            await repo.update(model)
        return entity

    async def _index_execution_knowledge(self, entity: ExecutionEntity, status: str) -> None:
        if self._knowledge_service is None:
            return
        try:
            trigger = entity.trigger.value if hasattr(entity.trigger, "value") else str(entity.trigger)
            await self._knowledge_service.index_execution(
                execution_id=entity.execution_id,
                mission_id=entity.mission_id,
                agent=entity.agent or "",
                status=status,
                trigger=trigger,
                result_data=entity.result if status == "completed" else None,
                error=entity.error_message if status == "failed" else None,
            )
        except Exception as exc:
            log.warning("Failed to index execution knowledge: %s", exc)

    async def _persist_result(self, entity: ExecutionEntity) -> None:
        repo = await self._repo_factory.execution_repo()
        model = await repo.get_by_execution_id(entity.execution_id)
        if model:
            model.result = entity.result or {}
            model.error_message = entity.error_message
            model.completed_at = entity.completed_at or datetime.now(timezone.utc)
            model.duration_ms = entity.duration_ms
            await repo.update(model)

    async def _publish_event(self, entity: ExecutionEntity, event_type: str,
                              from_status: Optional[str] = None,
                              to_status: Optional[str] = None,
                              actor: Optional[str] = None,
                              payload: Optional[dict[str, Any]] = None) -> None:
        await self._events.publish(ExecutionEvent(
            execution_id=entity.execution_id,
            event_type=event_type,
            correlation_id=entity.metadata.correlation_id,
            from_status=from_status or entity.status.value,
            to_status=to_status or entity.status.value,
            actor=actor,
            payload=payload or {},
        ))

    def _model_to_entity(self, model: ExecutionModel) -> ExecutionEntity:
        ctx = (model.context or {})
        return ExecutionEntity(
            id=model.id,
            execution_id=model.execution_id,
            status=ExecutionStatus(model.status.upper()) if model.status else ExecutionStatus.CREATED,
            execution_type=ExecutionType(ctx.get("execution_type", "custom")),
            trigger=ExecutionTrigger(model.trigger) if model.trigger else ExecutionTrigger.MANUAL,
            mission_id=ctx.get("mission_id"),
            mission_step_id=ctx.get("mission_step_id"),
            parent_execution_id=ctx.get("parent_execution_id"),
            agent=model.agent,
            context=ExecutionContext(
                inputs=ctx.get("inputs", {}),
                environment=ctx.get("environment", {}),
                parameters=ctx.get("parameters", {}),
            ),
            result=model.result or {},
            error_message=model.error_message,
            metadata=ExecutionMetadata(
                correlation_id=ctx.get("correlation_id", str(uuid.uuid4())),
                retry_count=0,
                max_retries=ctx.get("max_retries", 3),
                timeout_seconds=ctx.get("timeout_seconds", 300),
                source=ctx.get("source", "api"),
                tags=ctx.get("tags", []),
            ),
            started_at=model.started_at,
            completed_at=model.completed_at,
            duration_ms=model.duration_ms,
            created_at=model.created_at,
        )
