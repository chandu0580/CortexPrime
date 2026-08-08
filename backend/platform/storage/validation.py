"""The individual checks the storage boundary applies.

Split out from :mod:`backend.platform.storage.guard` so each check can be tested
on its own and so the guard reads as a sequence of named decisions rather than a
wall of conditionals. Every function here either returns normally or raises --
none of them return a boolean, because a boolean at a security boundary is a
value someone can forget to check.

Order matters and is fixed by :func:`validate_access`:

    context present  ->  context well-formed  ->  platform-internal permitted
                     ->  tenant resolved

Each step assumes the previous one held. Checking "is this tenant allowed"
before "is there a context at all" would raise ``AttributeError`` instead of a
boundary refusal, and an ``AttributeError`` in a query path gets triaged as a
bug rather than as an attempted violation.
"""

from __future__ import annotations

from typing import Any, Optional

from backend.contracts.storage import StorageAccess, StorageBinding, StorageOperation
from backend.contracts.tenant import TenantRef
from backend.platform.storage.context import is_repository_context
from backend.platform.storage.errors import (
    CrossTenantAccess,
    MissingExecutionContext,
    PlatformInternalDenied,
)

__all__ = [
    "validate_context",
    "validate_platform_internal",
    "resolve_tenant",
    "validate_access",
    "validate_record_scope",
]


def validate_context(context: Any, *, operation: StorageOperation, binding: StorageBinding) -> None:
    """Refuse a call that has no usable context.

    ``None`` and a malformed context produce the same error deliberately. From
    the boundary's point of view they are the same failure -- the caller could
    not establish who it was acting for -- and giving them separate errors would
    invite a caller to handle one and not the other.
    """
    if not is_repository_context(context):
        raise MissingExecutionContext(operation.value, binding.record_type)


def validate_platform_internal(
    context: Any, *, operation: StorageOperation, binding: StorageBinding
) -> bool:
    """Decide whether an untenanted context may proceed. Returns whether it is one."""
    if not context.is_platform_internal:
        return False
    if not binding.platform_internal_allowed:
        raise PlatformInternalDenied(
            operation=operation.value,
            record_type=binding.record_type,
            reason=getattr(context, "platform_internal_reason", None),
        )
    return True


def resolve_tenant(context: Any) -> TenantRef:
    """The tenant a storage call is bound to, taken only from the context.

    There is no parameter here and no fallback. Tenant identity is *derived*,
    never supplied: a repository that accepts a tenant argument lets its caller
    choose the isolation boundary, which is not isolation.
    """
    return TenantRef(tenant_id=context.tenant_id)


def validate_access(
    context: Any, *, operation: StorageOperation, binding: StorageBinding
) -> StorageAccess:
    """Run the full boundary check and return the resulting authorisation."""
    validate_context(context, operation=operation, binding=binding)
    platform_internal = validate_platform_internal(context, operation=operation, binding=binding)
    return StorageAccess(
        operation=operation,
        binding=binding,
        tenant=resolve_tenant(context),
        platform_internal=platform_internal,
    )


def validate_record_scope(
    record_tenant: Optional[Any], *, access: StorageAccess
) -> None:
    """Refuse a record that belongs to a tenant other than the authorised one.

    A platform-internal access skips the comparison -- that is what it is for --
    but everything else must match exactly.

    ``None`` is a violation, not a pass. An unstamped row is a row whose owner
    was never recorded, and treating "unknown owner" as "belongs to whoever is
    asking" is how one tenant inherits another's orphaned data.
    """
    if access.platform_internal:
        return

    expected = access.tenant_id
    if record_tenant is None:
        raise CrossTenantAccess(
            operation=access.operation.value,
            record_type=access.binding.record_type,
            context_tenant=expected,
            record_tenant="<unset>",
        )

    actual = str(record_tenant)
    if actual != expected:
        raise CrossTenantAccess(
            operation=access.operation.value,
            record_type=access.binding.record_type,
            context_tenant=expected,
            record_tenant=actual,
        )
