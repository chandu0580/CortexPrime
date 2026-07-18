from __future__ import annotations

import logging
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from backend.cognitive_memory.compression import MemoryCompressor, memory_compressor
from backend.cognitive_memory.context_store import ContextStore
from backend.cognitive_memory.context_store import context_store as _ctx_store
from backend.cognitive_memory.models import (
    ConversationTurn,
    MemoryArtifact,
    MemoryContext,
    MemoryPhase,
    MemorySnapshot,
    MemoryStatus,
    MissionMemory,
    ReasoningStep,
    WorkingMemory,
)

log = logging.getLogger(__name__)

DEFAULT_TTL_HOURS = 24


class MemoryManager:
    def __init__(
        self,
        context_store: Optional[ContextStore] = None,
        compressor: Optional[MemoryCompressor] = None,
    ) -> None:
        self._store = context_store or _ctx_store
        self._compressor = compressor or memory_compressor

    def create_context(
        self,
        mission_id: str,
        user_id: str = "",
        tenant_id: str = "",
        trace_id: str = "",
        correlation_id: str = "",
        ttl_hours: int = DEFAULT_TTL_HOURS,
        initial_goal: str = "",
        mission_name: str = "",
        objective: str = "",
        category: str = "",
    ) -> MemoryContext:
        now = datetime.now(timezone.utc)
        expires = now + timedelta(hours=ttl_hours) if ttl_hours > 0 else None
        context = MemoryContext(
            mission_id=mission_id,
            working_memory=WorkingMemory(
                current_goal=initial_goal,
                current_phase=MemoryPhase.INIT,
            ),
            mission_memory=MissionMemory(
                mission_id=mission_id,
                mission_name=mission_name or mission_id,
                objective=objective,
                category=category,
            ),
            status=MemoryStatus.ACTIVE,
            created_at=now.isoformat(),
            updated_at=now.isoformat(),
            expires_at=expires.isoformat() if expires else None,
            user_id=user_id,
            tenant_id=tenant_id,
            trace_id=trace_id,
            correlation_id=correlation_id,
        )
        self._store.put(context)
        log.info("Created memory context for mission %s", mission_id)
        return context

    def get_context(self, mission_id: str) -> Optional[MemoryContext]:
        context = self._store.get(mission_id)
        if context and self._is_expired(context):
            self.expire_context(mission_id)
            return None
        return context

    def update_context(self, mission_id: str, updates: Dict[str, Any]) -> Optional[MemoryContext]:
        context = self._store.get(mission_id)
        if not context:
            return None
        if self._is_expired(context):
            self.expire_context(mission_id)
            return None

        current_goal = updates.get("current_goal")
        if current_goal is not None:
            context.working_memory.current_goal = current_goal

        phase = updates.get("current_phase")
        if phase is not None:
            if isinstance(phase, MemoryPhase):
                context.working_memory.current_phase = phase
            elif isinstance(phase, str):
                context.working_memory.current_phase = MemoryPhase(phase)

        completed = updates.get("completed_steps")
        if completed is not None:
            existing = set(context.working_memory.completed_steps)
            for s in completed:
                if s not in existing:
                    context.working_memory.completed_steps.append(s)
                    existing.add(s)

        pending = updates.get("pending_steps")
        if pending is not None:
            existing = set(context.working_memory.pending_steps)
            for s in pending:
                if s not in existing:
                    context.working_memory.pending_steps.append(s)
                    existing.add(s)

        outputs = updates.get("task_outputs")
        if outputs is not None:
            context.working_memory.task_outputs.update(outputs)

        active = updates.get("active_context")
        if active is not None:
            context.working_memory.active_context.update(active)

        context.updated_at = datetime.now(timezone.utc).isoformat()
        self._store.put(context)
        return context

    def add_reasoning_step(
        self,
        mission_id: str,
        description: str,
        decision: str = "",
        alternatives: Optional[List[str]] = None,
        confidence: float = 1.0,
        critical: bool = False,
    ) -> Optional[MemoryContext]:
        context = self._store.get(mission_id)
        if not context:
            return None

        step = ReasoningStep(
            step_id=str(uuid4()),
            description=description,
            decision=decision,
            alternatives=alternatives or [],
            confidence=confidence,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
        context.reasoning_memory.reasoning_chain.append(step)
        if critical:
            context.reasoning_memory.critical_decisions.append(step.step_id)
        context.updated_at = datetime.now(timezone.utc).isoformat()
        self._store.put(context)
        return context

    def add_conversation_turn(
        self,
        mission_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[MemoryContext]:
        context = self._store.get(mission_id)
        if not context:
            return None

        turn = ConversationTurn(
            turn_id=str(uuid4()),
            role=role,
            content=content,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )
        context.conversation_memory.turns.append(turn)
        context.conversation_memory.turn_count += 1
        context.updated_at = datetime.now(timezone.utc).isoformat()
        self._store.put(context)
        return context

    def record_connector_output(
        self,
        mission_id: str,
        connector: str,
        operation: str,
        output: Any,
    ) -> Optional[MemoryContext]:
        context = self._store.get(mission_id)
        if not context:
            return None

        key = f"{connector}.{operation}"
        context.execution_memory.connector_outputs[key] = output
        context.execution_memory.execution_path.append(key)
        context.updated_at = datetime.now(timezone.utc).isoformat()
        self._store.put(context)
        return context

    def record_error(
        self,
        mission_id: str,
        source: str,
        error: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Optional[MemoryContext]:
        context = self._store.get(mission_id)
        if not context:
            return None

        context.execution_memory.error_history.append({
            "source": source,
            "error": error,
            "details": details or {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        context.updated_at = datetime.now(timezone.utc).isoformat()
        self._store.put(context)
        return context

    def add_artifact(
        self,
        mission_id: str,
        name: str,
        artifact_type: str,
        data: Any,
        source: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[MemoryArtifact]:
        context = self._store.get(mission_id)
        if not context:
            return None

        artifact = MemoryArtifact(
            artifact_id=str(uuid4()),
            name=name,
            artifact_type=artifact_type,
            data=data,
            source=source,
            created_at=datetime.now(timezone.utc).isoformat(),
            metadata=metadata or {},
        )
        context.execution_memory.artifacts.append(artifact)
        self._store.add_artifact(mission_id, artifact)
        context.updated_at = datetime.now(timezone.utc).isoformat()
        self._store.put(context)
        return artifact

    def snapshot(self, mission_id: str) -> Optional[MemorySnapshot]:
        context = self._store.get(mission_id)
        if not context:
            return None

        snapshot = self._compressor.create_checkpoint(deepcopy(context))
        self._store.put_snapshot(mission_id, snapshot)
        context.status = MemoryStatus.SNAPSHOTTED
        self._store.put(context)
        log.info("Created memory snapshot %s for mission %s", snapshot.snapshot_id, mission_id)
        return snapshot

    def restore(self, mission_id: str, snapshot_id: str) -> Optional[MemoryContext]:
        snapshot = self._store.get_snapshot(mission_id, snapshot_id)
        if not snapshot or not snapshot.context_copy:
            return None

        context = deepcopy(snapshot.context_copy)
        context.status = MemoryStatus.ACTIVE
        context.updated_at = datetime.now(timezone.utc).isoformat()
        self._store.put(context)
        log.info("Restored memory snapshot %s for mission %s", snapshot_id, mission_id)
        return context

    def list_snapshots(self, mission_id: str) -> List[MemorySnapshot]:
        return self._store.get_snapshots(mission_id)

    def compress(self, mission_id: str) -> Optional[MemoryContext]:
        context = self._store.get(mission_id)
        if not context:
            return None

        compressed = self._compressor.compress(deepcopy(context))
        self._store.put(compressed)
        log.info("Compressed memory for mission %s", mission_id)
        return compressed

    def expire_context(self, mission_id: str) -> bool:
        context = self._store.get(mission_id)
        if not context:
            return False
        context.status = MemoryStatus.EXPIRED
        context.updated_at = datetime.now(timezone.utc).isoformat()
        self._store.put(context)
        log.info("Expired memory context for mission %s", mission_id)
        return True

    def archive_context(self, mission_id: str) -> bool:
        context = self._store.get(mission_id)
        if not context:
            return False
        self.snapshot(mission_id)
        context.status = MemoryStatus.ARCHIVED
        context.updated_at = datetime.now(timezone.utc).isoformat()
        self._store.put(context)
        log.info("Archived memory context for mission %s", mission_id)
        return True

    def delete_context(self, mission_id: str) -> bool:
        removed = self._store.delete(mission_id)
        self._store.delete_snapshots(mission_id)
        self._store.delete_artifacts(mission_id)
        if removed:
            log.info("Deleted memory context for mission %s", mission_id)
        return removed

    def find_by_user(self, user_id: str) -> List[MemoryContext]:
        return self._store.find_by_user(user_id)

    def find_by_tenant(self, tenant_id: str) -> List[MemoryContext]:
        return self._store.find_by_tenant(tenant_id)

    def find_by_trace(self, trace_id: str) -> List[MemoryContext]:
        return self._store.find_by_trace(trace_id)

    def find_by_correlation(self, correlation_id: str) -> List[MemoryContext]:
        return self._store.find_by_correlation(correlation_id)

    def list_active(self) -> List[MemoryContext]:
        return [c for c in self._store.list_all() if c.status == MemoryStatus.ACTIVE]

    def count(self) -> int:
        return self._store.count()

    def clear_all(self) -> None:
        self._store.clear()

    def _is_expired(self, context: MemoryContext) -> bool:
        if not context.expires_at:
            return False
        try:
            expiry = datetime.fromisoformat(context.expires_at)
            return datetime.now(timezone.utc) > expiry
        except Exception:
            return False


memory_manager = MemoryManager()
