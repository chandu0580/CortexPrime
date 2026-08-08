"""Parallel groups, compensation rules, and resume points.

Parallel groups are checked against the graph, not trusted
------------------------------------------------------------
Declaring two nodes parallel does not make them independent. If one waits for the
other -- directly or through six intermediate nodes -- running them concurrently
is a deadlock or a race, depending on how the executor handles the dependency it
was told to ignore. The aggregate checks every pair against the graph's
transitive closure, so a group that claims independence it does not have is
refused rather than discovered at three in the morning.

Join policy is a decision about partial success
-------------------------------------------------
``ALL`` waits for everything. ``ANY`` proceeds on the first success and leaves
the rest running or abandoned. ``QUORUM`` needs *n* of *m*.

``ANY`` and ``QUORUM`` are legitimate and they have a cost this context makes
explicit: members that mutate and are not waited for may still be applying
changes after the workflow has moved on. So a group that does not wait for all
of its members refuses to contain a mutating one unless the mutation is
compensable -- otherwise the workflow's own record of what happened is wrong.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contexts.workflow.domain.errors import ParallelGroupTooSmall
from backend.contexts.workflow.domain.identifiers import GroupId, normalise_node_id

__all__ = ["JoinPolicy", "WorkflowParallelGroup", "WorkflowCompensation", "ResumePoint"]


class JoinPolicy(str, Enum):
    """What counts as the group being done."""

    ALL = "all"
    ANY = "any"
    QUORUM = "quorum"

    @property
    def waits_for_everything(self) -> bool:
        return self is JoinPolicy.ALL

    @property
    def needs_quorum_size(self) -> bool:
        return self is JoinPolicy.QUORUM

    @property
    def may_abandon_members(self) -> bool:
        """Whether members can still be running when the group is called done.

        The property that makes an un-waited-for mutation dangerous: the
        workflow has moved on while the change is still being applied.
        """
        return not self.waits_for_everything


@dataclass(frozen=True)
class WorkflowParallelGroup(Contract):
    """A fan-out of mutually independent nodes."""

    CONTRACT_NAME = "cortexprime.workflow.parallel_group"

    group_id: GroupId
    label: str
    members: tuple = ()
    join: JoinPolicy = JoinPolicy.ALL
    quorum: Optional[int] = None
    max_concurrency: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.group_id, GroupId):
            raise ContractViolation("group_id must be a GroupId")
        if not isinstance(self.label, str) or not self.label.strip():
            raise ContractViolation("a parallel group must be labelled")

        if not isinstance(self.members, tuple):
            raise ContractViolation("members must be a tuple")
        for member in self.members:
            normalise_node_id(member)
        if len(set(self.members)) != len(self.members):
            raise ContractViolation(
                f"parallel group {self.label!r} lists a member twice"
            )
        if len(self.members) < 2:
            raise ParallelGroupTooSmall(
                group=str(self.group_id), members=len(self.members)
            )

        if not isinstance(self.join, JoinPolicy):
            raise ContractViolation("join must be a JoinPolicy")

        if self.join.needs_quorum_size:
            if not isinstance(self.quorum, int) or self.quorum < 1:
                raise ContractViolation(
                    "a quorum join must say how many members it needs"
                )
            if self.quorum > len(self.members):
                raise ContractViolation(
                    f"a quorum of {self.quorum} cannot be met by "
                    f"{len(self.members)} member(s)"
                )
            if self.quorum == len(self.members):
                raise ContractViolation(
                    "a quorum of every member is an 'all' join wearing a different "
                    "name; say what is meant"
                )
        elif self.quorum is not None:
            raise ContractViolation(f"a {self.join.value!r} join takes no quorum size")

        if self.max_concurrency is not None:
            if not isinstance(self.max_concurrency, int) or self.max_concurrency < 2:
                raise ContractViolation(
                    "max_concurrency must be at least 2; a group that runs one member "
                    "at a time is sequential execution with more machinery"
                )

    # -- queries -------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self.members)

    @property
    def waits_for_everything(self) -> bool:
        return self.join.waits_for_everything

    @property
    def effective_concurrency(self) -> int:
        """How many members could actually be in flight at once."""
        if self.max_concurrency is None:
            return self.size
        return min(self.max_concurrency, self.size)

    def __contains__(self, node_id: str) -> bool:
        return node_id in self.members

    @classmethod
    def create(
        cls,
        label: str,
        members: Sequence[str],
        *,
        join: JoinPolicy = JoinPolicy.ALL,
        quorum: Optional[int] = None,
        max_concurrency: Optional[int] = None,
    ) -> "WorkflowParallelGroup":
        return cls(
            group_id=GroupId.new(),
            label=label,
            members=tuple(members),
            join=join,
            quorum=quorum,
            max_concurrency=max_concurrency,
        )


@dataclass(frozen=True)
class WorkflowCompensation(Contract):
    """A rule saying which node walks back which.

    Constitution S4 calls compensation a first-class path rather than a failure
    state, and ``TaskState`` carries ``COMPENSATED`` alongside ``FAILED`` for the
    same reason. This is the declaration that makes it one: the compensating node
    is a real node in the graph, reached by a real edge, with its own timeout.

    ``trigger`` says when it runs. Compensating on a *timeout* is the case worth
    naming separately: a timed-out write may still have applied, so treating the
    timeout as a plain failure and moving on leaves a change nobody recorded.
    """

    CONTRACT_NAME = "cortexprime.workflow.compensation"

    compensates: str
    performed_by: str
    trigger: str = "on_failure"
    order: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "compensates", normalise_node_id(self.compensates))
        object.__setattr__(self, "performed_by", normalise_node_id(self.performed_by))
        if self.compensates == self.performed_by:
            raise ContractViolation(
                f"node {self.compensates!r} cannot compensate itself"
            )
        if self.trigger not in ("on_failure", "on_timeout", "on_cancel", "always"):
            raise ContractViolation(
                "trigger must be one of: on_failure, on_timeout, on_cancel, always"
            )
        if not isinstance(self.order, int) or self.order < 0:
            raise ContractViolation("order must be non-negative")

    @property
    def triggers_on_timeout(self) -> bool:
        return self.trigger in ("on_timeout", "always")


@dataclass(frozen=True, order=True)
class ResumePoint:
    """A node a suspended run may restart from.

    Refused inside a parallel group by the aggregate: resuming into half a
    fan-out leaves the other members in a state nothing records -- they either
    already ran, never ran, or ran partially, and the workflow cannot say which.
    """

    node_id: str
    label: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "node_id", normalise_node_id(self.node_id))

    def __str__(self) -> str:
        return self.label or self.node_id
