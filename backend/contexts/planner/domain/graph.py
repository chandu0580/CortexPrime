"""The task dependency graph, and the invariants only the whole graph can check.

``TaskRef`` in ``backend/contracts/mission.py`` enforces what it can locally -- a
task cannot depend on itself, and ``depends_on`` holds no duplicates -- and says
so plainly:

    Cycles are forbidden by Constitution S4; detecting them requires the whole
    graph, so that check belongs to BC-1.

This module is where that check lives. It is the reason the Planner holds a graph
type at all rather than a list of tasks with dependency strings.

The two failures this prevents
-------------------------------
**A cycle stalls rather than fails.** No task inside one can ever become ready,
so an executor waits forever. Stalling is worse than failing because it looks
like slowness -- somebody eventually notices the plan has not moved, hours after
a failure would have paged them.

**A dangling dependency can never be satisfied.** A task waiting on something the
plan does not contain will never start, and the plan will report itself
incomplete without saying why.

Both are refused at construction, and both name their evidence: the cycle path,
or the missing ids. A refusal that says only "there is a cycle" leaves the reader
to find it in ninety tasks.

What this module deliberately does not do
------------------------------------------
It does not schedule. :meth:`DependencyGraph.layers` reports which tasks *could*
run together because nothing orders them relative to each other -- that is a
property of the graph, not a decision about execution. Choosing what actually
runs, when, and with how much parallelism belongs to Execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

from backend.contracts.errors import ContractViolation
from backend.contexts.planner.domain.errors import CyclicDependency, DanglingDependency

__all__ = ["DependencyGraph"]


@dataclass(frozen=True)
class DependencyGraph:
    """A directed acyclic graph of task ids.

    Built from ``{task_id: depends_on}``. Refuses to exist if it is cyclic or
    references a task it does not contain, so anything holding one has already
    been told it is sound.
    """

    edges: Mapping[str, tuple] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.edges is None:
            object.__setattr__(self, "edges", {})
        if not isinstance(self.edges, Mapping):
            raise ContractViolation("edges must be a mapping of task id to dependencies")

        normalised: dict = {}
        for task_id, dependencies in self.edges.items():
            if not isinstance(task_id, str) or not task_id.strip():
                raise ContractViolation("a task id must be non-blank text")
            if isinstance(dependencies, str):
                raise ContractViolation(
                    f"dependencies for {task_id!r} must be a sequence, not a string"
                )
            deps = tuple(dependencies or ())
            for dependency in deps:
                if not isinstance(dependency, str) or not dependency.strip():
                    raise ContractViolation(
                        f"task {task_id!r} has a blank dependency"
                    )
            if len(set(deps)) != len(deps):
                raise ContractViolation(
                    f"task {task_id!r} lists a dependency twice; the duplicate cannot "
                    "mean anything the single one does not"
                )
            if task_id in deps:
                raise ContractViolation(f"task {task_id!r} depends on itself")
            normalised[task_id.strip()] = deps

        object.__setattr__(self, "edges", normalised)

        self._assert_no_dangling()
        self._assert_acyclic()

    # ------------------------------------------------------------------
    # Invariants
    # ------------------------------------------------------------------

    def _assert_no_dangling(self) -> None:
        known = set(self.edges)
        for task_id, dependencies in self.edges.items():
            missing = [d for d in dependencies if d not in known]
            if missing:
                raise DanglingDependency(task_id=task_id, missing=missing)

    def _assert_acyclic(self) -> None:
        """Depth-first search that reports the cycle it found, not just that one exists.

        Iterative rather than recursive: a plan is allowed to be deep, and a
        recursion limit is a silly reason to refuse a legitimate one.
        """
        WHITE, GREY, BLACK = 0, 1, 2
        colour = {task_id: WHITE for task_id in self.edges}

        for start in sorted(self.edges):
            if colour[start] != WHITE:
                continue

            # (node, iterator over its dependencies) with an explicit path stack.
            stack: list = [(start, iter(sorted(self.edges[start])))]
            path: list = [start]
            colour[start] = GREY

            while stack:
                node, dependencies = stack[-1]
                advanced = False
                for dependency in dependencies:
                    if colour[dependency] == GREY:
                        # The cycle is the path from where this node first appeared.
                        index = path.index(dependency)
                        raise CyclicDependency(path[index:])
                    if colour[dependency] == WHITE:
                        colour[dependency] = GREY
                        path.append(dependency)
                        stack.append((dependency, iter(sorted(self.edges[dependency]))))
                        advanced = True
                        break
                if advanced:
                    continue
                colour[node] = BLACK
                stack.pop()
                path.pop()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self.edges)

    def __contains__(self, task_id: str) -> bool:
        return task_id in self.edges

    @property
    def is_empty(self) -> bool:
        return not self.edges

    @property
    def task_ids(self) -> tuple:
        return tuple(sorted(self.edges))

    @property
    def roots(self) -> tuple:
        """Tasks nothing has to happen before. Where the plan starts."""
        return tuple(sorted(t for t, deps in self.edges.items() if not deps))

    @property
    def leaves(self) -> tuple:
        """Tasks nothing depends on. Where the plan ends."""
        depended_on = {d for deps in self.edges.values() for d in deps}
        return tuple(sorted(t for t in self.edges if t not in depended_on))

    def dependents_of(self, task_id: str) -> tuple:
        """Tasks that wait on this one directly."""
        return tuple(sorted(t for t, deps in self.edges.items() if task_id in deps))

    def dependencies_of(self, task_id: str) -> tuple:
        return tuple(sorted(self.edges.get(task_id, ())))

    def layers(self) -> tuple:
        """Tasks grouped by how deep they sit in the graph.

        Each layer contains tasks whose dependencies are all satisfied by earlier
        layers, so nothing within a layer orders anything else within it.

        **This is not a schedule.** It reports what the graph permits, not what
        an executor should do -- concurrency limits, resource contention and
        failure handling all belong to Execution, which this context must not
        reach into.
        """
        remaining = {t: set(deps) for t, deps in self.edges.items()}
        done: set = set()
        result: list = []

        while remaining:
            ready = sorted(t for t, deps in remaining.items() if deps <= done)
            if not ready:  # pragma: no cover - acyclicity is enforced at construction
                raise CyclicDependency(sorted(remaining))
            result.append(tuple(ready))
            done.update(ready)
            for task_id in ready:
                del remaining[task_id]

        return tuple(result)

    @property
    def depth(self) -> int:
        """How many layers deep the plan is.

        The lower bound on how many sequential steps it takes, whatever the
        parallelism. A plan whose depth equals its task count is fully
        sequential; one with depth 1 is fully parallel.
        """
        return len(self.layers())

    @property
    def widest_layer(self) -> int:
        """The most tasks the graph permits at once. What parallelism could use."""
        layers = self.layers()
        return max((len(layer) for layer in layers), default=0)

    def reachable_from(self, task_id: str) -> frozenset:
        """Every task that transitively waits on this one.

        What a failure here would block, which is the question asked whenever a
        task looks risky.
        """
        if task_id not in self.edges:
            return frozenset()
        found: set = set()
        frontier = [task_id]
        while frontier:
            current = frontier.pop()
            for dependent in self.dependents_of(current):
                if dependent not in found:
                    found.add(dependent)
                    frontier.append(dependent)
        return frozenset(found)

    def blast_of(self, task_id: str) -> int:
        """How many tasks a failure at ``task_id`` would strand."""
        return len(self.reachable_from(task_id))

    @classmethod
    def of(cls, tasks: Iterable) -> "DependencyGraph":
        """Build from anything exposing ``task_id`` and ``depends_on``."""
        return cls(edges={t.task_id: tuple(t.depends_on) for t in tasks})
