"""Request metadata, feature flags, locale, mission, and the composite context.

:class:`ExecutionContext` is the single value every CortexPrime operation
receives. It is immutable, fully populated, and passed explicitly — there is no
ambient lookup, no thread-local, and no way to obtain one implicitly.

Why no ambient context
----------------------
``contextvars`` would make propagation invisible and therefore effortless. That
is exactly the problem: an operation that can obtain a context without being
given one can also obtain the *wrong* one, and a cross-tenant read caused by a
stale context variable is both easy to write and nearly impossible to see in
review.

Explicit passing makes an untenanted or misattributed operation a signature
change rather than a runtime surprise. It is more typing; it is the point.

(``backend/database/tenancy.py`` keeps its own ``ContextVar`` for the SQL
``search_path``. That is a *session* concern bound at the connection boundary,
not a request context, and it stays where it is.)

Never partially populated
-------------------------
Identity, tenancy, trace, correlation, and request metadata are all mandatory.
Optional members — organization, workspace, mission — are optional because they
are genuinely absent for some operations, not because they may be filled in
later. There is no builder and no mutable staging object, so a half-built
context cannot exist to be passed by accident.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional

from backend.contracts import (
    ContractViolation,
    MissionRef,
    SecurityContext,
    TenantScope,
    freeze_mapping,
)
from backend.platform.context.identity import IdentityContext
from backend.platform.context.tenancy import (
    OrganizationContext,
    TenantContext,
    WorkspaceContext,
    build_scope,
)
from backend.platform.context.tracing import CorrelationContext, TraceContext
from backend.platform.identity import monotonic_ulid

__all__ = [
    "RequestMetadata",
    "LocaleContext",
    "FeatureFlagContext",
    "MissionContext",
    "ExecutionContext",
]


@dataclass(frozen=True)
class RequestMetadata:
    """Transport-level facts about how an operation arrived.

    Descriptive only. Nothing here may influence an authorization decision —
    a client-supplied header is an attacker-controlled value, and policy that
    reads one is policy an attacker can steer.
    """

    request_id: str
    source: str
    """Where it came from: ``"http"``, ``"eventbus"``, ``"scheduler"``, ``"cli"``."""

    received_at: datetime
    method: Optional[str] = None
    path: Optional[str] = None
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None

    def __post_init__(self) -> None:
        for label, value in (("request_id", self.request_id), ("source", self.source)):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be a non-blank string")
        if self.received_at.tzinfo is None:
            raise ContractViolation("received_at must be timezone-aware")

    @classmethod
    def create(cls, source: str, **fields: Any) -> "RequestMetadata":
        return cls(
            request_id=monotonic_ulid(),
            source=source,
            received_at=datetime.now(timezone.utc),
            **fields,
        )


@dataclass(frozen=True)
class LocaleContext:
    """Presentation locale. Affects rendering only, never a decision."""

    language: str = "en"
    timezone_name: str = "UTC"

    def __post_init__(self) -> None:
        for label, value in (("language", self.language), ("timezone_name", self.timezone_name)):
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be a non-blank string")


@dataclass(frozen=True)
class FeatureFlagContext:
    """Flags resolved once, at the start of an operation.

    Resolved once rather than queried per-use so an operation cannot observe a
    flag changing mid-flight and take two different paths — a class of bug that
    is nearly impossible to reproduce.
    """

    flags: Mapping[str, bool] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name, value in dict(self.flags).items():
            if not isinstance(name, str) or not name.strip():
                raise ContractViolation("flag names must be non-blank strings")
            if not isinstance(value, bool):
                raise ContractViolation(f"flag {name!r} must be a bool, got {type(value).__name__}")
        object.__setattr__(self, "flags", freeze_mapping(dict(self.flags)))

    def enabled(self, name: str, default: bool = False) -> bool:
        return self.flags.get(name, default)


@dataclass(frozen=True)
class MissionContext:
    """The mission an operation belongs to, when it belongs to one."""

    mission: MissionRef
    objective: Optional[str] = None
    step: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.mission, MissionRef):
            raise ContractViolation("mission must be a MissionRef")
        if self.step is not None and (not isinstance(self.step, int) or self.step < 0):
            raise ContractViolation("step must be a non-negative integer when present")

    @classmethod
    def create(cls, mission_id: str, **fields: Any) -> "MissionContext":
        return cls(mission=MissionRef(mission_id=mission_id), **fields)

    @property
    def mission_id(self) -> str:
        return self.mission.mission_id


@dataclass(frozen=True)
class ExecutionContext:
    """The canonical context every CortexPrime operation receives.

    Immutable and fully populated. Derived contexts are produced by the
    ``with_*`` and ``child_*`` methods, each returning a new instance.
    """

    identity: IdentityContext
    tenancy: TenantContext
    trace: TraceContext
    correlation: CorrelationContext
    request: RequestMetadata
    organization: Optional[OrganizationContext] = None
    workspace: Optional[WorkspaceContext] = None
    mission: Optional[MissionContext] = None
    features: FeatureFlagContext = field(default_factory=FeatureFlagContext)
    locale: LocaleContext = field(default_factory=LocaleContext)

    def __post_init__(self) -> None:
        for label, value, expected in (
            ("identity", self.identity, IdentityContext),
            ("tenancy", self.tenancy, TenantContext),
            ("trace", self.trace, TraceContext),
            ("correlation", self.correlation, CorrelationContext),
            ("request", self.request, RequestMetadata),
        ):
            if not isinstance(value, expected):
                raise ContractViolation(f"{label} must be a {expected.__name__}")

        # A context that spans two tenants is a cross-tenant leak waiting to be
        # written; refuse it at construction rather than trusting every consumer
        # to check the right member.
        if self.organization is not None and self.organization.tenancy != self.tenancy:
            raise ContractViolation("organization belongs to a different tenant than the context")
        if self.workspace is not None:
            if self.organization is None:
                raise ContractViolation("a workspace context requires an organization context")
            if self.workspace.organization != self.organization:
                raise ContractViolation(
                    "workspace belongs to a different organization than the context"
                )

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    @classmethod
    def for_tenant(
        cls,
        *,
        tenant_id: str,
        identity: IdentityContext,
        source: str,
        correlation: Optional[CorrelationContext] = None,
        trace: Optional[TraceContext] = None,
        organization_id: Optional[str] = None,
        workspace_id: Optional[str] = None,
        mission_id: Optional[str] = None,
        flags: Optional[Mapping[str, bool]] = None,
        locale: Optional[LocaleContext] = None,
    ) -> "ExecutionContext":
        """Build a fully-populated context for a real tenant."""
        tenancy = TenantContext.for_tenant(tenant_id)

        organization = (
            OrganizationContext.create(tenancy, organization_id) if organization_id else None
        )
        workspace = (
            WorkspaceContext.create(organization, workspace_id)
            if workspace_id and organization
            else None
        )
        if workspace_id and not organization_id:
            raise ContractViolation("workspace_id requires organization_id")

        return cls(
            identity=identity,
            tenancy=tenancy,
            trace=trace or TraceContext.new_trace(),
            correlation=correlation or CorrelationContext.new_chain(),
            request=RequestMetadata.create(source),
            organization=organization,
            workspace=workspace,
            mission=MissionContext.create(mission_id) if mission_id else None,
            features=FeatureFlagContext(flags or {}),
            locale=locale or LocaleContext(),
        )

    @classmethod
    def platform_internal(
        cls,
        *,
        reason: str,
        component: str,
        source: str,
        correlation: Optional[CorrelationContext] = None,
    ) -> "ExecutionContext":
        """Context for work that genuinely has no tenant.

        Requires a stated ``reason`` that reaches the audit record. Every use is
        a gap in tenant attribution; making it verbose and greppable is what
        keeps the count honest and shrinking.
        """
        return cls(
            identity=IdentityContext.platform(component),
            tenancy=TenantContext.platform_internal(reason),
            trace=TraceContext.new_trace(),
            correlation=correlation or CorrelationContext.new_chain(),
            request=RequestMetadata.create(source),
        )

    # ------------------------------------------------------------------
    # Derivation — every one returns a new instance
    # ------------------------------------------------------------------

    def child_operation(self, caused_by: Optional[str] = None) -> "ExecutionContext":
        """A nested operation: new span, same trace, causation advanced.

        The correct way to enter a sub-operation. Reusing the parent context
        instead loses the causal edge, and reconstructing it by hand loses it
        more often.
        """
        correlation = (
            self.correlation.caused_by(caused_by)
            if caused_by
            else self.correlation.caused_by(self.request.request_id)
        )
        return ExecutionContext(
            identity=self.identity,
            tenancy=self.tenancy,
            trace=self.trace.child_span(),
            correlation=correlation,
            request=self.request,
            organization=self.organization,
            workspace=self.workspace,
            mission=self.mission,
            features=self.features,
            locale=self.locale,
        )

    def with_mission(self, mission_id: str, **fields: Any) -> "ExecutionContext":
        from dataclasses import replace

        return replace(self, mission=MissionContext.create(mission_id, **fields))

    def with_identity(self, identity: IdentityContext) -> "ExecutionContext":
        from dataclasses import replace

        return replace(self, identity=identity)

    def with_flags(self, flags: Mapping[str, bool]) -> "ExecutionContext":
        from dataclasses import replace

        return replace(self, features=FeatureFlagContext(dict(flags)))

    # ------------------------------------------------------------------
    # Boundary conversion
    # ------------------------------------------------------------------

    @property
    def scope(self) -> TenantScope:
        """The contract-vocabulary scope for crossing a context boundary."""
        return build_scope(self.tenancy, self.organization, self.workspace)

    @property
    def security_context(self) -> SecurityContext:
        """The contract every cross-context message must carry (BC-9)."""
        return SecurityContext(
            principal=self.identity.principal,
            scope=self.scope,
            capabilities=self.identity.capabilities,
            on_behalf_of=self.identity.on_behalf_of,
        )

    @property
    def tenant_id(self) -> str:
        return self.tenancy.tenant_id

    @property
    def is_platform_internal(self) -> bool:
        return self.tenancy.is_platform_internal

    def audit_detail(self) -> dict[str, Any]:
        """Context fields worth recording on an audit entry."""
        detail: dict[str, Any] = {
            "tenant_id": self.tenant_id,
            "principal_id": self.identity.principal_id,
            "principal_kind": self.identity.principal.kind.value,
            "request_id": self.request.request_id,
            "request_source": self.request.source,
            "trace_id": self.trace.trace_id,
            "span_id": self.trace.span_id,
        }
        if self.identity.on_behalf_of is not None:
            detail["on_behalf_of"] = self.identity.on_behalf_of.principal_id
        if self.organization is not None:
            detail["organization_id"] = self.organization.organization_id
        if self.workspace is not None:
            detail["workspace_id"] = self.workspace.workspace_id
        if self.mission is not None:
            detail["mission_id"] = self.mission.mission_id
        if self.tenancy.platform_internal_reason:
            detail["platform_internal_reason"] = self.tenancy.platform_internal_reason
        return detail
