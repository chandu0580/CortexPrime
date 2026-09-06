"""The product API's authenticated context. Tenant comes from the token, always.

Why this is a separate, very small module
-----------------------------------------
Phase 10.0 measured the reason: **89 of 96 V1 route modules contain no reference
to tenant at all**, and three take a tenant from a request body or query. A
product surface built on that habit would bypass the isolation the governed
engine spends its whole design enforcing.

So there is exactly one way for a product route to learn which tenant it is
serving, and it is this module. A route that wants a ``TenantRef`` depends on
:func:`product_context`; there is no other constructor reachable from the API
package, and no function here reads the request body, the query string, or a
header other than the one the existing authenticator already verifies.

What it reuses, and what it refuses to rebuild
----------------------------------------------
Authentication is **not** reimplemented. ``backend.auth.dependencies`` already
decodes the JWT, checks a revocation blacklist, and confirms the tenant exists
and is active -- and it reads ``tenant_id`` from the decoded token rather than
from the request. That is the property this phase needs, so this module adapts it
rather than replacing it.

This is a presentation adapter. It holds no authority: it cannot authorize,
approve, execute, or decide anything. It converts a verified identity into the
typed value the application services already require.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from fastapi import Depends, HTTPException, status

from backend.auth.dependencies import require_tenant
from backend.contracts.identity import PrincipalKind, PrincipalRef
from backend.contracts.tenant import TenantRef

__all__ = ["ProductContext", "product_context"]


@dataclass(frozen=True)
class ProductContext:
    """One authenticated product caller, resolved from a verified token.

    Frozen on purpose: a route that could mutate the tenant it was handed is a
    route that could serve one tenant's data under another's authority.
    """

    tenant: TenantRef
    principal: PrincipalRef
    roles: tuple

    @property
    def tenant_id(self) -> str:
        return self.tenant.tenant_id

    def execution_context(self) -> Any:
        """The platform's own context object, for services that require one.

        Built from the verified claims and nothing else. ``capabilities`` is
        deliberately empty: this phase is read-only, and a product caller holds
        no capability to invoke anything.
        """
        from backend.platform.context import ExecutionContext
        from backend.platform.context.identity import IdentityContext

        return ExecutionContext.for_tenant(
            tenant_id=self.tenant.tenant_id,
            identity=IdentityContext(principal=self.principal, capabilities=()),
            source="product-api",
        )


def _claim(claims: Mapping[str, Any], name: str) -> str:
    value = claims.get(name)
    return value.strip() if isinstance(value, str) else ""


async def product_context(
    claims: dict = Depends(require_tenant),
) -> ProductContext:
    """Resolve the caller. **The only source of tenant identity in this API.**

    ``require_tenant`` has already verified the signature, checked the token
    against the revocation list, and confirmed the tenant exists and is active.
    Everything below reads that verified payload.

    Note what is absent: no parameter of this function is a request body, query
    parameter or path parameter. A caller cannot influence which tenant it is
    resolved as, because nothing a caller sends is read here.
    """
    tenant_id = _claim(claims, "tenant_id")
    if not tenant_id:
        # Defence in depth: require_tenant already refuses this. Repeated here
        # because this function is the one place a missing tenant could turn
        # into an unscoped query, and that must fail closed rather than default.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="no tenant association in the authenticated identity",
        )

    subject = _claim(claims, "sub") or _claim(claims, "username")
    if not subject:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="the authenticated identity names no principal",
        )

    role = _claim(claims, "user_role")
    try:
        tenant = TenantRef(tenant_id=tenant_id)
        principal = PrincipalRef(principal_id=subject, kind=PrincipalKind.HUMAN)
    except Exception:  # noqa: BLE001 - a malformed identity is never a caller error to explain
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="the authenticated identity is not well formed",
        ) from None

    return ProductContext(
        tenant=tenant, principal=principal, roles=(role,) if role else ()
    )

def approver_authority(ctx: "ProductContext"):
    """This caller's approver authority, resolved LIVE from the store.

    A method on the context rather than a dependency, because it is asked in two
    places -- the queue projection and the decision route -- and both must ask
    the same question of the same source. Neither may consult a token claim: the
    session says who is calling, the store says what they may do.
    """
    from backend.auth.approver import resolve_approver_authority

    from backend.api.product.app import current_engine

    # Phase 10.8: the grants come from the durable, attributed store. Passing
    # the repository rather than reaching for a global keeps the dependency
    # explicit -- and a missing store refuses rather than reading an empty list
    # as "this person holds nothing".
    engine = current_engine()
    return resolve_approver_authority(
        principal_id=ctx.principal.principal_id, tenant_id=ctx.tenant_id,
        grants=getattr(engine, "grants", None))
