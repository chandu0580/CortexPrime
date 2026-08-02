"""
Regression test for a real cross-test-pollution bug found 2026-08-02: creating
an ApprovalWorkflow that requires multi-level approval spawns REAL
asyncio.sleep()-based escalation/expiration timers (15-45 real minutes).
Nothing in the test suite awaits or cancels them, so they leak past their
originating test's event-loop teardown and corrupt unrelated later tests
(observed as scattered, unrelated test failures plus the full suite's
runtime nearly doubling). Guarded the same way as the Docker event listener
earlier this session: skip scheduling entirely under pytest.
"""
from __future__ import annotations

import pytest

from backend.approval_center.models import RiskLevel
from backend.approval_center.workflows import ApprovalWorkflowEngine

pytestmark = pytest.mark.asyncio


class TestNoBackgroundTimersDuringTests:
    async def test_create_workflow_requiring_approval_schedules_no_tasks(self):
        engine = ApprovalWorkflowEngine()
        workflow = await engine.create_workflow(
            execution_id="guard-test-1",
            mission_id="enterprise.automated_rollback",
            objective="test",
            risk_level=RiskLevel.HIGH,
        )
        assert workflow.status.value == "pending"
        assert engine._escalation_tasks == {}
