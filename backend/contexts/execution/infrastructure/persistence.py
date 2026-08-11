"""Mapping between the Execution aggregate and a storable record.

Storage-agnostic: a plain mapping of primitives.

Every invariant is re-checked on the way in, including the ones about leases and
completion. A stored run edited to claim completion with an outstanding node
refuses to load rather than loading and reporting success for work that never
happened.

The outcome digest is **restored, not recomputed**. Recomputing would make it
always match -- a check that cannot fail -- and this is the record of what
actually happened to production, so that check is the one that matters most in
the whole codebase.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionResult, ExecutionStatus, SideEffectClass
from backend.contexts.execution.domain.checkpoint import ExecutionCheckpoint
from backend.contexts.execution.domain.execution import Execution
from backend.contexts.execution.domain.failure import FailureRecord
from backend.contexts.execution.domain.identifiers import (
    AttemptId,
    CheckpointId,
    ExecutionId,
    LeaseId,
)
from backend.contexts.execution.domain.lease import (
    ExecutionAttempt,
    ExecutionLease,
    NodeRun,
    NodeSpec,
)
from backend.contexts.execution.domain.state import ExecutionState, NodeState
from backend.contexts.execution.domain.worker import WorkerKind

__all__ = ["RECORD_SCHEMA_VERSION", "to_record", "from_record"]

RECORD_SCHEMA_VERSION = 2


def _optional_time(value):
    return datetime.fromisoformat(value) if value else None


def _result_to(result):
    if result is None:
        return None
    return {
        "execution_key": result.execution_key,
        "status": result.status.value,
        "started_at": result.started_at.isoformat(),
        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
        "failure_reason": result.failure_reason,
        "detail": dict(result.detail) if result.detail else {},
    }


def _result_from(data):
    if not data:
        return None
    return ExecutionResult(
        execution_key=data["execution_key"],
        status=ExecutionStatus(data["status"]),
        started_at=datetime.fromisoformat(data["started_at"]),
        completed_at=_optional_time(data.get("completed_at")),
        failure_reason=data.get("failure_reason"),
        detail=data.get("detail", {}),
    )


def to_record(execution: Execution, *, tenant_id: str) -> dict[str, Any]:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ContractViolation(
            "tenant_id must be non-blank; it is derived from the context"
        )

    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "execution_id": str(execution.execution_id),
        "workflow_id": execution.workflow_id,
        "workflow_digest": execution.workflow_digest,
        "mission_id": execution.mission_id,
        "attempt": execution.attempt,
        "state": execution.state.value,
        "outcome_note": execution.outcome_note,
        "digest": execution.digest,
        "resumed_from": execution.resumed_from,
        "requested_by": execution.requested_by,
        "created_at": execution.created_at.isoformat(),
        "started_at": execution.started_at.isoformat() if execution.started_at else None,
        "ended_at": execution.ended_at.isoformat() if execution.ended_at else None,
        "runs": [
            {
                "spec": {
                    "node_id": r.spec.node_id,
                    "worker_kind": r.spec.worker_kind.value,
                    "depends_on": list(r.spec.depends_on),
                    "side_effect": r.spec.side_effect.value,
                    "max_attempts": r.spec.max_attempts,
                    "timeout_seconds": r.spec.timeout_seconds,
                    "idempotency_key": r.spec.idempotency_key,
                    "compensates": r.spec.compensates,
                    "cancellable": r.spec.cancellable,
                    "execution_key": r.spec.execution_key,
                    # ``dict`` because the in-memory form is a read-only proxy,
                    # which is not JSON-serialisable.
                    "input": dict(r.spec.input),
                },
                "state": r.state.value,
                "skipped_reason": r.skipped_reason,
                "lease": (
                    {
                        "lease_id": str(r.lease.lease_id),
                        "node_id": r.lease.node_id,
                        "worker_id": r.lease.worker_id,
                        "granted_at": r.lease.granted_at.isoformat(),
                        "expires_at": r.lease.expires_at.isoformat(),
                        "released_at": (
                            r.lease.released_at.isoformat() if r.lease.released_at else None
                        ),
                        "heartbeat_at": (
                            r.lease.heartbeat_at.isoformat()
                            if r.lease.heartbeat_at
                            else None
                        ),
                    }
                    if r.lease
                    else None
                ),
                "attempts": [
                    {
                        "attempt_id": str(a.attempt_id),
                        "node_id": a.node_id,
                        "number": a.number,
                        "worker_id": a.worker_id,
                        "lease_id": a.lease_id,
                        "started_at": a.started_at.isoformat(),
                        "outcome": a.outcome.value,
                        "ended_at": a.ended_at.isoformat() if a.ended_at else None,
                        "result": _result_to(a.result),
                        "failure_reason": a.failure_reason,
                        "failure": a.failure.to_dict() if a.failure else None,
                        "retry_decision": dict(a.retry_decision) if a.retry_decision else None,
                    }
                    for a in r.attempts
                ],
            }
            for r in execution.runs
        ],
        "checkpoints": [
            {
                "checkpoint_id": str(c.checkpoint_id),
                "sequence": c.sequence,
                "label": c.label,
                "finished_nodes": sorted(c.finished_nodes),
                "resume_from": list(c.resume_from),
                "payload_ref": c.payload_ref,
                "recorded_by": c.recorded_by,
                "recorded_at": c.recorded_at.isoformat(),
                "digest": c.digest,
            }
            for c in execution.checkpoints
        ],
    }


def from_record(data: Mapping[str, Any]) -> Execution:
    schema = data.get("schema_version")
    if schema != RECORD_SCHEMA_VERSION:
        raise ContractViolation(
            f"record schema version {schema!r} is not {RECORD_SCHEMA_VERSION}; refusing "
            "to guess at a shape this build does not know"
        )

    return Execution(
        execution_id=ExecutionId(data["execution_id"]),
        workflow_id=data["workflow_id"],
        workflow_digest=data["workflow_digest"],
        mission_id=data["mission_id"],
        attempt=data["attempt"],
        state=ExecutionState(data["state"]),
        outcome_note=data.get("outcome_note"),
        digest=data.get("digest"),
        resumed_from=data.get("resumed_from"),
        requested_by=data["requested_by"],
        created_at=datetime.fromisoformat(data["created_at"]),
        started_at=_optional_time(data.get("started_at")),
        ended_at=_optional_time(data.get("ended_at")),
        runs=tuple(
            NodeRun(
                spec=NodeSpec(
                    node_id=r["spec"]["node_id"],
                    worker_kind=WorkerKind(r["spec"]["worker_kind"]),
                    depends_on=tuple(r["spec"]["depends_on"]),
                    side_effect=SideEffectClass(r["spec"]["side_effect"]),
                    max_attempts=r["spec"]["max_attempts"],
                    timeout_seconds=r["spec"].get("timeout_seconds"),
                    idempotency_key=r["spec"].get("idempotency_key"),
                    compensates=r["spec"].get("compensates"),
                    cancellable=r["spec"]["cancellable"],
                    execution_key=r["spec"].get("execution_key"),
                    # ``get`` with a default: an execution stored before this
                    # field existed has no key, and restores with an empty
                    # input -- which is what it actually had.
                    input=r["spec"].get("input") or {},
                ),
                state=NodeState(r["state"]),
                skipped_reason=r.get("skipped_reason"),
                lease=(
                    ExecutionLease(
                        lease_id=LeaseId(r["lease"]["lease_id"]),
                        node_id=r["lease"]["node_id"],
                        worker_id=r["lease"]["worker_id"],
                        granted_at=datetime.fromisoformat(r["lease"]["granted_at"]),
                        expires_at=datetime.fromisoformat(r["lease"]["expires_at"]),
                        released_at=_optional_time(r["lease"].get("released_at")),
                        heartbeat_at=_optional_time(r["lease"].get("heartbeat_at")),
                    )
                    if r.get("lease")
                    else None
                ),
                attempts=tuple(
                    ExecutionAttempt(
                        attempt_id=AttemptId(a["attempt_id"]),
                        node_id=a["node_id"],
                        number=a["number"],
                        worker_id=a["worker_id"],
                        lease_id=a["lease_id"],
                        started_at=datetime.fromisoformat(a["started_at"]),
                        outcome=NodeState(a["outcome"]),
                        ended_at=_optional_time(a.get("ended_at")),
                        result=_result_from(a.get("result")),
                        failure_reason=a.get("failure_reason"),
                        failure=(
                            FailureRecord.from_dict(a["failure"])
                            if a.get("failure")
                            else None
                        ),
                        retry_decision=a.get("retry_decision"),
                    )
                    for a in r["attempts"]
                ),
            )
            for r in data["runs"]
        ),
        checkpoints=tuple(
            ExecutionCheckpoint(
                checkpoint_id=CheckpointId(c["checkpoint_id"]),
                sequence=c["sequence"],
                label=c["label"],
                finished_nodes=frozenset(c["finished_nodes"]),
                resume_from=tuple(c["resume_from"]),
                payload_ref=c.get("payload_ref"),
                recorded_by=c["recorded_by"],
                recorded_at=datetime.fromisoformat(c["recorded_at"]),
                digest=c.get("digest"),
            )
            for c in data["checkpoints"]
        ),
    )
