"""Storage boundary vocabulary.

Owner: BC-9 Tenancy & Identity.

Constitution I6 requires that every tenant-scoped read and write carries tenant
identity *to the storage layer*. The contracts in :mod:`backend.contracts.tenant`
describe identity as it travels between contexts; these describe the moment it
arrives at persistence and is turned into a predicate.

The distinction that matters here is between a *declaration* and a *decision*.
A :class:`StorageBinding` is a declaration a repository makes once, at class
definition time: "records of this type carry their tenant in this column." A
:class:`StorageAccess` is a decision reached per call: "this operation, on this
binding, is authorised for this tenant." A repository cannot manufacture the
second without the first, which is what stops "scoped" from meaning whatever the
caller wanted it to mean.

There is deliberately no binding that declares a record *unscoped*. A record type
either carries tenant identity or it is not eligible to pass through the guarded
boundary at all -- the guard refuses rather than silently waving it through.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation
from backend.contracts.tenant import TenantRef

__all__ = ["StorageOperation", "StorageBinding", "StorageAccess"]


class StorageOperation(str, Enum):
    """What a storage call is about to do.

    Separated from a plain "read/write" boolean because the three have different
    failure consequences: a cross-tenant READ leaks, a cross-tenant WRITE
    corrupts, and a cross-tenant DELETE destroys. An audit record that cannot
    tell them apart cannot answer the only question that matters afterwards.
    """

    READ = "read"
    WRITE = "write"
    DELETE = "delete"

    @property
    def mutates(self) -> bool:
        return self is not StorageOperation.READ


@dataclass(frozen=True)
class StorageBinding(Contract):
    """A record type's declaration of where its tenant identity lives.

    ``scope_column`` names the persisted column carrying the owning tenant. It is
    mandatory and may not be blank: a binding that cannot name its column cannot
    produce a predicate, and a scoped repository without a predicate is an
    unscoped repository wearing the word "scoped".

    ``platform_internal_allowed`` is opt-in per record type rather than a global
    switch. Platform-internal work genuinely exists (migrations, provisioning,
    integrity sweeps), but it is the exception that erases the isolation
    boundary, so each record type states for itself whether it tolerates one.
    """

    CONTRACT_NAME = "cortexprime.storage.binding"

    record_type: str
    scope_column: str
    platform_internal_allowed: bool = False

    def __post_init__(self) -> None:
        for label, value in (
            ("record_type", self.record_type),
            ("scope_column", self.scope_column),
        ):
            if not isinstance(value, str):
                raise ContractViolation(
                    f"{label} must be a string, received {type(value).__name__}"
                )
            if not value.strip():
                raise ContractViolation(f"{label} must not be blank")
            if value != value.strip():
                raise ContractViolation(f"{label} must not have leading or trailing whitespace")
        if not isinstance(self.platform_internal_allowed, bool):
            raise ContractViolation("platform_internal_allowed must be a bool")


@dataclass(frozen=True)
class StorageAccess(Contract):
    """An authorised storage operation, scoped to exactly one tenant.

    The guard returns one of these instead of a boolean so the tenant that was
    actually resolved travels with the authorisation. A boolean would leave the
    caller free to authorise against one tenant and then query with another --
    the exact substitution the invariant exists to prevent.

    ``platform_internal`` records that this access bypassed tenant narrowing.
    When true, ``tenant`` still names the platform-internal pseudo-tenant rather
    than being absent, because a nullable tenant on an audit record makes "no
    tenant" and "forgot to record the tenant" indistinguishable.
    """

    CONTRACT_NAME = "cortexprime.storage.access"

    operation: StorageOperation
    binding: StorageBinding
    tenant: TenantRef
    platform_internal: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.operation, StorageOperation):
            raise ContractViolation("operation must be a StorageOperation")
        if not isinstance(self.binding, StorageBinding):
            raise ContractViolation("binding must be a StorageBinding")
        if not isinstance(self.tenant, TenantRef):
            raise ContractViolation("tenant must be a TenantRef")
        if not isinstance(self.platform_internal, bool):
            raise ContractViolation("platform_internal must be a bool")
        if self.platform_internal and not self.binding.platform_internal_allowed:
            raise ContractViolation(
                f"{self.binding.record_type} does not permit platform-internal access"
            )

    @property
    def scope_column(self) -> str:
        return self.binding.scope_column

    @property
    def tenant_id(self) -> str:
        return self.tenant.tenant_id

    def audit_detail(self) -> dict:
        """The fields worth recording when this access is exercised."""
        return {
            "storage_operation": self.operation.value,
            "record_type": self.binding.record_type,
            "scope_column": self.binding.scope_column,
            "tenant_id": self.tenant_id,
            "platform_internal": self.platform_internal,
        }
