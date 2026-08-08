"""The guard's refusals, which are the whole product.

Every test here asserts that something is *denied*. A guard whose tests only
demonstrate the happy path has not been shown to guard anything.
"""

from __future__ import annotations

import pytest

from backend.contracts.storage import StorageAccess, StorageBinding, StorageOperation
from backend.platform.storage import (
    CrossTenantAccess,
    MissingExecutionContext,
    PlatformInternalDenied,
    RepositoryGuard,
    UnscopedRecordType,
)

from tests.platform.storage.conftest import FakeContext, FakeRow


# ----------------------------------------------------------------------
# Missing context
# ----------------------------------------------------------------------


@pytest.mark.parametrize("operation", list(StorageOperation))
def test_no_context_is_refused_for_every_operation(guard, operation):
    with pytest.raises(MissingExecutionContext):
        guard.authorize(operation, None)


@pytest.mark.parametrize(
    "bad_context",
    [
        None,
        object(),                      # nothing resembling a context
        "tenant-a",                    # the tenant id itself, not a context
        123,
    ],
    ids=["none", "bare-object", "raw-string", "int"],
)
def test_malformed_contexts_are_refused(guard, bad_context):
    with pytest.raises(MissingExecutionContext):
        guard.authorize(StorageOperation.READ, bad_context)


def test_context_with_blank_tenant_is_refused(guard):
    """A whitespace tenant is absence wearing a string's clothes."""
    with pytest.raises(MissingExecutionContext):
        guard.authorize(StorageOperation.READ, FakeContext("   "))


def test_context_whose_accessor_raises_is_refused(guard):
    class Exploding:
        @property
        def tenant_id(self) -> str:
            raise RuntimeError("boom")

        is_platform_internal = False

        def audit_detail(self) -> dict:
            return {}

    # The RuntimeError must not surface -- it would be triaged as a database
    # fault rather than as a boundary refusal.
    with pytest.raises(MissingExecutionContext):
        guard.authorize(StorageOperation.READ, Exploding())


# ----------------------------------------------------------------------
# Tenant derivation
# ----------------------------------------------------------------------


def test_tenant_is_derived_from_the_context(guard, context):
    access = guard.authorize(StorageOperation.READ, context)
    assert access.tenant_id == "tenant-a"
    assert isinstance(access, StorageAccess)


def test_scope_filter_names_column_and_value(guard, context):
    access = guard.authorize(StorageOperation.READ, context)
    assert guard.scope_filter(access) == ("tenant_id", "tenant-a")


def test_guard_exposes_no_way_to_supply_a_tenant(guard, context):
    """The API surface itself must not offer tenant substitution.

    This is a design assertion, not a behavioural one: if a future change adds a
    tenant parameter to ``authorize``, the invariant is broken regardless of what
    the implementation does with it.
    """
    import inspect

    parameters = set(inspect.signature(guard.authorize).parameters)
    assert parameters == {"operation", "context"}


# ----------------------------------------------------------------------
# Cross-tenant access
# ----------------------------------------------------------------------


def test_reading_another_tenants_record_is_refused(guard, context):
    access = guard.authorize(StorageOperation.READ, context)
    with pytest.raises(CrossTenantAccess) as caught:
        guard.assert_in_scope(FakeRow("tenant-b"), access)

    error = caught.value
    assert error.context_tenant == "tenant-a"
    assert error.record_tenant == "tenant-b"


def test_own_tenants_record_is_allowed(guard, context):
    access = guard.authorize(StorageOperation.READ, context)
    guard.assert_in_scope(FakeRow("tenant-a"), access)   # no raise


def test_a_miss_is_not_a_violation(guard, context):
    """``None`` means the query found nothing, which leaks nothing."""
    access = guard.authorize(StorageOperation.READ, context)
    guard.assert_in_scope(None, access)   # no raise


def test_unstamped_record_is_refused(guard, context):
    """A row with no owner must not be inherited by whoever asks first."""
    access = guard.authorize(StorageOperation.READ, context)
    with pytest.raises(CrossTenantAccess) as caught:
        guard.assert_in_scope(FakeRow(None), access)
    assert caught.value.record_tenant == "<unset>"


# ----------------------------------------------------------------------
# Writes
# ----------------------------------------------------------------------


def test_write_stamps_the_authorised_tenant(guard, context):
    access = guard.authorize(StorageOperation.WRITE, context)
    row = FakeRow()
    guard.stamp(row, access)
    assert row.tenant_id == "tenant-a"


def test_write_into_another_tenant_is_refused_not_restamped(guard, context):
    """The attempt must fail loudly rather than succeed quietly as our own.

    Silently overwriting would convert an attempted cross-tenant write into a
    successful same-tenant write, destroying the evidence that it happened.
    """
    access = guard.authorize(StorageOperation.WRITE, context)
    row = FakeRow("tenant-b")

    with pytest.raises(CrossTenantAccess):
        guard.stamp(row, access)

    assert row.tenant_id == "tenant-b", "the record was mutated despite the refusal"


def test_restamping_own_tenant_is_a_no_op(guard, context):
    access = guard.authorize(StorageOperation.WRITE, context)
    row = FakeRow("tenant-a")
    guard.stamp(row, access)
    assert row.tenant_id == "tenant-a"


# ----------------------------------------------------------------------
# Platform-internal access
# ----------------------------------------------------------------------


def test_platform_internal_denied_by_default(guard):
    """Opt-in, not opt-out: the default binding refuses."""
    with pytest.raises(PlatformInternalDenied):
        guard.authorize(StorageOperation.READ, FakeContext("platform", platform_internal=True))


def test_platform_internal_allowed_where_declared(open_guard):
    access = open_guard.authorize(
        StorageOperation.READ, FakeContext("platform", platform_internal=True)
    )
    assert access.platform_internal is True


def test_platform_internal_access_applies_no_filter(open_guard):
    access = open_guard.authorize(
        StorageOperation.READ, FakeContext("platform", platform_internal=True)
    )
    assert open_guard.scope_filter(access) is None


def test_platform_internal_skips_the_scope_check(open_guard):
    access = open_guard.authorize(
        StorageOperation.READ, FakeContext("platform", platform_internal=True)
    )
    open_guard.assert_in_scope(FakeRow("any-tenant"), access)   # no raise


def test_denial_names_the_contexts_reason(guard):
    """The stated reason must reach the error, or the audit trail loses it."""
    with pytest.raises(PlatformInternalDenied) as caught:
        guard.authorize(
            StorageOperation.READ,
            FakeContext("platform", platform_internal=True, reason="nightly-integrity-sweep"),
        )
    assert "nightly-integrity-sweep" in str(caught.value)


def test_a_tenanted_context_is_never_treated_as_platform_internal(open_guard, context):
    access = open_guard.authorize(StorageOperation.READ, context)
    assert access.platform_internal is False
    assert open_guard.scope_filter(access) == ("tenant_id", "tenant-a")


# ----------------------------------------------------------------------
# Construction
# ----------------------------------------------------------------------


def test_guard_requires_a_binding():
    with pytest.raises(UnscopedRecordType):
        RepositoryGuard("tenant_id")           # type: ignore[arg-type]


def test_binding_rejects_a_blank_scope_column():
    from backend.contracts.errors import ContractViolation

    with pytest.raises(ContractViolation):
        StorageBinding(record_type="ProbeModel", scope_column="   ")


def test_access_cannot_claim_platform_internal_against_a_closed_binding():
    """The contract refuses the inconsistent combination at construction."""
    from backend.contracts.errors import ContractViolation
    from backend.contracts.tenant import TenantRef

    with pytest.raises(ContractViolation):
        StorageAccess(
            operation=StorageOperation.READ,
            binding=StorageBinding(record_type="ProbeModel", scope_column="tenant_id"),
            tenant=TenantRef(tenant_id="platform"),
            platform_internal=True,
        )


# ----------------------------------------------------------------------
# Unattributed platform-internal writes
# ----------------------------------------------------------------------


def test_platform_internal_write_without_a_tenant_is_refused(open_guard):
    """There is no tenant to derive, so there is nothing to stamp.

    Allowing it would persist a row with a null owner -- which
    ``assert_in_scope`` then treats as a violation on the way back out, so the
    boundary would be creating data it can never return.
    """
    from backend.platform.storage import UnattributedWrite

    access = open_guard.authorize(
        StorageOperation.WRITE, FakeContext("platform", platform_internal=True)
    )
    with pytest.raises(UnattributedWrite):
        open_guard.stamp(FakeRow(None), access)


def test_platform_internal_write_with_an_explicit_tenant_is_allowed(open_guard):
    """A migration writing on a tenant's behalf must say which tenant."""
    access = open_guard.authorize(
        StorageOperation.WRITE, FakeContext("platform", platform_internal=True)
    )
    row = FakeRow("acme")
    open_guard.stamp(row, access)
    assert row.tenant_id == "acme"


def test_no_stamped_row_can_ever_fail_its_own_scope_check(guard, context):
    """Round trip: whatever stamp() accepts, assert_in_scope() must return."""
    access = guard.authorize(StorageOperation.WRITE, context)
    row = FakeRow()
    guard.stamp(row, access)
    guard.assert_in_scope(row, access)   # no raise
