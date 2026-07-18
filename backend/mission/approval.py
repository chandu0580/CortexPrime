from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class ApprovalState(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SKIPPED = "skipped"
    CANCELLED = "cancelled"


@dataclass
class ApprovalRequest:
    request_id: str
    mission_id: str
    requester: str
    resource_type: str
    resource_id: str
    action: str
    reason: Optional[str] = None
    status: ApprovalState = ApprovalState.PENDING
    reviewers: list[str] = field(default_factory=list)
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ApprovalRule(ABC):
    @abstractmethod
    async def evaluate(self, request: ApprovalRequest) -> Optional[bool]:
        ...


class ManualApprovalHook(ABC):
    @abstractmethod
    async def request_approval(self, request: ApprovalRequest) -> None:
        ...

    @abstractmethod
    async def on_approved(self, request: ApprovalRequest) -> None:
        ...

    @abstractmethod
    async def on_rejected(self, request: ApprovalRequest) -> None:
        ...


class AutoApprovalRule(ApprovalRule):
    def __init__(self, auto_approve_categories: Optional[list[str]] = None,
                 low_risk_threshold: str = "low") -> None:
        self._auto_categories = auto_approve_categories or ["maintenance", "exploratory"]
        self._low_risk = low_risk_threshold

    async def evaluate(self, request: ApprovalRequest) -> Optional[bool]:
        if request.resource_type in self._auto_categories:
            return True
        return None


class MissionApprovalService:
    def __init__(self) -> None:
        self._rules: list[ApprovalRule] = []
        self._manual_hooks: list[ManualApprovalHook] = []
        self._requests: dict[str, ApprovalRequest] = {}

    def add_rule(self, rule: ApprovalRule) -> None:
        self._rules.append(rule)

    def add_manual_hook(self, hook: ManualApprovalHook) -> None:
        self._manual_hooks.append(hook)

    async def request_approval(self, mission_id: str, requester: str,
                               resource_type: str, resource_id: str,
                               action: str, reason: Optional[str] = None,
                               reviewers: Optional[list[str]] = None) -> ApprovalRequest:
        import uuid
        request = ApprovalRequest(
            request_id=f"apr-{uuid.uuid4().hex[:12]}",
            mission_id=mission_id,
            requester=requester,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            reason=reason,
            reviewers=reviewers or [],
        )
        for rule in self._rules:
            result = await rule.evaluate(request)
            if result is True:
                request.status = ApprovalState.APPROVED
                request.approved_by = "auto-approval"
                request.approved_at = datetime.now()
                break
            elif result is False:
                request.status = ApprovalState.REJECTED
                break

        self._requests[request.request_id] = request

        if request.status == ApprovalState.PENDING:
            for hook in self._manual_hooks:
                await hook.request_approval(request)

        return request

    async def approve(self, request_id: str, approved_by: str) -> Optional[ApprovalRequest]:
        request = self._requests.get(request_id)
        if not request or request.status != ApprovalState.PENDING:
            return None
        request.status = ApprovalState.APPROVED
        request.approved_by = approved_by
        request.approved_at = datetime.now()
        for hook in self._manual_hooks:
            await hook.on_approved(request)
        return request

    async def reject(self, request_id: str) -> Optional[ApprovalRequest]:
        request = self._requests.get(request_id)
        if not request or request.status != ApprovalState.PENDING:
            return None
        request.status = ApprovalState.REJECTED
        for hook in self._manual_hooks:
            await hook.on_rejected(request)
        return request

    async def get_request(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(request_id)

    async def list_for_mission(self, mission_id: str) -> list[ApprovalRequest]:
        return [r for r in self._requests.values() if r.mission_id == mission_id]
