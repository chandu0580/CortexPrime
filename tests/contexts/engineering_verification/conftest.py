"""Fixtures for the Verification context tests."""

from __future__ import annotations

import pytest

from backend.contexts.engineering_verification import (
    ClaimType, EvidenceKind, InMemoryVerificationRepository, ReproductionMethod,
    TrustLevel, VerificationService, claim, default_policy, evidence, reproduction,
    request_verification,
)
from backend.platform.context import ExecutionContext

BASE = "abc123def456"


@pytest.fixture
def context() -> ExecutionContext:
    return ExecutionContext.platform_internal(
        reason="verification-tests", component="tests", source="pytest"
    )


@pytest.fixture
def tenant_context() -> ExecutionContext:
    from backend.platform.context.identity import IdentityContext

    return ExecutionContext.for_tenant(
        tenant_id="tenant-a", identity=IdentityContext.platform("tests"), source="pytest"
    )


@pytest.fixture
def repository() -> InMemoryVerificationRepository:
    return InMemoryVerificationRepository()


@pytest.fixture
def service(repository) -> VerificationService:
    return VerificationService(repository=repository, policy=default_policy())


@pytest.fixture
def behaviour_claim():
    return claim("a read with no context is refused", ClaimType.BEHAVIOUR)


@pytest.fixture
def absence_claim():
    return claim("no cross-tenant read is possible", ClaimType.ABSENCE)


@pytest.fixture
def good_evidence():
    return evidence(
        "ran the guard against a foreign-tenant row; CrossTenantAccess raised",
        kind=EvidenceKind.COMMAND,
        trust=TrustLevel.ENVIRONMENTAL,
        base_commit=BASE,
    )


def running(*claims, base_commit: str = BASE, verifier: str = "verifier-1"):
    """A record in RUNNING status with the given claims."""
    return request_verification("WO-1", claims, base_commit=base_commit).start(verifier)


def command_step(spec: str = "pytest tests/contexts -q"):
    return reproduction(spec, ReproductionMethod.COMMAND_EXECUTION)


def adversarial_step(spec: str = "construct the violation and observe refusal"):
    return reproduction(spec, ReproductionMethod.ADVERSARIAL_CONSTRUCTION)
