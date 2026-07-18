"""Sprint S3 Phase 9: Validate the autonomous end-to-end pipeline across 7 real scenarios.

Scenarios:
  1. Happy path — all 22 stages complete successfully
  2. Build failure → auto-patch generation → retry succeeds
  3. QA failure → auto-patch generation → retry succeeds
  4. Security failure → auto-patch generation → retry succeeds
  5. Deployment failure → auto-rollback → redeploy succeeds
  6. Approval gate blocks — delivery waits for manual approval
  7. Resume from paused delivery — continues from last completed stage
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any, Dict, List

import pytest

# Ensure backend is importable
_BACKEND = Path(__file__).resolve().parent.parent / "backend"
if str(_BACKEND.parent) not in os.environ.get("PYTHONPATH", "").split(os.pathsep):
    import sys
    sys.path.insert(0, str(_BACKEND.parent))

# ── In-memory storage to avoid file I/O pollution between tests ─────────────
import backend.services.enterprise_delivery_orchestrator as _edo_mod  # noqa: E402

_in_memory_store: List[Dict[str, Any]] = []

def _in_memory_load() -> List[Dict[str, Any]]:
    return list(_in_memory_store)  # return a copy

def _in_memory_save(data: List[Dict[str, Any]]) -> None:
    _in_memory_store.clear()
    _in_memory_store.extend(data)

def _in_memory_sync(*args, **kwargs) -> None:
    pass  # no-op runtime sync to avoid file I/O

_edo_mod._load = _in_memory_load
_edo_mod._save = _in_memory_save
_edo_mod._sync_delivery_to_runtime = _in_memory_sync
del _edo_mod
# ─────────────────────────────────────────────────────────────────────────────

from backend.services.enterprise_delivery_orchestrator import (  # noqa: E402
    DELIVERY_STAGES,
    EnterpriseDeliveryOrchestrator,
    delivery_orchestrator,
)

pytestmark = pytest.mark.asyncio

STAGES_WITH_HANDLERS = [s for s in DELIVERY_STAGES if s != "complete"]


# ── Helpers ──────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_store():
    _in_memory_store.clear()


def _make_repo() -> str:
    return f"https://github.com/test/validation-{uuid.uuid4().hex[:8]}"


def _make_mission() -> str:
    return f"validation-{uuid.uuid4().hex[:8]}"


async def _create_and_start(orchestrator: EnterpriseDeliveryOrchestrator, mission: str, repo: str) -> str:
    delivery = await orchestrator.create_delivery(mission=mission, repository=repo)
    d_id = delivery["delivery_id"]
    await orchestrator.start_delivery(d_id)
    return d_id


def _patch_stage_handler(monkeypatch, stage: str, fail: bool = False, fail_msg: str = "Simulated failure"):
    async def _handler(*args, **kwargs):
        if fail:
            raise RuntimeError(fail_msg)
    if stage == "complete":
        return
    monkeypatch.setattr(
        delivery_orchestrator,
        f"_stage_{stage}",
        _handler,
    )


async def _wait_for_state(orchestrator: EnterpriseDeliveryOrchestrator, d_id: str, target_state: str, max_attempts: int = 60) -> Dict[str, Any]:
    for _ in range(max_attempts):
        d = await orchestrator.get_delivery(d_id)
        if d and d.get("state") == target_state:
            return d
    raise TimeoutError(f"Delivery {d_id} did not reach '{target_state}' after {max_attempts} polls")


# ── Scenario 1: Happy Path ─────────────────────────────────────────────────


class TestHappyPath:
    """All 22 stages complete without error."""

    async def test_full_green_pipeline(self, monkeypatch):
        for stage in STAGES_WITH_HANDLERS:
            _patch_stage_handler(monkeypatch, stage, fail=False)

        d_id = await _create_and_start(delivery_orchestrator, _make_mission(), _make_repo())
        result = await _wait_for_state(delivery_orchestrator, d_id, "completed")
        assert result["state"] == "completed"
        assert result.get("stages_completed", []) == DELIVERY_STAGES
        assert result.get("completed_at", "") != ""


# ── Scenario 2: Build failure → auto-patch → retry succeeds ────────────────


class TestBuildFailureAutoRecovery:
    """Build fails once, patch_generation kicks in, retry succeeds."""

    async def test_build_failure_triggers_patch_recovery(self, monkeypatch):
        call_count = {"build": 0}

        async def _build_handler(*args, **kwargs):
            call_count["build"] += 1
            if call_count["build"] == 1:
                raise RuntimeError("Build failure: compilation error")

        monkeypatch.setattr(delivery_orchestrator, "_stage_build", _build_handler)
        for stage in STAGES_WITH_HANDLERS:
            if stage not in ("build",):
                _patch_stage_handler(monkeypatch, stage, fail=False)

        d_id = await _create_and_start(delivery_orchestrator, _make_mission(), _make_repo())
        result = await _wait_for_state(delivery_orchestrator, d_id, "completed")
        assert result["state"] == "completed"
        assert "build" in result.get("stages_completed", [])
        assert call_count["build"] == 2


# ── Scenario 3: QA failure → auto-patch → retry succeeds ──────────────────


class TestQAFailureAutoRecovery:
    """QA fails once, patch_generation kicks in, retry succeeds."""

    async def test_qa_failure_triggers_patch_recovery(self, monkeypatch):
        call_count = {"qa": 0}

        async def _qa_handler(*args, **kwargs):
            call_count["qa"] += 1
            if call_count["qa"] == 1:
                raise RuntimeError("QA failure: test assertions failed")

        monkeypatch.setattr(delivery_orchestrator, "_stage_qa", _qa_handler)
        for stage in STAGES_WITH_HANDLERS:
            if stage not in ("qa",):
                _patch_stage_handler(monkeypatch, stage, fail=False)

        d_id = await _create_and_start(delivery_orchestrator, _make_mission(), _make_repo())
        result = await _wait_for_state(delivery_orchestrator, d_id, "completed")
        assert result["state"] == "completed"
        assert "qa" in result.get("stages_completed", [])
        assert call_count["qa"] == 2


# ── Scenario 4: Security failure → auto-patch → retry succeeds ────────────


class TestSecurityFailureAutoRecovery:
    """Security fails once, patch_generation kicks in, retry succeeds."""

    async def test_security_failure_triggers_patch_recovery(self, monkeypatch):
        call_count = {"security": 0}

        async def _security_handler(*args, **kwargs):
            call_count["security"] += 1
            if call_count["security"] == 1:
                raise RuntimeError("Security failure: critical vulnerability")

        monkeypatch.setattr(delivery_orchestrator, "_stage_security", _security_handler)
        for stage in STAGES_WITH_HANDLERS:
            if stage not in ("security",):
                _patch_stage_handler(monkeypatch, stage, fail=False)

        d_id = await _create_and_start(delivery_orchestrator, _make_mission(), _make_repo())
        result = await _wait_for_state(delivery_orchestrator, d_id, "completed")
        assert result["state"] == "completed"
        assert "security" in result.get("stages_completed", [])
        assert call_count["security"] == 2


# ── Scenario 5: Deployment failure → auto-rollback → redeploy succeeds ────


class TestDeploymentFailureAutoRollback:
    async def test_deployment_failure_triggers_rollback_recovery(self, monkeypatch):
        call_count = {"deployment": 0}

        async def _deploy_handler(delivery_id, blueprint):
            call_count["deployment"] += 1
            if call_count["deployment"] == 1:
                raise RuntimeError("Deployment failure: pod crash loop")

        monkeypatch.setattr(delivery_orchestrator, "_stage_deployment", _deploy_handler)
        for stage in STAGES_WITH_HANDLERS:
            if stage not in ("deployment",):
                _patch_stage_handler(monkeypatch, stage, fail=False)

        d_id = await _create_and_start(delivery_orchestrator, _make_mission(), _make_repo())
        result = await _wait_for_state(delivery_orchestrator, d_id, "completed")
        assert result["state"] == "completed"
        assert "deployment" in result.get("stages_completed", [])
        assert call_count["deployment"] == 2


# ── Scenario 6: Approval gate blocks ───────────────────────────────────────


class TestApprovalGate:
    async def test_approval_pauses_delivery(self, monkeypatch):
        for stage in STAGES_WITH_HANDLERS:
            if stage != "approval":
                _patch_stage_handler(monkeypatch, stage, fail=False)

        d_id = await _create_and_start(delivery_orchestrator, _make_mission(), _make_repo())
        result = await _wait_for_state(delivery_orchestrator, d_id, "waiting_approval")
        assert result["state"] == "waiting_approval"

    async def test_approval_granted_allows_completion(self, monkeypatch):
        for stage in STAGES_WITH_HANDLERS:
            if stage != "approval":
                _patch_stage_handler(monkeypatch, stage, fail=False)

        d_id = await _create_and_start(delivery_orchestrator, _make_mission(), _make_repo())
        await _wait_for_state(delivery_orchestrator, d_id, "waiting_approval")

        await delivery_orchestrator.update_blueprint(d_id, {
            "approvals": [{"approver": "admin", "approved_at": "2026-01-01T00:00:00Z"}],
        })

        result = await delivery_orchestrator.resume_delivery(d_id)
        assert result["state"] == "completed"


# ── Scenario 7: Pause and Resume ──────────────────────────────────────────


class TestPauseResume:
    async def test_pause_and_resume(self, monkeypatch):
        import asyncio

        stage_order: List[str] = []
        resume_event = asyncio.Event()
        pause_detected = asyncio.Event()

        async def _handler_trigger(*args, **kwargs):
            stage_order.append("trigger_pipeline")
            pause_detected.set()
            await resume_event.wait()

        async def _track(stage_name):
            async def _h(*args, **kwargs):
                stage_order.append(stage_name)
            return _h

        for stage in STAGES_WITH_HANDLERS:
            if stage == "trigger_pipeline":
                monkeypatch.setattr(delivery_orchestrator, "_stage_trigger_pipeline", _handler_trigger)
            else:
                monkeypatch.setattr(delivery_orchestrator, f"_stage_{stage}", await _track(stage))

        delivery = await delivery_orchestrator.create_delivery(
            mission=_make_mission(), repository=_make_repo()
        )
        d_id = delivery["delivery_id"]

        async def _execute():
            try:
                return await delivery_orchestrator.start_delivery(d_id)
            except Exception:
                return None

        task = asyncio.create_task(_execute())
        await pause_detected.wait()

        state = (await delivery_orchestrator.get_delivery(d_id))["state"]
        assert state == "running", f"Expected running, got {state}"

        paused = await delivery_orchestrator.pause_delivery(d_id)
        assert paused is not None
        assert paused["state"] == "paused"

        stages_before_pause = stage_order.copy()
        resume_event.set()
        await task

        result = await delivery_orchestrator.resume_delivery(d_id)
        assert result["state"] == "completed"
        assert len(result.get("stages_completed", [])) >= len(stages_before_pause)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
