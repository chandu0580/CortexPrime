"""Shared fixtures for contract tests.

Builders return the smallest valid instance of each contract. Tests that care
about a specific field override it explicitly, which keeps the interesting part
of each test visible instead of buried in construction noise.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from backend.contracts import (
    ActionRef,
    ApprovalArtifact,
    Citation,
    ExecutionContract,
    ExecutionScope,
    HashAlgorithm,
    OrganizationRef,
    PayloadDigest,
    PrincipalKind,
    PrincipalRef,
    ProjectRef,
    SecurityContext,
    SideEffectClass,
    TenantRef,
    TenantScope,
)

NOW = datetime(2030, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
LATER = NOW + timedelta(minutes=30)


@pytest.fixture
def tenant() -> TenantRef:
    return TenantRef(tenant_id="tenant-alpha")


@pytest.fixture
def organization(tenant: TenantRef) -> OrganizationRef:
    return OrganizationRef(tenant=tenant, organization_id="org-platform")


@pytest.fixture
def project(organization: OrganizationRef) -> ProjectRef:
    return ProjectRef(organization=organization, project_id="proj-checkout")


@pytest.fixture
def scope(tenant: TenantRef, organization: OrganizationRef, project: ProjectRef) -> TenantScope:
    return TenantScope(tenant=tenant, organization=organization, project=project)


@pytest.fixture
def human() -> PrincipalRef:
    return PrincipalRef(
        principal_id="user-42", kind=PrincipalKind.HUMAN, display_name="On-call Engineer"
    )


@pytest.fixture
def platform_principal() -> PrincipalRef:
    return PrincipalRef(principal_id="cortexprime", kind=PrincipalKind.PLATFORM)


@pytest.fixture
def security_context(human: PrincipalRef, scope: TenantScope) -> SecurityContext:
    return SecurityContext(principal=human, scope=scope, capabilities=("mission:create",))


@pytest.fixture
def reversible_action() -> ActionRef:
    return ActionRef(action_type="docker.restart", parameters={"container": "web-01"})


@pytest.fixture
def execution_scope() -> ExecutionScope:
    return ExecutionScope(system="docker", resources=("web-01",), environment="production")


@pytest.fixture
def execution_contract(
    reversible_action: ActionRef, execution_scope: ExecutionScope
) -> ExecutionContract:
    return ExecutionContract(
        execution_key="restart-web-01",
        action=reversible_action,
        scope=execution_scope,
        side_effect_class=SideEffectClass.REVERSIBLE_WRITE,
        inverse=reversible_action,
        verification_criteria=("container reports running",),
    )


@pytest.fixture
def digest() -> PayloadDigest:
    return PayloadDigest(algorithm=HashAlgorithm.SHA256, value="a" * 64)


@pytest.fixture
def other_digest() -> PayloadDigest:
    return PayloadDigest(algorithm=HashAlgorithm.SHA256, value="b" * 64)


@pytest.fixture
def approval_artifact(
    execution_contract: ExecutionContract, digest: PayloadDigest, scope: TenantScope
) -> ApprovalArtifact:
    return ApprovalArtifact(
        artifact_id="artifact-1",
        execution=execution_contract,
        digest=digest,
        scope=scope,
        created_at=NOW,
    )


@pytest.fixture
def citation() -> Citation:
    return Citation(
        citation_id="cite-1",
        source_system="prometheus",
        query='rate(http_errors_total[5m])',
        observed_at=NOW,
        retrieved_at=NOW,
    )
