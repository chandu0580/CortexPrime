from __future__ import annotations

import pytest

from backend.cognitive_memory.compression import MemoryCompressor, memory_compressor
from backend.cognitive_memory.context_store import ContextStore, context_store
from backend.cognitive_memory.manager import MemoryManager, memory_manager
from backend.cognitive_memory.models import (
    ConversationTurn,
    MemoryArtifact,
    MemoryContext,
    MemoryPhase,
    MemorySnapshot,
    MemoryStatus,
    MissionMemory,
    ReasoningMemory,
    ReasoningStep,
    WorkingMemory,
)
from backend.cognitive_memory.service import CognitiveMemoryService, cognitive_memory_service


@pytest.fixture(autouse=True)
def clear_store():
    memory_manager.clear_all()
    yield


# ==============================================================================
# Model Tests
# ==============================================================================

class TestModels:
    def test_memory_phase_values(self):
        assert MemoryPhase.INIT.value == "init"
        assert MemoryPhase.PLANNING.value == "planning"
        assert MemoryPhase.EXECUTING.value == "executing"
        assert MemoryPhase.VERIFYING.value == "verifying"
        assert MemoryPhase.COMPLETED.value == "completed"

    def test_memory_status_values(self):
        assert MemoryStatus.ACTIVE.value == "active"
        assert MemoryStatus.SNAPSHOTTED.value == "snapshotted"
        assert MemoryStatus.COMPRESSED.value == "compressed"
        assert MemoryStatus.EXPIRED.value == "expired"
        assert MemoryStatus.ARCHIVED.value == "archived"

    def test_working_memory_defaults(self):
        wm = WorkingMemory()
        assert wm.current_goal == ""
        assert wm.current_phase == MemoryPhase.INIT
        assert wm.completed_steps == []
        assert wm.pending_steps == []
        assert wm.task_outputs == {}

    def test_reasoning_step_defaults(self):
        rs = ReasoningStep(step_id="s1", description="test")
        assert rs.decision == ""
        assert rs.alternatives == []
        assert rs.confidence == 1.0

    def test_conversation_turn_defaults(self):
        ct = ConversationTurn(turn_id="t1", role="user", content="hello")
        assert ct.metadata == {}

    def test_memory_context_defaults(self):
        mc = MemoryContext(mission_id="m1")
        assert mc.status == MemoryStatus.ACTIVE
        assert mc.working_memory.current_phase == MemoryPhase.INIT
        assert mc.user_id == ""
        assert mc.tags == {}

    def test_memory_snapshot_defaults(self):
        ms = MemorySnapshot()
        assert ms.snapshot_id == ""
        assert ms.context_copy is None
        assert ms.step_count == 0

    def test_memory_artifact_defaults(self):
        ma = MemoryArtifact(artifact_id="a1", name="test", artifact_type="doc", data="data")
        assert ma.source == ""
        assert ma.metadata == {}


# ==============================================================================
# Context Store Tests
# ==============================================================================

class TestContextStore:
    def test_put_and_get(self):
        store = ContextStore()
        ctx = MemoryContext(mission_id="m1")
        store.put(ctx)
        assert store.get("m1") is ctx
        assert store.get("nonexistent") is None

    def test_delete(self):
        store = ContextStore()
        ctx = MemoryContext(mission_id="m1")
        store.put(ctx)
        assert store.delete("m1") is True
        assert store.delete("m1") is False

    def test_list_all(self):
        store = ContextStore()
        store.put(MemoryContext(mission_id="m1"))
        store.put(MemoryContext(mission_id="m2"))
        assert len(store.list_all()) == 2

    def test_count(self):
        store = ContextStore()
        assert store.count() == 0
        store.put(MemoryContext(mission_id="m1"))
        assert store.count() == 1

    def test_snapshots(self):
        store = ContextStore()
        snap = MemorySnapshot(snapshot_id="s1", mission_id="m1")
        store.put_snapshot("m1", snap)
        assert len(store.get_snapshots("m1")) == 1
        assert store.get_snapshot("m1", "s1") is snap
        assert store.get_snapshot("m1", "nonexistent") is None
        assert store.delete_snapshots("m1") is True

    def test_artifacts(self):
        store = ContextStore()
        art = MemoryArtifact(artifact_id="a1", name="test", artifact_type="txt", data="x")
        store.add_artifact("m1", art)
        assert len(store.get_artifacts("m1")) == 1
        assert store.delete_artifacts("m1") is True

    def test_find_by_user(self):
        store = ContextStore()
        store.put(MemoryContext(mission_id="m1", user_id="u1"))
        store.put(MemoryContext(mission_id="m2", user_id="u2"))
        store.put(MemoryContext(mission_id="m3", user_id="u1"))
        assert len(store.find_by_user("u1")) == 2
        assert len(store.find_by_user("u3")) == 0

    def test_find_by_tenant(self):
        store = ContextStore()
        store.put(MemoryContext(mission_id="m1", tenant_id="t1"))
        store.put(MemoryContext(mission_id="m2", tenant_id="t2"))
        assert len(store.find_by_tenant("t1")) == 1

    def test_find_by_trace(self):
        store = ContextStore()
        store.put(MemoryContext(mission_id="m1", trace_id="tr1"))
        assert len(store.find_by_trace("tr1")) == 1

    def test_find_by_correlation(self):
        store = ContextStore()
        store.put(MemoryContext(mission_id="m1", correlation_id="c1"))
        assert len(store.find_by_correlation("c1")) == 1

    def test_clear(self):
        store = ContextStore()
        store.put(MemoryContext(mission_id="m1"))
        store.clear()
        assert store.count() == 0

    pass


# ==============================================================================
# Memory Manager Tests
# ==============================================================================

class TestMemoryManager:
    def test_create_context(self):
        ctx = memory_manager.create_context(
            mission_id="m1",
            user_id="u1",
            tenant_id="t1",
            trace_id="tr1",
            correlation_id="c1",
            initial_goal="Deploy release",
            mission_name="Release v2",
            objective="Deploy to production",
            category="software_release",
        )
        assert ctx.mission_id == "m1"
        assert ctx.user_id == "u1"
        assert ctx.tenant_id == "t1"
        assert ctx.trace_id == "tr1"
        assert ctx.correlation_id == "c1"
        assert ctx.working_memory.current_goal == "Deploy release"
        assert ctx.mission_memory.mission_name == "Release v2"
        assert ctx.mission_memory.category == "software_release"
        assert ctx.status == MemoryStatus.ACTIVE
        assert ctx.created_at is not None
        assert ctx.expires_at is not None

    def test_get_context_nonexistent(self):
        assert memory_manager.get_context("nonexistent") is None

    def test_get_context(self):
        memory_manager.create_context(mission_id="m1")
        ctx = memory_manager.get_context("m1")
        assert ctx is not None
        assert ctx.mission_id == "m1"

    def test_update_context_goal(self):
        memory_manager.create_context(mission_id="m1")
        updated = memory_manager.update_context("m1", {"current_goal": "New goal"})
        assert updated is not None
        assert updated.working_memory.current_goal == "New goal"

    def test_update_context_phase(self):
        memory_manager.create_context(mission_id="m1")
        updated = memory_manager.update_context("m1", {"current_phase": "executing"})
        assert updated.working_memory.current_phase == MemoryPhase.EXECUTING

    def test_update_context_completed_steps(self):
        memory_manager.create_context(mission_id="m1")
        updated = memory_manager.update_context("m1", {"completed_steps": ["step1", "step2"]})
        assert "step1" in updated.working_memory.completed_steps
        assert "step2" in updated.working_memory.completed_steps

    def test_update_context_pending_steps(self):
        memory_manager.create_context(mission_id="m1")
        updated = memory_manager.update_context("m1", {"pending_steps": ["step3"]})
        assert "step3" in updated.working_memory.pending_steps

    def test_update_context_task_outputs(self):
        memory_manager.create_context(mission_id="m1")
        updated = memory_manager.update_context("m1", {"task_outputs": {"build": "success"}})
        assert updated.working_memory.task_outputs["build"] == "success"

    def test_update_context_active_context(self):
        memory_manager.create_context(mission_id="m1")
        updated = memory_manager.update_context("m1", {"active_context": {"env": "prod"}})
        assert updated.working_memory.active_context["env"] == "prod"

    def test_add_reasoning_step(self):
        memory_manager.create_context(mission_id="m1")
        updated = memory_manager.add_reasoning_step(
            "m1",
            description="Chose Kubernetes",
            decision="Use k8s cluster",
            alternatives=["Docker Swarm", "Nomad"],
            confidence=0.9,
        )
        assert updated is not None
        assert len(updated.reasoning_memory.reasoning_chain) == 1
        step = updated.reasoning_memory.reasoning_chain[0]
        assert step.description == "Chose Kubernetes"
        assert step.decision == "Use k8s cluster"
        assert len(step.alternatives) == 2

    def test_add_critical_reasoning_step(self):
        memory_manager.create_context(mission_id="m1")
        updated = memory_manager.add_reasoning_step(
            "m1", description="Critical decision", decision="Rollback", critical=True,
        )
        assert len(updated.reasoning_memory.critical_decisions) == 1

    def test_add_conversation_turn(self):
        memory_manager.create_context(mission_id="m1")
        updated = memory_manager.add_conversation_turn("m1", role="user", content="Deploy now")
        assert updated is not None
        assert updated.conversation_memory.turn_count == 1
        assert updated.conversation_memory.turns[0].content == "Deploy now"

    def test_record_connector_output(self):
        memory_manager.create_context(mission_id="m1")
        updated = memory_manager.record_connector_output("m1", "github", "deploy", {"status": "ok"})
        assert updated is not None
        assert "github.deploy" in updated.execution_memory.connector_outputs
        assert updated.execution_memory.execution_path == ["github.deploy"]

    def test_record_error(self):
        memory_manager.create_context(mission_id="m1")
        updated = memory_manager.record_error("m1", "github", "Connection failed")
        assert updated is not None
        assert len(updated.execution_memory.error_history) == 1
        assert updated.execution_memory.error_history[0]["error"] == "Connection failed"

    def test_add_artifact(self):
        memory_manager.create_context(mission_id="m1")
        art = memory_manager.add_artifact("m1", "build.log", "log", "Build output", source="github")
        assert art is not None
        assert art.name == "build.log"
        assert art.artifact_type == "log"

    def test_context_not_found_returns_none(self):
        assert memory_manager.add_reasoning_step("nonexistent", "test", "test") is None
        assert memory_manager.add_conversation_turn("nonexistent", "user", "hi") is None
        assert memory_manager.record_connector_output("nonexistent", "x", "y", {}) is None
        assert memory_manager.record_error("nonexistent", "x", "err") is None
        assert memory_manager.add_artifact("nonexistent", "n", "t", "d") is None


# ==============================================================================
# Snapshot / Restore Tests
# ==============================================================================

class TestSnapshotRestore:
    def test_create_snapshot(self):
        memory_manager.create_context(mission_id="m1", initial_goal="Release")
        memory_manager.add_reasoning_step("m1", "Decided approach", "Use k8s")
        memory_manager.update_context("m1", {"pending_steps": ["step1"]})
        snapshot = memory_manager.snapshot("m1")
        assert snapshot is not None
        assert snapshot.mission_id == "m1"
        assert snapshot.snapshot_id != ""
        assert snapshot.context_copy is not None
        assert snapshot.step_count == 1

    def test_snapshot_preserves_state(self):
        memory_manager.create_context(mission_id="m1", initial_goal="Deploy")
        memory_manager.add_reasoning_step("m1", "Chose tool", "Helm")
        snapshot = memory_manager.snapshot("m1")
        assert snapshot.context_copy.working_memory.current_goal == "Deploy"
        assert len(snapshot.context_copy.reasoning_memory.reasoning_chain) == 1

    def test_restore_snapshot(self):
        memory_manager.create_context(mission_id="m1", initial_goal="Original goal")
        memory_manager.add_reasoning_step("m1", "Step 1", "Decision 1")
        snapshot = memory_manager.snapshot("m1")
        memory_manager.update_context("m1", {"current_goal": "Changed goal"})
        restored = memory_manager.restore("m1", snapshot.snapshot_id)
        assert restored is not None
        assert restored.working_memory.current_goal == "Original goal"
        assert len(restored.reasoning_memory.reasoning_chain) == 1

    def test_list_snapshots(self):
        memory_manager.create_context(mission_id="m1")
        memory_manager.snapshot("m1")
        memory_manager.snapshot("m1")
        snapshots = memory_manager.list_snapshots("m1")
        assert len(snapshots) == 2

    def test_restore_nonexistent_snapshot(self):
        memory_manager.create_context(mission_id="m1")
        assert memory_manager.restore("m1", "nonexistent") is None

    def test_snapshot_nonexistent_context(self):
        assert memory_manager.snapshot("nonexistent") is None


# ==============================================================================
# Compression Tests
# ==============================================================================

class TestCompression:
    def test_compress_context(self):
        memory_manager.create_context(mission_id="m1")
        for i in range(10):
            memory_manager.add_reasoning_step("m1", f"Step {i}", f"Decision {i}")
        for i in range(10):
            memory_manager.add_conversation_turn("m1", "user", f"Message {i}")
        compressed = memory_manager.compress("m1")
        assert compressed is not None
        assert compressed.status == MemoryStatus.COMPRESSED

    def test_compress_nonexistent(self):
        assert memory_manager.compress("nonexistent") is None

    def test_compressor_deduplicates(self):
        compressor = MemoryCompressor()
        ctx = MemoryContext(mission_id="m1")
        ctx.reasoning_memory.reasoning_chain = [
            ReasoningStep(step_id="1", description="Same step", decision="Same"),
            ReasoningStep(step_id="2", description="Same step", decision="Same"),
            ReasoningStep(step_id="3", description="Different", decision="Other"),
        ]
        compressed = compressor.compress(ctx)
        assert len(compressed.reasoning_memory.reasoning_chain) == 2

    def test_compressor_preserves_critical(self):
        compressor = MemoryCompressor()
        ctx = MemoryContext(mission_id="m1")
        ctx.reasoning_memory.decisions = [
            {"decision_id": "d1", "text": "Important"},
            {"decision_id": "d2", "text": "Minor"},
            {"decision_id": "d3", "text": "Critical"},
        ]
        ctx.reasoning_memory.critical_decisions = ["d1", "d3"]
        compressed = compressor.compress(ctx)
        assert len(compressed.reasoning_memory.decisions) == 2

    def test_compressor_truncates_outputs(self):
        compressor = MemoryCompressor()
        ctx = MemoryContext(mission_id="m1")
        for i in range(10):
            ctx.working_memory.task_outputs[f"task_{i}"] = f"output_{i}"
        compressed = compressor.compress(ctx)
        assert len(compressed.working_memory.task_outputs) <= 5

    def test_compressor_truncates_conversation(self):
        compressor = MemoryCompressor()
        ctx = MemoryContext(mission_id="m1")
        for i in range(30):
            ctx.conversation_memory.turns.append(
                ConversationTurn(turn_id=f"t{i}", role="user", content=f"msg{i}")
            )
        ctx.conversation_memory.turn_count = 30
        compressed = compressor.compress(ctx)
        assert len(compressed.conversation_memory.turns) <= 20

    def test_compressor_skips_small_outputs(self):
        compressor = MemoryCompressor()
        ctx = MemoryContext(mission_id="m1")
        ctx.working_memory.task_outputs = {"a": "1", "b": "2"}
        compressed = compressor.compress(ctx)
        assert len(compressed.working_memory.task_outputs) == 2

    def test_checkpoint_creation(self):
        compressor = MemoryCompressor()
        ctx = MemoryContext(mission_id="m1", working_memory=WorkingMemory(
            current_goal="Test", current_phase=MemoryPhase.EXECUTING,
            completed_steps=["s1"], pending_steps=["s2"],
        ))
        snapshot = compressor.create_checkpoint(ctx)
        assert snapshot.mission_id == "m1"
        assert snapshot.context_copy is ctx
        assert "completed_steps" in snapshot.compression_metadata
        assert snapshot.step_count == 2


# ==============================================================================
# Context Lifecycle Tests
# ==============================================================================

class TestContextLifecycle:
    def test_expire_context(self):
        memory_manager.create_context(mission_id="m1")
        assert memory_manager.expire_context("m1") is True
        ctx = memory_manager.get_context("m1")
        assert ctx is not None
        assert ctx.status == MemoryStatus.EXPIRED

    def test_expire_nonexistent(self):
        assert memory_manager.expire_context("nonexistent") is False

    def test_archive_context(self):
        memory_manager.create_context(mission_id="m1")
        assert memory_manager.archive_context("m1") is True
        ctx = memory_manager.get_context("m1")
        assert ctx is not None
        assert ctx.status == MemoryStatus.ARCHIVED

    def test_archive_creates_snapshot(self):
        memory_manager.create_context(mission_id="m1")
        memory_manager.archive_context("m1")
        snapshots = memory_manager.list_snapshots("m1")
        assert len(snapshots) >= 1

    def test_delete_context(self):
        memory_manager.create_context(mission_id="m1")
        assert memory_manager.delete_context("m1") is True
        assert memory_manager.get_context("m1") is None

    def test_delete_nonexistent(self):
        assert memory_manager.delete_context("nonexistent") is False

    def test_list_active(self):
        memory_manager.create_context(mission_id="m1")
        memory_manager.create_context(mission_id="m2")
        memory_manager.expire_context("m2")
        active = memory_manager.list_active()
        assert len(active) == 1
        assert active[0].mission_id == "m1"


# ==============================================================================
# Retrieval Tests
# ==============================================================================

class TestRetrieval:
    def test_find_by_user(self):
        memory_manager.create_context(mission_id="m1", user_id="u1")
        memory_manager.create_context(mission_id="m2", user_id="u1")
        memory_manager.create_context(mission_id="m3", user_id="u2")
        results = memory_manager.find_by_user("u1")
        assert len(results) == 2

    def test_find_by_tenant(self):
        memory_manager.create_context(mission_id="m1", tenant_id="t1")
        memory_manager.create_context(mission_id="m2", tenant_id="t2")
        results = memory_manager.find_by_tenant("t1")
        assert len(results) == 1

    def test_find_by_trace(self):
        memory_manager.create_context(mission_id="m1", trace_id="tr1")
        results = memory_manager.find_by_trace("tr1")
        assert len(results) == 1

    def test_find_by_correlation(self):
        memory_manager.create_context(mission_id="m1", correlation_id="c1")
        results = memory_manager.find_by_correlation("c1")
        assert len(results) == 1

    def test_no_results(self):
        assert memory_manager.find_by_user("unknown") == []
        assert memory_manager.find_by_tenant("unknown") == []
        assert memory_manager.find_by_trace("unknown") == []
        assert memory_manager.find_by_correlation("unknown") == []


# ==============================================================================
# Cognitive Memory Service Tests
# ==============================================================================

class TestCognitiveMemoryService:
    def test_service_create_context(self):
        ctx = cognitive_memory_service.create_context(mission_id="m1", initial_goal="Goal")
        assert ctx.mission_id == "m1"
        assert ctx.working_memory.current_goal == "Goal"

    def test_service_full_lifecycle(self):
        ctx = cognitive_memory_service.create_context(
            mission_id="m1",
            user_id="u1",
            initial_goal="Deploy",
            mission_name="Release",
            category="software_release",
        )
        assert ctx is not None

        cognitive_memory_service.add_reasoning_step("m1", "Analysis", "Use k8s", critical=True)
        cognitive_memory_service.add_conversation_turn("m1", "user", "Proceed")
        cognitive_memory_service.record_connector_output("m1", "github", "deploy", {"status": "ok"})
        cognitive_memory_service.record_error("m1", "docker", "Timeout")

        snapshot = cognitive_memory_service.snapshot("m1")
        assert snapshot is not None

        restored = cognitive_memory_service.restore("m1", snapshot.snapshot_id)
        assert restored is not None

        compressed = cognitive_memory_service.compress("m1")
        assert compressed is not None
        assert compressed.status == MemoryStatus.COMPRESSED

    def test_service_retrieval(self):
        cognitive_memory_service.create_context(mission_id="m1", user_id="u1", tenant_id="t1")
        cognitive_memory_service.create_context(mission_id="m2", user_id="u1", tenant_id="t2")
        assert len(cognitive_memory_service.find_by_user("u1")) == 2
        assert len(cognitive_memory_service.find_by_tenant("t2")) == 1

    def test_service_health(self):
        health = cognitive_memory_service.health()
        assert health["status"] == "healthy"
        assert health["service"] == "cognitive_memory"
        assert isinstance(health["active_contexts"], int)

    def test_service_artifact(self):
        cognitive_memory_service.create_context(mission_id="m1")
        art = cognitive_memory_service.add_artifact("m1", "report.pdf", "document", b"pdfdata", source="test")
        assert art is not None
        assert art.name == "report.pdf"

    def test_service_expire_archive(self):
        cognitive_memory_service.create_context(mission_id="m1")
        assert cognitive_memory_service.expire_context("m1") is True
        cognitive_memory_service.create_context(mission_id="m2")
        assert cognitive_memory_service.archive_context("m2") is True

    def test_service_get_nonexistent(self):
        assert cognitive_memory_service.get_context("nonexistent") is None

    pass
