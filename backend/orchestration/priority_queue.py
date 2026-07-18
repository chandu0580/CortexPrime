from __future__ import annotations

import asyncio
import heapq
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


# =========================================================
# PRIORITY TASK
# =========================================================

@dataclass(order=True)
class PriorityTask:
    """
    A task entry in the priority queue.
    Lower priority value = higher priority (1 is highest).
    Tie-breaking by sequence_number ensures FIFO within same priority.
    """
    priority:        int
    sequence_number: int
    task_id:         str       = field(compare=False)
    execution_id:    str       = field(compare=False)
    agent:           str       = field(compare=False)
    task_data:       Dict[str, Any] = field(compare=False, default_factory=dict)
    created_at:      str       = field(
        compare=False,
        default_factory=lambda: datetime.utcnow().isoformat(),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id":      self.task_id,
            "execution_id": self.execution_id,
            "agent":        self.agent,
            "priority":     self.priority,
            "created_at":   self.created_at,
        }


# =========================================================
# EXECUTION PRIORITY QUEUE
# =========================================================

class ExecutionPriorityQueue:
    """
    A min-heap priority queue for agent task dispatch.

    Priority 1 = critical (governance, safety)
    Priority 3 = high     (orchestrator, planner)
    Priority 5 = normal   (research, critic, optimizer)
    Priority 7 = low      (memory, reflection)
    Priority 9 = idle     (background maintenance)
    """

    def __init__(self):
        self._heap:     List[PriorityTask] = []
        self._counter:  int = 0
        self._lock:     asyncio.Lock = asyncio.Lock()
        self._not_empty: asyncio.Event = asyncio.Event()

    # ---------------------------------------------------------
    # PUSH
    # ---------------------------------------------------------

    async def push(
        self,
        task_id:      str,
        execution_id: str,
        agent:        str,
        task_data:    Dict[str, Any],
        priority:     int = 5,
    ) -> None:
        async with self._lock:
            entry = PriorityTask(
                priority=priority,
                sequence_number=self._counter,
                task_id=task_id,
                execution_id=execution_id,
                agent=agent,
                task_data=task_data,
            )
            heapq.heappush(self._heap, entry)
            self._counter += 1
            self._not_empty.set()

        log.debug(
            "Queued task: agent=%s priority=%d exec=%s",
            agent, priority, execution_id,
        )

    # ---------------------------------------------------------
    # POP (blocking)
    # ---------------------------------------------------------

    async def pop(self, timeout: Optional[float] = None) -> Optional[PriorityTask]:
        """Pop the highest-priority task. Returns None on timeout."""
        try:
            await asyncio.wait_for(
                self._not_empty.wait(),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            return None

        async with self._lock:
            if not self._heap:
                self._not_empty.clear()
                return None

            task = heapq.heappop(self._heap)
            if not self._heap:
                self._not_empty.clear()

            return task

    # ---------------------------------------------------------
    # PEEK
    # ---------------------------------------------------------

    async def peek(self) -> Optional[PriorityTask]:
        async with self._lock:
            if self._heap:
                return self._heap[0]
            return None

    # ---------------------------------------------------------
    # SIZE
    # ---------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self._heap)

    # ---------------------------------------------------------
    # SNAPSHOT
    # ---------------------------------------------------------

    async def snapshot(self) -> List[Dict[str, Any]]:
        async with self._lock:
            return [t.to_dict() for t in sorted(self._heap)]


# =========================================================
# SINGLETON
# =========================================================

execution_priority_queue = ExecutionPriorityQueue()
