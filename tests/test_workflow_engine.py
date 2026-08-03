"""
Sprint 53.2 — Phase 2: Workflow / Approval Engine
==================================================
Tests for the approval workflow engine and approval queue covering:

  - Workflow CRUD (create, approve, reject, query)
  - Multi-step approval chains
  - Escalation, expiration, delegation
  - Break-glass emergency override
  - Approval queue submit/resolve lifecycle

Usage:
    pytest tests/test_workflow_engine.py -v
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio


# =============================================================
# 1. APPROVAL QUEUE
# =============================================================

class TestApprovalQueue:
    """Test the basic approval queue lifecycle."""

    async def test_submit_request_returns_pending(self, monkeypatch):
        from backend.safety.approval_queue import ApprovalQueue

        monkeypatch.setattr(
            "backend.safety.approval_queue._emit_governance_event",
            AsyncMock(),
        )

        queue = ApprovalQueue()

        # ApprovalQueue.request() blocks until resolved or timed out — it can
        # never itself return "pending". Run it as a background task so we
        # can observe the pending state before resolving it.
        task = asyncio.create_task(queue.request(
            execution_id="exec-1",
            agent="orchestrator",
            action="execute_mission",
            description="Test mission",
            risk_level="medium",
            timeout=5,
        ))
        await asyncio.sleep(0.05)

        pending = queue.get_pending()
        assert len(pending) == 1
        assert pending[0]["execution_id"] == "exec-1"
        assert pending[0]["status"] == "pending"

        queue.approve(pending[0]["request_id"], approved_by="admin")
        req = await task
        assert req.execution_id == "exec-1"

    async def test_approve_resolves_request(self, monkeypatch):
        from backend.safety.approval_queue import ApprovalQueue

        monkeypatch.setattr(
            "backend.safety.approval_queue._emit_governance_event",
            AsyncMock(),
        )

        queue = ApprovalQueue()

        async def _submit_and_approve():
            req = await queue.request(
                execution_id="exec-2",
                agent="orchestrator",
                action="execute_mission",
                description="Test",
                risk_level="high",
                timeout=30,
            )
            return req

        task = asyncio.create_task(_submit_and_approve())
        await asyncio.sleep(0.05)

        pending = queue.get_pending()
        assert len(pending) == 1
        rid = pending[0]["request_id"]

        queue.approve(rid, approved_by="admin")
        req = await task

        assert req.status.value == "approved"
        assert req.resolved_by == "admin"

    async def test_reject_resolves_request(self, monkeypatch):
        from backend.safety.approval_queue import ApprovalQueue

        monkeypatch.setattr(
            "backend.safety.approval_queue._emit_governance_event",
            AsyncMock(),
        )

        queue = ApprovalQueue()

        async def _submit_and_reject():
            req = await queue.request(
                execution_id="exec-3",
                agent="orchestrator",
                action="execute_mission",
                description="Test",
                risk_level="critical",
                timeout=30,
            )
            return req

        task = asyncio.create_task(_submit_and_reject())
        await asyncio.sleep(0.05)

        pending = queue.get_pending()
        rid = pending[0]["request_id"]

        queue.reject(rid, rejected_by="admin", reason="Not allowed")
        req = await task

        assert req.status.value == "rejected"
        assert req.reject_reason == "Not allowed"

    async def test_timeout_auto_rejects(self, monkeypatch):
        from backend.safety.approval_queue import ApprovalQueue

        monkeypatch.setattr(
            "backend.safety.approval_queue._emit_governance_event",
            AsyncMock(),
        )

        queue = ApprovalQueue()
        req = await queue.request(
            execution_id="exec-4",
            agent="orchestrator",
            action="execute_mission",
            description="Timeout test",
            risk_level="low",
            timeout=0.1,
        )
        assert req.status.value == "timed_out"
        assert "Auto-rejected" in req.reject_reason

    async def test_get_returns_none_for_unknown(self):
        from backend.safety.approval_queue import ApprovalQueue
        queue = ApprovalQueue()
        assert queue.get("nonexistent") is None

    async def test_get_queue_filters_by_status(self, monkeypatch):
        from backend.safety.approval_queue import ApprovalQueue

        monkeypatch.setattr(
            "backend.safety.approval_queue._emit_governance_event",
            AsyncMock(),
        )

        queue = ApprovalQueue()

        req1 = await queue.request(execution_id="e1", agent="a", action="act", description="d1", risk_level="low", timeout=0.1)
        assert req1.status.value == "timed_out"

        pending = queue.get_queue(status="pending")
        timed_out = queue.get_queue(status="timed_out")
        assert len(pending) == 0
        assert len(timed_out) >= 1


# =============================================================
# 2. APPROVAL WORKFLOW ENGINE
# =============================================================

class TestApprovalWorkflowEngine:
    """Test ApprovalWorkflowEngine with mock policies."""

    @pytest.fixture(autouse=True)
    def _patch_deps(self, monkeypatch):
        monkeypatch.setattr(
            "backend.approval_center.workflows.get_policy_for_mission",
            lambda *a, **kw: MagicMock(
                policy_id="pol-1",
                required_roles=["admin"],
                required_levels=1,
                escalation_minutes=0,
                expiration_minutes=0,
                requires_break_glass=True,
                break_glass_roles=["super_admin"],
            ),
        )
        monkeypatch.setattr(
            "backend.approval_center.workflows.get_policy_for_risk",
            lambda *a, **kw: MagicMock(
                policy_id="pol-1",
                required_roles=["admin"],
                required_levels=1,
                escalation_minutes=0,
                expiration_minutes=0,
                requires_break_glass=True,
                break_glass_roles=["super_admin"],
            ),
        )
        monkeypatch.setattr(
            "backend.approval_center.workflows.approval_queue",
            MagicMock(approve=AsyncMock(), reject=AsyncMock()),
        )

    async def test_create_workflow(self):
        from backend.approval_center.workflows import ApprovalWorkflowEngine
        from backend.approval_center.models import RiskLevel

        engine = ApprovalWorkflowEngine()
        wf = await engine.create_workflow(
            execution_id="exec-1",
            mission_id="mission-1",
            objective="test mission",
            risk_level=RiskLevel.HIGH,
        )
        assert wf.execution_id == "exec-1"
        assert wf.status.value == "pending"
        assert len(wf.steps) == 1

    async def test_approve_step_completes_single_step_workflow(self):
        from backend.approval_center.workflows import ApprovalWorkflowEngine
        from backend.approval_center.models import ApproverRole, RiskLevel

        engine = ApprovalWorkflowEngine()
        wf = await engine.create_workflow(
            execution_id="exec-2",
            mission_id="mission-2",
            objective="approve me",
            risk_level=RiskLevel.HIGH,
        )
        wf = await engine.approve_step(wf.workflow_id, "admin", ApproverRole.ADMIN, reason="Looks good")
        assert wf.status.value == "approved"
        assert wf.steps[0].status.value == "approved"

    async def test_reject_step_rejects_workflow(self):
        from backend.approval_center.workflows import ApprovalWorkflowEngine
        from backend.approval_center.models import RiskLevel

        engine = ApprovalWorkflowEngine()
        wf = await engine.create_workflow(
            execution_id="exec-3",
            mission_id="mission-3",
            objective="reject me",
            risk_level=RiskLevel.CRITICAL,
        )
        wf = await engine.reject_step(wf.workflow_id, "admin", reason="Not appropriate")
        assert wf.status.value == "rejected"

    async def test_raise_on_approve_wrong_role(self):
        from backend.approval_center.workflows import ApprovalWorkflowEngine
        from backend.approval_center.models import ApproverRole, RiskLevel

        engine = ApprovalWorkflowEngine()
        wf = await engine.create_workflow(
            execution_id="exec-4",
            mission_id="mission-4",
            objective="wrong role",
            risk_level=RiskLevel.HIGH,
        )
        with pytest.raises(ValueError, match="Role"):
            await engine.approve_step(wf.workflow_id, "dev", ApproverRole.DEVELOPER)

    async def test_raise_on_unknown_workflow(self):
        from backend.approval_center.workflows import ApprovalWorkflowEngine

        engine = ApprovalWorkflowEngine()
        with pytest.raises(ValueError, match="Unknown workflow"):
            await engine.approve_step("nonexistent", "admin", None)

    async def test_workflow_not_found_returns_none(self):
        from backend.approval_center.workflows import ApprovalWorkflowEngine

        engine = ApprovalWorkflowEngine()
        assert engine.get_workflow("nonexistent") is None

    async def test_get_workflow_by_execution(self):
        from backend.approval_center.workflows import ApprovalWorkflowEngine
        from backend.approval_center.models import RiskLevel

        engine = ApprovalWorkflowEngine()
        wf = await engine.create_workflow(
            execution_id="exec-find",
            mission_id="mission-find",
            objective="find me",
            risk_level=RiskLevel.MEDIUM,
        )
        found = engine.get_workflow_by_execution("exec-find")
        assert found is not None
        assert found.workflow_id == wf.workflow_id

    async def test_list_workflows_filters_by_status(self):
        from backend.approval_center.workflows import ApprovalWorkflowEngine
        from backend.approval_center.models import RiskLevel, WorkflowStatus

        engine = ApprovalWorkflowEngine()
        await engine.create_workflow(execution_id="e1", mission_id="m1", objective="o1", risk_level=RiskLevel.LOW)
        await engine.create_workflow(execution_id="e2", mission_id="m2", objective="o2", risk_level=RiskLevel.LOW)

        all_wf = engine.list_workflows()
        pending = engine.list_workflows(status=WorkflowStatus.PENDING)
        assert len(all_wf) == 2
        assert len(pending) == 2

    async def test_break_glass_overrides_workflow(self):
        from backend.approval_center.workflows import ApprovalWorkflowEngine
        from backend.approval_center.models import ApproverRole, RiskLevel

        engine = ApprovalWorkflowEngine()
        wf = await engine.create_workflow(
            execution_id="exec-bg",
            mission_id="mission-bg",
            objective="emergency",
            risk_level=RiskLevel.CRITICAL,
        )
        wf = await engine.break_glass(
            wf.workflow_id,
            overridden_by="super_admin",
            role=ApproverRole.SUPER_ADMIN,
            reason="Emergency override",
            justification="Production down",
        )
        assert wf.break_glass is True
        assert wf.status.value == "break_glass"

    async def test_delegate_approval(self):
        from backend.approval_center.workflows import ApprovalWorkflowEngine
        from backend.approval_center.models import RiskLevel

        engine = ApprovalWorkflowEngine()
        wf = await engine.create_workflow(
            execution_id="exec-del",
            mission_id="mission-del",
            objective="delegate",
            risk_level=RiskLevel.MEDIUM,
        )
        wf = await engine.delegate(
            wf.workflow_id,
            from_user="admin",
            to_user="backup_admin",
            reason="On leave",
        )
        assert wf.steps[0].status.value == "delegated"
        assert wf.steps[0].delegated_to == "backup_admin"

    async def test_get_workflow_summary(self):
        from backend.approval_center.workflows import ApprovalWorkflowEngine
        from backend.approval_center.models import RiskLevel

        engine = ApprovalWorkflowEngine()
        await engine.create_workflow(execution_id="e1", mission_id="m1", objective="o1", risk_level=RiskLevel.LOW)
        summary = engine.get_workflow_summary()
        assert summary["total_workflows"] == 1
        assert summary["active"] == 1

    async def test_zero_level_policy_auto_approves(self, monkeypatch):
        from backend.approval_center.workflows import ApprovalWorkflowEngine
        from backend.approval_center.models import RiskLevel

        monkeypatch.setattr(
            "backend.approval_center.workflows.get_policy_for_mission",
            lambda *a, **kw: MagicMock(
                policy_id="pol-auto",
                required_roles=[],
                required_levels=0,
                escalation_minutes=0,
                expiration_minutes=0,
                requires_break_glass=False,
                break_glass_roles=[],
            ),
        )

        engine = ApprovalWorkflowEngine()
        wf = await engine.create_workflow(
            execution_id="exec-auto",
            mission_id="mission-auto",
            objective="auto approved",
            risk_level=RiskLevel.LOW,
        )
        assert wf.status.value == "approved"
