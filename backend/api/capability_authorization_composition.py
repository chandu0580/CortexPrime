"""Composition root for capability authorization.

Builds the authorization service and — the point of Phase 3.2.3 — installs it as
the registry's ``RegistrationGuard``, replacing ``OpenRegistration``.

Why the guard is wired here rather than inside the context
------------------------------------------------------------
The registry defines the ``RegistrationGuard`` Protocol (ADR-032) and the
authorization service implements it. Both live in BC-8, so no boundary is
crossed — but *which* policy a deployment runs, whether an approval system is
reachable, and whether audit is durable are deployment decisions. Keeping the
assembly in one named module means a reviewer can answer "what actually governs
this platform?" by reading one file.

The two contexts still do not know each other. Nothing here imports Execution,
Workflow, Mission, Intent or Planner, and nothing in those imports this.

What is deliberately *not* wired
----------------------------------
There is no adapter to the V1 RBAC/ABAC modules in ``backend/identity`` or
``backend/security_center``. Adapting them means deciding how their role model
maps onto capability operations, and getting that mapping wrong would quietly
grant lifecycle powers nobody intended. That mapping is a decision to make
deliberately with the people who own those modules, not one to infer here.

Until then the platform runs ``GrantBackedPolicy``, which reads the grants the
authenticated identity already carries. Swapping in an OPA or RBAC adapter is a
one-line change at this seam.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from backend.contexts.connectivity import (
    CapabilityAuthorizationService,
    CapabilityService,
    PolicyBackedRegistrationGuard,
)

__all__ = ["build_authorization", "install_registration_guard", "governed_registry"]

log = logging.getLogger(__name__)


def build_authorization(
    registry: CapabilityService,
    *,
    policy: Optional[Any] = None,
    approvals: Optional[Any] = None,
    audit: Optional[Any] = None,
) -> CapabilityAuthorizationService:
    """The authorization service this deployment runs.

    ``policy=None`` uses the guarded grant-backed default. ``approvals=None``
    means no approval system is reachable, and every approval lookup therefore
    fails closed — a request that policy says needs approval will be refused
    rather than waved through.
    """
    return CapabilityAuthorizationService(
        registry=registry, policy=policy, approvals=approvals, audit=audit
    )


def install_registration_guard(
    registry: CapabilityService, authorization: CapabilityAuthorizationService
) -> CapabilityService:
    """Replace ``OpenRegistration`` on an existing registry service.

    Mutates the service's private guard deliberately, because the alternative is
    rebuilding the service and losing whatever it already holds. This is the one
    place that reaches in, and it exists so the swap happens exactly once at
    startup rather than being threaded through every construction site.
    """
    registry._guard = PolicyBackedRegistrationGuard(authorization)  # noqa: SLF001
    log.info(
        "capability registration is now policy-governed (%s)",
        authorization.policy_version,
    )
    return registry


def governed_registry(
    registry: CapabilityService,
    *,
    policy: Optional[Any] = None,
    approvals: Optional[Any] = None,
    audit: Optional[Any] = None,
) -> tuple:
    """Build authorization and install it. Returns ``(registry, authorization)``."""
    authorization = build_authorization(
        registry, policy=policy, approvals=approvals, audit=audit
    )
    return install_registration_guard(registry, authorization), authorization
