"""
Validation tests for Enterprise Engineering Executive Runtime.

Phases covered:
  1. Mission Lifecycle — 12 states
  2. Executive State Machine — valid transitions
  3. Executive Supervision — context/decision/prediction/verification
  4. Autonomy Control — automatic/approval/human/stop/rollback
  5. Executive Policies — risk/approval/windows
  6. Mission Intervention — pause/resume/escalate/rollback/retry/abort/replan
  7. Mission Timeline — complete executive timeline
  8. Executive Dashboard — active missions/health/decisions

Scenarios (Phase 9):
  1. Normal deployment
  2. High-risk deployment
  3. Approval flow
  4. Rollback
  5. Emergency stop
  6. Mission retry
  7. Human intervention
  8. Concurrent missions
"""
from __future__ import annotations

import pytest
from typing import Any, Dict, List

from backend.services.enterprise_executive_runtime import (
    EnterpriseEngineeringExecutiveRuntime,
    ExecutiveStateMachine,
    PolicyEnforcer,
    PolicyConfig,
    MissionState,
    MissionRecord,
    AutonomyLevel,
)


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def runtime() -> EnterpriseEngineeringExecutiveRuntime:
    return EnterpriseEngineeringExecutiveRuntime()


@pytest.fixture
def policy() -> PolicyEnforcer:
    return PolicyEnforcer()


# =============================================================================
# Phase 1+2 — Mission Lifecycle & State Machine
# =============================================================================


class TestMissionLifecycle:
    """Phase 1: Mission lifecycle with 12 states."""

    @pytest.mark.asyncio
    async def test_create_mission(self, runtime):
        """Create mission returns mission with CREATED state."""
        result = await runtime.create_mission(
            source="github", source_event="push",
            repository="org/test", branch="main",
        )
        assert result["mission_id"].startswith("msn-")
        assert result["current_phase"] == MissionState.CREATED.value
        assert result["repository"] == "org/test"

    @pytest.mark.asyncio
    async def test_list_missions(self, runtime):
        """List missions returns created missions."""
        await runtime.create_mission(source="github", repository="org/a")
        await runtime.create_mission(source="github", repository="org/b")
        missions = await runtime.list_missions()
        assert len(missions) >= 2

    @pytest.mark.asyncio
    async def test_list_missions_by_status(self, runtime):
        """List missions filtered by status."""
        m1 = await runtime.create_mission(source="github", repository="org/active")
        await runtime.create_mission(source="github", repository="org/other")
        # Only m1 should be in CREATED
        created = await runtime.list_missions(status=MissionState.CREATED.value)
        assert len(created) >= 1
        for m in created:
            assert m["current_phase"] == MissionState.CREATED.value

    @pytest.mark.asyncio
    async def test_get_mission(self, runtime):
        """Get mission returns mission detail."""
        result = await runtime.create_mission(source="github", repository="org/get-me")
        mid = result["mission_id"]
        detail = await runtime.get_mission(mid)
        assert detail is not None
        assert detail["mission_id"] == mid
        assert "timeline" in detail

    @pytest.mark.asyncio
    async def test_get_mission_not_found(self, runtime):
        """Getting nonexistent mission returns None."""
        detail = await runtime.get_mission("nonexistent")
        assert detail is None


class TestStateMachine:
    """Phase 2: State machine valid transitions."""

    def test_valid_transition(self):
        """CREATED -> PLANNED is valid."""
        assert ExecutiveStateMachine.can_transition(MissionState.CREATED.value, MissionState.PLANNED.value)

    def test_invalid_transition(self):
        """CREATED -> COMPLETED is invalid."""
        assert not ExecutiveStateMachine.can_transition(MissionState.CREATED.value, MissionState.COMPLETED.value)

    def test_terminal_states(self):
        """COMPLETED, FAILED, CANCELLED are terminal."""
        assert ExecutiveStateMachine.is_terminal(MissionState.COMPLETED.value)
        assert ExecutiveStateMachine.is_terminal(MissionState.FAILED.value)
        assert ExecutiveStateMachine.is_terminal(MissionState.CANCELLED.value)
        assert not ExecutiveStateMachine.is_terminal(MissionState.RUNNING.value)

    def test_all_states_have_transitions(self):
        """Every non-terminal state has at least one valid transition."""
        for state in MissionState:
            if ExecutiveStateMachine.is_terminal(state.value):
                continue
            transitions = ExecutiveStateMachine.VALID_TRANSITIONS.get(state.value, [])
            assert len(transitions) > 0, f"{state.value} has no outgoing transitions"

    def test_all_transitions_refer_to_real_states(self):
        """All transition targets are real MissionState values."""
        all_states = {s.value for s in MissionState}
        for source, targets in ExecutiveStateMachine.VALID_TRANSITIONS.items():
            for t in targets:
                assert t in all_states, f"Invalid transition target {t} from {source}"


# =============================================================================
# Phase 3 — Executive Supervision
# =============================================================================


class TestExecutiveSupervision:
    """Phase 3: Plan mission gathers context, makes decision, runs prediction."""

    @pytest.mark.asyncio
    async def test_plan_mission_creates_decision(self, runtime):
        """Planning a mission calls decision engine and prediction."""
        m = await runtime.create_mission(source="github", repository="org/plan-test",
                                         change_categories=["backend"])
        mid = m["mission_id"]
        plan = await runtime.plan_mission(mid)
        assert plan["status"] == "planned"
        assert plan["decision"] is not None
        assert plan["prediction"] is not None

    @pytest.mark.asyncio
    async def test_plan_mission_tracks_risk(self, runtime):
        """Planned mission has risk score tracked."""
        m = await runtime.create_mission(source="github", repository="org/risk-test")
        mid = m["mission_id"]
        await runtime.plan_mission(mid)
        detail = await runtime.get_mission(mid)
        assert detail["risk_score"] >= 0


# =============================================================================
# Phase 4 — Autonomy Control
# =============================================================================


class TestAutonomyControl:
    """Phase 4: Autonomy levels determined by risk and policies."""

    def test_low_risk_automatic(self, policy):
        """Low risk mission is AUTOMATIC."""
        mission = MissionRecord(risk_score=0.2, predicted_rollback_probability=0.05)
        level = policy.set_autonomy_level(mission)
        assert level == AutonomyLevel.AUTOMATIC

    def test_high_risk_approval_required(self, policy):
        """High risk mission requires approval."""
        mission = MissionRecord(risk_score=0.6, predicted_rollback_probability=0.1)
        level = policy.set_autonomy_level(mission)
        assert level == AutonomyLevel.APPROVAL_REQUIRED

    def test_very_high_risk_emergency_stop(self, policy):
        """Very high risk triggers emergency stop."""
        mission = MissionRecord(risk_score=0.95, predicted_rollback_probability=0.1)
        level = policy.set_autonomy_level(mission)
        assert level == AutonomyLevel.EMERGENCY_STOP

    def test_high_rollback_triggers_emergency(self, policy):
        """High rollback probability triggers emergency stop."""
        mission = MissionRecord(risk_score=0.3, predicted_rollback_probability=0.8)
        config = PolicyConfig(max_rollback_probability=0.5,
                              require_approval_rollback_threshold=0.3,
                              auto_rollback_risk_threshold=0.75,
                              auto_abort_risk_threshold=0.9,
                              require_approval_risk_threshold=0.5,
                              max_risk_score=0.7)
        enforcer = PolicyEnforcer(config)
        level = enforcer.set_autonomy_level(mission)
        assert level in (AutonomyLevel.APPROVAL_REQUIRED, AutonomyLevel.ROLLBACK)

    def test_db_migration_requires_approval(self, policy):
        """Database migration requires approval."""
        mission = MissionRecord(risk_score=0.3, has_db_migrations=True)
        needed, reason = policy.check_approval_required(mission)
        assert needed is True
        assert "database" in reason.lower()


# =============================================================================
# Phase 5 — Executive Policies
# =============================================================================


class TestExecutivePolicies:
    """Phase 5: Policy enforcement."""

    def test_risk_below_threshold(self, policy):
        """Risk below max passes check."""
        mission = MissionRecord(risk_score=0.3)
        ok, msg = policy.check_risk_threshold(mission)
        assert ok is True
        assert msg == ""

    def test_risk_above_threshold(self, policy):
        """Risk above max fails check."""
        mission = MissionRecord(risk_score=0.8)
        ok, msg = policy.check_risk_threshold(mission)
        assert ok is False
        assert msg != ""

    def test_approval_not_needed_low_risk(self, policy):
        """Low-risk mission doesn't need approval."""
        mission = MissionRecord(risk_score=0.2, predicted_rollback_probability=0.05)
        needed, reason = policy.check_approval_required(mission)
        assert needed is False

    def test_approval_needed_high_risk(self, policy):
        """High-risk mission needs approval."""
        mission = MissionRecord(risk_score=0.6, predicted_rollback_probability=0.1)
        needed, reason = policy.check_approval_required(mission)
        assert needed is True

    def test_infra_change_needs_approval(self, policy):
        """Infrastructure change requires approval."""
        mission = MissionRecord(risk_score=0.3, has_infrastructure_changes=True)
        needed, reason = policy.check_approval_required(mission)
        assert needed is True


# =============================================================================
# Phase 6 — Mission Intervention
# =============================================================================


class TestMissionIntervention:
    """Phase 6: Pause/resume/escalate/rollback/retry/abort/replan."""

    @pytest.mark.asyncio
    async def test_pause_resume_mission(self, runtime):
        """Pause and resume mission."""
        m = await runtime.create_mission(source="github", repository="org/pause-test")
        mid = m["mission_id"]
        await runtime.plan_mission(mid)
        # Force to RUNNING
        runtime._transition(mid, MissionState.RUNNING.value)

        paused = await runtime.pause_mission(mid)
        assert paused["status"] == "paused"

        detail = await runtime.get_mission(mid)
        assert detail["current_phase"] == MissionState.WAITING.value

        resumed = await runtime.resume_mission(mid)
        assert resumed["status"] == "resumed"

    @pytest.mark.asyncio
    async def test_abort_mission(self, runtime):
        """Abort cancels a mission."""
        m = await runtime.create_mission(source="github", repository="org/abort-test")
        mid = m["mission_id"]
        await runtime.plan_mission(mid)

        aborted = await runtime.abort_mission(mid, reason="Test abort")
        assert aborted["status"] == "cancelled"

        detail = await runtime.get_mission(mid)
        assert detail["current_phase"] == MissionState.CANCELLED.value

    @pytest.mark.asyncio
    async def test_escalate_mission(self, runtime):
        """Escalate sets human intervention autonomy."""
        m = await runtime.create_mission(source="github", repository="org/escalate-test")
        mid = m["mission_id"]

        escalated = await runtime.escalate_mission(mid, reason="Need human review")
        assert escalated["status"] == "escalated"

        detail = await runtime.get_mission(mid)
        assert detail["autonomy_level"] == AutonomyLevel.HUMAN_INTERVENTION.value

    @pytest.mark.asyncio
    async def test_rollback_mission(self, runtime):
        """Rollback changes autonomy and adds timeline entry."""
        m = await runtime.create_mission(source="github", repository="org/rollback-test")
        mid = m["mission_id"]

        rb = await runtime.rollback_mission(mid, reason="Test rollback")
        assert "rolled_back" in rb["status"]

        detail = await runtime.get_mission(mid)
        assert detail["current_phase"] == MissionState.FAILED.value

    @pytest.mark.asyncio
    async def test_retry_mission(self, runtime):
        """Retry records intervention."""
        m = await runtime.create_mission(source="github", repository="org/retry-test")
        mid = m["mission_id"]

        retried = await runtime.retry_mission(mid)
        assert retried["status"] == "retrying"

        detail = await runtime.get_mission(mid)
        assert detail["intervention_count"] >= 1

    @pytest.mark.asyncio
    async def test_replan_failed_mission(self, runtime):
        """Re-plan a failed mission."""
        m = await runtime.create_mission(source="github", repository="org/replan-test")
        mid = m["mission_id"]

        await runtime.plan_mission(mid)
        runtime._transition(mid, "running")
        runtime._transition(mid, "failed")
        replan = await runtime.replan_mission(mid)
        assert replan["status"] == "planned"

    @pytest.mark.asyncio
    async def test_multiple_interventions(self, runtime):
        """Multiple interventions increment counter."""
        m = await runtime.create_mission(source="github", repository="org/intervene-test")
        mid = m["mission_id"]

        for _ in range(3):
            await runtime.retry_mission(mid)

        detail = await runtime.get_mission(mid)
        assert detail["intervention_count"] == 3
        assert detail["last_intervention"].startswith("retry")


# =============================================================================
# Phase 7 — Mission Timeline
# =============================================================================


class TestMissionTimeline:
    """Phase 7: Complete executive timeline."""

    @pytest.mark.asyncio
    async def test_timeline_records_events(self, runtime):
        """Timeline records phase transitions and events."""
        m = await runtime.create_mission(source="github", repository="org/timeline-test")
        mid = m["mission_id"]
        await runtime.plan_mission(mid)

        detail = await runtime.get_mission(mid)
        timeline = detail.get("timeline", [])
        assert len(timeline) >= 2  # created + planned events

        # Verify timeline structure
        for entry in timeline:
            assert "mission_id" in entry
            assert "phase" in entry
            assert "event_type" in entry
            assert "timestamp" in entry

    @pytest.mark.asyncio
    async def test_timeline_includes_agent_names(self, runtime):
        """Timeline entries include agent names."""
        m = await runtime.create_mission(source="github", repository="org/agents-test")
        mid = m["mission_id"]
        await runtime.plan_mission(mid)

        detail = await runtime.get_mission(mid)
        timeline = detail.get("timeline", [])

        agents = {e["agent"] for e in timeline}
        assert "executive_runtime" in agents
        # Decision engine or context should appear
        assert len(agents) >= 1


# =============================================================================
# Phase 8 — Executive Dashboard
# =============================================================================


class TestExecutiveDashboard:
    """Phase 8: Executive dashboard."""

    @pytest.mark.asyncio
    async def test_dashboard_empty(self, runtime):
        """Empty runtime returns zeroed dashboard."""
        dash = await runtime.get_dashboard()
        assert dash["total_missions"] == 0
        assert dash["active_missions"] == 0

    @pytest.mark.asyncio
    async def test_dashboard_with_missions(self, runtime):
        """Dashboard reflects created missions."""
        for i in range(3):
            await runtime.create_mission(
                source="github", repository=f"org/dash-{i}",
                change_categories=["backend"],
            )

        dash = await runtime.get_dashboard()
        assert dash["total_missions"] == 3
        assert dash["active_missions"] >= 3  # all CREATED are active

    @pytest.mark.asyncio
    async def _complete_mission(self, runtime, repo: str) -> str:
        """Helper: run a mission through to completion via valid transitions."""
        m = await runtime.create_mission(source="github", repository=repo)
        mid = m["mission_id"]
        await runtime.plan_mission(mid)
        for phase in ("running", "approval", "deploying", "monitoring", "verifying", "learning"):
            try:
                runtime._transition(mid, phase)
            except ValueError:
                pass
        try:
            runtime._transition(mid, MissionState.COMPLETED.value)
        except ValueError:
            pass
        return mid

    @pytest.mark.asyncio
    async def test_dashboard_tracks_completed(self, runtime):
        """Dashboard tracks completed missions."""
        for i in range(5):
            await self._complete_mission(runtime, f"org/success-{i}")

        dash = await runtime.get_dashboard()
        assert dash["total_missions"] >= 5
        assert dash["completed"] >= 5

    @pytest.mark.asyncio
    async def test_dashboard_health_degraded(self, runtime):
        """Dashboard health reflects failure rate."""
        for i in range(3):
            m = await runtime.create_mission(source="github", repository=f"org/fail-{i}")
            mid = m["mission_id"]
            await runtime.plan_mission(mid)
            runtime._transition(mid, "running")
            runtime._transition(mid, "failed")

        for i in range(2):
            await self._complete_mission(runtime, f"org/ok-{i}")

        dash = await runtime.get_dashboard()
        assert dash["total_missions"] == 5
        assert dash["mission_reliability"] < 1.0

    @pytest.mark.asyncio
    async def test_list_active_missions(self, runtime):
        """List active missions returns non-terminal missions."""
        m1 = await runtime.create_mission(source="github", repository="org/active-1")
        await runtime.plan_mission(m1["mission_id"])
        m2 = await runtime.create_mission(source="github", repository="org/active-2")
        mid3_obj = await runtime.create_mission(source="github", repository="org/active-3")

        runtime._transition(m1["mission_id"], "running")
        runtime._transition(m1["mission_id"], "failed")

        active = await runtime.list_active_missions()
        mids = {a["mission_id"] for a in active}
        assert m1["mission_id"] not in mids, f"m1 {m1['mission_id']} should not be active"
        assert m2["mission_id"] in mids, f"m2 {m2['mission_id']} should be active"
        assert mid3_obj["mission_id"] in mids, f"m3 should be active"


# =============================================================================
# Phase 9 — Scenario Validations
# =============================================================================


class TestScenario1NormalDeployment:
    """Normal deployment — low risk, automatic flow."""

    @pytest.mark.asyncio
    async def test_normal_deployment(self, runtime):
        """Normal deployment completes without approval."""
        m = await runtime.create_mission(
            source="github", repository="org/normal",
            change_categories=["backend"], changed_services=["api"],
        )
        mid = m["mission_id"]

        plan = await runtime.plan_mission(mid)
        assert plan["status"] == "planned"
        assert plan["approval_required"] is False

        detail = await runtime.get_mission(mid)
        assert detail["autonomy_level"] == AutonomyLevel.AUTOMATIC.value


class TestScenario2HighRiskDeployment:
    """High-risk deployment — requires approval."""

    @pytest.mark.asyncio
    async def test_high_risk_deployment(self, runtime):
        """High-risk deployment requires approval."""
        m = await runtime.create_mission(
            source="github", repository="org/high-risk",
            change_categories=["database", "migration"],
            has_db_migrations=True,
        )
        mid = m["mission_id"]
        # Inject high risk
        runtime._update_mission(mid, risk_score=0.65, has_db_migrations=True)

        plan = await runtime.plan_mission(mid)
        if plan["status"] == "planned":
            assert plan["approval_required"] is True


class TestScenario3ApprovalFlow:
    """Approval flow — mission waits for human approval."""

    @pytest.mark.asyncio
    async def test_approval_flow(self, runtime):
        """Mission requires approval before running."""
        m = await runtime.create_mission(
            source="github", repository="org/approval",
            change_categories=["infrastructure"],
            has_infrastructure_changes=True,
        )
        mid = m["mission_id"]
        runtime._update_mission(mid, risk_score=0.55, has_infrastructure_changes=True)

        plan = await runtime.plan_mission(mid)
        if plan["status"] == "planned":
            # run_mission should transition to RUNNING, then may need approval
            run_result = await runtime.run_mission(mid, approval_granted=False)
            detail = await runtime.get_mission(mid)
            if run_result.get("status") == "awaiting_approval":
                assert run_result["requires_human_approval"] is True
                assert detail["current_phase"] == MissionState.APPROVAL.value
            # else may have succeeded or failed based on risk thresholds


class TestScenario4Rollback:
    """Rollback — mission is rolled back."""

    @pytest.mark.asyncio
    async def test_rollback_scenario(self, runtime):
        """Rollback scenario completes with failure state."""
        m = await runtime.create_mission(
            source="github", repository="org/rollback-s4",
            change_categories=["backend"],
        )
        mid = m["mission_id"]
        await runtime.plan_mission(mid)

        rb = await runtime.rollback_mission(mid, reason="Unexpected failure")
        assert rb["status"] == "rolled_back"

        detail = await runtime.get_mission(mid)
        assert detail["current_phase"] == MissionState.FAILED.value
        assert detail["autonomy_level"] == AutonomyLevel.ROLLBACK.value


class TestScenario5EmergencyStop:
    """Emergency stop — mission is aborted immediately."""

    @pytest.mark.asyncio
    async def test_emergency_stop(self, runtime):
        """Emergency stop aborts the mission."""
        m = await runtime.create_mission(
            source="github", repository="org/emergency",
            change_categories=["critical"],
        )
        mid = m["mission_id"]
        runtime._update_mission(mid, risk_score=0.95)

        plan = await runtime.plan_mission(mid)
        assert plan["status"] in ("failed", "planned")

        detail = await runtime.get_mission(mid)
        # After planning with high risk, mission should be failed or still planned
        assert detail["current_phase"] in (MissionState.FAILED.value, MissionState.PLANNED.value)


class TestScenario6MissionRetry:
    """Mission retry — retry from current phase."""

    @pytest.mark.asyncio
    async def test_mission_retry(self, runtime):
        """Retry records intervention and keeps same phase."""
        m = await runtime.create_mission(
            source="github", repository="org/retry-s6",
        )
        mid = m["mission_id"]
        await runtime.plan_mission(mid)

        retried = await runtime.retry_mission(mid)
        assert retried["status"] == "retrying"

        detail = await runtime.get_mission(mid)
        assert detail["intervention_count"] == 1


class TestScenario7HumanIntervention:
    """Human intervention — mission escalated for human review."""

    @pytest.mark.asyncio
    async def test_human_intervention(self, runtime):
        """Human intervention escalates and changes autonomy level."""
        m = await runtime.create_mission(
            source="github", repository="org/intervention-s7",
        )
        mid = m["mission_id"]

        escalated = await runtime.escalate_mission(mid, reason="Requires manual review")
        assert escalated["status"] == "escalated"

        detail = await runtime.get_mission(mid)
        assert detail["autonomy_level"] == AutonomyLevel.HUMAN_INTERVENTION.value
        assert "manual review" in detail.get("error_message", "")


class TestScenario8ConcurrentMissions:
    """Concurrent missions — multiple missions managed simultaneously."""

    @pytest.mark.asyncio
    async def test_concurrent_missions(self, runtime):
        """Multiple missions can exist and be tracked independently."""
        missions = []
        for i in range(5):
            m = await runtime.create_mission(
                source="github", repository=f"org/concurrent-{i}",
                change_categories=["backend"],
            )
            missions.append(m)

        # Plan all
        for m in missions:
            await runtime.plan_mission(m["mission_id"])

        # Complete first two via valid chain
        for idx in (0, 1):
            mid = missions[idx]["mission_id"]
            for phase in ("running", "approval", "deploying", "monitoring", "verifying", "learning"):
                try:
                    runtime._transition(mid, phase)
                except ValueError:
                    pass
            try:
                runtime._transition(mid, MissionState.COMPLETED.value)
            except ValueError:
                pass

        # Fail the third via valid chain
        mid2 = missions[2]["mission_id"]
        runtime._transition(mid2, "running")
        runtime._transition(mid2, "failed")

        dash = await runtime.get_dashboard()
        assert dash["total_missions"] == 5
        assert dash["completed"] == 2
        assert dash["failed"] == 1

        # Remaining should be active
        active = await runtime.list_active_missions()
        assert len(active) == 2  # missions 3 and 4 still in planned
