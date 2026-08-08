"""Storage boundary tenant enforcement.

Constitution I6 -- *every tenant-scoped read and write carries tenant identity to
the storage layer* -- has reported PARTIAL since the architecture gate went live.
Contracts refused to construct without a scope, and ADR-017 threaded an
``ExecutionContext`` through operations, but nothing stopped a repository from
simply not asking for one.

This package is the enforcement point. It is deliberately persistence-agnostic:
it deals in a scope *column name* and a tenant *value*, never in SQL. Constitution
S10 forbids ``platform/`` from importing ``backend.database``, and binding the
guard to SQLAlchemy would also have stranded Redis, Neo4j and the JSONL stores
outside the boundary they most need.

    from backend.contracts.storage import StorageBinding, StorageOperation
    from backend.platform.storage import RepositoryGuard

    guard = RepositoryGuard(
        StorageBinding(record_type="MissionModel", scope_column="tenant_id")
    )

    access = guard.authorize(StorageOperation.READ, context)
    column, value = guard.scope_filter(access)     # narrow the query
    guard.assert_in_scope(row, access)             # verify what came back

Three rules the guard exists to make unbreakable:

* A storage operation without an ``ExecutionContext`` is refused, not defaulted.
* Tenant identity is *derived* from the context, never accepted as a parameter --
  a repository that takes a ``tenant_id`` argument lets its caller pick the
  isolation boundary.
* Platform-internal access is opt-in per record type, so the escape hatch is
  countable rather than ambient.

See ADR-018.
"""

from backend.platform.storage.context import RepositoryContext, is_repository_context
from backend.platform.storage.errors import (
    CrossTenantAccess,
    MissingExecutionContext,
    PlatformInternalDenied,
    StorageBoundaryViolation,
    UnattributedWrite,
    UnscopedRecordType,
)
from backend.platform.storage.guard import RepositoryGuard
from backend.platform.storage.validation import (
    resolve_tenant,
    validate_access,
    validate_context,
    validate_platform_internal,
    validate_record_scope,
)

__all__ = [
    # Context
    "RepositoryContext",
    "is_repository_context",
    # Guard
    "RepositoryGuard",
    # Validation
    "validate_access",
    "validate_context",
    "validate_platform_internal",
    "validate_record_scope",
    "resolve_tenant",
    # Errors
    "StorageBoundaryViolation",
    "MissingExecutionContext",
    "CrossTenantAccess",
    "PlatformInternalDenied",
    "UnattributedWrite",
    "UnscopedRecordType",
]
