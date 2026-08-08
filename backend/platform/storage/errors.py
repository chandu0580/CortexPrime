"""Failures at the storage boundary.

Every one of these is a refusal, never a warning. A storage call that cannot
establish which tenant it belongs to does not fall back to "all tenants" or to
"no filter" -- it stops. The alternative is a query that silently widens, which
is precisely how cross-tenant leaks reach production without anyone noticing.

These derive from :class:`~backend.contracts.errors.ContractViolation` so a
caller that already handles contract failures at its boundary handles these too,
rather than needing a second, parallel except clause that someone will forget.
"""

from __future__ import annotations

from typing import Optional

from backend.contracts.errors import ContractViolation

__all__ = [
    "StorageBoundaryViolation",
    "MissingExecutionContext",
    "CrossTenantAccess",
    "PlatformInternalDenied",
    "UnattributedWrite",
    "UnscopedRecordType",
]


class StorageBoundaryViolation(ContractViolation):
    """Base for every refusal raised by the storage boundary guard."""


class MissingExecutionContext(StorageBoundaryViolation):
    """A repository method was called without an execution context.

    Raised rather than defaulted. There is no ambient context to fall back to
    (see ADR-017), and inventing one here would reintroduce exactly the implicit
    propagation that decision removed.
    """

    def __init__(self, operation: str, record_type: Optional[str] = None) -> None:
        target = f" on {record_type}" if record_type else ""
        super().__init__(
            f"storage operation {operation!r}{target} requires an ExecutionContext; "
            "none was supplied"
        )
        self.operation = operation
        self.record_type = record_type


class CrossTenantAccess(StorageBoundaryViolation):
    """An operation tried to touch a record belonging to another tenant.

    Carries both tenants because the pair is the finding. Knowing only that a
    violation occurred tells an investigator nothing about blast radius; knowing
    that tenant A reached for tenant B's row tells them what to check.
    """

    def __init__(
        self,
        *,
        operation: str,
        record_type: str,
        context_tenant: str,
        record_tenant: str,
    ) -> None:
        super().__init__(
            f"{operation} on {record_type} refused: context is scoped to tenant "
            f"{context_tenant!r} but the record belongs to {record_tenant!r}"
        )
        self.operation = operation
        self.record_type = record_type
        self.context_tenant = context_tenant
        self.record_tenant = record_tenant


class PlatformInternalDenied(StorageBoundaryViolation):
    """A platform-internal context reached a record type that does not allow one.

    Platform-internal access erases the isolation boundary, so it is granted per
    record type rather than globally. A denial here means the record type never
    opted in -- not that the caller lacked a permission it could be granted at
    runtime.
    """

    def __init__(self, *, operation: str, record_type: str, reason: Optional[str] = None) -> None:
        stated = f" (context reason: {reason})" if reason else ""
        super().__init__(
            f"{operation} on {record_type} refused: platform-internal access is not "
            f"permitted for this record type{stated}"
        )
        self.operation = operation
        self.record_type = record_type
        self.reason = reason


class UnattributedWrite(StorageBoundaryViolation):
    """A platform-internal write arrived with no tenant set on the record.

    Platform-internal work has no tenant to derive, so there is nothing to stamp.
    Letting the write through would persist a row with a null owner -- and
    ``validate_record_scope`` treats such a row as a cross-tenant violation on
    the way back out, so the boundary would be creating data it can never return.

    A migration or sweep writing on a tenant's behalf must say which tenant.
    """

    def __init__(self, *, operation: str, record_type: str, scope_column: str) -> None:
        super().__init__(
            f"platform-internal {operation} on {record_type} refused: {scope_column} is "
            "unset and a platform-internal context has no tenant to derive; set it "
            "explicitly on the record"
        )
        self.operation = operation
        self.record_type = record_type
        self.scope_column = scope_column


class UnscopedRecordType(StorageBoundaryViolation):
    """A repository claimed tenant scoping without declaring a scope column.

    Raised at repository construction, not at query time. A repository that
    cannot name the column carrying tenant identity cannot build a predicate,
    and discovering that on the first production read is far too late.
    """

    def __init__(self, repository: str) -> None:
        super().__init__(
            f"{repository} is tenant-scoped but declares no __scope_column__; "
            "a scoped repository must name the column carrying tenant identity"
        )
        self.repository = repository
