"""Adapter seams: where a provider attaches, under one governed lifecycle.

**Phase 4.3 made these real.** Until now every seam here refused, closed, having
sent nothing — which was the right shape to build *before* a provider arrived,
because a transport written first tends to bring its own authorization, its own
retries and its own idea of what a capability is with it. That shape is now
filled in, and the boundary it defined is what the implementations sit inside.

One adapter lifecycle, three specialisations
----------------------------------------------
MCP, connectors and agents share ``AdapterSeam``: the same authority check, the
same TOCTOU re-read, the same effect comparison, the same failure taxonomy, the
same ambiguity rule. They differ only in how one authorized operation becomes one
protocol exchange. Three separate execution frameworks would be three places the
ambiguity rule could be got wrong, and the first one to get it wrong reports a
timeout as a failure.

    base        the shared gate every adapter runs before it touches a provider
    channel     the one route to the Phase 4.2 transport broker
    mcp         MCP tool adapter -- server is a provider, tool is the capability
    connector   generic connector adapter -- no provider-specific code, ever
    agent       agent-as-capability seam -- a mechanism, never an orchestrator
    connectors/ per-provider declarations: catalogs and translators, no clients
    testing     a scripted adapter for exercising the chain. Never production

What an adapter is allowed to do
----------------------------------
Translate a ``ProviderAuthority`` into a provider call, make it once, and map
what came back onto ``WorkerExecutionResult`` and the Phase 3.1 failure taxonomy.

What no adapter may do
------------------------
Authorize. Resolve. Rebind. Retry. Acquire a credential. Open its own socket.
Mutate the execution aggregate or the binding. Change the tenant or the
principal. Choose a provider, a tool or a destination. Each of those belongs to
something that has already run by the time an adapter is called, and doing it
again here would create a second place the answer could differ.
"""

from backend.contexts.execution.infrastructure.adapters.base import (
    ADAPTER_UNAVAILABLE_REASON,
    AUTHORITY_REQUIRED_REASON,
    PROVIDER_FAILURE_CLASSES,
    AdapterPreflight,
    AdapterSeam,
    ProviderInvoker,
    ProviderOutcome,
    TransportUnavailable,
)
from backend.contexts.execution.infrastructure.adapters.channel import (
    RATE_LIMIT_HEADERS,
    TRANSPORT_FAILURE_MAP,
    ProviderChannel,
    ProviderExchange,
)
from backend.contexts.execution.infrastructure.adapters.agent import (
    UNCONFINED_AGENT_REASON,
    AgentAdapter,
    AgentInvocation,
    AgentInvoker,
    AgentTarget,
)
from backend.contexts.execution.infrastructure.adapters.connector import (
    DEFAULT_STATUS_FAILURES,
    ConnectorAdapter,
    HttpStatusTranslator,
    ProviderResponseTranslator,
)
from backend.contexts.execution.infrastructure.adapters.mcp import (
    MCP_ERROR_FAILURES,
    MCP_RESERVED_ARGUMENT_KEYS,
    McpServerRef,
    McpToolAdapter,
    McpToolTarget,
)
from backend.contexts.execution.infrastructure.adapters.testing import (
    ScriptedResponse,
    TestProviderAdapter,
)

__all__ = [
    "AdapterSeam",
    "AdapterPreflight",
    "ProviderInvoker",
    "ProviderOutcome",
    "TransportUnavailable",
    "ADAPTER_UNAVAILABLE_REASON",
    "AUTHORITY_REQUIRED_REASON",
    "PROVIDER_FAILURE_CLASSES",
    "ProviderChannel",
    "ProviderExchange",
    "TRANSPORT_FAILURE_MAP",
    "RATE_LIMIT_HEADERS",
    "McpToolAdapter",
    "McpToolTarget",
    "McpServerRef",
    "MCP_RESERVED_ARGUMENT_KEYS",
    "MCP_ERROR_FAILURES",
    "ConnectorAdapter",
    "ProviderResponseTranslator",
    "HttpStatusTranslator",
    "DEFAULT_STATUS_FAILURES",
    "AgentAdapter",
    "AgentInvoker",
    "AgentInvocation",
    "AgentTarget",
    "UNCONFINED_AGENT_REASON",
    "TestProviderAdapter",
    "ScriptedResponse",
]
