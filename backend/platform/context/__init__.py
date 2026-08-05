"""Request context runtime — the canonical context every operation receives.

    from backend.platform.context import ExecutionContext, IdentityContext

    context = ExecutionContext.for_tenant(
        tenant_id="acme",
        identity=IdentityContext.human("user-42", capabilities=("mission:create",)),
        source="http",
    )

    result = do_work(context, ...)          # explicit, always
    nested = context.child_operation()      # new span, causation advanced

Rules this package enforces in the type system
----------------------------------------------
**No default tenant.** ``TenantContext`` has no zero-argument form and no
fallback. An untenanted operation cannot be expressed.

**No implicit system tenant.** Work with genuinely no tenant uses
``platform_internal(reason=...)``, which demands a stated reason, reports
``is_platform_internal``, and uses a reserved id no real tenant may claim. The
gap is marked, not disguised.

**Never partially populated.** Identity, tenancy, trace, correlation, and
request metadata are mandatory. There is no builder and no mutable staging
object, so a half-built context cannot exist to be passed by accident.

**No global mutable context.** No ``contextvars``, no thread-locals, no
ambient lookup. An operation that can obtain a context without being given one
can also obtain the *wrong* one, and a cross-tenant read from a stale context
variable is easy to write and nearly invisible in review.

**Immutable.** Every ``with_*`` and ``child_*`` method returns a new instance.

Boundary conversion
-------------------
``context.scope`` and ``context.security_context`` produce the contract
vocabulary for crossing a bounded-context boundary (BC-9). Converting at the
edge keeps runtime context and published contract from drifting.

See ``docs/adr/ADR-017-request-context-runtime.md``.
"""

from __future__ import annotations

from backend.platform.context.identity import IdentityContext
from backend.platform.context.runtime import (
    ExecutionContext,
    FeatureFlagContext,
    LocaleContext,
    MissionContext,
    RequestMetadata,
)
from backend.platform.context.tenancy import (
    PLATFORM_INTERNAL_TENANT_ID,
    OrganizationContext,
    TenantContext,
    WorkspaceContext,
    build_scope,
)
from backend.platform.context.tracing import CorrelationContext, TraceContext

__all__ = [
    "ExecutionContext",
    "IdentityContext",
    "TenantContext",
    "OrganizationContext",
    "WorkspaceContext",
    "MissionContext",
    "TraceContext",
    "CorrelationContext",
    "FeatureFlagContext",
    "LocaleContext",
    "RequestMetadata",
    "PLATFORM_INTERNAL_TENANT_ID",
    "build_scope",
]
