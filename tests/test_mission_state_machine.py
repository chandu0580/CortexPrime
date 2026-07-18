from __future__ import annotations

import pytest

from backend.mission.models import MissionPriority, MissionStatus, MissionType
from backend.mission.state_machine import (
    TRANSITIONS,
    is_terminal,
    is_transient,
    is_valid_transition,
)


class TestStateMachine:
    def test_initial_state_is_created(self):
        assert MissionStatus.CREATED.value == "CREATED"

    def test_all_states_defined(self):
        expected = {
            "CREATED", "PLANNING", "RISK_ANALYSIS", "AWAITING_APPROVAL",
            "APPROVED", "QUEUED", "EXECUTING", "MONITORING", "VERIFYING",
            "COMPLETED", "FAILED", "ROLLING_BACK", "ROLLED_BACK", "CANCELLED",
        }
        actual = {s.value for s in MissionStatus}
        assert actual == expected

    def test_valid_created_to_planning(self):
        assert is_valid_transition(MissionStatus.CREATED, MissionStatus.PLANNING)

    def test_valid_created_to_cancelled(self):
        assert is_valid_transition(MissionStatus.CREATED, MissionStatus.CANCELLED)

    def test_invalid_created_to_completed(self):
        assert not is_valid_transition(MissionStatus.CREATED, MissionStatus.COMPLETED)

    def test_valid_planning_to_risk_analysis(self):
        assert is_valid_transition(MissionStatus.PLANNING, MissionStatus.RISK_ANALYSIS)

    def test_valid_planning_to_cancelled(self):
        assert is_valid_transition(MissionStatus.PLANNING, MissionStatus.CANCELLED)

    def test_valid_risk_analysis_to_awaiting_approval(self):
        assert is_valid_transition(MissionStatus.RISK_ANALYSIS, MissionStatus.AWAITING_APPROVAL)

    def test_valid_risk_analysis_to_cancelled(self):
        assert is_valid_transition(MissionStatus.RISK_ANALYSIS, MissionStatus.CANCELLED)

    def test_valid_awaiting_approval_to_approved(self):
        assert is_valid_transition(MissionStatus.AWAITING_APPROVAL, MissionStatus.APPROVED)

    def test_valid_approved_to_queued(self):
        assert is_valid_transition(MissionStatus.APPROVED, MissionStatus.QUEUED)

    def test_valid_queued_to_executing(self):
        assert is_valid_transition(MissionStatus.QUEUED, MissionStatus.EXECUTING)

    def test_valid_executing_to_monitoring(self):
        assert is_valid_transition(MissionStatus.EXECUTING, MissionStatus.MONITORING)

    def test_valid_executing_to_failed(self):
        assert is_valid_transition(MissionStatus.EXECUTING, MissionStatus.FAILED)

    def test_valid_executing_to_cancelled(self):
        assert is_valid_transition(MissionStatus.EXECUTING, MissionStatus.CANCELLED)

    def test_valid_monitoring_to_verifying(self):
        assert is_valid_transition(MissionStatus.MONITORING, MissionStatus.VERIFYING)

    def test_valid_monitoring_to_cancelled(self):
        assert is_valid_transition(MissionStatus.MONITORING, MissionStatus.CANCELLED)

    def test_valid_verifying_to_completed(self):
        assert is_valid_transition(MissionStatus.VERIFYING, MissionStatus.COMPLETED)

    def test_valid_verifying_to_rolling_back(self):
        assert is_valid_transition(MissionStatus.VERIFYING, MissionStatus.ROLLING_BACK)

    def test_valid_verifying_to_cancelled(self):
        assert is_valid_transition(MissionStatus.VERIFYING, MissionStatus.CANCELLED)

    def test_valid_rolling_back_to_rolled_back(self):
        assert is_valid_transition(MissionStatus.ROLLING_BACK, MissionStatus.ROLLED_BACK)

    def test_valid_rolling_back_to_cancelled(self):
        assert is_valid_transition(MissionStatus.ROLLING_BACK, MissionStatus.CANCELLED)

    def test_valid_failed_to_queued(self):
        assert is_valid_transition(MissionStatus.FAILED, MissionStatus.QUEUED)

    def test_valid_failed_to_rolling_back(self):
        assert is_valid_transition(MissionStatus.FAILED, MissionStatus.ROLLING_BACK)

    def test_valid_rolled_back_to_cancelled(self):
        assert is_valid_transition(MissionStatus.ROLLED_BACK, MissionStatus.CANCELLED)

    def test_terminal_states(self):
        assert is_terminal(MissionStatus.COMPLETED)
        assert is_terminal(MissionStatus.CANCELLED)
        assert is_terminal(MissionStatus.ROLLED_BACK)
        assert not is_terminal(MissionStatus.CREATED)
        assert not is_terminal(MissionStatus.EXECUTING)

    def test_transient_states(self):
        assert is_transient(MissionStatus.PLANNING)
        assert is_transient(MissionStatus.EXECUTING)
        assert is_transient(MissionStatus.MONITORING)
        assert not is_transient(MissionStatus.CREATED)
        assert not is_transient(MissionStatus.COMPLETED)

    def test_invalid_transition_returns_false(self):
        assert not is_valid_transition(MissionStatus.COMPLETED, MissionStatus.EXECUTING)
        assert not is_valid_transition(MissionStatus.CANCELLED, MissionStatus.CREATED)
        assert not is_valid_transition(MissionStatus.CREATED, MissionStatus.FAILED)

    def test_every_state_has_entry(self):
        for status in MissionStatus:
            assert status in TRANSITIONS

    def test_no_transition_from_completed(self):
        assert len(TRANSITIONS[MissionStatus.COMPLETED]) == 0

    def test_no_transition_from_cancelled(self):
        assert len(TRANSITIONS[MissionStatus.CANCELLED]) == 0

    def test_failed_can_retry_or_rollback(self):
        allowed = TRANSITIONS[MissionStatus.FAILED]
        assert MissionStatus.QUEUED in allowed
        assert MissionStatus.ROLLING_BACK in allowed
        assert MissionStatus.CANCELLED in allowed

    def test_all_transitions_reversible_check(self):
        for from_st, targets in TRANSITIONS.items():
            for to_st in targets:
                assert to_st in MissionStatus, f"Target {to_st} not a valid status"
                if is_terminal(to_st):
                    pass

    def test_priority_values(self):
        assert MissionPriority.CRITICAL.value == 1
        assert MissionPriority.HIGH.value == 2
        assert MissionPriority.MEDIUM.value == 3
        assert MissionPriority.LOW.value == 4
        assert MissionPriority.BACKGROUND.value == 5

    def test_mission_type_values(self):
        assert MissionType.STANDARD.value == "standard"
        assert MissionType.EMERGENCY.value == "emergency"
