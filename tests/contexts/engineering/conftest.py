"""Fixtures for the Engineering Runtime tests.

The fakes here implement the runtime's ports without any bounded context. That is
the point of the ports: the runtime can be driven, broken, and raced against
collaborators that are entirely under the test's control -- including ones that
fail on demand, which no real service will do reliably.

``tests/contexts/engineering/test_integration.py`` separately drives the runtime
against the *real* WorkOrder context through the composition root, so these fakes
cannot drift into describing a shape nothing implements.
"""

from __future__ import annotations

import threading
from typing import Any, Optional, Sequence

import pytest

from backend.contexts.engineering import (
    Collaborators,
    ContextBundleRef,
    EngineeringRuntime,
    EngineeringRuntimeQueries,
    ReviewOutcome,
    VerificationOutcome,
    WorkOrderPhase,
    WorkOrderSnapshot,
    default_policy,
)
from backend.platform.context import ExecutionContext


class FakeWorkOrderPort:
    """An in-memory WorkOrder port with controllable failure.

    ``fail_on`` makes ``transition`` raise for a given target phase, which is how
    the rollback path is exercised -- there is no other way to make a real
    service fail at exactly the moment after a collaborator was told to start.
    """

    def __init__(self) -> None:
        self._orders: dict = {}
        self.fail_on: Optional[WorkOrderPhase] = None
        self.transition_calls: list = []
        self.reject_calls: list = []
        self._lock = threading.RLock()

    def add(
        self,
        work_id: str,
        phase: WorkOrderPhase = WorkOrderPhase.APPROVED,
        *,
        digest: Optional[str] = "digest-abc",
        constraints: tuple = (),
        unresolved_assumptions: int = 0,
        blocking_assumptions: int = 0,
        dependencies: tuple = (),
        superseded_by: Optional[str] = None,
        version: int = 1,
    ) -> WorkOrderSnapshot:
        snapshot = WorkOrderSnapshot(
            work_id=work_id,
            version=version,
            phase=phase,
            digest=digest,
            priority="p1",
            intent="a stated outcome",
            constraints=constraints,
            unresolved_assumptions=unresolved_assumptions,
            blocking_assumptions=blocking_assumptions,
            dependencies=dependencies,
            superseded_by=superseded_by,
        )
        with self._lock:
            self._orders[work_id] = snapshot
        return snapshot

    # -- WorkOrderPort --------------------------------------------------

    def snapshot(self, context: Any, work_id: str) -> Optional[WorkOrderSnapshot]:
        with self._lock:
            return self._orders.get(work_id)

    def transition(
        self, context: Any, work_id: str, to_phase: WorkOrderPhase, actor: str
    ) -> WorkOrderSnapshot:
        self.transition_calls.append((work_id, to_phase, actor))
        if self.fail_on is not None and to_phase is self.fail_on:
            raise RuntimeError(f"the port refuses to move to {to_phase.value}")
        with self._lock:
            current = self._orders[work_id]
            moved = WorkOrderSnapshot(
                work_id=current.work_id,
                version=current.version,
                phase=to_phase,
                digest=current.digest,
                priority=current.priority,
                intent=current.intent,
                blast_radius_allowed=current.blast_radius_allowed,
                constraints=current.constraints,
                unresolved_assumptions=current.unresolved_assumptions,
                blocking_assumptions=current.blocking_assumptions,
                dependencies=current.dependencies,
                superseded_by=current.superseded_by,
            )
            self._orders[work_id] = moved
            return moved

    def reject(
        self, context: Any, work_id: str, rejection_type: str, detail: str, raised_by: str
    ) -> WorkOrderSnapshot:
        self.reject_calls.append((work_id, rejection_type, detail, raised_by))
        return self.transition(context, work_id, WorkOrderPhase.REJECTED, raised_by)

    def supersede(
        self, context: Any, work_id: str, successor_id: str, actor: str
    ) -> WorkOrderSnapshot:
        with self._lock:
            current = self._orders[work_id]
            moved = WorkOrderSnapshot(
                work_id=current.work_id,
                version=current.version,
                phase=current.phase,
                digest=current.digest,
                priority=current.priority,
                intent=current.intent,
                superseded_by=successor_id,
            )
            self._orders[work_id] = moved
            return moved

    def active(self, context: Any) -> Sequence[WorkOrderSnapshot]:
        with self._lock:
            return tuple(s for s in self._orders.values() if not s.is_terminal)


class FakeReviewPort:
    def __init__(self, lenses: Sequence[str] = ("correctness", "security")) -> None:
        self._lenses = tuple(lenses)
        self.requests: list = []
        self.outcome_map: dict = {}

    def required_lenses(self) -> Sequence[str]:
        return self._lenses

    def request(self, context: Any, work_id: str, round: int, lenses: Sequence[str]) -> Sequence[str]:
        self.requests.append((work_id, round, tuple(lenses)))
        return tuple(lenses)

    def outcomes(self, context: Any, work_id: str, round: int) -> Sequence[ReviewOutcome]:
        if (work_id, round) in self.outcome_map:
            return self.outcome_map[(work_id, round)]
        return tuple(
            ReviewOutcome(work_id=work_id, round=round, lens=lens, verdict="pass")
            for lens in self._lenses
        )


class FakeVerificationPort:
    def __init__(self) -> None:
        self.requests: list = []
        self.outcome_map: dict = {}

    def request(self, context: Any, work_id: str, attempt: int) -> str:
        self.requests.append((work_id, attempt))
        return f"verification-{work_id}-{attempt}"

    def outcome(self, context: Any, work_id: str, attempt: int) -> Optional[VerificationOutcome]:
        return self.outcome_map.get(
            (work_id, attempt),
            VerificationOutcome(
                work_id=work_id, attempt=attempt, status="complete", claims_reproduced=3
            ),
        )


class FakeContextPort:
    def __init__(self) -> None:
        self.assembled: list = []

    def assemble(self, context: Any, work_id: str, work_order_version: int) -> ContextBundleRef:
        self.assembled.append((work_id, work_order_version))
        return ContextBundleRef(
            work_id=work_id,
            work_order_version=work_order_version,
            base_commit="abc123",
            manifest_digest=f"manifest-{work_id}",
        )

    def current(self, context: Any, work_id: str) -> Optional[ContextBundleRef]:
        return None


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="engineering-runtime-tests", component="tests", source="pytest"
    )


@pytest.fixture
def work_order_port() -> FakeWorkOrderPort:
    return FakeWorkOrderPort()


@pytest.fixture
def review_port() -> FakeReviewPort:
    return FakeReviewPort()


@pytest.fixture
def verification_port() -> FakeVerificationPort:
    return FakeVerificationPort()


@pytest.fixture
def context_port() -> FakeContextPort:
    return FakeContextPort()


@pytest.fixture
def bare_runtime(work_order_port) -> EngineeringRuntime:
    """Only the WorkOrder port wired -- the honest current state of the system."""
    return EngineeringRuntime(Collaborators(work_order=work_order_port))


@pytest.fixture
def full_runtime(
    work_order_port, review_port, verification_port, context_port
) -> EngineeringRuntime:
    """Every port wired, so the whole lifecycle is reachable."""
    return EngineeringRuntime(
        Collaborators(
            work_order=work_order_port,
            review=review_port,
            verification=verification_port,
            context_bundles=context_port,
        ),
        policy=default_policy(),
    )


@pytest.fixture
def queries(full_runtime) -> EngineeringRuntimeQueries:
    return EngineeringRuntimeQueries(full_runtime)


def drive(runtime, context, work_id: str, phases: Sequence[str], actor: str = "orchestrator"):
    """Walk a WorkOrder through several phases, returning the last result."""
    result = None
    for phase in phases:
        result = runtime.transition(context, work_id, phase, actor=actor)
    return result
