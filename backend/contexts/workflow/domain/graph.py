"""The workflow control-flow graph.

Four things only the whole graph can answer, and each prevents a distinct failure:

**Is it acyclic?** There is no loop construct here, deliberately. A cycle is a
path that can never complete, so an executor entering one spins or waits forever.

**Is every node reachable?** An unreachable node never runs, and the workflow
completes *successfully* having silently skipped it. That is worse than an error:
the work simply never happened and nothing says so.

**Are two nodes independent?** Required before they may be put in a parallel
group. If one waits for the other, running them concurrently is a deadlock or a
race depending on how the executor handles the dependency it was told to ignore.

**How long is the longest path?** The workflow's own timeout must not be shorter
than it, or the workflow can never complete within its own deadline -- it will
always be killed, and the kill will always look like a slow dependency.

Failure and compensating edges are part of the graph
------------------------------------------------------
They are traversed for cycle and reachability checks, because a cycle through a
failure path is still a cycle, and a compensation nothing can reach is still
never going to run. They are *excluded* from the critical path: the longest
**forward** path is what a successful run takes, and budgeting the deadline for
the failure path would make every workflow's timeout absurd.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from backend.contracts.errors import ContractViolation
from backend.contexts.workflow.domain.errors import (
    CyclicWorkflow,
    DanglingEdge,
    UnreachableNode,
)
from backend.contexts.workflow.domain.nodes import WorkflowEdge

__all__ = ["WorkflowGraph"]


@dataclass(frozen=True)
class WorkflowGraph:
    """A directed acyclic graph of node ids, built from nodes and edges.

    Refuses to exist if it is cyclic or references a node it does not contain, so
    anything holding one has already been told it is traversable.
    """

    nodes: tuple = ()
    edges: tuple = ()

    def __post_init__(self) -> None:
        if not isinstance(self.nodes, tuple):
            raise ContractViolation("nodes must be a tuple of node ids")
        if not isinstance(self.edges, tuple):
            raise ContractViolation("edges must be a tuple of WorkflowEdge")

        for node_id in self.nodes:
            if not isinstance(node_id, str) or not node_id.strip():
                raise ContractViolation("a node id must be non-blank text")
        if len(set(self.nodes)) != len(self.nodes):
            raise ContractViolation("nodes contains a duplicate id")

        for edge in self.edges:
            if not isinstance(edge, WorkflowEdge):
                raise ContractViolation(f"edges contains {edge!r}, not a WorkflowEdge")

        known = set(self.nodes)
        for edge in self.edges:
            missing = [n for n in (edge.from_node, edge.to_node) if n not in known]
            if missing:
                raise DanglingEdge(edge=edge.edge_id, missing=missing)

        self._assert_acyclic()

    # ------------------------------------------------------------------
    # Adjacency
    # ------------------------------------------------------------------

    def _successors(self, *, forward_only: bool = False) -> dict:
        adjacency: dict = {node: [] for node in self.nodes}
        for edge in self.edges:
            if forward_only and not edge.kind.is_forward:
                continue
            adjacency[edge.from_node].append(edge.to_node)
        return {node: sorted(set(targets)) for node, targets in adjacency.items()}

    def _predecessors(self, *, forward_only: bool = False) -> dict:
        adjacency: dict = {node: [] for node in self.nodes}
        for edge in self.edges:
            if forward_only and not edge.kind.is_forward:
                continue
            adjacency[edge.to_node].append(edge.from_node)
        return {node: sorted(set(sources)) for node, sources in adjacency.items()}

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------

    def _assert_acyclic(self) -> None:
        """Iterative depth-first search that reports the cycle it found.

        Iterative rather than recursive: a workflow is allowed to be deep, and a
        recursion limit is a silly reason to refuse a legitimate one.
        """
        WHITE, GREY, BLACK = 0, 1, 2
        successors = self._successors()
        colour = {node: WHITE for node in self.nodes}

        for start in sorted(self.nodes):
            if colour[start] != WHITE:
                continue
            stack: list = [(start, iter(successors[start]))]
            path: list = [start]
            colour[start] = GREY

            while stack:
                node, targets = stack[-1]
                advanced = False
                for target in targets:
                    if colour[target] == GREY:
                        index = path.index(target)
                        raise CyclicWorkflow(path[index:])
                    if colour[target] == WHITE:
                        colour[target] = GREY
                        path.append(target)
                        stack.append((target, iter(successors[target])))
                        advanced = True
                        break
                if advanced:
                    continue
                colour[node] = BLACK
                stack.pop()
                path.pop()

    def assert_fully_reachable(self) -> None:
        """Refuse a graph that is not one connected workflow.

        Reachability from entry points is the obvious check and the wrong one: a
        node with no edges at all has no predecessors, so it *is* an entry point,
        and the check passes on exactly the mistake it was meant to catch --
        somebody added a node and forgot to wire it.

        Weak connectivity is the honest test. Treating edges as undirected, every
        node must sit in one component. That catches the orphan and the
        disconnected cluster, which is two workflows sharing one record.
        """
        if len(self.nodes) < 2:
            return

        undirected: dict = {node: set() for node in self.nodes}
        for edge in self.edges:
            undirected[edge.from_node].add(edge.to_node)
            undirected[edge.to_node].add(edge.from_node)

        start = sorted(self.nodes)[0]
        seen = {start}
        frontier = [start]
        while frontier:
            current = frontier.pop()
            for neighbour in sorted(undirected[current]):
                if neighbour not in seen:
                    seen.add(neighbour)
                    frontier.append(neighbour)

        stranded = sorted(set(self.nodes) - seen)
        if stranded:
            raise UnreachableNode(stranded)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.nodes)

    def __contains__(self, node_id: str) -> bool:
        return node_id in self.nodes

    @property
    def is_empty(self) -> bool:
        return not self.nodes

    @property
    def entry_points(self) -> tuple:
        """Nodes nothing leads to. Where a run starts."""
        predecessors = self._predecessors()
        return tuple(sorted(n for n in self.nodes if not predecessors[n]))

    @property
    def exit_points(self) -> tuple:
        """Nodes leading nowhere. Where a run ends."""
        successors = self._successors()
        return tuple(sorted(n for n in self.nodes if not successors[n]))

    def successors_of(self, node_id: str) -> tuple:
        return tuple(self._successors().get(node_id, ()))

    def predecessors_of(self, node_id: str) -> tuple:
        return tuple(self._predecessors().get(node_id, ()))

    def reachable_set(self) -> frozenset:
        """Every node some entry point can reach, including the entry points."""
        successors = self._successors()
        seen: set = set()
        frontier = list(self.entry_points)
        seen.update(frontier)
        while frontier:
            current = frontier.pop()
            for target in successors[current]:
                if target not in seen:
                    seen.add(target)
                    frontier.append(target)
        return frozenset(seen)

    def _forward_reachable(self) -> frozenset:
        """Every node a *successful* run visits.

        Entry points plus whatever forward edges lead to. Excludes anything only
        a failure or compensating edge reaches, which is what keeps the critical
        path a statement about the happy path.
        """
        forward = self._successors(forward_only=True)
        seen: set = set(self.entry_points)
        frontier = list(self.entry_points)
        while frontier:
            current = frontier.pop()
            for target in forward[current]:
                if target not in seen:
                    seen.add(target)
                    frontier.append(target)
        return frozenset(seen)

    @property
    def forward_reachable(self) -> tuple:
        return tuple(sorted(self._forward_reachable()))

    def ancestors_of(self, node_id: str) -> frozenset:
        """Every node that must have run before this one can.

        What makes the upstream-condition check possible: a condition may only
        read a node in this set.
        """
        if node_id not in self.nodes:
            return frozenset()
        predecessors = self._predecessors()
        seen: set = set()
        frontier = list(predecessors[node_id])
        seen.update(frontier)
        while frontier:
            current = frontier.pop()
            for source in predecessors[current]:
                if source not in seen:
                    seen.add(source)
                    frontier.append(source)
        return frozenset(seen)

    def descendants_of(self, node_id: str) -> frozenset:
        if node_id not in self.nodes:
            return frozenset()
        successors = self._successors()
        seen: set = set()
        frontier = list(successors[node_id])
        seen.update(frontier)
        while frontier:
            current = frontier.pop()
            for target in successors[current]:
                if target not in seen:
                    seen.add(target)
                    frontier.append(target)
        return frozenset(seen)

    def are_independent(self, left: str, right: str) -> bool:
        """Whether neither node waits for the other, directly or transitively.

        The precondition for putting two nodes in a parallel group.
        """
        if left == right:
            return False
        return left not in self.ancestors_of(right) and right not in self.ancestors_of(left)

    def layers(self) -> tuple:
        """Nodes grouped by depth. What the graph permits, not a schedule."""
        predecessors = self._predecessors()
        remaining = {n: set(predecessors[n]) for n in self.nodes}
        done: set = set()
        result: list = []

        while remaining:
            ready = sorted(n for n, deps in remaining.items() if deps <= done)
            if not ready:  # pragma: no cover - acyclicity is enforced at construction
                raise CyclicWorkflow(sorted(remaining))
            result.append(tuple(ready))
            done.update(ready)
            for node in ready:
                del remaining[node]

        return tuple(result)

    @property
    def depth(self) -> int:
        return len(self.layers())

    @property
    def widest_layer(self) -> int:
        return max((len(layer) for layer in self.layers()), default=0)

    def topological_order(self) -> tuple:
        """A deterministic execution order.

        Frozen at compilation so two executors cannot disagree about the shape of
        a graph both consider valid. Ties broken by id, so the order is stable
        across processes rather than merely correct.
        """
        return tuple(node for layer in self.layers() for node in layer)

    def critical_path(self, weights: Mapping[str, int]) -> tuple:
        """The longest *forward* path by weight. Returns ``(seconds, path)``.

        Forward edges only: budgeting a deadline for the failure path would make
        every workflow's timeout absurd, and the failure path has its own
        handling.
        """
        forward_predecessors = self._predecessors(forward_only=True)

        # Only nodes a successful run actually visits. A compensation reachable
        # solely by a failure edge has no forward predecessor, and without this
        # it would look like an entry point and become a path of its own --
        # making the longest "forward" path the failure path, which is exactly
        # backwards.
        reachable = self._forward_reachable()

        best: dict = {}
        route: dict = {}

        for layer in self.layers():
            for node in layer:
                if node not in reachable:
                    continue
                incoming = [p for p in forward_predecessors[node] if p in best]
                if not incoming:
                    best[node] = weights.get(node, 0)
                    route[node] = (node,)
                    continue
                heaviest = max(incoming, key=lambda p: (best[p], p))
                best[node] = best[heaviest] + weights.get(node, 0)
                route[node] = route[heaviest] + (node,)

        if not best:
            return (0, ())
        end = max(best, key=lambda n: (best[n], n))
        return (best[end], route[end])

    @classmethod
    def of(cls, nodes: Iterable, edges: Iterable) -> "WorkflowGraph":
        """Build from anything exposing ``node_id``, plus edges."""
        return cls(
            nodes=tuple(n.node_id for n in nodes),
            edges=tuple(edges),
        )
