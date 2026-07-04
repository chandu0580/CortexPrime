"""
Human Approval Queue  (CortexPrime)
======================================
Async approval gate: missions / agents submit an ApprovalRequest and then
``await`` the decision.  A human operator calls approve() or reject() via
the governance API, which resolves the asyncio.Event the awaiting code
is blocked on.

If no decision arrives within ``timeout_seconds`` the request is
auto-rejected (safety-first default).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

log = logging.getLogger(__name__)


# =========================================================
# APPROVAL STATUS
# =========================================================

class ApprovalStatus(str, Enum):
    PENDING  = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"


# =========================================================
# APPROVAL REQUEST
# =========================================================

@dataclass
class ApprovalRequest:
    request_id:    str
    execution_id:  str
    agent:         str
    action:        str
    description:   str
    risk_level:    str
    context:       Dict[str, Any]
    session_id:    Optional[str]

    status:        ApprovalStatus = ApprovalStatus.PENDING
    created_at:    str            = field(default_factory=lambda: datetime.utcnow().isoformat())
    resolved_at:   Optional[str]  = None
    resolved_by:   Optional[str]  = None
    reject_reason: Optional[str]  = None

    # Internal asyncio event — not serialised
    _event:        asyncio.Event  = field(default_factory=asyncio.Event, compare=False, repr=False)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "request_id":    self.request_id,
            "execution_id":  self.execution_id,
            "agent":         self.agent,
            "action":        self.action,
            "description":   self.description,
            "risk_level":    self.risk_level,
            "context":       self.context,
            "session_id":    self.session_id,
            "status":        self.status.value,
            "created_at":    self.created_at,
            "resolved_at":   self.resolved_at,
            "resolved_by":   self.resolved_by,
            "reject_reason": self.reject_reason,
        }


# =========================================================
# APPROVAL QUEUE
# =========================================================

class ApprovalQueue:
    """
    In-memory approval queue with async wait support.

    Lifecycle
    ---------
    1. Caller calls ``await queue.request(...)`` — creates a request and
       blocks until the request is resolved or times out.
    2. Human operator calls ``queue.approve(request_id)`` or
       ``queue.reject(request_id, reason)`` via the governance API.
    3. The awaiting caller receives the resolution.
    """

    DEFAULT_TIMEOUT = 300  # seconds

    def __init__(self) -> None:
        self._requests: Dict[str, ApprovalRequest] = {}

    # ----------------------------------------------------------
    # SUBMIT AND AWAIT
    # ----------------------------------------------------------

    async def request(
        self,
        execution_id:  str,
        agent:         str,
        action:        str,
        description:   str,
        risk_level:    str,
        context:       Dict[str, Any] | None = None,
        session_id:    Optional[str]         = None,
        timeout:       float                 = DEFAULT_TIMEOUT,
    ) -> ApprovalRequest:
        """
        Submit an approval request and suspend until resolved or timed out.
        Returns the resolved ApprovalRequest.
        """
        req = ApprovalRequest(
            request_id   = str(uuid4()),
            execution_id = execution_id,
            agent        = agent,
            action       = action,
            description  = description,
            risk_level   = risk_level,
            context      = context or {},
            session_id   = session_id,
        )
        self._requests[req.request_id] = req

        log.info(
            "⏳ Approval requested | %s | agent=%s | action=%s | risk=%s",
            req.request_id[:8], agent, action, risk_level,
        )

        # Publish WebSocket event so the UI can show the request
        await _emit_governance_event(
            event_type  = "approval_requested",
            request     = req,
            session_id  = session_id,
        )

        # Wait for human decision or timeout
        try:
            await asyncio.wait_for(req._event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            req.status     = ApprovalStatus.TIMED_OUT
            req.resolved_at = datetime.utcnow().isoformat()
            req.reject_reason = f"Auto-rejected: no decision within {timeout}s"
            log.warning("Approval timed out: %s", req.request_id[:8])

            await _emit_governance_event(
                event_type = "approval_timed_out",
                request    = req,
                session_id = session_id,
            )

        return req

    # ----------------------------------------------------------
    # APPROVE
    # ----------------------------------------------------------

    def approve(
        self,
        request_id: str,
        approved_by: str = "operator",
    ) -> ApprovalRequest:
        req = self._get_or_raise(request_id)
        if req.status != ApprovalStatus.PENDING:
            return req

        req.status      = ApprovalStatus.APPROVED
        req.resolved_at = datetime.utcnow().isoformat()
        req.resolved_by = approved_by
        req._event.set()

        log.info("✅ Approved: %s by %s", request_id[:8], approved_by)

        asyncio.ensure_future(_emit_governance_event(
            event_type = "approval_granted",
            request    = req,
            session_id = req.session_id,
        ))

        return req

    # ----------------------------------------------------------
    # REJECT
    # ----------------------------------------------------------

    def reject(
        self,
        request_id:    str,
        rejected_by:   str  = "operator",
        reason:        str  = "Rejected by operator",
    ) -> ApprovalRequest:
        req = self._get_or_raise(request_id)
        if req.status != ApprovalStatus.PENDING:
            return req

        req.status        = ApprovalStatus.REJECTED
        req.resolved_at   = datetime.utcnow().isoformat()
        req.resolved_by   = rejected_by
        req.reject_reason = reason
        req._event.set()

        log.info("❌ Rejected: %s by %s — %s", request_id[:8], rejected_by, reason)

        asyncio.ensure_future(_emit_governance_event(
            event_type = "approval_rejected",
            request    = req,
            session_id = req.session_id,
        ))

        return req

    # ----------------------------------------------------------
    # QUERY
    # ----------------------------------------------------------

    def get_queue(self, status: Optional[str] = None) -> List[Dict[str, Any]]:
        """Return all requests, optionally filtered by status."""
        items = list(self._requests.values())
        if status:
            items = [r for r in items if r.status.value == status]
        return [r.as_dict() for r in sorted(items, key=lambda r: r.created_at, reverse=True)]

    def get_pending(self) -> List[Dict[str, Any]]:
        return self.get_queue(status="pending")

    def get(self, request_id: str) -> Optional[ApprovalRequest]:
        return self._requests.get(request_id)

    def _get_or_raise(self, request_id: str) -> ApprovalRequest:
        req = self._requests.get(request_id)
        if req is None:
            raise KeyError(f"Approval request not found: {request_id}")
        return req


# =========================================================
# WEBSOCKET EVENT HELPER
# =========================================================

async def _emit_governance_event(
    event_type: str,
    request:    ApprovalRequest,
    session_id: Optional[str] = None,
) -> None:
    """Broadcast a governance event over the WebSocket event bus."""
    try:
        from backend.events.event_bus    import event_bus
        from backend.events.event_models import CognitionEvent
        await event_bus.publish(CognitionEvent(
            agent            = "governance",
            event_type       = event_type,
            status           = "info",
            phase            = "governance",
            execution_id     = request.execution_id,
            message          = f"[{event_type.replace('_', ' ').title()}] {request.description}",
            payload          = request.as_dict(),
            session_id       = session_id,
            governance_status = request.status.value,
        ))
    except Exception as exc:
        log.warning("Governance event publish failed: %s", exc)


# =========================================================
# SINGLETON
# =========================================================

approval_queue = ApprovalQueue()
