"""Tenant vocabulary.

Owner: BC-9 Tenancy & Identity.

Constitution I6 requires that every tenant-scoped read and write carries tenant
identity to the storage layer. These contracts are how that identity travels
between contexts. They carry identity only -- no configuration, no entitlements,
no billing. Those belong to the Administration capability.

There is deliberately no "default tenant" and no way to construct a tenant
reference from an empty string (Constitution S2, BC-9 failure boundary:
unresolvable identity halts the request).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.contracts._contract import Contract
from backend.contracts.errors import ContractViolation

__all__ = ["TenantRef", "OrganizationRef", "ProjectRef", "TenantScope"]


def _require_identifier(value: str, label: str) -> None:
    if not isinstance(value, str):
        raise ContractViolation(f"{label} must be a string, received {type(value).__name__}")
    if not value.strip():
        raise ContractViolation(f"{label} must not be blank")
    if value != value.strip():
        raise ContractViolation(f"{label} must not have leading or trailing whitespace")


@dataclass(frozen=True)
class TenantRef(Contract):
    """The isolation boundary. Every persisted row belongs to exactly one."""

    CONTRACT_NAME = "cortexprime.tenant.ref"

    tenant_id: str

    def __post_init__(self) -> None:
        _require_identifier(self.tenant_id, "tenant_id")


@dataclass(frozen=True)
class OrganizationRef(Contract):
    """An organization within a tenant.

    Organizations subdivide a tenant for ownership and routing. They are *not*
    an isolation boundary -- isolation is the tenant's job alone. Treating an
    organization as a security boundary would violate I6.
    """

    CONTRACT_NAME = "cortexprime.tenant.organization"

    tenant: TenantRef
    organization_id: str

    def __post_init__(self) -> None:
        _require_identifier(self.organization_id, "organization_id")


@dataclass(frozen=True)
class ProjectRef(Contract):
    """A project within an organization: the unit missions are scoped to."""

    CONTRACT_NAME = "cortexprime.tenant.project"

    organization: OrganizationRef
    project_id: str

    def __post_init__(self) -> None:
        _require_identifier(self.project_id, "project_id")

    @property
    def tenant(self) -> TenantRef:
        return self.organization.tenant


@dataclass(frozen=True)
class TenantScope(Contract):
    """The resolved scope a unit of work executes within.

    ``organization`` and ``project`` are optional because platform-level work
    (tenant provisioning, cross-project reporting) legitimately has no narrower
    scope. ``tenant`` is never optional: there is no unscoped work.
    """

    CONTRACT_NAME = "cortexprime.tenant.scope"

    tenant: TenantRef
    organization: Optional[OrganizationRef] = None
    project: Optional[ProjectRef] = None

    def __post_init__(self) -> None:
        if self.organization is not None and self.organization.tenant != self.tenant:
            raise ContractViolation("organization belongs to a different tenant than the scope")
        if self.project is not None:
            if self.organization is None:
                raise ContractViolation("a project scope requires an organization scope")
            if self.project.organization != self.organization:
                raise ContractViolation("project belongs to a different organization than the scope")
