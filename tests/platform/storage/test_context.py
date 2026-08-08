"""The context protocol, and the fact that the real context satisfies it.

The guard is written against a structural protocol so it can be tested with
doubles. That buys testability and costs a risk: the doubles could drift into
describing a shape nothing in production actually has, and every test would keep
passing. These tests are the tether.
"""

from __future__ import annotations

import pytest

from backend.contracts.storage import StorageBinding, StorageOperation
from backend.platform.context import ExecutionContext
from backend.platform.context.identity import IdentityContext
from backend.platform.storage import RepositoryGuard, is_repository_context
from backend.platform.storage.context import RepositoryContext

from tests.platform.storage.conftest import FakeContext


def _real_context(tenant_id: str = "tenant-a") -> ExecutionContext:
    return ExecutionContext.for_tenant(
        tenant_id=tenant_id,
        identity=IdentityContext.platform("storage-tests"),
        source="test",
    )


# ----------------------------------------------------------------------
# The real thing satisfies the protocol
# ----------------------------------------------------------------------


def test_execution_context_satisfies_the_protocol():
    """Structurally, with no registration and no inheritance."""
    assert is_repository_context(_real_context())


def test_platform_internal_execution_context_satisfies_the_protocol():
    context = ExecutionContext.platform_internal(
        reason="integrity-sweep", component="audit", source="scheduler"
    )
    assert is_repository_context(context)


def test_guard_accepts_a_real_execution_context():
    """End to end: the production context type flows through the real guard."""
    guard = RepositoryGuard(StorageBinding(record_type="ProbeModel", scope_column="tenant_id"))
    access = guard.authorize(StorageOperation.READ, _real_context("acme"))

    assert access.tenant_id == "acme"
    assert guard.scope_filter(access) == ("tenant_id", "acme")


def test_real_platform_internal_context_is_denied_by_a_closed_binding():
    guard = RepositoryGuard(StorageBinding(record_type="ProbeModel", scope_column="tenant_id"))
    context = ExecutionContext.platform_internal(
        reason="integrity-sweep", component="audit", source="scheduler"
    )
    from backend.platform.storage import PlatformInternalDenied

    with pytest.raises(PlatformInternalDenied):
        guard.authorize(StorageOperation.READ, context)


# ----------------------------------------------------------------------
# What the protocol rejects
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "candidate",
    [None, object(), "tenant-a", 42, {"tenant_id": "tenant-a"}],
    ids=["none", "bare-object", "string", "int", "dict"],
)
def test_non_contexts_are_rejected(candidate):
    assert not is_repository_context(candidate)


def test_isinstance_alone_is_not_sufficient():
    """The runtime protocol check is too weak on its own, by design of Protocol.

    ``runtime_checkable`` verifies attribute *names*, not types or values. This
    object passes ``isinstance`` and must still be rejected -- which is the
    entire reason ``is_repository_context`` exists rather than a bare isinstance.
    """

    class NamesOnly:
        tenant_id = None            # present, but not a tenant
        is_platform_internal = "no"  # present, but not a bool

        def audit_detail(self) -> dict:
            return {}

    candidate = NamesOnly()
    assert isinstance(candidate, RepositoryContext)
    assert not is_repository_context(candidate)


@pytest.mark.parametrize("tenant_id", ["", "   ", "\t\n"])
def test_blank_tenants_are_rejected(tenant_id):
    assert not is_repository_context(FakeContext(tenant_id))


def test_non_bool_platform_internal_is_rejected():
    context = FakeContext("tenant-a")
    context.is_platform_internal = 1     # truthy, but not a bool
    assert not is_repository_context(context)


def test_missing_audit_detail_is_rejected():
    class NoAudit:
        tenant_id = "tenant-a"
        is_platform_internal = False

    assert not is_repository_context(NoAudit())


# ----------------------------------------------------------------------
# The protocol stays narrow
# ----------------------------------------------------------------------


def test_protocol_exposes_only_what_the_boundary_needs():
    """The guard must not be able to see anything it could be steered by.

    Feature flags, locale and request headers are all attacker-influenced or
    caller-influenced. A boundary that cannot read them cannot branch on them.
    """
    members = {
        name
        for name in dir(RepositoryContext)
        if not name.startswith("_")
    }
    assert members == {"tenant_id", "is_platform_internal", "audit_detail"}
