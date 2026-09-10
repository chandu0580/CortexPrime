"""The authentication perimeter of the V1 application — Phase 11.1 (ADR-121).

Why one perimeter instead of ninety router edits
--------------------------------------------------
Phase 11.0 counted the V1 surface honestly: 180 routers, of which roughly ninety
declare no authentication at router or route level — 394 unauthenticated
state-changing routes and 543 unauthenticated reads at the start of this phase
(``docs/PHASE_11_1_IMPLEMENTATION_MAP.md`` carries the census). Editing each
router is a rewrite, and a rewrite is how a boundary phase becomes an outage.

So authentication is enforced **once, at the edge, by default**. Every HTTP
request into ``backend.main`` must carry a verified access token unless its path
is on one of two explicit lists:

``PUBLIC``          paths that must work before anyone has a token: health,
                    OpenAPI, the auth endpoints themselves, the Prometheus
                    scrape.
``SIGNED_INGRESS``  machine ingress that authenticates by a provider secret
                    instead of a token: the GitHub HMAC webhook and the GitLab
                    token webhook. The perimeter lets them through **because
                    the route verifies the signature itself and refuses
                    anything unverified** (``backend.safety.ingress_boundary``).

Everything else is default-deny. A route that was never written with
authentication in mind is therefore no longer reachable without it, and a new
route added tomorrow inherits the perimeter rather than escaping it.

Verification is not re-implemented. The perimeter calls the same
``verify_request_token`` that ``require_user`` uses: signature, expiry, and the
Redis revocation list (fail-closed unless ``REVOCATION_FAIL_OPEN`` says
otherwise, which is that module's decision, not this one's).

The V1 tenant fence (decision D1, interpreted as FENCE for this phase)
------------------------------------------------------------------------
The V1 surface is tenant-unaware: 35 of 57 tables carry no ``tenant_id`` and
its Redis and JSON stores carry no tenant either. It cannot *scope* data by
tenant without a rewrite, so this phase makes the only honest statement it can:
**a V1 deployment serves one tenant**, and says which.

``CORTEXPRIME_V1_TENANT_ID``:

* declared — a token is admitted only when its verified ``tenant_id`` equals the
  declared tenant. Any other tenant, and any token with no tenant, is refused
  with 403. A second tenant cannot read the first tenant's memory, replay,
  knowledge or incidents through V1 routes, because it cannot reach them.
* undeclared — only tokens that carry **no** tenant claim are admitted (the
  single-operator deployment, which is what every local install is). A token
  that carries a tenant is refused with an instruction to declare the binding,
  because "which tenant does this data belong to" is exactly the question the
  V1 stores cannot answer.

The governed plane is unaffected: the product API is a separate process
(ADR-094) with ``product_context`` as its only tenant source, and the tenant
administration routes in this process (``/api/tenants``) are exempt from the
fence because they are governed, admin-only and tenant-aware by construction.

What this is not
------------------
Authentication is not authorization. Passing the perimeter proves who is
asking and which tenant they hold; it grants nothing. Routes that act still
need their own authority (``require_admin``, the legacy execution guard, the
governed approval path). The perimeter closes the "no identity at all" hole;
it does not open anything.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Callable, Optional, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

log = logging.getLogger(__name__)

__all__ = [
    "V1_TENANT_ENV",
    "PUBLIC_EXACT",
    "PUBLIC_PREFIXES",
    "SIGNED_INGRESS",
    "FENCE_EXEMPT_PREFIXES",
    "PerimeterIdentity",
    "declared_v1_tenant",
    "v1_tenant_verdict",
    "is_public_path",
    "is_signed_ingress",
    "AuthPerimeterMiddleware",
]

#: The one tenant a V1 deployment serves. See the module docstring.
V1_TENANT_ENV = "CORTEXPRIME_V1_TENANT_ID"

#: Paths reachable without a token. Exact matches.
PUBLIC_EXACT = frozenset(
    {
        "/",
        "/health",
        "/metrics",
        "/openapi.json",
        "/docs",
        "/redoc",
        "/api/v1/health",
    }
)

#: Path prefixes reachable without a token. ``/api/auth/`` is here because the
#: routes that mint tokens cannot require one; the auth routes that do need a
#: token (``/me``, ``/revoke-all``, ``/admin/*``) enforce it themselves.
PUBLIC_PREFIXES: tuple = (
    "/health/",
    "/docs/",
    "/redoc/",
    "/openapi",
    "/favicon",
    "/static/",
    "/_next/",
    "/api/auth/",
)

#: Machine ingress authenticated by a provider secret, verified by the route.
#: Adding a path here without a verifying route is a hole; the ingress boundary
#: tests pin every entry to its verifier.
SIGNED_INGRESS = frozenset({"/api/github/webhook", "/api/gitlab/webhook"})

#: Authenticated paths the V1 tenant fence does not apply to: governed,
#: tenant-aware surfaces living in this process.
FENCE_EXEMPT_PREFIXES: tuple = ("/api/auth/", "/api/tenants")


@dataclass(frozen=True)
class PerimeterIdentity:
    """What the perimeter established. Read from ``request.state.perimeter``."""

    principal_id: str
    tenant_id: Optional[str]
    role: str
    user_role: str
    token_id: str

    def to_dict(self) -> dict:
        return {
            "principal_id": self.principal_id,
            "tenant_id": self.tenant_id,
            "role": self.role,
            "user_role": self.user_role,
        }


def declared_v1_tenant() -> Optional[str]:
    """The tenant the V1 surface is bound to, or ``None`` when undeclared.

    Read at call time, never cached: the fence must follow the deployment's
    configuration, and a test must not be able to latch it for later tests.
    """
    value = os.environ.get(V1_TENANT_ENV, "").strip()
    return value or None


def v1_tenant_verdict(token_tenant: Optional[str]) -> Tuple[bool, str]:
    """Whether an identity holding ``token_tenant`` may use the V1 surface.

    Returns ``(admitted, reason)``. The reason is written to the audit trail and
    returned to the caller; it names the rule, never a secret.
    """
    declared = declared_v1_tenant()
    held = (token_tenant or "").strip() or None
    if declared is not None:
        if held == declared:
            return True, "declared_tenant"
        if held is None:
            return False, (
                "the V1 surface is bound to a single tenant and this identity "
                "holds no tenant membership"
            )
        return False, (
            "the V1 surface is bound to a single tenant and this identity "
            "belongs to a different one"
        )
    if held is None:
        return True, "single_operator"
    return False, (
        "the V1 surface serves one tenant per deployment and none is declared; "
        f"set {V1_TENANT_ENV} to the tenant this deployment serves"
    )


def is_public_path(path: str) -> bool:
    if path in PUBLIC_EXACT:
        return True
    # Every subsystem health probe (``/governance/health``, ``/operator/health``,
    # ``/api/voice/v2/health``, ...) is a liveness signal the deployment's own
    # probes call before anyone holds a token; the existing auth-enforcement
    # contract (tests/test_auth_enforcement.py) already names them public.
    # Only the exact last segment qualifies -- ``/health/llm/providers`` does
    # not -- and a router that wants its probe authenticated still can be.
    if path.endswith("/health"):
        return True
    return any(path.startswith(prefix) for prefix in PUBLIC_PREFIXES)


def is_signed_ingress(path: str) -> bool:
    return path in SIGNED_INGRESS


def _fence_exempt(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in FENCE_EXEMPT_PREFIXES)


def _client_host(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _request_id(request: Request) -> Optional[str]:
    return getattr(request.state, "request_id", None)


async def _audit_refusal(request: Request, *, action: str, reason: str,
                         principal: str, tenant_id: Optional[str]) -> None:
    """Tenant refusals are security decisions about a known identity; record them.

    Anonymous 401s are logged, not audited: they carry no identity to attribute
    and a flood of them would be noise in the ledger rather than evidence.
    """
    try:
        from backend.safety.audit_logger import audit_logger

        # Fire-and-forget (cached in process, persisted asynchronously) so an
        # unreachable audit database cannot hold the refusal for a connect
        # timeout. The refusal itself is already decided.
        audit_logger.log(
            execution_id=f"perimeter:{_request_id(request) or 'no-request-id'}",
            agent="auth_perimeter",
            user=principal,
            action=action,
            target=request.url.path,
            risk_level="medium",
            outcome="blocked",
            reason=reason,
            request_id=_request_id(request),
            metadata={
                "method": request.method,
                "path": request.url.path,
                "tenant_id": tenant_id,
                "client": _client_host(request),
            },
        )
    except Exception as exc:  # noqa: BLE001 - audit must not turn a refusal into a 500
        log.warning("perimeter audit write failed (refusal still enforced): %s", exc)


class AuthPerimeterMiddleware(BaseHTTPMiddleware):
    """Default-deny authentication at the edge of ``backend.main``.

    Mounted just inside the rate limiter (so floods are shed before signature
    checks) and outside everything else (so no route, middleware or dependency
    below it ever sees an unauthenticated request to a non-public path).
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        path = request.url.path

        # Pre-flight and WebSocket upgrades are not API calls: CORS answers the
        # former, the WebSocket gateway authenticates the latter by cookie.
        if request.method == "OPTIONS":
            return await call_next(request)
        if request.headers.get("upgrade", "").lower() == "websocket":
            return await call_next(request)
        if is_public_path(path) or is_signed_ingress(path):
            return await call_next(request)

        from backend.auth.dependencies import verify_request_token

        try:
            claims = await verify_request_token(
                request.headers.get("authorization"),
                request.cookies.get("cortex_access"),
            )
        except Exception as exc:  # noqa: BLE001 - a verifier crash is a refusal, never a pass
            log.error("token verification raised; refusing request: %s", exc)
            claims = None

        if not claims:
            log.warning(
                "perimeter refused %s %s from %s: no valid token",
                request.method, path, _client_host(request),
            )
            return JSONResponse(
                status_code=401,
                content={
                    "error": "authentication_required",
                    "detail": "Authentication required",
                },
                headers={"WWW-Authenticate": "Bearer"},
            )

        principal = str(claims.get("sub") or "")
        tenant_id = claims.get("tenant_id")
        tenant_id = str(tenant_id).strip() if tenant_id else None

        if not _fence_exempt(path):
            admitted, reason = v1_tenant_verdict(tenant_id)
            if not admitted:
                log.warning(
                    "perimeter refused %s %s for principal=%s tenant=%s: %s",
                    request.method, path, principal, tenant_id, reason,
                )
                await _audit_refusal(
                    request, action="perimeter.tenant_refused", reason=reason,
                    principal=principal or "unknown", tenant_id=tenant_id,
                )
                return JSONResponse(
                    status_code=403,
                    content={"error": "tenant_not_admitted", "detail": reason},
                )

        request.state.perimeter = PerimeterIdentity(
            principal_id=principal,
            tenant_id=tenant_id,
            role=str(claims.get("role") or ""),
            user_role=str(claims.get("user_role") or ""),
            token_id=str(claims.get("jti") or ""),
        )
        return await call_next(request)
