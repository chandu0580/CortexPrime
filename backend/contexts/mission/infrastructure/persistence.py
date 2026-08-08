"""Mapping between the Mission aggregate and a storable record.

Storage-agnostic: a plain mapping of primitives.

Every invariant is re-checked on the way in, and the archival digest is
**restored, not recomputed**. Recomputing would make it always match -- a check
that cannot fail -- and for the one artifact that seals a mission's whole history
that check is the entire point.

The timeline round-trips entry for entry, sequence for sequence. That is what
makes replay meaningful after a restart rather than only inside one process.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from backend.contracts.errors import ContractViolation
from backend.contracts.identity import SecurityContext
from backend.contracts.mission import MissionIntent, MissionState
from backend.contexts.mission.domain.checkpoint import MissionCheckpoint
from backend.contexts.mission.domain.execution import ExecutionOutcome, MissionExecution
from backend.contexts.mission.domain.identifiers import (
    CheckpointId,
    ExecutionId,
    MissionId,
)
from backend.contexts.mission.domain.metadata import (
    MissionKind,
    MissionMetadata,
    MissionPriority,
    PlanRef,
    Precondition,
)
from backend.contexts.mission.domain.mission import Mission
from backend.contexts.mission.domain.status import MissionStatus
from backend.contexts.mission.domain.timeline import (
    MissionTimeline,
    MissionTimelineEntry,
    TimelineEntryKind,
)

__all__ = ["RECORD_SCHEMA_VERSION", "to_record", "from_record"]

RECORD_SCHEMA_VERSION = 1


def _optional_time(value):
    return datetime.fromisoformat(value) if value else None


def to_record(mission: Mission, *, tenant_id: str) -> dict[str, Any]:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ContractViolation(
            "tenant_id must be non-blank; it is derived from the context"
        )

    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "mission_id": str(mission.mission_id),
        "intent": {
            "stated_goal": mission.intent.stated_goal,
            "requested_by": mission.intent.requested_by.to_dict(),
            "requested_at": mission.intent.requested_at.isoformat(),
        },
        "metadata": {
            "title": mission.metadata.title,
            "kind": mission.metadata.kind.value,
            "priority": mission.metadata.priority.value,
            "target": mission.metadata.target,
            "tags": sorted(mission.metadata.tags),
            "labels": list(mission.metadata.labels),
        },
        "status": mission.status.value,
        "execution_state": mission.execution_state.value,
        "plan_ref": (
            {
                "plan_id": mission.plan_ref.plan_id,
                "produced_by": mission.plan_ref.produced_by,
                "revision": mission.plan_ref.revision,
            }
            if mission.plan_ref
            else None
        ),
        "preconditions": [
            {
                "key": p.key,
                "description": p.description,
                "satisfied": p.satisfied,
                "satisfied_by": p.satisfied_by,
                "satisfied_at": p.satisfied_at.isoformat() if p.satisfied_at else None,
                "note": p.note,
            }
            for p in mission.preconditions
        ],
        "timeline": [
            {
                "sequence": e.sequence,
                "kind": e.kind.value,
                "reason": e.reason,
                "occurred_at": e.occurred_at.isoformat(),
                "actor": e.actor,
                "from_status": e.from_status.value if e.from_status else None,
                "to_status": e.to_status.value if e.to_status else None,
                "from_execution_state": (
                    e.from_execution_state.value if e.from_execution_state else None
                ),
                "to_execution_state": (
                    e.to_execution_state.value if e.to_execution_state else None
                ),
                "checkpoint_id": e.checkpoint_id,
                "detail": e.detail,
            }
            for e in mission.timeline
        ],
        "checkpoints": [
            {
                "checkpoint_id": str(c.checkpoint_id),
                "sequence": c.sequence,
                "label": c.label,
                "execution_state": c.execution_state.value,
                "execution_id": c.execution_id,
                "payload_ref": c.payload_ref,
                "payload_digest": c.payload_digest,
                "recorded_by": c.recorded_by,
                "recorded_at": c.recorded_at.isoformat(),
                "digest": c.digest,
            }
            for c in mission.checkpoints
        ],
        "executions": [
            {
                "execution_id": str(e.execution_id),
                "mission_id": e.mission_id,
                "attempt": e.attempt,
                "state": e.state.value,
                "outcome": e.outcome.value,
                "started_at": e.started_at.isoformat(),
                "ended_at": e.ended_at.isoformat() if e.ended_at else None,
                "resumed_from_checkpoint": e.resumed_from_checkpoint,
                "executor_ref": e.executor_ref,
                "closing_note": e.closing_note,
            }
            for e in mission.executions
        ],
        "outcome_note": mission.outcome_note,
        "digest": mission.digest,
        "created_at": mission.created_at.isoformat(),
        "archived_at": mission.archived_at.isoformat() if mission.archived_at else None,
    }


def from_record(data: Mapping[str, Any]) -> Mission:
    schema = data.get("schema_version")
    if schema != RECORD_SCHEMA_VERSION:
        raise ContractViolation(
            f"record schema version {schema!r} is not {RECORD_SCHEMA_VERSION}; refusing "
            "to guess at a shape this build does not know"
        )

    intent = data["intent"]
    metadata = data["metadata"]
    plan = data.get("plan_ref")

    return Mission(
        mission_id=MissionId(data["mission_id"]),
        intent=MissionIntent(
            stated_goal=intent["stated_goal"],
            requested_by=SecurityContext.from_dict(intent["requested_by"]),
            requested_at=datetime.fromisoformat(intent["requested_at"]),
        ),
        metadata=MissionMetadata(
            title=metadata["title"],
            kind=MissionKind(metadata["kind"]),
            priority=MissionPriority(metadata["priority"]),
            target=metadata.get("target"),
            tags=frozenset(metadata["tags"]),
            labels=tuple(metadata.get("labels", ())),
        ),
        status=MissionStatus(data["status"]),
        execution_state=MissionState(data["execution_state"]),
        plan_ref=(
            PlanRef(
                plan_id=plan["plan_id"],
                produced_by=plan["produced_by"],
                revision=plan.get("revision"),
            )
            if plan
            else None
        ),
        preconditions=tuple(
            Precondition(
                key=p["key"],
                description=p.get("description", ""),
                satisfied=p["satisfied"],
                satisfied_by=p.get("satisfied_by"),
                satisfied_at=_optional_time(p.get("satisfied_at")),
                note=p.get("note"),
            )
            for p in data["preconditions"]
        ),
        timeline=MissionTimeline(
            entries=tuple(
                MissionTimelineEntry(
                    sequence=e["sequence"],
                    kind=TimelineEntryKind(e["kind"]),
                    reason=e["reason"],
                    occurred_at=datetime.fromisoformat(e["occurred_at"]),
                    actor=e["actor"],
                    from_status=(
                        MissionStatus(e["from_status"]) if e.get("from_status") else None
                    ),
                    to_status=MissionStatus(e["to_status"]) if e.get("to_status") else None,
                    from_execution_state=(
                        MissionState(e["from_execution_state"])
                        if e.get("from_execution_state")
                        else None
                    ),
                    to_execution_state=(
                        MissionState(e["to_execution_state"])
                        if e.get("to_execution_state")
                        else None
                    ),
                    checkpoint_id=e.get("checkpoint_id"),
                    detail=e.get("detail"),
                )
                for e in data["timeline"]
            )
        ),
        checkpoints=tuple(
            MissionCheckpoint(
                checkpoint_id=CheckpointId(c["checkpoint_id"]),
                sequence=c["sequence"],
                label=c["label"],
                execution_state=MissionState(c["execution_state"]),
                execution_id=c["execution_id"],
                payload_ref=c.get("payload_ref"),
                payload_digest=c.get("payload_digest"),
                recorded_by=c["recorded_by"],
                recorded_at=datetime.fromisoformat(c["recorded_at"]),
                digest=c.get("digest"),
            )
            for c in data["checkpoints"]
        ),
        executions=tuple(
            MissionExecution(
                execution_id=ExecutionId(e["execution_id"]),
                mission_id=e["mission_id"],
                attempt=e["attempt"],
                state=MissionState(e["state"]),
                outcome=ExecutionOutcome(e["outcome"]),
                started_at=datetime.fromisoformat(e["started_at"]),
                ended_at=_optional_time(e.get("ended_at")),
                resumed_from_checkpoint=e.get("resumed_from_checkpoint"),
                executor_ref=e.get("executor_ref"),
                closing_note=e.get("closing_note"),
            )
            for e in data["executions"]
        ),
        outcome_note=data.get("outcome_note"),
        digest=data.get("digest"),
        created_at=datetime.fromisoformat(data["created_at"]),
        archived_at=_optional_time(data.get("archived_at")),
    )
