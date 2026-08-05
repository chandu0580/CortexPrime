"""Tenant, organization, and workspace context.

Constitution I6: every tenant-scoped read and write carries tenant identity to
the storage layer. This is the runtime half of that -- contracts define the
*vocabulary* (``TenantRef``, ``TenantScope``); this defines the *context an
operation executes within*.

No default tenant, and no implicit one
--------------------------------------
``TenantContext`` cannot be constructed without a tenant. There is no
zero-argument form, no ``DEFAULT_TENANT``, and no fallback that quietly
substitutes one. Retrofitting tenancy is the migration that kills companies;
the way to avoid it is to make an untenanted operation impossible to express.

Platform-internal work is the one exception, and it is explicit
---------------------------------------------------------------
Some work genuinely has no tenant: a scheduler tick, a startup check, the
approval dispatcher replaying an event whose tenancy was never captured.

Pretending those belong to a tenant called ``"system"`` is what the current
integrity audit does, and it is wrong twice -- it invents an owner, and it makes
a real tenant named "system" indistinguishable from the absence of one.

:meth:`TenantContext.platform_internal` instead marks the absence explicitly. It
demands a stated reason, reports ``is_platform_internal``, and uses a reserved
identifier no real tenant may claim. The gap stays visible and greppable rather
than disguised.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backend.contracts import (
    ContractViolation,
    OrganizationRef,
    ProjectRef,
    TenantRef,
    TenantScope,
)

__all__ = [
    "PLATFORM_INTERNAL_TENANT_ID",
    "TenantContext",
    "OrganizationContext",
    "WorkspaceContext",
]

PLATFORM_INTERNAL_TENANT_ID = "__platform_internal__"
"""Reserved identifier for work with no tenant.

Double-underscored on both sides so it cannot collide with a real tenant id and
is trivially greppable. Every use is a gap that PR-11 and later close; the count
is the size of that gap.
"""


@dataclass(frozen=True)
class TenantContext:
    """The isolation boundary an operation executes within."""

    tenant: TenantRef
    platform_internal_reason: Optional[str] = None
    """Set only via :meth:`platform_internal`. States why no tenant applies."""

    def __post_init__(self) -> None:
        if not isinstance(self.tenant, TenantRef):
            raise ContractViolation("tenant must be a TenantRef")
        if self.tenant.tenant_id == PLATFORM_INTERNAL_TENANT_ID:
            if not (self.platform_internal_reason or "").strip():
                raise ContractViolation(
                    "platform-internal context requires a stated reason; construct it "
                    "with TenantContext.platform_internal(reason=...)"
                )
        elif self.platform_internal_reason is not None:
            raise ContractViolation(
                "a tenant-scoped context must not carry a platform-internal reason"
            )

    @classmethod
    def for_tenant(cls, tenant_id: str) -> "TenantContext":
        """Context for a real tenant. The normal constructor."""
        if tenant_id == PLATFORM_INTERNAL_TENANT_ID:
            raise ContractViolation(
                f"{PLATFORM_INTERNAL_TENANT_ID!r} is reserved and cannot be a tenant id"
            )
        return cls(tenant=TenantRef(tenant_id=tenant_id))

    @classmethod
    def platform_internal(cls, reason: str) -> "TenantContext":
        """Context for work that genuinely has no tenant.

        ``reason`` is mandatory and appears in audit records, so a reviewer can
        tell a legitimate scheduler tick from a missing plumbing job.
        """
        if not isinstance(reason, str) or not reason.strip():
            raise ContractViolation("platform-internal context requires a stated reason")
        return cls(
            tenant=TenantRef(tenant_id=PLATFORM_INTERNAL_TENANT_ID),
            platform_internal_reason=reason,
        )

    @property
    def is_platform_internal(self) -> bool:
        return self.tenant.tenant_id == PLATFORM_INTERNAL_TENANT_ID

    @property
    def tenant_id(self) -> str:
        return self.tenant.tenant_id

    def isolates_from(self, other: "TenantContext") -> bool:
        """Whether these two contexts are in different isolation boundaries."""
        return self.tenant != other.tenant


@dataclass(frozen=True)
class OrganizationContext:
    """An organization within a tenant.

    Subdivides a tenant for ownership and routing. **Not** an isolation
    boundary -- isolation is the tenant's job alone, and treating an
    organization as one would violate I6 by allowing cross-tenant reads that
    happen to share an organization id.
    """

    tenancy: TenantContext
    organization: OrganizationRef

    def __post_init__(self) -> None:
        if self.organization.tenant != self.tenancy.tenant:
            raise ContractViolation(
                "organization belongs to a different tenant than its context"
            )

    @classmethod
    def create(cls, tenancy: TenantContext, organization_id: str) -> "OrganizationContext":
        return cls(
            tenancy=tenancy,
            organization=OrganizationRef(
                tenant=tenancy.tenant, organization_id=organization_id
            ),
        )

    @property
    def organization_id(self) -> str:
        return self.organization.organization_id


@dataclass(frozen=True)
class WorkspaceContext:
    """A workspace -- the unit missions are scoped to.

    Maps to ``ProjectRef`` in the contract vocabulary. The two names coexist
    because the product calls it a workspace and the schema calls it a project;
    renaming either is a migration, not a context change.
    """

    organization: OrganizationContext
    project: ProjectRef

    def __post_init__(self) -> None:
        if self.project.organization != self.organization.organization:
            raise ContractViolation(
                "workspace belongs to a different organization than its context"
            )

    @classmethod
    def create(cls, organization: OrganizationContext, workspace_id: str) -> "WorkspaceContext":
        return cls(
            organization=organization,
            project=ProjectRef(
                organization=organization.organization, project_id=workspace_id
            ),
        )

    @property
    def workspace_id(self) -> str:
        return self.project.project_id

    @property
    def tenancy(self) -> TenantContext:
        return self.organization.tenancy


def build_scope(
    tenancy: TenantContext,
    organization: Optional[OrganizationContext] = None,
    workspace: Optional[WorkspaceContext] = None,
) -> TenantScope:
    """Collapse the context hierarchy into the contract vocabulary.

    ``TenantScope`` is what crosses a context boundary (Constitution BC-9); the
    contexts above are what an operation carries internally. Converting at the
    edge keeps the two from drifting.
    """
    return TenantScope(
        tenant=tenancy.tenant,
        organization=organization.organization if organization else None,
        project=workspace.project if workspace else None,
    )
