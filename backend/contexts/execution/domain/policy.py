"""Execution policy: whether a run may make a move, and what an operator should know.

The aggregate enforces what is *structurally* true while work is in flight. This
decides what is *advisable*, and reports every reason at once -- a run can have an
ambiguous node *and* a blocked subgraph *and* a stale lease, and discovering them
one refusal at a time is how an incident takes an hour instead of a minute.

The rules, and the failure each prevents
-----------------------------------------
**X0 the run is open, and the move is legal.**

**X1 completion covers every node.** The failure every context here refuses in
its own vocabulary: reporting success for work that never happened.

**X2 nothing ambiguous is left unresolved at completion.** A node nobody can say
ran is not a node that succeeded. It must be retried, skipped deliberately, or
compensated first.

**X3 a cancelled run declares what it changed.** Advisory-turned-visible:
cancellation does not un-change the world, and ``mutated_nodes`` is the list an
operator reads next.

**X4 no node is blocked forever.** A node waiting on something that failed can
never become ready. Left alone the run neither completes nor fails -- it stalls,
which looks like slowness.

**X5 leases are not stale.** Advisory: a lease past its expiry with no result is
a worker that has probably gone. Reporting it is what turns a stall into a
reclaim.

**X6 stateful work that went unknown is called out.** Advisory: a Docker,
Kubernetes, Terraform or browser node that ended ambiguous has probably left
something behind, and "probably" is exactly what an operator needs to be told.

**X7 a run with no checkpoint cannot resume.** Advisory: it can only restart,
over a world that has already changed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from backend.contexts.execution.domain.state import (
    ExecutionState,
    NodeState,
    execution_refusal_reason,
    execution_permitted_from,
    is_legal_execution_transition,
)

__all__ = [
    "Severity",
    "PolicyFinding",
    "PolicyReport",
    "ExecutionPolicy",
    "default_policy",
]


class Severity(str, Enum):
    BLOCKING = "blocking"
    ADVISORY = "advisory"

    @property
    def refuses(self) -> bool:
        return self is Severity.BLOCKING


@dataclass(frozen=True)
class PolicyFinding:
    rule: str
    severity: Severity
    detail: str
    subject: Optional[str] = None

    def __str__(self) -> str:  # pragma: no cover - diagnostic only
        return f"{self.rule}: {self.detail}"


@dataclass(frozen=True)
class PolicyReport:
    findings: tuple = ()

    @property
    def blocking(self) -> tuple:
        return tuple(f for f in self.findings if f.severity.refuses)

    @property
    def advisory(self) -> tuple:
        return tuple(f for f in self.findings if not f.severity.refuses)

    @property
    def may_proceed(self) -> bool:
        return not self.blocking


class ExecutionPolicy:
    """Decides whether a run may move, and reports what is worth knowing."""

    def __init__(self, *, require_resolved_ambiguity: bool = True) -> None:
        self._require_resolved_ambiguity = require_resolved_ambiguity

    @property
    def requires_resolved_ambiguity(self) -> bool:
        return self._require_resolved_ambiguity

    def evaluate(
        self,
        execution,
        to_state: ExecutionState,
        *,
        now: Optional[datetime] = None,
    ) -> PolicyReport:
        """Every finding, not just the first."""
        moment = now or datetime.now(timezone.utc)
        findings: list = []

        # X0 -- open, and the move is legal.
        if execution.state.is_terminal:
            findings.append(
                PolicyFinding(
                    rule="X0-run-open",
                    severity=Severity.BLOCKING,
                    detail=(
                        f"the run is {execution.state.value}; "
                        + (
                            execution_refusal_reason(execution.state, to_state)
                            or "it may no longer be driven"
                        )
                    ),
                    subject=str(execution.execution_id),
                )
            )
            return PolicyReport(findings=tuple(findings))

        if not is_legal_execution_transition(execution.state, to_state):
            findings.append(
                PolicyFinding(
                    rule="X0-legal-transition",
                    severity=Severity.BLOCKING,
                    detail=(
                        execution_refusal_reason(execution.state, to_state)
                        or f"{execution.state.value} may only move to: "
                        f"{', '.join(execution_permitted_from(execution.state))}"
                    ),
                    subject=to_state.value,
                )
            )

        if to_state is ExecutionState.COMPLETED:
            # X1 -- everything finished.
            for node_id in execution.outstanding_nodes:
                findings.append(
                    PolicyFinding(
                        rule="X1-all-nodes-finished",
                        severity=Severity.BLOCKING,
                        detail=(
                            f"node {node_id!r} has not finished; completing now would "
                            "report success for work that never happened"
                        ),
                        subject=node_id,
                    )
                )

            # X2 -- nothing ambiguous left hanging.
            if self._require_resolved_ambiguity:
                for node_id in execution.ambiguous_nodes:
                    findings.append(
                        PolicyFinding(
                            rule="X2-ambiguity-resolved",
                            severity=Severity.BLOCKING,
                            detail=(
                                f"node {node_id!r} ended unknown -- nobody can say "
                                "whether it ran. Retry it, skip it deliberately, or "
                                "compensate it; a run cannot succeed over work whose "
                                "outcome is unknown"
                            ),
                            subject=node_id,
                        )
                    )

        # X3 -- a cancelled run says what it changed.
        if to_state is ExecutionState.CANCELLED:
            for node_id in execution.mutated_nodes:
                findings.append(
                    PolicyFinding(
                        rule="X3-cancellation-left-changes",
                        severity=Severity.ADVISORY,
                        detail=(
                            f"node {node_id!r} changed something before the run was "
                            "cancelled; cancelling does not un-change the world"
                        ),
                        subject=node_id,
                    )
                )

        # X4 -- a stalled subgraph.
        for node_id in execution.blocked_nodes():
            findings.append(
                PolicyFinding(
                    rule="X4-blocked-node",
                    severity=Severity.ADVISORY,
                    detail=(
                        f"node {node_id!r} waits on something that will not satisfy "
                        "it; left alone the run neither completes nor fails, which "
                        "looks like slowness"
                    ),
                    subject=node_id,
                )
            )

        # X5 -- stale leases.
        for run in execution.runs:
            if run.state is NodeState.LEASED and run.lease is not None:
                if run.lease.has_expired_at(moment):
                    findings.append(
                        PolicyFinding(
                            rule="X5-stale-lease",
                            severity=Severity.ADVISORY,
                            detail=(
                                f"the lease {run.held_by!r} holds on {run.node_id!r} "
                                "has expired with no result; reclaiming it records the "
                                "outcome as unknown rather than leaving the run stalled"
                            ),
                            subject=run.node_id,
                        )
                    )

        # X6 -- stateful work that went unknown.
        for run in execution.runs:
            if run.state.is_ambiguous and run.spec.worker_kind.is_inherently_stateful:
                findings.append(
                    PolicyFinding(
                        rule="X6-stateful-ambiguity",
                        severity=Severity.ADVISORY,
                        detail=(
                            f"node {run.node_id!r} runs {run.spec.worker_kind.value!r} "
                            "work and ended unknown; work of this kind usually leaves "
                            "something behind, so something may still be running"
                        ),
                        subject=run.node_id,
                    )
                )

        # X7 -- nowhere to resume from.
        if to_state is ExecutionState.PAUSED and not execution.checkpoints:
            findings.append(
                PolicyFinding(
                    rule="X7-resumable",
                    severity=Severity.ADVISORY,
                    detail=(
                        "no checkpoint has been recorded, so resuming restarts the run "
                        "over a world that has already changed"
                    ),
                    subject=str(execution.execution_id),
                )
            )

        return PolicyReport(findings=tuple(findings))


def default_policy() -> ExecutionPolicy:
    """The policy the Constitution defines."""
    return ExecutionPolicy(require_resolved_ambiguity=True)
