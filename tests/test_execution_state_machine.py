from __future__ import annotations

import pytest

from backend.execution.models import ExecutionStatus
from backend.execution.state_machine import TERMINAL, TRANSITIONS, is_terminal, is_valid_transition


class TestExecutionStateMachine:
    def test_all_states_defined(self):
        expected = {
            "CREATED", "QUEUED", "STARTING", "RUNNING", "PAUSED",
            "RETRYING", "SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT",
        }
        actual = {s.value for s in ExecutionStatus}
        assert actual == expected

    def test_valid_created_to_queued(self):
        assert is_valid_transition(ExecutionStatus.CREATED, ExecutionStatus.QUEUED)

    def test_valid_created_to_cancelled(self):
        assert is_valid_transition(ExecutionStatus.CREATED, ExecutionStatus.CANCELLED)

    def test_invalid_created_to_running(self):
        assert not is_valid_transition(ExecutionStatus.CREATED, ExecutionStatus.RUNNING)

    def test_valid_queued_to_starting(self):
        assert is_valid_transition(ExecutionStatus.QUEUED, ExecutionStatus.STARTING)

    def test_valid_queued_to_cancelled(self):
        assert is_valid_transition(ExecutionStatus.QUEUED, ExecutionStatus.CANCELLED)

    def test_valid_starting_to_running(self):
        assert is_valid_transition(ExecutionStatus.STARTING, ExecutionStatus.RUNNING)

    def test_valid_starting_to_failed(self):
        assert is_valid_transition(ExecutionStatus.STARTING, ExecutionStatus.FAILED)

    def test_valid_starting_to_cancelled(self):
        assert is_valid_transition(ExecutionStatus.STARTING, ExecutionStatus.CANCELLED)

    def test_valid_running_to_succeeded(self):
        assert is_valid_transition(ExecutionStatus.RUNNING, ExecutionStatus.SUCCEEDED)

    def test_valid_running_to_failed(self):
        assert is_valid_transition(ExecutionStatus.RUNNING, ExecutionStatus.FAILED)

    def test_valid_running_to_cancelled(self):
        assert is_valid_transition(ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED)

    def test_valid_running_to_paused(self):
        assert is_valid_transition(ExecutionStatus.RUNNING, ExecutionStatus.PAUSED)

    def test_valid_running_to_retrying(self):
        assert is_valid_transition(ExecutionStatus.RUNNING, ExecutionStatus.RETRYING)

    def test_valid_running_to_timed_out(self):
        assert is_valid_transition(ExecutionStatus.RUNNING, ExecutionStatus.TIMED_OUT)

    def test_valid_paused_to_running(self):
        assert is_valid_transition(ExecutionStatus.PAUSED, ExecutionStatus.RUNNING)

    def test_valid_paused_to_cancelled(self):
        assert is_valid_transition(ExecutionStatus.PAUSED, ExecutionStatus.CANCELLED)

    def test_valid_retrying_to_queued(self):
        assert is_valid_transition(ExecutionStatus.RETRYING, ExecutionStatus.QUEUED)

    def test_valid_retrying_to_failed(self):
        assert is_valid_transition(ExecutionStatus.RETRYING, ExecutionStatus.FAILED)

    def test_valid_failed_to_retrying(self):
        assert is_valid_transition(ExecutionStatus.FAILED, ExecutionStatus.RETRYING)

    def test_valid_failed_to_cancelled(self):
        assert is_valid_transition(ExecutionStatus.FAILED, ExecutionStatus.CANCELLED)

    def test_valid_timed_out_to_retrying(self):
        assert is_valid_transition(ExecutionStatus.TIMED_OUT, ExecutionStatus.RETRYING)

    def test_valid_timed_out_to_cancelled(self):
        assert is_valid_transition(ExecutionStatus.TIMED_OUT, ExecutionStatus.CANCELLED)

    def test_terminal_states(self):
        assert is_terminal(ExecutionStatus.SUCCEEDED)
        assert is_terminal(ExecutionStatus.FAILED)
        assert is_terminal(ExecutionStatus.CANCELLED)
        assert is_terminal(ExecutionStatus.TIMED_OUT)
        assert not is_terminal(ExecutionStatus.CREATED)
        assert not is_terminal(ExecutionStatus.RUNNING)

    def test_no_transition_from_succeeded(self):
        assert len(TRANSITIONS[ExecutionStatus.SUCCEEDED]) == 0

    def test_no_transition_from_cancelled(self):
        assert len(TRANSITIONS[ExecutionStatus.CANCELLED]) == 0

    def test_timed_out_can_retry_or_queue_or_cancel(self):
        allowed = TRANSITIONS[ExecutionStatus.TIMED_OUT]
        assert ExecutionStatus.RETRYING in allowed
        assert ExecutionStatus.QUEUED in allowed
        assert ExecutionStatus.CANCELLED in allowed

    def test_every_state_has_entry(self):
        for status in ExecutionStatus:
            assert status in TRANSITIONS

    def test_invalid_transitions_return_false(self):
        assert not is_valid_transition(ExecutionStatus.CREATED, ExecutionStatus.SUCCEEDED)
        assert not is_valid_transition(ExecutionStatus.CREATED, ExecutionStatus.FAILED)
        assert not is_valid_transition(ExecutionStatus.QUEUED, ExecutionStatus.RUNNING)
        assert not is_valid_transition(ExecutionStatus.SUCCEEDED, ExecutionStatus.RUNNING)
        assert not is_valid_transition(ExecutionStatus.CANCELLED, ExecutionStatus.CREATED)
        assert not is_valid_transition(ExecutionStatus.TIMED_OUT, ExecutionStatus.RUNNING)

    def test_failed_can_retry_or_cancel(self):
        allowed = TRANSITIONS[ExecutionStatus.FAILED]
        assert ExecutionStatus.RETRYING in allowed
        assert ExecutionStatus.CANCELLED in allowed

    def test_running_has_multiple_outgoing(self):
        allowed = TRANSITIONS[ExecutionStatus.RUNNING]
        assert len(allowed) == 6

    def test_all_targets_are_valid_status(self):
        for from_st, targets in TRANSITIONS.items():
            for to_st in targets:
                assert to_st in ExecutionStatus, f"Target {to_st} not a valid status"
