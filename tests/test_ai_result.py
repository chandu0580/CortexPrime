from __future__ import annotations

from backend.ai.models import RuntimeTarget
from backend.ai.result import RuntimeResult


def test_runtime_result_defaults():
    r = RuntimeResult(runtime=RuntimeTarget.KNOWLEDGE)
    assert r.runtime == RuntimeTarget.KNOWLEDGE
    assert r.status == "success"
    assert r.error is None
    assert r.duration_ms == 0.0
    assert r.is_success
    assert not r.is_failure
    assert not r.is_partial


def test_runtime_result_with_error():
    r = RuntimeResult(runtime=RuntimeTarget.EXECUTION, status="failed", error="something broke")
    assert r.is_failure
    assert not r.is_success
    assert r.error == "something broke"


def test_runtime_result_partial():
    r = RuntimeResult(runtime=RuntimeTarget.MISSION, status="partial")
    assert r.is_partial
    assert not r.is_success
    assert not r.is_failure


def test_runtime_result_data():
    r = RuntimeResult(
        runtime=RuntimeTarget.CONNECTOR,
        data={"result": "ok", "count": 5},
        warnings=["slow response"],
    )
    assert r.data["result"] == "ok"
    assert r.data["count"] == 5
    assert r.warnings == ["slow response"]


def test_runtime_result_step_id():
    r = RuntimeResult(runtime=RuntimeTarget.GOVERNANCE, step_id="step-abc", correlation_id="corr-xyz")
    assert r.step_id == "step-abc"
    assert r.correlation_id == "corr-xyz"


def test_runtime_result_trace():
    r = RuntimeResult(runtime=RuntimeTarget.LEARNING)
    r.trace.append({"action": "search", "duration": 1.5})
    assert len(r.trace) == 1
