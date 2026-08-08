"""Composition root for capability discovery: V1 registries → BC-8 candidates.

**This is the only module that imports both the Connectivity context and the V1
registries**, and that is why it lives at the API layer. A bounded context may
not import ``backend.mcp``, ``backend.connectors`` or ``backend.agents``
(Constitution S2), and it should not want to: those are strangler targets whose
shapes will change or disappear.

The boundary between them is ``RawObservation`` — plain primitives. Nothing
V1-shaped reaches the domain, so when the V1 registries are eventually removed
only this file changes.

Nothing here performs a network call
--------------------------------------
Every adapter reads information the platform already holds locally:

* **MCP** — ``MCPConnector.get_tools()`` returns tool definitions that came from
  the connector's own configuration. There is no remote round trip in the V1
  implementation, so none is made here. A remote transport needs a credential
  story that does not yet exist, and inventing one to raise a feature count
  would be inventing the security model with it.
* **Connectors** — ``ConnectorRegistry.get_all_operations()`` returns declared
  operation metadata.
* **Agents** — the agent registry lists what agents claim they can do.

Everything these adapters read is a **claim**. An agent asserting it can deploy
to production is an assertion by the agent about itself, which is precisely why
``CapabilitySource.AGENT`` and ``MCP`` are marked ``is_self_declared``.

Why every adapter produces INCOMPLETE candidates
--------------------------------------------------
None of these sources declares a side-effect class, effect semantics, or an
isolation tier. Those are the three facts that decide whether something may run
twice, and how far it must be sandboxed. No adapter supplies a default for them.

The result is that discovery from these sources yields *incomplete* candidates
which cannot be ingested until a human states the missing facts. That is not a
gap in the adapters — it is the design. The alternative is guessing the effect
class of a tool called ``delete_everything``, and there is no safe guess.
"""

from __future__ import annotations

import logging
from typing import Any, Iterable, Optional, Sequence

from backend.contexts.connectivity import (
    CapabilitySource,
    DiscoveryEndpoint,
    RawObservation,
    SourceHealth,
    StaticObservationSource,
    UnsafeEndpoint,
)

__all__ = [
    "mcp_source",
    "connector_source",
    "agent_source",
    "manual_source",
    "available_sources",
]

log = logging.getLogger(__name__)


def _endpoint(value: Optional[str]) -> Optional[DiscoveryEndpoint]:
    """Record an endpoint if it is safe to hold; drop it if not.

    A source whose endpoint is unusable is still a source worth inventorying —
    losing the whole observation because a URL had a password in it would hide
    the very thing somebody needs to see. So the endpoint is dropped, the
    observation is kept, and the reason is logged.
    """
    if not value:
        return None
    try:
        return DiscoveryEndpoint.parse(value)
    except UnsafeEndpoint as exc:
        log.warning("discovery endpoint refused: %s", exc)
        return None


# ----------------------------------------------------------------------
# MCP
# ----------------------------------------------------------------------


def mcp_source(registry: Any = None, *, source_id: str = "mcp-local"):
    """Adapt the V1 MCP registry into a discovery source.

    An MCP **server** is a provider; an MCP **tool** is a capability. They are
    kept apart here: each tool becomes its own candidate, and the server travels
    as ``server_name`` and as the identity's provider segment. Collapsing them
    would make one unreachable server look like one broken capability rather
    than like every capability that server exposes being unavailable.
    """
    observations: list = []
    health = SourceHealth.HEALTHY
    error: Optional[str] = None

    try:
        if registry is None:
            from backend.mcp.registry import MCPRegistry  # noqa: PLC0415

            registry = MCPRegistry()
        connectors = list(getattr(registry, "_connectors", {}).values()) or []
        for connector in connectors:
            server = getattr(connector, "name", None) or "unknown"
            config = getattr(connector, "config", None)
            endpoint = _endpoint(getattr(config, "endpoint", None) or getattr(config, "url", None))
            for tool in connector.get_tools() or ():
                observations.append(
                    RawObservation(
                        source_id=source_id,
                        source_type=CapabilitySource.MCP,
                        name=getattr(tool, "name", ""),
                        description=getattr(tool, "description", ""),
                        provider=server,
                        namespace="platform",
                        capability=getattr(tool, "name", ""),
                        interface="mcp_tool",
                        endpoint=endpoint,
                        server_name=server,
                        input_schema=getattr(tool, "input_schema", None),
                        output_schema=getattr(tool, "output_schema", None),
                        # No side_effect_class, effect_semantics or
                        # isolation_tier: MCP does not carry them, and this
                        # adapter does not invent them.
                        raw={
                            "server": server,
                            "tool": getattr(tool, "name", ""),
                            "protocol": "mcp",
                        },
                    )
                )
    except Exception as exc:  # noqa: BLE001 - a broken registry is a health fact
        health, error = SourceHealth.UNAVAILABLE, f"{type(exc).__name__}: {exc}"
        observations = []

    return StaticObservationSource(
        source_id, CapabilitySource.MCP, observations, health=health, error=error
    )


# ----------------------------------------------------------------------
# Connectors
# ----------------------------------------------------------------------


def connector_source(registry: Any = None, *, source_id: str = "connectors-v1"):
    """Adapt V1 connector operation metadata into a discovery source."""
    observations: list = []
    health = SourceHealth.HEALTHY
    error: Optional[str] = None

    try:
        if registry is None:
            from backend.connectors.registry import ConnectorRegistry  # noqa: PLC0415

            registry = ConnectorRegistry()
        operations = registry.get_all_operations() or {}
        for connector_type, ops in operations.items():
            for operation_name, meta in (ops or {}).items():
                description = ""
                if isinstance(meta, dict):
                    description = str(meta.get("description", ""))
                observations.append(
                    RawObservation(
                        source_id=source_id,
                        source_type=CapabilitySource.CONNECTOR_PACKAGE,
                        name=operation_name,
                        description=description,
                        provider=connector_type,
                        namespace="platform",
                        capability=connector_type,
                        operation=operation_name,
                        interface="connector",
                        input_schema=(
                            meta.get("parameters") if isinstance(meta, dict) else None
                        ),
                        raw={"connector": connector_type, "operation": operation_name},
                    )
                )
    except Exception as exc:  # noqa: BLE001
        health, error = SourceHealth.UNAVAILABLE, f"{type(exc).__name__}: {exc}"
        observations = []

    return StaticObservationSource(
        source_id,
        CapabilitySource.CONNECTOR_PACKAGE,
        observations,
        health=health,
        error=error,
    )


# ----------------------------------------------------------------------
# Agents
# ----------------------------------------------------------------------


def agent_source(registry: Any = None, *, source_id: str = "agents-v1"):
    """Adapt what agents claim they can do.

    Claims about themselves, and marked as such: ``CapabilitySource.AGENT`` is
    ``is_self_declared``, which travels with the candidate and into the
    registered capability's metadata. Nothing here launches an agent, imports an
    agent runtime into the domain, or treats an agent's self-description as
    evidence of anything beyond what it said.
    """
    observations: list = []
    health = SourceHealth.HEALTHY
    error: Optional[str] = None

    try:
        if registry is None:
            from backend.runtime.agent_registry import AgentRegistry  # noqa: PLC0415

            registry = AgentRegistry()
        listed = registry.list_agents() if hasattr(registry, "list_agents") else []
        for agent in listed or ():
            agent_id = str(agent.get("agent_id") or agent.get("id") or "unknown")
            agent_type = str(agent.get("agent_type") or agent.get("type") or "agent")
            for claimed in agent.get("capabilities", ()) or ():
                observations.append(
                    RawObservation(
                        source_id=source_id,
                        source_type=CapabilitySource.AGENT,
                        name=str(claimed),
                        description=str(agent.get("description", "")),
                        provider=agent_type,
                        namespace="platform",
                        capability=str(claimed),
                        interface="agent",
                        server_name=agent_id,
                        raw={"agent_id": agent_id, "agent_type": agent_type},
                        claims={"declared_by_agent": agent_id},
                    )
                )
    except Exception as exc:  # noqa: BLE001
        health, error = SourceHealth.UNAVAILABLE, f"{type(exc).__name__}: {exc}"
        observations = []

    return StaticObservationSource(
        source_id, CapabilitySource.AGENT, observations, health=health, error=error
    )


# ----------------------------------------------------------------------
# Manual
# ----------------------------------------------------------------------


def manual_source(
    observations: Sequence[RawObservation], *, source_id: str = "manual"
):
    """A human-submitted candidate.

    Travels the identical path: normalised, validated, and landing REGISTERED
    and UNVERIFIED like anything else. Submitting by hand is not a way to skip
    ahead of the lifecycle.
    """
    return StaticObservationSource(
        source_id, CapabilitySource.MANUAL, tuple(observations)
    )


def available_sources(*, include: Iterable[str] = ("mcp", "connector", "agent")) -> tuple:
    """The adapters this deployment can offer. Each reports its own health."""
    builders = {"mcp": mcp_source, "connector": connector_source, "agent": agent_source}
    return tuple(builders[name]() for name in include if name in builders)
