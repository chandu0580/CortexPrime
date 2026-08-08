"""Construction helpers for the Execution Runtime."""

from __future__ import annotations

from typing import Optional, Sequence

from backend.contracts.execution import SideEffectClass
from backend.contexts.execution.domain.execution import Execution
from backend.contexts.execution.domain.lease import NodeSpec
from backend.contexts.execution.domain.worker import WorkerKind, WorkerRegistration

__all__ = ["start_run", "node_spec", "worker"]


def start_run(
    *,
    workflow_id: str,
    workflow_digest: str,
    mission_id: str,
    nodes: Sequence[NodeSpec],
    attempt: int = 1,
    requested_by: str = "mission-runtime",
) -> Execution:
    """A pending run over the projection of a compiled workflow.

    ``workflow_digest`` has no default. A run that could be opened without
    naming the exact graph it executes would be a run of whatever somebody later
    decided it was running.
    """
    return Execution.of(
        workflow_id=workflow_id,
        workflow_digest=workflow_digest,
        mission_id=mission_id,
        nodes=nodes,
        attempt=attempt,
        requested_by=requested_by,
    )


def node_spec(
    node_id: str,
    worker_kind: WorkerKind,
    *,
    depends_on: Sequence[str] = (),
    side_effect: SideEffectClass = SideEffectClass.READ,
    max_attempts: int = 1,
    timeout_seconds: Optional[int] = None,
    idempotency_key: Optional[str] = None,
    compensates: Optional[str] = None,
    cancellable: bool = True,
    execution_key: Optional[str] = None,
) -> NodeSpec:
    """One node of the compiled graph, as the runtime needs it.

    ``side_effect`` defaults to READ, the only safe default: a node that mutates
    without saying so would slip past the idempotency rule that guards retries.
    """
    return NodeSpec(
        node_id=node_id,
        worker_kind=worker_kind,
        depends_on=tuple(depends_on),
        side_effect=side_effect,
        max_attempts=max_attempts,
        timeout_seconds=timeout_seconds,
        idempotency_key=idempotency_key,
        compensates=compensates,
        cancellable=cancellable,
        execution_key=execution_key,
    )


def worker(
    worker_id: str,
    kinds: Sequence[WorkerKind],
    *,
    max_concurrent: int = 1,
    lease_seconds: int = 300,
    labels: Sequence[str] = (),
) -> WorkerRegistration:
    return WorkerRegistration.create(
        worker_id,
        kinds,
        max_concurrent=max_concurrent,
        lease_seconds=lease_seconds,
        labels=labels,
    )
