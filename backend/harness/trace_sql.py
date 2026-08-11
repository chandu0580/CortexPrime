"""The durable trace recorder — ``cp_harness_trace`` over the durable store.

Append-only by interface: this class exposes ``record`` and reads, nothing
else. There is no update statement in this module, and the migration created
no state a mutation would maintain. A failed insert raises — a span the
recorder could not persist is a failure the caller must see (Part J item 9),
not a silent gap in the evidence.
"""

from __future__ import annotations

from typing import Any, Optional

import sqlalchemy as sa

from backend.database.durable.session import DurableStore
from backend.database.durable.tables import harness_trace_table
from backend.harness.trace import HarnessSpan

__all__ = ["SqlTraceRecorder", "TraceWriteFailed"]


class TraceWriteFailed(RuntimeError):
    """A harness span could not be persisted. Loud on purpose."""


class SqlTraceRecorder:
    """Persist spans into ``cp_harness_trace`` (migration 0014)."""

    __slots__ = ("_store",)

    def __init__(self, store: DurableStore) -> None:
        if not isinstance(store, DurableStore):
            raise TraceWriteFailed("SqlTraceRecorder requires a DurableStore")
        self._store = store

    def record(self, span: HarnessSpan) -> None:
        try:
            with self._store.atomic() as work:
                work.execute(
                    sa.insert(harness_trace_table).values(
                        span_record_id=span.span_record_id,
                        kind=span.kind,
                        mission_id=span.mission_id,
                        iteration=span.iteration,
                        step_id=span.step_id,
                        harness_version=span.harness_version,
                        correlation_id=span.correlation_id,
                        trace_id=span.trace_id,
                        trace_span_id=span.trace_span_id,
                        started_at=span.started_at,
                        finished_at=span.finished_at,
                        record=span.as_record(),
                        recorded_at=work.now,
                    )
                )
        except TraceWriteFailed:
            raise
        except Exception as exc:
            raise TraceWriteFailed(
                f"harness span {span.span_record_id} was not persisted: "
                f"{type(exc).__name__}"
            ) from exc

    # Reads — for recovery hooks and the verification report, not a query API.

    def spans_for_mission(self, mission_id: str) -> tuple[dict[str, Any], ...]:
        with self._store.atomic() as work:
            rows = work.execute(
                sa.select(harness_trace_table.c.record)
                .where(harness_trace_table.c.mission_id == mission_id)
                .order_by(harness_trace_table.c.span_record_id)
            ).fetchall()
        return tuple(row[0] for row in rows)

    def last_loop_state(self, mission_id: str) -> Optional[dict[str, Any]]:
        """The recovery hook: where did this mission's loop last stand?"""
        with self._store.atomic() as work:
            row = work.execute(
                sa.select(harness_trace_table.c.record)
                .where(
                    harness_trace_table.c.mission_id == mission_id,
                    harness_trace_table.c.kind == "loop_state",
                )
                .order_by(harness_trace_table.c.span_record_id.desc())
                .limit(1)
            ).fetchone()
        return row[0] if row else None
