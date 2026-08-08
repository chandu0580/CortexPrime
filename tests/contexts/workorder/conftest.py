"""Shared fixtures for the WorkOrder context tests."""

from __future__ import annotations

import pytest

from backend.contexts.workorder import (
    AssumptionSpec, BlastRadius, InMemoryWorkOrderRepository, StaticReferenceResolver,
    WorkOrderService, draft_work_order,
)
from backend.platform.context import ExecutionContext


@pytest.fixture
def context() -> ExecutionContext:
    """A platform-internal context. Engineering work has no customer tenant."""
    return ExecutionContext.platform_internal(
        reason="workorder-tests", component="tests", source="pytest"
    )


@pytest.fixture
def tenant_context() -> ExecutionContext:
    from backend.platform.context.identity import IdentityContext

    return ExecutionContext.for_tenant(
        tenant_id="tenant-a", identity=IdentityContext.platform("tests"), source="pytest"
    )


@pytest.fixture
def resolver() -> StaticReferenceResolver:
    # A superseded ADR and stale evidence must also be *known* -- otherwise the
    # "does not resolve" branch fires first and the supersession/staleness
    # branches are never reached, which would leave them untested.
    return StaticReferenceResolver(
        known_adrs=frozenset({"ADR-018", "ADR-017", "ADR-002"}),
        superseded_adrs=frozenset({"ADR-002"}),
        known_evidence=frozenset({"EV-1", "EV-2", "EV-STALE"}),
        stale_evidence=frozenset({"EV-STALE"}),
        enforceable_constraints=frozenset({"I6", "I2", "DEP-LAYERS"}),
    )


@pytest.fixture
def repository() -> InMemoryWorkOrderRepository:
    return InMemoryWorkOrderRepository()


@pytest.fixture
def service(repository, resolver) -> WorkOrderService:
    return WorkOrderService(repository=repository, resolver=resolver)


@pytest.fixture
def radius() -> BlastRadius:
    return BlastRadius.of(["backend/contexts/workorder/**"])


def make_draft(*, radius=None, **overrides):
    """A valid Draft. Overrides let a test invalidate exactly one thing."""
    fields = dict(
        intent="The storage boundary refuses operations without an ExecutionContext",
        acceptance_criteria={"A read with no context is refused"},
        blast_radius=radius or BlastRadius.of(["backend/contexts/workorder/**"]),
        adr_references=["ADR-018"],
        evidence=["EV-1"],
        constraints=["I6"],
        definition_of_done={"The guard refuses an unattributed write"},
        assumptions=[AssumptionSpec("Models carry a tenant column", "grep tenant_id")],
    )
    fields.update(overrides)
    return draft_work_order(**fields)


@pytest.fixture
def drafted(repository, context):
    work_order = make_draft()
    repository.save(context, work_order)
    return work_order
