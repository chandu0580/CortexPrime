from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from backend.database.repositories.factory import repo_factory as _repo_factory, RepositoryFactory
except ImportError:
    _repo_factory = None
from backend.database.repositories.missions import MissionModel, MissionRepository, MissionStepModel, MissionStepRepository
from backend.mission.approval import ApprovalState, AutoApprovalRule, MissionApprovalService
from backend.mission.dispatcher.dispatcher import MissionDispatcherImpl
from backend.governance.models import DecisionRequest, GovernanceDecision
from backend.mission.dispatcher.interfaces import ProgressReport, StepStatus
from backend.mission.events import MissionEvent, MissionEventPublisher, mission_event_publisher
from backend.mission.models import (
    MissionContext,
    MissionEntity,
    MissionMetadata,
    MissionOwnership,
    MissionPriority,
    MissionStatus,
    MissionTimeline,
    MissionType,
)
from backend.mission.planner.interfaces import MissionPlan, MissionStep
from backend.mission.planner.planner import StructuredMissionPlanner
from backend.mission.state_machine import is_terminal, is_transient, is_valid_transition
from backend.mission.timeline import MissionTimelineService, mission_timeline

log = logging.getLogger(__name__)


class MissionService:
    def __init__(
        self,
        planner: Optional[StructuredMissionPlanner] = None,
        dispatcher: Optional[MissionDispatcherImpl] = None,
        approval: Optional[MissionApprovalService] = None,
        events: Optional[MissionEventPublisher] = None,
        timeline: Optional[MissionTimelineService] = None,
        repo_factory: Optional[RepositoryFactory] = None,
        execution_service: Optional[Any] = None,
        governance_service: Optional[Any] = None,
        knowledge_service: Optional[Any] = None,
    ) -> None:
        self._planner = planner or StructuredMissionPlanner()
        self._dispatcher = dispatcher or MissionDispatcherImpl(execution_service=execution_service)
        self._approval = approval or MissionApprovalService()
        self._events = events or mission_event_publisher
        self._timeline = timeline or mission_timeline
        self._repo_factory = repo_factory or _repo_factory or RepositoryFactory()
        self._governance_service = governance_service
        self._knowledge_service = knowledge_service

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------

    async def create_mission(
        self,
        title: str,
        objective: str,
        priority: MissionPriority = MissionPriority.MEDIUM,
        mission_type: MissionType = MissionType.STANDARD,
        category: Optional[str] = None,
        owner: Optional[str] = None,
        team: Optional[str] = None,
        department: Optional[str] = None,
        created_by: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        tags: Optional[list[str]] = None,
    ) -> MissionEntity:
        mission_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        correlation_id = str(uuid.uuid4())

        model = MissionModel(
            id=mission_id,
            title=title,
            objective=objective,
            status=MissionStatus.CREATED.value,
            priority=priority.value,
            category=category or mission_type.value,
            owner=owner or created_by or "",
            context=context or {},
        )
        repo = await self._repo_factory.mission_repo()
        model = await repo.create(model)

        entity = self._model_to_entity(model)
        entity.metadata.correlation_id = correlation_id
        entity.metadata.tags = tags or []
        entity.ownership = MissionOwnership(
            owner=owner or created_by or "",
            team=team,
            department=department,
            created_by=created_by or "",
        )

        await self._publish_event(entity, "mission.created",
                                  to_status="CREATED", actor=created_by)
        await self._timeline.add_state_change(
            str(mission_id), "", "CREATED", actor=created_by,
            reason="Mission created",
        )

        return entity

    # ------------------------------------------------------------------
    # Plan
    # ------------------------------------------------------------------

    async def plan_mission(self, mission_id: uuid.UUID,
                           actor: Optional[str] = None) -> Optional[MissionEntity]:
        entity = await self._get_entity(mission_id)
        if not entity:
            return None
        if not is_valid_transition(entity.status, MissionStatus.PLANNING):
            raise ValueError(f"Cannot plan mission in status {entity.status.value}")

        await self._transition(entity, MissionStatus.PLANNING, actor)
        plan = await self._planner.create_plan(
            str(mission_id), entity.title, entity.objective,
            entity.context.__dict__,
        )
        await self._publish_event(entity, "mission.planned",
                                  to_status="PLANNING", actor=actor,
                                  payload={"plan_id": plan.plan_id, "steps": len(plan.steps)})
        await self._timeline.add_state_change(
            str(mission_id), "CREATED", "PLANNING", actor=actor,
            reason="Plan generated",
        )
        return entity

    # ------------------------------------------------------------------
    # Risk Analysis
    # ------------------------------------------------------------------

    async def analyze_risk(self, mission_id: uuid.UUID,
                           actor: Optional[str] = None) -> Optional[MissionEntity]:
        entity = await self._get_entity(mission_id)
        if not entity:
            return None
        if not is_valid_transition(entity.status, MissionStatus.RISK_ANALYSIS):
            raise ValueError(f"Cannot analyze risk in status {entity.status.value}")

        await self._transition(entity, MissionStatus.RISK_ANALYSIS, actor)
        await self._publish_event(entity, "mission.risk_analyzed",
                                  to_status="RISK_ANALYSIS", actor=actor)
        await self._timeline.add_state_change(
            str(mission_id), "PLANNING", "RISK_ANALYSIS", actor=actor,
            reason="Risk analysis completed",
        )
        return entity

    # ------------------------------------------------------------------
    # Request / handle approval
    # ------------------------------------------------------------------

    async def submit_for_approval(self, mission_id: uuid.UUID,
                                  requester: str,
                                  reason: Optional[str] = None,
                                  reviewers: Optional[list[str]] = None) -> Optional[MissionEntity]:
        entity = await self._get_entity(mission_id)
        if not entity:
            return None
        if not is_valid_transition(entity.status, MissionStatus.AWAITING_APPROVAL):
            raise ValueError(f"Cannot submit for approval in status {entity.status.value}")

        await self._transition(entity, MissionStatus.AWAITING_APPROVAL, requester)
        approval_req = await self._approval.request_approval(
            mission_id=str(mission_id),
            requester=requester,
            resource_type=entity.mission_type.value,
            resource_id=str(mission_id),
            action="execute_mission",
            reason=reason,
            reviewers=reviewers,
        )
        await self._publish_event(entity, "mission.awaiting_approval",
                                  to_status="AWAITING_APPROVAL", actor=requester,
                                  payload={"approval_request_id": approval_req.request_id})
        await self._timeline.add_state_change(
            str(mission_id), "RISK_ANALYSIS", "AWAITING_APPROVAL", actor=requester)
        await self._timeline.add_approval_event(
            str(mission_id), "submit", requester, False,
            reason=reason or "Awaiting approval",
        )

        if approval_req.status == ApprovalState.APPROVED:
            return await self._handle_approved(mission_id, requester)
        elif approval_req.status == ApprovalState.REJECTED:
            await self._transition(entity, MissionStatus.CANCELLED, requester)
            await self._publish_event(entity, "mission.approval_rejected",
                                      to_status="CANCELLED", actor=requester)
            return entity

        return entity

    async def approve_mission(self, mission_id: uuid.UUID, request_id: str,
                              approved_by: str) -> Optional[MissionEntity]:
        req = await self._approval.approve(request_id, approved_by)
        if not req:
            return None
        return await self._handle_approved(mission_id, approved_by)

    async def reject_mission(self, mission_id: uuid.UUID, request_id: str) -> Optional[MissionEntity]:
        req = await self._approval.reject(request_id)
        if not req:
            return None
        entity = await self._get_entity(mission_id)
        if not entity:
            return None
        await self._transition(entity, MissionStatus.CANCELLED, req.requester)
        await self._publish_event(entity, "mission.approval_rejected",
                                  to_status="CANCELLED", actor=req.requester)
        return entity

    async def _handle_approved(self, mission_id: uuid.UUID,
                               approved_by: str) -> MissionEntity:
        entity = await self._get_entity(mission_id)
        if not entity:
            raise ValueError(f"Mission {mission_id} not found")
        await self._transition(entity, MissionStatus.APPROVED, approved_by)
        await self._publish_event(entity, "mission.approved",
                                  to_status="APPROVED", actor=approved_by)
        await self._timeline.add_approval_event(
            str(mission_id), "approve", approved_by, True)
        if entity.ownership:
            entity.ownership.approved_by = approved_by
        return entity

    # ------------------------------------------------------------------
    # Queue & Execute
    # ------------------------------------------------------------------

    async def queue_mission(self, mission_id: uuid.UUID,
                            actor: Optional[str] = None) -> Optional[MissionEntity]:
        entity = await self._get_entity(mission_id)
        if not entity:
            return None
        if not is_valid_transition(entity.status, MissionStatus.QUEUED):
            raise ValueError(f"Cannot queue mission in status {entity.status.value}")

        await self._transition(entity, MissionStatus.QUEUED, actor)
        entity.timeline.queued_at = datetime.now(timezone.utc)
        await self._publish_event(entity, "mission.queued",
                                  to_status="QUEUED", actor=actor)
        await self._timeline.add_state_change(
            str(mission_id), "APPROVED", "QUEUED", actor=actor)
        return entity

    async def execute_mission(self, mission_id: uuid.UUID,
                              actor: Optional[str] = None) -> Optional[MissionEntity]:
        entity = await self._get_entity(mission_id)
        if not entity:
            return None
        if not is_valid_transition(entity.status, MissionStatus.EXECUTING):
            raise ValueError(f"Cannot execute mission in status {entity.status.value}")

        await self._transition(entity, MissionStatus.EXECUTING, actor)
        entity.timeline.executing_at = datetime.now(timezone.utc)
        await self._publish_event(entity, "mission.executing",
                                  to_status="EXECUTING", actor=actor)
        await self._timeline.add_state_change(
            str(mission_id), "QUEUED", "EXECUTING", actor=actor)

        if self._governance_service is not None:
            try:
                gov_request = DecisionRequest(
                    requester=actor or "",
                    user=actor or "",
                    role="",
                    tenant="",
                    mission_id=str(mission_id),
                    mission_type=entity.mission_type.value if entity.mission_type else "",
                    action="execute_mission",
                    resource_type="mission",
                    resource_id=str(mission_id),
                    risk_level=entity.metadata.custom.get("risk_level", "low") if entity.metadata else "low",
                    context={"title": entity.title, "objective": entity.objective},
                )
                gov_response = await self._governance_service.evaluate(gov_request)
                if gov_response.denied:
                    await self._transition(entity, MissionStatus.FAILED, actor)
                    entity.timeline.failed_at = datetime.now(timezone.utc)
                    await self._publish_event(entity, "mission.failed",
                                              to_status="FAILED", actor=actor,
                                              payload={"error": f"Governance denied: {gov_response.message}"})
                    return entity
            except Exception as exc:
                log.warning("Governance evaluation failed (proceeding without): %s", exc)

        plan = await self._planner.get_plan_for_mission(str(mission_id))
        if plan:
            result = await self._dispatcher.dispatch(str(mission_id), plan.plan_id, plan.steps)
            if result.success:
                await self._transition(entity, MissionStatus.MONITORING, actor)
                await self._publish_event(entity, "mission.monitoring",
                                          to_status="MONITORING", actor=actor)
                await self._index_mission_knowledge(entity, "completed")
            else:
                await self._transition(entity, MissionStatus.FAILED, actor)
                entity.timeline.failed_at = datetime.now(timezone.utc)
                await self._publish_event(entity, "mission.failed",
                                          to_status="FAILED", actor=actor,
                                          payload={"error": result.error})
                await self._index_mission_knowledge(entity, "failed")
        return entity

    # ------------------------------------------------------------------
    # Verify
    # ------------------------------------------------------------------

    async def verify_mission(self, mission_id: uuid.UUID,
                             verified: bool = True,
                             actor: Optional[str] = None) -> Optional[MissionEntity]:
        entity = await self._get_entity(mission_id)
        if not entity:
            return None
        if not is_valid_transition(entity.status, MissionStatus.VERIFYING):
            raise ValueError(f"Cannot verify mission in status {entity.status.value}")

        await self._transition(entity, MissionStatus.VERIFYING, actor)
        await self._timeline.add_verification_event(
            str(mission_id), "passed" if verified else "failed")

        if verified:
            await self._transition(entity, MissionStatus.COMPLETED, actor)
            entity.timeline.completed_at = datetime.now(timezone.utc)
            await self._publish_event(entity, "mission.completed",
                                      to_status="COMPLETED", actor=actor)
            await self._timeline.add_state_change(
                str(mission_id), "VERIFYING", "COMPLETED", actor=actor,
                reason="Verification passed")
        else:
            await self._transition(entity, MissionStatus.ROLLING_BACK, actor)
            await self._publish_event(entity, "mission.rollback_started",
                                      to_status="ROLLING_BACK", actor=actor)
            await self._timeline.add_state_change(
                str(mission_id), "VERIFYING", "ROLLING_BACK", actor=actor,
                reason="Verification failed, initiating rollback")
            await self._transition(entity, MissionStatus.ROLLED_BACK, actor)
            await self._publish_event(entity, "mission.rollback_completed",
                                      to_status="ROLLED_BACK", actor=actor)

        return entity

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------

    async def cancel_mission(self, mission_id: uuid.UUID,
                             reason: Optional[str] = None,
                             actor: Optional[str] = None) -> Optional[MissionEntity]:
        entity = await self._get_entity(mission_id)
        if not entity:
            return None
        if is_terminal(entity.status):
            raise ValueError(f"Cannot cancel mission in terminal status {entity.status.value}")

        await self._dispatcher.cancel(str(mission_id))
        await self._transition(entity, MissionStatus.CANCELLED, actor)
        entity.timeline.cancelled_at = datetime.now(timezone.utc)
        await self._publish_event(entity, "mission.cancelled",
                                  to_status="CANCELLED", actor=actor,
                                  payload={"reason": reason or ""})
        await self._timeline.add_state_change(
            str(mission_id), entity.status.value, "CANCELLED", actor=actor,
            reason=reason or "Cancelled",
        )
        return entity

    # ------------------------------------------------------------------
    # Retry
    # ------------------------------------------------------------------

    async def retry_mission(self, mission_id: uuid.UUID,
                            actor: Optional[str] = None) -> Optional[MissionEntity]:
        entity = await self._get_entity(mission_id)
        if not entity:
            return None
        if entity.status not in (MissionStatus.FAILED, MissionStatus.ROLLED_BACK):
            raise ValueError(f"Cannot retry mission in status {entity.status.value}")

        entity.metadata.retry_count += 1
        await self._transition(entity, MissionStatus.QUEUED, actor)
        await self._publish_event(entity, "mission.retry",
                                  to_status="QUEUED", actor=actor,
                                  payload={"retry_count": entity.metadata.retry_count})
        await self._timeline.add_retry_event(
            str(mission_id), "mission", entity.metadata.retry_count, 5,
            error=f"Retry #{entity.metadata.retry_count}",
        )
        return entity

    # ------------------------------------------------------------------
    # Read / Query
    # ------------------------------------------------------------------

    async def get_mission(self, mission_id: uuid.UUID) -> Optional[MissionEntity]:
        repo = await self._repo_factory.mission_repo()
        model = await repo.get(mission_id)
        return self._model_to_entity(model) if model else None

    async def get_progress(self, mission_id: uuid.UUID) -> Optional[ProgressReport]:
        return await self._dispatcher.get_progress(str(mission_id))

    async def list_missions(self, limit: int = 50, offset: int = 0) -> list[MissionEntity]:
        repo = await self._repo_factory.mission_repo()
        models = await repo.list(limit=limit, offset=offset)
        return [self._model_to_entity(m) for m in models]

    async def search_missions(
        self,
        query: Optional[str] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        owner: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[MissionEntity]:
        repo = await self._repo_factory.mission_repo()
        models = await repo.search(
            query=query, status=status,
            category=category, owner=owner,
            limit=limit, offset=offset,
        )
        return [self._model_to_entity(m) for m in models]

    async def get_mission_timeline(self, mission_id: uuid.UUID) -> list[Any]:
        return await self._timeline.get_timeline(str(mission_id))

    async def get_mission_events(self, mission_id: uuid.UUID) -> list[MissionEvent]:
        return await self._events.get_events(str(mission_id))

    async def get_plan(self, mission_id: uuid.UUID) -> Optional[MissionPlan]:
        return await self._planner.get_plan_for_mission(str(mission_id))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _get_entity(self, mission_id: uuid.UUID) -> Optional[MissionEntity]:
        repo = await self._repo_factory.mission_repo()
        model = await repo.get(mission_id)
        return self._model_to_entity(model) if model else None

    async def _transition(self, entity: MissionEntity, target: MissionStatus,
                          actor: Optional[str] = None) -> None:
        if not is_valid_transition(entity.status, target):
            raise ValueError(
                f"Invalid transition: {entity.status.value} → {target.value}"
            )
        old_status = entity.status
        entity.status = target
        repo = await self._repo_factory.mission_repo()
        model = await repo.get(entity.id)
        if model:
            model.status = target.value
            if target == MissionStatus.COMPLETED:
                model.completed_at = datetime.now(timezone.utc)
            elif target == MissionStatus.EXECUTING:
                model.started_at = model.started_at or datetime.now(timezone.utc)
            await repo.update(model)
        await self._timeline.add_state_change(
            str(entity.id), old_status.value, target.value, actor=actor)

    async def _index_mission_knowledge(self, entity: MissionEntity, status: str) -> None:
        if self._knowledge_service is None:
            return
        try:
            await self._knowledge_service.index_mission(
                mission_id=str(entity.id),
                title=entity.title,
                objective=entity.objective,
                status=status,
                owner=entity.ownership.owner,
                metadata={
                    "mission_type": entity.mission_type.value if entity.mission_type else "standard",
                    "category": entity.category or "",
                    "priority": entity.priority.value if entity.priority else 3,
                },
            )
        except Exception as exc:
            log.warning("Failed to index mission knowledge: %s", exc)

    async def _publish_event(self, entity: MissionEntity, event_type: str,
                             from_status: Optional[str] = None,
                             to_status: Optional[str] = None,
                             actor: Optional[str] = None,
                             payload: Optional[dict[str, Any]] = None) -> None:
        await self._events.publish(MissionEvent(
            mission_id=str(entity.id),
            event_type=event_type,
            correlation_id=entity.metadata.correlation_id,
            from_status=from_status or entity.status.value,
            to_status=to_status or entity.status.value,
            actor=actor,
            payload=payload or {},
        ))

    def _model_to_entity(self, model: MissionModel) -> MissionEntity:
        return MissionEntity(
            id=model.id,
            title=model.title,
            objective=model.objective,
            status=MissionStatus(model.status.upper()) if model.status else MissionStatus.CREATED,
            priority=MissionPriority(model.priority) if model.priority else MissionPriority.MEDIUM,
            mission_type=MissionType.STANDARD,
            category=model.category,
            timeline=MissionTimeline(
                created_at=model.created_at,
                executing_at=model.started_at,
                completed_at=model.completed_at,
            ),
            context=MissionContext(inputs=model.context or {}),
            ownership=MissionOwnership(
                owner=model.owner or "",
                created_by=model.owner or "",
            ),
        )
