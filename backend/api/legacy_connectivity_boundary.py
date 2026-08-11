"""The strangler boundary around V1 *connectivity* surfaces.

Why a second boundary
-----------------------
ADR-038's boundary gates V1 **execution** routes — the ones that run something.
Phase 4.4's reconciliation found a category it never covered, and which was
sitting in exactly the state §31 of the Phase 4.4 directive warns about:
**reachable but forgotten**.

Three kinds of route, none of them "execution", all of them producing external
side effects or holding credentials:

``credential configuration``  ``POST /api/connectors/{type}/connect`` and
                              ``/test`` take a **credential in the request body**
                              and write it into a process-wide connector
                              singleton. One authenticated user therefore sets a
                              provider credential for every tenant in the
                              process. There is no tenant in the request at all,
                              so there is nothing to check one against.

``lifecycle mutation``        ``/disconnect`` and ``/refresh`` mutate that same
                              global. Any authenticated user can shut down every
                              tenant's connector.

``outbound provider reads``   ``GET /api/connectors/github/repos`` and a dozen
                              siblings make authenticated calls to real providers
                              using a process-wide environment credential, with
                              no tenant, no capability and no authorization.

Plus one registry-mutation route: ``POST /api/v2/mcp/connectors/register``
inserts into the global MCP registry, whose ``execute`` resolves a tool **by
name across every registered connector, first match wins**. Registering a
connector that claims an existing tool name shadows it for the whole process.

Authentication is not authorization
-------------------------------------
Every one of these requires a valid user. That proves who is asking. It does not
prove the action was authorized against a capability, a binding and a tenant —
which is the distinction the whole of Phase 3 established and the reason none of
these belongs on a production path.

The flag, and why it is a separate one
----------------------------------------
``CORTEXPRIME_ENABLE_LEGACY_CONNECTIVITY``, default off, deliberately **not**
``CORTEXPRIME_ENABLE_LEGACY_EXECUTION``. An operator migrating a workflow needs
to turn execution back on for a specific run; that must not simultaneously
reopen a route that writes provider credentials into a global. Two levers because
they are two decisions.

The behaviour change, stated plainly
--------------------------------------
Turning these off by default **breaks the connector configuration UI and the
live connector dashboards** until they move to the governed path. That is a real
cost and it is the correct trade: the alternative is leaving a credential-writing
endpoint open because a page renders from it.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

__all__ = [
    "LEGACY_CONNECTIVITY_FLAG",
    "LegacyConnectivitySurface",
    "LEGACY_CONNECTIVITY_SURFACES",
    "legacy_connectivity_enabled",
    "legacy_connectivity_refusal",
    "guard_legacy_connectivity",
    "ungated_surfaces",
    "summary",
]

log = logging.getLogger(__name__)

LEGACY_CONNECTIVITY_FLAG = "CORTEXPRIME_ENABLE_LEGACY_CONNECTIVITY"

_TRUE = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LegacyConnectivitySurface:
    """One pre-existing route that reaches a provider or holds a credential."""

    route: str
    module: str
    kind: str
    """``credential_write`` | ``lifecycle_mutation`` | ``provider_read`` |
    ``registry_write``. Recorded because the four need different replacements
    and merging them would hide which."""

    finding: str
    gated: bool
    """Whether this module actually enforces the flag. Recorded honestly: an
    inventory implying coverage it does not have is worse than none, because it
    is believed."""


LEGACY_CONNECTIVITY_SURFACES: tuple = (
    LegacyConnectivitySurface(
        route="POST /api/connectors/{type}/connect",
        module="backend.api.connector_routes",
        kind="credential_write",
        finding="Accepts a provider credential in the request body and calls "
        "``conn.configure(body.credentials)`` on the process-wide connector "
        "singleton, then dials the provider. One authenticated user sets a "
        "credential for every tenant in the process. No tenant appears anywhere "
        "in the request, so there is nothing to check one against. The "
        "credential is not the caller's to set and not the process's to hold.",
        gated=True,
    ),
    LegacyConnectivitySurface(
        route="POST /api/connectors/{type}/test",
        module="backend.api.connector_routes",
        kind="credential_write",
        finding="Same body-supplied credential as ``/connect``, plus an "
        "outbound authenticated call, plus a ``shutdown()`` afterwards that "
        "clears whatever the process was using.",
        gated=True,
    ),
    LegacyConnectivitySurface(
        route="POST /api/connectors/{type}/disconnect",
        module="backend.api.connector_routes",
        kind="lifecycle_mutation",
        finding="Shuts down a connector shared by the whole process. Any "
        "authenticated user can stop every tenant's integration.",
        gated=True,
    ),
    LegacyConnectivitySurface(
        route="POST /api/connectors/{type}/refresh",
        module="backend.api.connector_routes",
        kind="lifecycle_mutation",
        finding="Re-initialises the shared connector, which re-reads the "
        "process environment credential and dials the provider.",
        gated=True,
    ),
    LegacyConnectivitySurface(
        route="GET /api/connectors/{github,jira,slack,teams,azure-devops,"
        "confluence,servicenow,notion}/**",
        module="backend.api.connector_routes",
        kind="provider_read",
        finding="Roughly fourteen routes making authenticated outbound calls to "
        "real providers with a process-wide environment credential. Read-only "
        "at the provider, and still an external side effect performed with no "
        "tenant, no capability, no binding and no audit attributable to one. "
        "They also return ``str(e)`` on failure, and an httpx exception carries "
        "the request it was making.",
        gated=True,
    ),
    LegacyConnectivitySurface(
        route="POST /api/v2/mcp/connectors/register",
        module="backend.mcp.routes",
        kind="registry_write",
        finding="Inserts a caller-named connector with caller-named tools into "
        "the global ``mcp_registry``. ``MCPRegistry.execute`` resolves a tool by "
        "name across every registered connector and calls the first match, so a "
        "registration can shadow an existing tool name for the whole process. "
        "No tenant, and the registration outlives the request.",
        gated=True,
    ),
)


def legacy_connectivity_enabled() -> bool:
    """Whether V1 connectivity surfaces are permitted. Default **no**.

    Read at call time rather than import time so the flag can be flipped for a
    migration without a restart, and so a test cannot leave it latched on for
    every module imported after it.
    """
    return os.environ.get(LEGACY_CONNECTIVITY_FLAG, "").strip().lower() in _TRUE


def legacy_connectivity_refusal(route: str) -> str:
    """The message a refused legacy connectivity call receives."""
    return (
        f"{route} is a V1 connectivity surface and is disabled. Provider "
        "credentials are issued by the credential fabric against an authorized "
        "action, and provider calls reach a provider through the invocation "
        "gateway, a capability binding and a governed adapter. "
        f"Set {LEGACY_CONNECTIVITY_FLAG}=1 only to perform a specific migration."
    )


def guard_legacy_connectivity(route: str):
    """A FastAPI dependency that refuses unless the flag is set.

    Returns a callable rather than being one so each route names itself in its
    own refusal — an operator who hits this needs to know which endpoint they
    reached, and a generic message sends them through the whole inventory.
    """

    def _guard() -> None:
        if legacy_connectivity_enabled():
            # Loud every time. A bypass in use should be visible in the log as it
            # happens, not discovered later in an audit.
            log.warning(
                "legacy connectivity surface %s used with %s enabled; this path "
                "holds credentials outside the credential fabric and reaches "
                "providers outside the transport fabric",
                route,
                LEGACY_CONNECTIVITY_FLAG,
            )
            return
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=legacy_connectivity_refusal(route))

    return _guard


def ungated_surfaces() -> tuple:
    """Surfaces reported but not enforced. **Empty as of Phase 4.4.**

    Kept rather than deleted: it is the assertion that nothing was found and
    left open. A future surface added without a guard shows up here rather than
    in an incident.
    """
    return tuple(s for s in LEGACY_CONNECTIVITY_SURFACES if not s.gated)


def summary() -> dict:
    return {
        "flag": LEGACY_CONNECTIVITY_FLAG,
        "enabled": legacy_connectivity_enabled(),
        "total": len(LEGACY_CONNECTIVITY_SURFACES),
        "ungated": [s.route for s in ungated_surfaces()],
        "by_kind": {
            kind: [s.route for s in LEGACY_CONNECTIVITY_SURFACES if s.kind == kind]
            for kind in sorted({s.kind for s in LEGACY_CONNECTIVITY_SURFACES})
        },
        "note": (
            "These are not execution routes, which is why the ADR-038 boundary "
            "did not cover them. They configure credentials, mutate shared "
            "connector state, read from providers, or write to a global "
            "registry -- each an external side effect or a credential surface "
            "with no tenant."
        ),
    }
