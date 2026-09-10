"""The strangler boundary around V1 execution surfaces.

Why this exists
-----------------
Phase 3.3.3 built one governed path from an approved action to a running one. A
governed path is only worth having if it is the *only* path, and it is not: this
codebase predates it and carries HTTP endpoints that reach real providers without
passing through any of it.

Those endpoints are not deleted. Deleting behaviour somebody may depend on, on
the strength of an architecture document, is how a migration becomes an outage.
They are named here, gated behind one explicit flag, and refused by default —
which is the honest middle position between "leave a hidden bypass" and "break
production on a Tuesday".

What was found
----------------
Every route below can cause real external effects without a capability binding,
without an authorization decision, without a worker selection, and without an
audit record attributable to a tenant.

``/api/v2/mcp/execute`` is the sharpest. It takes an arbitrary tool name and an
arbitrary parameter dict, requires only that *some* user is authenticated, and
hands both to the V1 MCP gateway. There is no tenant in the request at all, so
there is nothing to check one against.

``/api/agents/run`` and ``/api/agents/delegate`` are the second. They read
``tenant_id`` from the request body. A tenant taken from the body is a tenant the
caller chose, which is the same as having none — and it is exactly the pattern
``ExecutionContext`` exists to make impossible.

The flag
----------
``CORTEXPRIME_ENABLE_LEGACY_EXECUTION`` — unset or falsey means these endpoints
refuse with ``503`` and a message naming the governed path. Set it only to
migrate something specific, and unset it afterwards.

Default-off is a deliberate behaviour change and is recorded as one in ADR-038.
The alternative was leaving a documented bypass switched on, which is a longer
way of saying the gate is optional.

Scope
-------
This gates *execution* surfaces. Read-only V1 routes (listing connectors, reading
tool definitions, health) are untouched: they expose no capability to act, and
sweeping them in would make the flag too expensive to keep off.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

__all__ = [
    "LEGACY_EXECUTION_FLAG",
    "LegacyExecutionSurface",
    "LEGACY_EXECUTION_SURFACES",
    "legacy_execution_enabled",
    "legacy_execution_refusal",
    "guard_legacy_execution",
    "LegacyExecutionRefused",
    "guard_legacy_internal",
]

log = logging.getLogger(__name__)

LEGACY_EXECUTION_FLAG = "CORTEXPRIME_ENABLE_LEGACY_EXECUTION"

_TRUE = {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class LegacyExecutionSurface:
    """One pre-existing route that can act without the gateway."""

    route: str
    module: str
    reaches: str
    gap: str
    gated: bool
    """Whether this module actually enforces the flag on that route. Recorded
    honestly: an inventory that implied coverage it does not have would be worse
    than no inventory, because it would be believed."""


#: The inventory. Every entry was found by reading the route, not inferred from a
#: name.
#:
#: **Phase 3.3.4 reconciled all ten.** Phase 3.3.3 gated the three sharpest and
#: reported seven; leaving a known privileged bypass switched on is a documented
#: hole rather than a boundary, so the remaining seven are now gated on the same
#: flag. Every one of them is privileged, every one bypasses the invocation
#: gateway, and none of them can be reached without the operator setting the flag
#: deliberately.
LEGACY_EXECUTION_SURFACES: tuple = (
    LegacyExecutionSurface(
        route="POST /api/v2/mcp/execute",
        module="backend.mcp.routes",
        reaches="the V1 MCP gateway and any registered MCP connector",
        gap="arbitrary tool name and params; no tenant in the request at all; "
        "no capability, binding, authorization, worker selection or audit",
        gated=True,
    ),
    LegacyExecutionSurface(
        route="POST /api/agents/run",
        module="backend.agents.routes",
        reaches="the V1 multi-agent coordinator and every tool it can call",
        gap="tenant_id is read from the request body, so the caller chooses its "
        "own tenant; no capability authorization and no binding",
        gated=True,
    ),
    LegacyExecutionSurface(
        route="POST /api/agents/delegate",
        module="backend.agents.routes",
        reaches="the V1 agent registry",
        gap="same body-supplied tenancy as /run",
        gated=True,
    ),
    LegacyExecutionSurface(
        route="POST /api/v1/runtime/execute",
        module="backend.api.runtime_api",
        reaches="the V1 execution manager's cognition pipeline",
        gap="no tenant binding, no capability authorization; runs the V1 "
        "cognition pipeline, which can reach every tool the runtime holds",
        gated=True,
    ),
    LegacyExecutionSurface(
        route="POST /api/executions/run",
        module="backend.execution.routes",
        reaches="the V1 execution service, which runs commands",
        gap="accepts a command string and an environment directly -- arbitrary "
        "command execution with no capability in sight",
        gated=True,
    ),
    LegacyExecutionSurface(
        route="POST /api/orchestrator/execute",
        module="backend.api.routes.orchestrator_routes",
        reaches="the V1 orchestrator",
        gap="no capability binding; drives the V1 master agent runtime",
        gated=True,
    ),
    LegacyExecutionSurface(
        route="POST /operator/execute",
        module="backend.api.operator_routes",
        reaches="operator tooling",
        gap="admin-guarded, which proves who is asking and not that the action "
        "was authorized against a capability, a binding and a worker",
        gated=True,
    ),
    LegacyExecutionSurface(
        route="POST /api/computer/execute-workflow",
        module="backend.api.computer_routes",
        reaches="computer-use automation",
        gap="no capability binding; drives computer-use automation",
        gated=True,
    ),
    LegacyExecutionSurface(
        route="POST /api/engineering/sandbox/{id}/execute",
        module="backend.api.enterprise_sandbox_routes",
        reaches="sandbox execution",
        gap="runs an arbitrary command string; sandboxed, but a sandbox is a "
        "containment boundary and not an authorization one",
        gated=True,
    ),
    LegacyExecutionSurface(
        route="POST /api/engineering/execute",
        module="backend.api.enterprise_engineering_routes",
        reaches="the enterprise engineering executor",
        gap="no capability binding; runs a full engineering workflow",
        gated=True,
    ),
    # ------------------------------------------------------------------
    # Phase 5.15 (ADR-058): the mission runtimes. Found by tracing actual
    # call paths, and the sharpest of them never crosses an HTTP route.
    # ------------------------------------------------------------------
    LegacyExecutionSurface(
        route="INTERNAL enterprise_mission_orchestrator.launch",
        module="backend.services.enterprise_mission_orchestrator",
        reaches="getattr(connector, operation)(**params) on the V1 connector "
        "registry -- real writes to GitHub/Jira/ServiceNow, plus recovery and "
        "rollback re-invocations by the same mechanism",
        gap="no tenant exists anywhere in the call; no capability, binding, "
        "authorization, worker selection, or durable audit; reachable from an "
        "always-on watcher timer and the continuous cognition loop with no "
        "HTTP request in the stack",
        gated=True,
    ),
    LegacyExecutionSurface(
        route="POST /api/missions/{mission_id}/execute",
        module="backend.mission.routes",
        reaches="the V1 mission dispatcher and its shell/HTTP sandboxes",
        gap="no capability authorization; V1 governance evaluation is "
        "optional and failures are swallowed",
        gated=True,
    ),
    LegacyExecutionSurface(
        route="POST /api/enterprise/missions/launch",
        module="backend.api.enterprise_mission_routes",
        reaches="enterprise_mission_orchestrator.launch (see the INTERNAL "
        "entry above)",
        gap="template and params chosen by the caller; no tenant in the "
        "request",
        gated=True,
    ),
    LegacyExecutionSurface(
        route="POST /execute (mission execution; router mounted unprefixed)",
        module="backend.api.mission_execution_routes",
        reaches="the V1 cognition mission runtime: LLM router, browser agent, "
        "computer agent",
        gap="no capability authorization and no binding; drives autonomous "
        "browser/computer actions",
        gated=True,
    ),
    # ------------------------------------------------------------------
    # Phase 11.1 (ADR-121): surfaces the Phase 9.11 "0 ungated surfaces"
    # census did not see, because they never mentioned execution by name.
    # Found by reading every POST on the infrastructure, GitHub and approval
    # centre routers for what it reaches, not what it is called.
    # ------------------------------------------------------------------
    LegacyExecutionSurface(
        route="POST /api/infrastructure/terraform/{init,plan,apply,destroy,workspaces/select}",
        module="backend.api.enterprise_infrastructure_routes",
        reaches="the terraform connector: a terraform subprocess against the "
        "deployment's working directory and real cloud providers (apply and "
        "destroy are irreversible)",
        gap="until this phase: no authentication of any kind, no tenant, no "
        "capability, no approval, no audit; caller-chosen workspace and var "
        "file",
        gated=True,
    ),
    LegacyExecutionSurface(
        route="POST /api/infrastructure/argocd/applications/{name}/{sync,refresh,rollback}",
        module="backend.api.enterprise_infrastructure_routes",
        reaches="the ArgoCD connector: syncs and rolls back live applications",
        gap="until this phase: no authentication, no tenant, no capability, no "
        "approval; caller-chosen application and revision",
        gated=True,
    ),
    LegacyExecutionSurface(
        route="POST /api/github/{translate,launch-mission}",
        module="backend.api.enterprise_github_routes",
        reaches="the enterprise engineering executive: creates a task, plans it "
        "and executes the plan from a caller-supplied webhook payload",
        gap="until this phase: no authentication; the payload -- commit "
        "messages, PR titles -- became the mission objective verbatim, which is "
        "untrusted text becoming an instruction",
        gated=True,
    ),
    LegacyExecutionSurface(
        route="POST /api/approval-center/workflows[/{id}/{approve,reject,delegate,break-glass}]",
        module="backend.api.approval_center_routes",
        reaches="the V1 approval workflow engine and, through "
        "enterprise_approval_action_dispatcher, the deploy-rollback, "
        "vulnerability-fix, branch-protection, docker-health and cost-anomaly "
        "executors (real provider writes)",
        gap="a second approval authority beside cp_approval (ADR-090/113): "
        "in-memory, no tenant, no action digest, and until this phase the "
        "approver identity was a query parameter the caller chose",
        gated=True,
    ),
)


def legacy_execution_enabled() -> bool:
    """Whether V1 execution surfaces are permitted. Default **no**.

    Read at call time rather than import time so the flag can be flipped for a
    migration without a restart, and so a test cannot leave it latched on for
    every module imported after it.
    """
    return os.environ.get(LEGACY_EXECUTION_FLAG, "").strip().lower() in _TRUE


def legacy_execution_refusal(route: str) -> str:
    """The message a refused legacy call receives. No internal detail."""
    return (
        f"{route} is a V1 execution surface and is disabled. Execution reaches a "
        "provider through the governed Mission Control path: an approved workflow, "
        "a capability binding, a worker selection, and the invocation gateway. "
        f"Set {LEGACY_EXECUTION_FLAG}=1 only to perform a specific migration."
    )


def guard_legacy_execution(route: str):
    """A FastAPI dependency that refuses unless the flag is set.

    Returns a callable rather than being one so each route names itself in its
    own refusal — an operator who hits this needs to know which endpoint they
    reached, and a generic message sends them looking through the whole
    inventory.
    """

    def _guard() -> None:
        if legacy_execution_enabled():
            # Loud on purpose. A bypass that is in use should be visible in the
            # log every time, not discovered later in an audit.
            log.warning(
                "legacy execution surface %s used with %s enabled; this path is "
                "not governed by the invocation gateway",
                route,
                LEGACY_EXECUTION_FLAG,
            )
            return
        from fastapi import HTTPException

        raise HTTPException(status_code=503, detail=legacy_execution_refusal(route))

    return _guard


class LegacyExecutionRefused(RuntimeError):
    """A V1 execution surface was reached internally while disabled.

    Phase 5.15 found execution paths that never cross an HTTP route at all —
    the watcher → autonomous-mission-generator → orchestrator chain launches
    missions that write to real providers from a background timer. A FastAPI
    dependency cannot gate those. This exception is the internal form of the
    same refusal: same flag, same message, no second mechanism.
    """


def guard_legacy_internal(surface: str) -> None:
    """Refuse an internal V1 execution surface unless the flag is set.

    The non-HTTP twin of :func:`guard_legacy_execution`, for call sites that
    are reached by background loops and internal callers rather than routes.
    Raises :class:`LegacyExecutionRefused`; callers that already contain
    failures (the autonomous mission generator, the watcher poll loop) degrade
    to "mission not created" with the reason in the log, which is the correct
    behaviour for an autonomous action the platform cannot yet govern.
    """
    if legacy_execution_enabled():
        log.warning(
            "legacy execution surface %s used with %s enabled; this path is "
            "not governed by the invocation gateway",
            surface,
            LEGACY_EXECUTION_FLAG,
        )
        return
    raise LegacyExecutionRefused(legacy_execution_refusal(surface))


def ungated_surfaces() -> tuple:
    """V1 surfaces reported but not enforced. **Empty again as of Phase 5.15.**

    Kept rather than deleted: it is the assertion that nothing was found and
    left open. Phase 5.15 falsified the previous "empty as of 3.3.4" claim —
    three mission HTTP routes and two internal launch paths executed provider
    operations ungated — and re-established it by gating all five on the same
    flag. A future surface added without a guard shows up here rather than in
    an incident, which is the only reason a function that returns nothing
    earns its place.
    """
    return tuple(s for s in LEGACY_EXECUTION_SURFACES if not s.gated)
