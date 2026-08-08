"""Mapping between the Workflow aggregate and a storable record.

Storage-agnostic: a plain mapping of primitives.

Every invariant is re-checked on the way in -- including the whole graph, which
``Workflow.__post_init__`` rebuilds. So a stored workflow whose edges were edited
into a cycle refuses to load rather than loading and stalling an executor later.

The compilation digest is **restored, not recomputed**. Recomputing would make it
always match -- a check that cannot fail -- and this is the artifact execution
runs, so that check is how anyone knows the graph on file is the one compiled.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import SideEffectClass
from backend.contexts.workflow.domain.identifiers import GroupId, WorkflowId
from backend.contexts.workflow.domain.nodes import (
    BackoffKind,
    BranchArm,
    ConditionKind,
    EdgeKind,
    NodeKind,
    WorkflowCondition,
    WorkflowEdge,
    WorkflowNode,
    WorkflowRetryPolicy,
    WorkflowTimeout,
)
from backend.contexts.workflow.domain.parallel import (
    JoinPolicy,
    ResumePoint,
    WorkflowCompensation,
    WorkflowParallelGroup,
)
from backend.contexts.workflow.domain.status import WorkflowStatus
from backend.contexts.workflow.domain.workflow import Workflow

__all__ = ["RECORD_SCHEMA_VERSION", "to_record", "from_record"]

RECORD_SCHEMA_VERSION = 1


def _optional_time(value):
    return datetime.fromisoformat(value) if value else None


def _condition_to(condition: WorkflowCondition) -> dict:
    return {
        "kind": condition.kind.value,
        "source_node": condition.source_node,
        "expression": condition.expression,
        "description": condition.description,
    }


def _condition_from(data: Mapping[str, Any]) -> WorkflowCondition:
    return WorkflowCondition(
        kind=ConditionKind(data["kind"]),
        source_node=data.get("source_node"),
        expression=data.get("expression"),
        description=data.get("description", ""),
    )


def _timeout_to(value):
    if value is None:
        return None
    return {
        "seconds": value.seconds,
        "on_timeout": value.on_timeout,
        "grace_seconds": value.grace_seconds,
    }


def _timeout_from(data):
    if not data:
        return None
    return WorkflowTimeout(
        seconds=data["seconds"],
        on_timeout=data["on_timeout"],
        grace_seconds=data.get("grace_seconds", 0),
    )


def to_record(workflow: Workflow, *, tenant_id: str) -> dict[str, Any]:
    if not isinstance(tenant_id, str) or not tenant_id.strip():
        raise ContractViolation(
            "tenant_id must be non-blank; it is derived from the context"
        )

    return {
        "schema_version": RECORD_SCHEMA_VERSION,
        "tenant_id": tenant_id,
        "workflow_id": str(workflow.workflow_id),
        "plan_id": workflow.plan_id,
        "plan_digest": workflow.plan_digest,
        "mission_id": workflow.mission_id,
        "title": workflow.title,
        "plan_task_ids": sorted(workflow.plan_task_ids),
        "version": workflow.version,
        "nodes": [
            {
                "node_id": n.node_id,
                "kind": n.kind.value,
                "purpose": n.purpose,
                "plan_task_id": n.plan_task_id,
                "side_effect": n.side_effect.value,
                "retry": {
                    "max_attempts": n.retry.max_attempts,
                    "backoff": n.retry.backoff.value,
                    "initial_delay_seconds": n.retry.initial_delay_seconds,
                    "max_delay_seconds": n.retry.max_delay_seconds,
                    "idempotency_key": n.retry.idempotency_key,
                    "retry_on": list(n.retry.retry_on),
                },
                "timeout": _timeout_to(n.timeout),
                "compensates": n.compensates,
                "arms": [
                    {
                        "to_node": a.to_node,
                        "condition": _condition_to(a.condition),
                        "label": a.label,
                    }
                    for a in n.arms
                ],
                "group_id": n.group_id,
                "cancellable": n.cancellable,
                "execution_key": n.execution_key,
            }
            for n in workflow.nodes
        ],
        "edges": [
            {
                "from_node": e.from_node,
                "to_node": e.to_node,
                "kind": e.kind.value,
                "condition": _condition_to(e.condition),
                "label": e.label,
            }
            for e in workflow.edges
        ],
        "parallel_groups": [
            {
                "group_id": str(g.group_id),
                "label": g.label,
                "members": list(g.members),
                "join": g.join.value,
                "quorum": g.quorum,
                "max_concurrency": g.max_concurrency,
            }
            for g in workflow.parallel_groups
        ],
        "compensations": [
            {
                "compensates": c.compensates,
                "performed_by": c.performed_by,
                "trigger": c.trigger,
                "order": c.order,
            }
            for c in workflow.compensations
        ],
        "resume_points": [
            {"node_id": p.node_id, "label": p.label} for p in workflow.resume_points
        ],
        "workflow_timeout": _timeout_to(workflow.workflow_timeout),
        "status": workflow.status.value,
        "validated_at": workflow.validated_at.isoformat() if workflow.validated_at else None,
        "compiled_at": workflow.compiled_at.isoformat() if workflow.compiled_at else None,
        "approved_at": workflow.approved_at.isoformat() if workflow.approved_at else None,
        "approved_by": workflow.approved_by,
        "digest": workflow.digest,
        "execution_order": list(workflow.execution_order),
        "compensation_order": list(workflow.compensation_order),
        "supersedes": str(workflow.supersedes) if workflow.supersedes else None,
        "superseded_by": str(workflow.superseded_by) if workflow.superseded_by else None,
        "compiled_by": workflow.compiled_by,
        "created_at": workflow.created_at.isoformat(),
    }


def from_record(data: Mapping[str, Any]) -> Workflow:
    schema = data.get("schema_version")
    if schema != RECORD_SCHEMA_VERSION:
        raise ContractViolation(
            f"record schema version {schema!r} is not {RECORD_SCHEMA_VERSION}; refusing "
            "to guess at a shape this build does not know"
        )

    return Workflow(
        workflow_id=WorkflowId(data["workflow_id"]),
        plan_id=data["plan_id"],
        plan_digest=data["plan_digest"],
        mission_id=data["mission_id"],
        title=data["title"],
        plan_task_ids=frozenset(data["plan_task_ids"]),
        version=data["version"],
        nodes=tuple(
            WorkflowNode(
                node_id=n["node_id"],
                kind=NodeKind(n["kind"]),
                purpose=n["purpose"],
                plan_task_id=n.get("plan_task_id"),
                side_effect=SideEffectClass(n["side_effect"]),
                retry=WorkflowRetryPolicy(
                    max_attempts=n["retry"]["max_attempts"],
                    backoff=BackoffKind(n["retry"]["backoff"]),
                    initial_delay_seconds=n["retry"]["initial_delay_seconds"],
                    max_delay_seconds=n["retry"].get("max_delay_seconds"),
                    idempotency_key=n["retry"].get("idempotency_key"),
                    retry_on=tuple(n["retry"].get("retry_on", ())),
                ),
                timeout=_timeout_from(n.get("timeout")),
                compensates=n.get("compensates"),
                arms=tuple(
                    BranchArm(
                        to_node=a["to_node"],
                        condition=_condition_from(a["condition"]),
                        label=a.get("label", ""),
                    )
                    for a in n.get("arms", ())
                ),
                group_id=n.get("group_id"),
                cancellable=n["cancellable"],
                execution_key=n.get("execution_key"),
            )
            for n in data["nodes"]
        ),
        edges=tuple(
            WorkflowEdge(
                from_node=e["from_node"],
                to_node=e["to_node"],
                kind=EdgeKind(e["kind"]),
                condition=_condition_from(e["condition"]),
                label=e.get("label", ""),
            )
            for e in data["edges"]
        ),
        parallel_groups=tuple(
            WorkflowParallelGroup(
                group_id=GroupId(g["group_id"]),
                label=g["label"],
                members=tuple(g["members"]),
                join=JoinPolicy(g["join"]),
                quorum=g.get("quorum"),
                max_concurrency=g.get("max_concurrency"),
            )
            for g in data["parallel_groups"]
        ),
        compensations=tuple(
            WorkflowCompensation(
                compensates=c["compensates"],
                performed_by=c["performed_by"],
                trigger=c["trigger"],
                order=c.get("order", 0),
            )
            for c in data["compensations"]
        ),
        resume_points=tuple(
            ResumePoint(node_id=p["node_id"], label=p.get("label", ""))
            for p in data["resume_points"]
        ),
        workflow_timeout=_timeout_from(data.get("workflow_timeout")),
        status=WorkflowStatus(data["status"]),
        validated_at=_optional_time(data.get("validated_at")),
        compiled_at=_optional_time(data.get("compiled_at")),
        approved_at=_optional_time(data.get("approved_at")),
        approved_by=data.get("approved_by"),
        digest=data.get("digest"),
        execution_order=tuple(data.get("execution_order", ())),
        compensation_order=tuple(data.get("compensation_order", ())),
        supersedes=WorkflowId(data["supersedes"]) if data.get("supersedes") else None,
        superseded_by=(
            WorkflowId(data["superseded_by"]) if data.get("superseded_by") else None
        ),
        compiled_by=data["compiled_by"],
        created_at=datetime.fromisoformat(data["created_at"]),
    )
