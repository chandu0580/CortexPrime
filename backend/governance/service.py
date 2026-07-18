from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from backend.database.repositories.factory import repo_factory as _repo_factory, RepositoryFactory
except ImportError:
    _repo_factory = None
from backend.governance.events import GovernanceEvent, GovernanceEventPublisher, governance_event_publisher
from backend.governance.models import (
    DecisionReasonCode,
    DecisionRequest,
    DecisionResponse,
    GovernanceDecision,
)
from backend.governance.pipeline import DecisionPipeline

log = logging.getLogger(__name__)


class GovernanceService:
    """
    Central governance runtime service.

    Wraps existing governance components:
    - DecisionPipeline (policy evaluation)
    - ApprovalRequestRepository (DB-backed approval persistence)
    - MissionApprovalService (auto-approval rules)
    - audit_logger (audit trail)
    - safety_guard (risk assessment)
    - emergency_stop (global kill-switch)
    """

    def __init__(
        self,
        pipeline: Optional[DecisionPipeline] = None,
        events: Optional[GovernanceEventPublisher] = None,
        repo_factory: Optional[RepositoryFactory] = None,
    ) -> None:
        self._pipeline = pipeline or DecisionPipeline(repo_factory=repo_factory)
        self._events = events or governance_event_publisher
        self._repo_factory = repo_factory or _repo_factory or RepositoryFactory()

    # ------------------------------------------------------------------
    # Policy Management
    # ------------------------------------------------------------------

    async def list_policies(
        self,
        category: Optional[str] = None,
        enabled_only: bool = False,
    ) -> list[dict[str, Any]]:
        repo = await self._repo_factory.policy_repo()
        if enabled_only:
            models = await repo.list_enabled()
        elif category:
            models = await repo.list_by_category(category)
        else:
            models = await repo.list()
        return [
            {
                "id": str(m.id),
                "name": m.name,
                "description": m.description,
                "category": m.category,
                "severity": m.severity,
                "enabled": m.enabled,
                "conditions": m.conditions or {},
                "actions": m.actions or {},
                "created_at": m.created_at.isoformat() if m.created_at else "",
            }
            for m in models
        ]

    async def get_policy(self, policy_id: str) -> Optional[dict[str, Any]]:
        repo = await self._repo_factory.policy_repo()
        try:
            model = await repo.get(uuid.UUID(policy_id))
        except ValueError:
            return None
        if not model:
            return None
        return {
            "id": str(model.id),
            "name": model.name,
            "description": model.description,
            "category": model.category,
            "severity": model.severity,
            "enabled": model.enabled,
            "conditions": model.conditions or {},
            "actions": model.actions or {},
            "created_at": model.created_at.isoformat() if model.created_at else "",
        }

    async def create_policy(
        self,
        name: str,
        category: str = "general",
        description: str = "",
        severity: str = "medium",
        conditions: Optional[dict[str, Any]] = None,
        actions: Optional[dict[str, Any]] = None,
        enabled: bool = True,
    ) -> dict[str, Any]:
        from backend.database.repositories.governance import PolicyModel
        model = PolicyModel(
            id=uuid.uuid4(),
            name=name,
            description=description or "",
            category=category,
            severity=severity,
            enabled=enabled,
            conditions=conditions or {},
            actions=actions or {"action": "allow"},
        )
        repo = await self._repo_factory.policy_repo()
        model = await repo.create(model)
        return {
            "id": str(model.id),
            "name": model.name,
            "category": model.category,
            "severity": model.severity,
            "enabled": model.enabled,
        }

    async def update_policy(
        self,
        policy_id: str,
        updates: dict[str, Any],
    ) -> Optional[dict[str, Any]]:
        repo = await self._repo_factory.policy_repo()
        try:
            model = await repo.get(uuid.UUID(policy_id))
        except ValueError:
            return None
        if not model:
            return None
        for key, value in updates.items():
            if hasattr(model, key) and key not in ("id", "created_at"):
                setattr(model, key, value)
        model = await repo.update(model)
        return {"id": str(model.id), "name": model.name, "updated": True}

    async def delete_policy(self, policy_id: str) -> bool:
        repo = await self._repo_factory.policy_repo()
        try:
            return await repo.delete(uuid.UUID(policy_id))
        except (ValueError, Exception):
            return False

    # ------------------------------------------------------------------
    # Decision Evaluation
    # ------------------------------------------------------------------

    async def evaluate(self, request: DecisionRequest) -> DecisionResponse:
        response = await self._pipeline.evaluate(request)
        await self._publish_event("governance.policy_evaluated", request, response)
        if response.allowed:
            await self._publish_event("governance.allowed", request, response)
        elif response.denied:
            await self._publish_event("governance.denied", request, response)
        elif response.requires_approval:
            await self._publish_event("governance.approval_requested", request, response)
        return response

    async def evaluate_mission(self, request: DecisionRequest) -> DecisionResponse:
        return await self.evaluate(request)

    async def evaluate_execution(self, request: DecisionRequest) -> DecisionResponse:
        return await self.evaluate(request)

    async def evaluate_connector(self, request: DecisionRequest) -> DecisionResponse:
        return await self.evaluate(request)

    # ------------------------------------------------------------------
    # Approval Management
    # ------------------------------------------------------------------

    async def request_approval(
        self,
        request: DecisionRequest,
        reason: Optional[str] = None,
        reviewers: Optional[list[str]] = None,
    ) -> Optional[dict[str, Any]]:
        repo = await self._repo_factory.approval_request_repo()
        from backend.database.repositories.governance import ApprovalRequestModel
        model = ApprovalRequestModel(
            id=uuid.uuid4(),
            request_id=f"gov-{uuid.uuid4().hex[:12]}",
            requester=request.requester or request.user,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            action=request.action,
            reason=reason or request.context.get("reason", ""),
            status="pending",
            reviewers=reviewers or [],
        )
        model = await repo.create(model)

        response = DecisionResponse(
            decision=GovernanceDecision.REQUIRE_APPROVAL,
            reason_code=DecisionReasonCode.APPROVAL_REQUIRED,
            message=reason or "Approval required",
            approval_request_id=model.request_id,
            risk_level=request.risk_level,
        )
        await self._publish_event("governance.approval_requested", request, response,
                                   payload={"approval_request_id": model.request_id})
        return {
            "request_id": model.request_id,
            "id": str(model.id),
            "status": model.status,
            "requester": model.requester,
            "resource_type": model.resource_type,
            "resource_id": model.resource_id,
            "action": model.action,
            "reason": model.reason,
            "reviewers": model.reviewers,
            "created_at": model.created_at.isoformat() if model.created_at else "",
        }

    async def approve(self, request_id: str, approved_by: str) -> Optional[dict[str, Any]]:
        repo = await self._repo_factory.approval_request_repo()
        model = await repo.get_by_request_id(request_id)
        if not model or model.status != "pending":
            return None
        model.status = "approved"
        model.approved_by = approved_by
        model.approved_at = datetime.now(timezone.utc).isoformat()
        model = await repo.update(model)

        await self._events.publish(GovernanceEvent(
            event_type="governance.approved",
            decision="APPROVED",
            reason_code="approved",
            requester=model.requester,
            resource_type=model.resource_type,
            resource_id=model.resource_id,
            action=model.action,
            approval_request_id=model.request_id,
            message=f"Approved by {approved_by}",
        ))
        return {
            "request_id": model.request_id,
            "status": model.status,
            "approved_by": model.approved_by,
            "approved_at": model.approved_at,
        }

    async def reject(self, request_id: str, rejected_by: Optional[str] = None) -> Optional[dict[str, Any]]:
        repo = await self._repo_factory.approval_request_repo()
        model = await repo.get_by_request_id(request_id)
        if not model or model.status != "pending":
            return None
        model.status = "rejected"
        model.approved_by = rejected_by
        model.approved_at = datetime.now(timezone.utc).isoformat()
        model = await repo.update(model)

        await self._events.publish(GovernanceEvent(
            event_type="governance.rejected",
            decision="REJECTED",
            reason_code="rejected",
            requester=model.requester,
            resource_type=model.resource_type,
            resource_id=model.resource_id,
            action=model.action,
            approval_request_id=model.request_id,
            message=f"Rejected by {rejected_by or 'system'}",
        ))
        return {
            "request_id": model.request_id,
            "status": model.status,
            "rejected_by": rejected_by,
        }

    async def list_approval_requests(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        repo = await self._repo_factory.approval_request_repo()
        if status:
            models = await repo.list_by_status(status, limit=limit, offset=offset)
        else:
            models = await repo.list(limit=limit, offset=offset)
        return [
            {
                "id": str(m.id),
                "request_id": m.request_id,
                "requester": m.requester,
                "resource_type": m.resource_type,
                "resource_id": m.resource_id,
                "action": m.action,
                "reason": m.reason,
                "status": m.status,
                "reviewers": m.reviewers,
                "approved_by": m.approved_by,
                "approved_at": m.approved_at,
                "created_at": m.created_at.isoformat() if m.created_at else "",
            }
            for m in models
        ]

    async def get_approval_request(self, request_id: str) -> Optional[dict[str, Any]]:
        repo = await self._repo_factory.approval_request_repo()
        model = await repo.get_by_request_id(request_id)
        if not model:
            return None
        return {
            "id": str(model.id),
            "request_id": model.request_id,
            "requester": model.requester,
            "resource_type": model.resource_type,
            "resource_id": model.resource_id,
            "action": model.action,
            "reason": model.reason,
            "status": model.status,
            "reviewers": model.reviewers,
            "approved_by": model.approved_by,
            "approved_at": model.approved_at,
            "created_at": model.created_at.isoformat() if model.created_at else "",
        }

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        try:
            repo = await self._repo_factory.policy_repo()
            policy_count = await repo.count()
            approval_repo = await self._repo_factory.approval_request_repo()
            pending = len(await approval_repo.list_by_status("pending", limit=1))
            return {
                "status": "healthy",
                "policy_count": policy_count,
                "pending_approvals": pending,
                "service": "governance_runtime",
            }
        except Exception as exc:
            return {
                "status": "degraded",
                "error": str(exc),
                "service": "governance_runtime",
            }

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _publish_event(
        self,
        event_type: str,
        request: DecisionRequest,
        response: DecisionResponse,
        payload: Optional[dict[str, Any]] = None,
    ) -> None:
        await self._events.publish(GovernanceEvent(
            event_type=event_type,
            decision=response.decision.value,
            reason_code=response.reason_code.value,
            requester=request.requester or request.user,
            resource_type=request.resource_type,
            resource_id=request.resource_id,
            action=request.action,
            mission_id=request.mission_id,
            execution_id=request.execution_id,
            approval_request_id=response.approval_request_id,
            message=response.message,
            payload=payload or {},
        ))
