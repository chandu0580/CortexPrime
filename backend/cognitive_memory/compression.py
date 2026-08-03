from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import uuid4

from backend.cognitive_memory.models import (
    MemoryContext,
    MemorySnapshot,
    MemoryStatus,
    ReasoningStep,
)

log = logging.getLogger(__name__)


class MemoryCompressor:
    def compress(self, context: MemoryContext) -> MemoryContext:
        original_step_count = len(context.reasoning_memory.reasoning_chain)
        original_output_count = len(context.working_memory.task_outputs)

        context = self._deduplicate_reasoning(context)
        context = self._preserve_critical_decisions(context)
        context = self._summarize_task_outputs(context)
        context = self._truncate_conversation(context)
        context.status = MemoryStatus.COMPRESSED

        log.info(
            "Compressed memory for %s: %d reasoning steps → %d, %d outputs before → %d after",
            context.mission_id,
            original_step_count,
            len(context.reasoning_memory.reasoning_chain),
            original_output_count,
            len(context.working_memory.task_outputs),
        )
        return context

    def create_checkpoint(self, context: MemoryContext) -> MemorySnapshot:
        compression_meta: Dict[str, Any] = {
            "reasoning_count": len(context.reasoning_memory.reasoning_chain),
            "decision_count": len(context.reasoning_memory.decisions),
            "completed_steps": list(context.working_memory.completed_steps),
            "pending_steps": list(context.working_memory.pending_steps),
            "phase": context.working_memory.current_phase.value,
        }
        now = datetime.now(timezone.utc).isoformat()
        snapshot = MemorySnapshot(
            snapshot_id=str(uuid4()),
            mission_id=context.mission_id,
            context_copy=context,
            captured_at=now,
            compression_metadata=compression_meta,
            step_count=len(context.working_memory.completed_steps) + len(context.working_memory.pending_steps),
            artifact_count=len(context.execution_memory.artifacts),
            size_estimate_bytes=self._estimate_size(context),
        )
        return snapshot

    def _deduplicate_reasoning(self, context: MemoryContext) -> MemoryContext:
        seen: set = set()
        unique: List[ReasoningStep] = []
        for step in context.reasoning_memory.reasoning_chain:
            key = (step.description[:50], step.decision[:50])
            if key not in seen:
                seen.add(key)
                unique.append(step)
        context.reasoning_memory.reasoning_chain = unique
        return context

    def _preserve_critical_decisions(self, context: MemoryContext) -> MemoryContext:
        critical_ids = set(context.reasoning_memory.critical_decisions)
        if critical_ids:
            preserved = [
                d for d in context.reasoning_memory.decisions
                if d.get("decision_id") in critical_ids
            ]
            context.reasoning_memory.decisions = preserved
        return context

    def _summarize_task_outputs(self, context: MemoryContext) -> MemoryContext:
        if len(context.working_memory.task_outputs) <= 5:
            return context
        keys = list(context.working_memory.task_outputs.keys())
        to_remove = keys[:-5]
        for key in to_remove:
            task_id = key.replace("task_", "").replace("step_", "")
            context.working_memory.completed_steps.append(f"summarized:{task_id}")
            del context.working_memory.task_outputs[key]
        return context

    def _truncate_conversation(self, context: MemoryContext) -> MemoryContext:
        max_turns = 20
        if context.conversation_memory.turn_count > max_turns:
            context.conversation_memory.turns = context.conversation_memory.turns[-max_turns:]
            context.conversation_memory.turn_count = len(context.conversation_memory.turns)
        return context

    def _estimate_size(self, context: MemoryContext) -> int:
        try:
            import json
            raw = json.dumps({
                "wm": len(str(context.working_memory)),
                "mm": len(str(context.mission_memory)),
                "rm": len(str(context.reasoning_memory)),
                "cm": len(str(context.conversation_memory)),
                "em": len(str(context.execution_memory)),
            })
            return len(raw.encode("utf-8"))
        except Exception:
            return 0


memory_compressor = MemoryCompressor()
