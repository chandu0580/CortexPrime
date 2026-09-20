"""Phase 11.4: the asynchronous execution contract.

The product surface this phase adds is small on purpose: a caller may say it is
not going to wait, and come back later for the answer. What must NOT change is
anything governance depends on -- so these tests pin the two properties that
make that true.

1. ``submit`` runs the identical chain as ``write`` up to the point a caller
   would have started waiting, and stops there. Authorization, the approval
   check against the action digest and the binding have all happened before it
   returns; only the provider call has not.
2. A request governance refuses does **not** become a durable execution that
   somebody later discovers and runs. "Accepted, ask later" must never be the
   answer to "no".
"""
from __future__ import annotations

from backend.api.capability_execution_composition import (
    PUBLIC_NODE_STATE,
    execution_status,
)


class _Stream:
    def __init__(self, nodes, state="running"):
        self._nodes = nodes
        self._state = state

    def stream_state(self, context, execution_id):
        return {
            "execution_id": execution_id,
            "state": self._state,
            "progress": {"finished": 0, "total": len(self._nodes)},
            "nodes": [
                {"node_id": n, "state": s, "attempts": 1}
                for n, s in self._nodes
            ],
        }


class _Runtime:
    def __init__(self, executions):
        self.executions = executions


def test_status_translates_the_durable_state_and_invents_nothing():
    runtime = _Runtime(_Stream([("node-1", "leased")]))
    found = execution_status(runtime, None, "exec-1")
    assert found["status"] == "EXECUTING"
    assert found["execution_state"] == "running"
    assert found["nodes"][0]["node_id"] == "node-1"


def test_an_ambiguous_node_is_not_reported_as_failure():
    """The aggregate says UNKNOWN when it cannot tell whether the provider
    acted. Flattening that into FAILED is how an ambiguous mutation gets
    attempted twice."""
    runtime = _Runtime(_Stream([("node-1", "unknown")]))
    assert execution_status(runtime, None, "e")["status"] == "INSUFFICIENT_EVIDENCE"


def test_the_public_vocabulary_claims_no_verification_state():
    """Verification is a separate record with its own verdict. An execution
    state called VERIFIED would claim the execution knows something it does
    not."""
    assert "VERIFIED" not in set(PUBLIC_NODE_STATE.values())
    assert "VERIFYING" not in set(PUBLIC_NODE_STATE.values())


def test_every_durable_node_state_has_a_public_name():
    """A state the translation does not know would surface raw to a caller."""
    from backend.contexts.execution.domain.state import NodeState

    for state in NodeState:
        assert state.value in PUBLIC_NODE_STATE, state.value


def test_submit_and_write_are_the_same_door():
    """Not a second execution path: both reach ``_perform``, and the only
    difference is whether it dispatches."""
    import inspect

    from backend.api.capability_execution_composition import GovernedCapabilityWriter

    submit = inspect.getsource(GovernedCapabilityWriter.submit)
    write = inspect.getsource(GovernedCapabilityWriter.write)
    assert "self._perform(" in submit and "self._perform(" in write
    assert "dispatch=False" in submit
    # The guards a write performs must not be skipped by the asynchronous door.
    for guard in ("is not a capability this writer was given", "is a read"):
        assert guard in submit, guard


def test_submit_returns_a_dispatchable_receipt_without_driving():
    """The receipt names a durable execution and does not claim an outcome."""
    import inspect

    from backend.api.capability_execution_composition import GovernedCapabilityReader

    source = inspect.getsource(GovernedCapabilityReader._perform)
    # The early return must sit AFTER resolution and BEFORE _drive.
    assert source.index("resolution.resolve") < source.index("if not dispatch:")
    assert source.index("if not dispatch:") < source.index("self._drive(")


# ---------------------------------------------------------------- F-11


def test_the_audit_writer_role_is_reclaimed_not_only_acquired_once():
    """ADR-128 F-11. Audit writing must survive losing the role.

    ``is_writer`` renews the lease on every append, so a quiet spell longer than
    the lease lets it lapse -- and then any process may take the role. The
    incumbent's next heartbeat returns None and it drops its handle. Until this
    fix, ``acquire`` was called only at startup, so that process stopped writing
    audit permanently and silently: a refused append is *contained* rather than
    raised (ADR-054/056), so nothing would have told anyone.

    Proven live before the fix: a second process seized the role from an idle
    deployment (fencing token 51 -> 52).
    """
    import inspect

    from backend.api.application_runtime import GovernedApplicationRuntime

    pump = inspect.getsource(GovernedApplicationRuntime._pump)
    assert "self.audit_writer.acquire()" in pump, (
        "the pump must be able to reclaim the audit-writer role"
    )
    # And it must only do so when the role is actually free, never stealing it
    # from itself on every cycle.
    assert 'getattr(self.audit_writer, "handle", None) is None' in pump
