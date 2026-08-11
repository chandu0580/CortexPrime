"""The MCP adapter: a real one, through the governed transport seam.

A server is not a tool
------------------------
Preserved from ADR-033 and the single most important thing in this module. An
MCP *server* is a provider boundary; an MCP *tool* is a capability. They are
modelled separately so one server-level trust decision cannot authorize
everything that server happens to expose — which is precisely the accident that
makes "connect this MCP server" a security event rather than a configuration
change.

The chain stays:

    MCP server (provider) → MCP tool (capability) → binding → MCP adapter

``McpToolTarget`` carries both, derived from the binding's provider and
operation **by exact field copy**. There is no lookup table, no name similarity,
and no inference about which tool a capability "probably" means.

The tool is pinned before the invocation exists
-------------------------------------------------
There is no ``tools/list`` at call time and no code path that could add one.
Discovery is BC-8's (ADR-033) and it feeds the registry, not the invocation. An
adapter that listed a server's tools and chose one would be choosing a
capability, which is the one thing an adapter must never do.

A caller can carry a tool name in the payload — under a reserved key, checked
against the bound tool, and refused on any disagreement. That path exists so a
caller who *tries* to redirect the call gets a refusal that names the problem,
rather than having their field silently ignored and wondering why.

Initialization is negotiation, never authorization
----------------------------------------------------
``initialize`` establishes a protocol version and reads what the server says it
offers. A server declaring ``dangerous_tool`` has advertised something; it has
granted nothing. ``McpInitialization`` holds that declaration as data, and this
module never consults it to decide what to call. The binding decides, and the
binding was made before any of this ran.

Sessions are per-invocation, and that is deliberate
-----------------------------------------------------
One invocation opens one session, initializes it, calls one tool, and closes it.
No pooling, no reuse, no cache. That costs a round trip and buys the property
that matters: there is no authenticated MCP client outliving the authority that
created it, and therefore no channel one tenant's credential could answer
another tenant's call on. Phase 4.2 does not pool authenticated connections
either, for the same reason.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Optional, Tuple

from backend.contracts.errors import ContractViolation
from backend.contracts.provider import ProviderDelivery, ProviderFailure, ProviderRef
from backend.contexts.execution.domain.bound_capability import BoundCapability
from backend.contexts.execution.domain.mcp_session import (
    MCP_PREFERRED_PROTOCOL_VERSION,
    MCP_PROTOCOL_VERSIONS,
    McpInitialization,
    McpSession,
    McpSessionKey,
    McpSessionRefused,
    McpSessionState,
)
from backend.contexts.execution.domain.provider_invocation import ProviderAuthority
from backend.contexts.execution.domain.provider_operation import (
    OperationCatalog,
    ProviderOperationSpec,
    ProviderRequestPlan,
    UnknownOperation,
)
from backend.contexts.execution.domain.worker import WorkerKind
from backend.contexts.execution.domain.worker_contract import WorkerExecutionRequest
from backend.contexts.execution.domain.worker_directory import (
    WorkerImplementation,
    WorkerInterface,
)
from backend.contexts.execution.infrastructure.adapters.base import (
    AdapterPreflight,
    AdapterSeam,
    ProviderOutcome,
)
from backend.contexts.execution.infrastructure.adapters.channel import (
    ProviderChannel,
    ProviderExchange,
)

__all__ = [
    "McpServerRef",
    "McpToolTarget",
    "McpToolAdapter",
    "MCP_RESERVED_ARGUMENT_KEYS",
    "MCP_ERROR_FAILURES",
]

#: Keys a caller may not use as tool arguments. Each one would name something
#: this adapter takes from the binding, so a payload carrying one is either a
#: mistake or an attempt to redirect the call. Both are refused rather than
#: stripped: silently dropping a caller's field means the operation performed is
#: not the one they described.
MCP_RESERVED_ARGUMENT_KEYS = ("_mcp_tool", "_mcp_server", "_mcp_endpoint")

#: JSON-RPC and MCP error codes projected onto the neutral taxonomy. Codes
#: outside this table become ``PROTOCOL_ERROR`` rather than a definite failure:
#: an error nobody recognises says nothing about whether the tool ran.
MCP_ERROR_FAILURES: Mapping[int, ProviderFailure] = {
    -32700: ProviderFailure.PROTOCOL_ERROR,   # parse error
    -32600: ProviderFailure.PROTOCOL_ERROR,   # invalid request
    -32601: ProviderFailure.OPERATION_NOT_SUPPORTED,  # method/tool not found
    -32602: ProviderFailure.VALIDATION_FAILURE,       # invalid params
    -32603: ProviderFailure.UNAVAILABLE,              # internal error
    -32002: ProviderFailure.NOT_FOUND,                # resource not found
    -32001: ProviderFailure.AUTHORIZATION_FAILURE,
    -32000: ProviderFailure.UNAVAILABLE,
}

_MAX_CONTENT_ITEMS = 64
_MAX_TEXT_EVIDENCE = 512


@dataclass(frozen=True)
class McpServerRef:
    """The server that exposes a tool. A provider, never a capability.

    Carries no endpoint, no credential and no transport detail. Where the server
    is and how one authenticates to it belong to the channel and to the
    credential fabric respectively; putting either here would make this object
    the thing an operator has to keep secret.
    """

    server_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.server_id, str) or not self.server_id.strip():
            raise ContractViolation("server_id must be non-blank text")
        object.__setattr__(self, "server_id", self.server_id.strip())


@dataclass(frozen=True)
class McpToolTarget:
    """Which tool, on which server. Derived from the binding by exact copy.

    Both halves come straight off the ``BoundCapability``: the provider *is* the
    server, the operation *is* the tool name. No mapping table, because a table
    is a place where a capability can be quietly pointed at a different tool.
    """

    server: McpServerRef
    tool_name: str
    capability_ref: str
    capability_digest: str

    def __post_init__(self) -> None:
        if not isinstance(self.server, McpServerRef):
            raise ContractViolation("server must be an McpServerRef")
        for label in ("tool_name", "capability_ref", "capability_digest"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")

    @classmethod
    def from_binding(cls, binding: BoundCapability) -> "McpToolTarget":
        return cls(
            server=McpServerRef(server_id=binding.provider),
            tool_name=binding.operation,
            capability_ref=binding.capability_ref,
            capability_digest=binding.capability_digest,
        )

    def to_dict(self) -> dict:
        return {
            "server_id": self.server.server_id,
            "tool_name": self.tool_name,
            "capability_ref": self.capability_ref,
            "capability_digest": self.capability_digest,
        }


class McpToolAdapter(AdapterSeam):
    """Performs one bound MCP tool call, through one scoped session."""

    WORKER_KIND = WorkerKind.MCP
    INTERFACE = WorkerInterface.MCP_TOOL
    IMPLEMENTATION_VERSION = "1.0.0"

    #: The JSON-RPC request ids this adapter uses. Fixed rather than
    #: incrementing: a session performs exactly two exchanges, and a counter
    #: would make two runs of one authorized action differ in their bytes
    #: (ADR-042 §55).
    INITIALIZE_ID = 1
    TOOL_CALL_ID = 2

    def __init__(
        self,
        *,
        implementation: WorkerImplementation,
        provider: ProviderRef,
        catalog: Optional[OperationCatalog] = None,
        channel: Optional[ProviderChannel] = None,
        preflight: Optional[AdapterPreflight] = None,
        metrics: Optional[Any] = None,
        client_name: str = "cortexprime",
        client_version: str = "1.0.0",
        session_seconds: int = 300,
    ) -> None:
        if catalog is not None and catalog.provider_id != provider.provider_id:
            raise ContractViolation(
                f"the catalog describes {catalog.provider_id!r} but this adapter "
                f"serves the MCP server {provider.provider_id!r}"
            )
        if channel is not None and not channel.provider.matches(provider.provider_id):
            raise ContractViolation(
                "the channel reaches a different MCP server than this adapter serves"
            )
        super().__init__(
            implementation=implementation,
            provider=provider,
            invoker=channel,
            preflight=preflight,
            metrics=metrics,
        )
        self._catalog = catalog
        self._channel = channel
        self._client_name = client_name
        self._client_version = client_version
        self._session_seconds = max(1, int(session_seconds))

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def server(self) -> McpServerRef:
        return McpServerRef(server_id=self.provider.provider_id)

    def supports_operation(self, operation: str) -> bool:
        """Exact catalog membership.

        **Fails closed with no catalog.** An MCP adapter with no declared tools
        can perform nothing, rather than anything the server happens to expose —
        "we did not declare it" is not "the server may choose".
        """
        return self._catalog is not None and operation in self._catalog

    def describe(self) -> dict:
        return {
            "adapter": self.adapter.value,
            "server": self.provider.provider_id,
            "tools": list(self._catalog.operations) if self._catalog else [],
            "catalog_digest": self._catalog.digest if self._catalog else None,
            "protocol_versions": list(MCP_PROTOCOL_VERSIONS),
            "endpoint": (
                self._channel.base_endpoint.normalised if self._channel else None
            ),
        }

    # ------------------------------------------------------------------
    # The provider call
    # ------------------------------------------------------------------

    def _perform(
        self,
        context: Any,
        request: WorkerExecutionRequest,
        authority: ProviderAuthority,
    ) -> ProviderOutcome:
        if self._catalog is None or self._channel is None:
            return ProviderOutcome.refused(
                ProviderFailure.ADAPTER_UNAVAILABLE,
                "this MCP adapter has no declared tools or no channel; nothing "
                "was sent",
            )

        target = McpToolTarget.from_binding(authority.binding)

        try:
            spec = self._catalog.require(target.tool_name)
        except UnknownOperation as unknown:
            return ProviderOutcome.refused(
                ProviderFailure.OPERATION_NOT_SUPPORTED, str(unknown)[:400]
            )

        drift = spec.contract_refusals(authority.binding)
        if drift:
            return ProviderOutcome.refused(
                ProviderFailure.CONTRACT_MISMATCH, "; ".join(drift)[:400]
            )

        # The pin. A payload that names a tool or a server must name *this* one.
        redirect = self._redirect_attempt(target, authority.payload)
        if redirect is not None:
            return ProviderOutcome.refused(ProviderFailure.PROVIDER_MISMATCH, redirect)

        problems = spec.input_problems(
            {k: v for k, v in authority.payload.items()
             if k not in MCP_RESERVED_ARGUMENT_KEYS}
        )
        if problems:
            return ProviderOutcome.refused(
                ProviderFailure.VALIDATION_FAILURE, "; ".join(problems)[:400]
            )

        now = datetime.now(timezone.utc)
        session = McpSession(
            key=self._session_key(authority),
            expires_at=min(
                now + timedelta(seconds=self._session_seconds),
                now + timedelta(seconds=max(1.0, authority.remaining_seconds(now))),
            ),
        )

        # -- CONNECTING → INITIALIZING → READY ---------------------------
        session = session.initializing(now=now)
        initialization, refusal = self._initialize(authority, spec, session)
        if refusal is not None:
            return refusal
        session = session.ready(initialization, now=datetime.now(timezone.utc))

        if not session.permits_tool_call_at(datetime.now(timezone.utc)):
            # The window closed while initializing. Nothing was invoked.
            return ProviderOutcome.refused(
                ProviderFailure.TRANSPORT_REFUSED,
                "the authority window closed during MCP initialization; the tool "
                "was not called",
            )

        # -- the one tool call --------------------------------------------
        outcome = self._call_tool(authority, spec, session, target)
        # The session ends with the invocation. There is nothing to reuse and
        # deliberately nowhere to put it if there were.
        return outcome

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------

    def _session_key(self, authority: ProviderAuthority) -> McpSessionKey:
        """Scope the session to exactly the authority that opened it."""
        grant = authority.credential_grant
        return McpSessionKey(
            tenant_id=authority.tenant_id,
            provider_id=self.provider.provider_id,
            environment=authority.environment,
            principal_id=authority.effective_principal_id,
            credential_fingerprint=grant.fingerprint if grant is not None else None,
        )

    def _initialize(
        self,
        authority: ProviderAuthority,
        spec: ProviderOperationSpec,
        session: McpSession,
    ) -> Tuple[Optional[McpInitialization], Optional[ProviderOutcome]]:
        """Negotiate the protocol. Returns ``(initialization, refusal)``.

        A failure here is **never ambiguous about the tool**: initialization does
        not invoke anything, so a lost initialize response means the tool was not
        called. That is the one place in this module where a definite answer is
        available, and it is worth taking.
        """
        plan = self._envelope(
            self.INITIALIZE_ID,
            "initialize",
            {
                "protocolVersion": MCP_PREFERRED_PROTOCOL_VERSION,
                # No capabilities are claimed. This client performs one tool call
                # per session; advertising sampling or roots would invite a
                # server to ask CortexPrime to do work nobody authorized.
                "capabilities": {},
                "clientInfo": {
                    "name": self._client_name,
                    "version": self._client_version,
                },
            },
        )
        exchange = self._channel.send(
            authority,
            plan,
            provider_timeout_seconds=spec.provider_timeout_seconds,
            max_response_bytes=spec.max_response_bytes,
        )
        if exchange.delivery is not ProviderDelivery.DELIVERED:
            return None, ProviderOutcome(
                # Initialization never invokes the tool. Whatever happened to
                # this request, the operation did not run.
                delivery=ProviderDelivery.NOT_ATTEMPTED,
                provider_failure=exchange.failure or ProviderFailure.UNAVAILABLE,
                error_message=(
                    exchange.reason
                    or "the MCP server could not be reached to initialize a session"
                )[:400],
                status_code=exchange.status_code,
                metadata={**exchange.metadata(), "mcp_phase": "initialize"},
            )

        body, problem = exchange.json()
        if problem is not None or not isinstance(body, Mapping):
            return None, ProviderOutcome.refused(
                ProviderFailure.PROTOCOL_ERROR,
                (problem or "the MCP server's initialize response is not an object"),
                status_code=exchange.status_code,
                metadata={"mcp_phase": "initialize"},
            )
        if "error" in body:
            failure, message = _rpc_error(body["error"])
            return None, ProviderOutcome.refused(
                failure,
                f"the MCP server refused initialization: {message}",
                status_code=exchange.status_code,
                metadata={"mcp_phase": "initialize"},
            )

        result = body.get("result")
        if not isinstance(result, Mapping):
            return None, ProviderOutcome.refused(
                ProviderFailure.PROTOCOL_ERROR,
                "the MCP server's initialize response carries no result object",
                status_code=exchange.status_code,
                metadata={"mcp_phase": "initialize"},
            )

        server_info = result.get("serverInfo")
        server_info = server_info if isinstance(server_info, Mapping) else {}
        capabilities = result.get("capabilities")
        capabilities = capabilities if isinstance(capabilities, Mapping) else {}
        try:
            initialization = McpInitialization(
                protocol_version=str(result.get("protocolVersion", "")),
                server_name=str(server_info.get("name") or "unknown"),
                server_version=str(server_info.get("version") or "unknown"),
                session_id=exchange.headers.get("mcp-session-id"),
                capabilities=dict(capabilities),
                declared_tools=_declared_tools(capabilities),
            )
        except McpSessionRefused as refused:
            # An unsupported protocol version, a malformed session id, an absurd
            # tool declaration. All of them refuse before any tool is called.
            return None, ProviderOutcome.refused(
                ProviderFailure.PROTOCOL_ERROR,
                refused.safe_message[:400],
                status_code=exchange.status_code,
                metadata={"mcp_phase": "initialize", "mcp_refusal": refused.reason_code},
            )

        if not initialization.supports("tools"):
            # The server does not offer tools at all. Refused here rather than
            # discovered as a confusing error on the call itself.
            return None, ProviderOutcome.refused(
                ProviderFailure.OPERATION_NOT_SUPPORTED,
                "the MCP server does not advertise the tools capability",
                status_code=exchange.status_code,
                metadata={"mcp_phase": "initialize"},
            )
        return initialization, None

    # ------------------------------------------------------------------
    # The tool call
    # ------------------------------------------------------------------

    def _call_tool(
        self,
        authority: ProviderAuthority,
        spec: ProviderOperationSpec,
        session: McpSession,
        target: McpToolTarget,
    ) -> ProviderOutcome:
        arguments = {
            key: value
            for key, value in authority.payload.items()
            if key not in MCP_RESERVED_ARGUMENT_KEYS
        }
        plan = self._envelope(
            self.TOOL_CALL_ID,
            "tools/call",
            # The tool name comes from the binding by way of ``McpToolTarget``.
            # There is no other expression in this module that produces it.
            {"name": target.tool_name, "arguments": arguments},
            session=session,
            idempotency_key=(
                authority.idempotency_key if spec.supports_idempotency_key else None
            ),
            idempotency_header=spec.idempotency_header,
        )
        exchange = self._channel.send(
            authority,
            plan,
            provider_timeout_seconds=spec.provider_timeout_seconds,
            max_response_bytes=spec.max_response_bytes,
        )
        return self._normalise(spec, target, session, exchange)

    def _normalise(
        self,
        spec: ProviderOperationSpec,
        target: McpToolTarget,
        session: McpSession,
        exchange: ProviderExchange,
    ) -> ProviderOutcome:
        """Turn an MCP answer into provider-neutral facts.

        MCP has two error channels and they mean different things. A JSON-RPC
        ``error`` is the protocol refusing — the tool did not run. An
        ``isError`` result is the *tool* reporting failure — it ran, and it
        failed. Collapsing them would make "the server does not know that
        method" and "the deployment failed" the same outcome.
        """
        common = {
            "status_code": exchange.status_code,
            "response_digest": exchange.response_digest,
            "retry_after_seconds": exchange.retry_after_seconds,
            "provider_request_id": exchange.provider_request_id,
            "delivery": exchange.delivery,
            "metadata": {
                **exchange.metadata(),
                "mcp_phase": "tools/call",
                "mcp_tool": target.tool_name,
                "mcp_server": target.server.server_id,
                "mcp_protocol_version": session.protocol_version,
                "mcp_session_state": McpSessionState.READY.value,
                "mcp_declaration_digest": (
                    session.initialization.digest if session.initialization else None
                ),
            },
        }

        if exchange.delivery is not ProviderDelivery.DELIVERED:
            return ProviderOutcome(
                ambiguous=exchange.delivery is ProviderDelivery.UNKNOWN,
                provider_failure=exchange.failure or ProviderFailure.UNKNOWN_OUTCOME,
                error_message=(
                    exchange.reason
                    or "the tool call did not reach the server, or nobody can say"
                )[:400],
                **common,
            )

        body, problem = exchange.json()
        if problem is not None:
            return ProviderOutcome(
                ambiguous=True,
                provider_failure=(
                    ProviderFailure.RESPONSE_TOO_LARGE
                    if exchange.truncated
                    else ProviderFailure.MALFORMED_RESPONSE
                ),
                error_message=problem,
                **common,
            )
        if not isinstance(body, Mapping):
            return ProviderOutcome(
                ambiguous=True,
                provider_failure=ProviderFailure.PROTOCOL_ERROR,
                error_message="the tool call response is not a JSON-RPC object",
                **common,
            )

        # -- protocol refusal: the tool did not run -----------------------
        if "error" in body:
            failure, message = _rpc_error(body["error"])
            return ProviderOutcome(
                provider_failure=failure,
                error_code=str(_rpc_code(body["error"]) or ""),
                error_message=message[:400],
                ambiguous=failure.is_ambiguous,
                **common,
            )

        result = body.get("result")
        if not isinstance(result, Mapping):
            return ProviderOutcome(
                ambiguous=True,
                provider_failure=ProviderFailure.PROTOCOL_ERROR,
                error_message="the tool call response carries no result object",
                **common,
            )

        content = result.get("content")
        if content is not None and (
            not isinstance(content, list) or len(content) > _MAX_CONTENT_ITEMS
        ):
            return ProviderOutcome(
                ambiguous=True,
                provider_failure=ProviderFailure.MALFORMED_RESPONSE,
                error_message=(
                    "the tool returned content that is not a bounded list; an "
                    "unbounded result is an unbounded allocation"
                ),
                **common,
            )

        structured = result.get("structuredContent")
        structured = structured if isinstance(structured, Mapping) else None

        # -- the tool ran and reported failure ---------------------------
        if result.get("isError") is True:
            return ProviderOutcome(
                # The tool executed. Whatever it did, it did — so this is a
                # definite provider failure rather than an ambiguous one, and
                # the effect it may have had before failing is the binding's
                # problem, not a reason to call the outcome unknown.
                provider_failure=ProviderFailure.UNAVAILABLE,
                error_code="mcp_tool_error",
                error_message=_first_text(content) or "the tool reported an error",
                **common,
            )

        # -- shape ---------------------------------------------------------
        shape = spec.response_problems(structured if structured is not None else result)
        if shape:
            return ProviderOutcome(
                ambiguous=True,
                provider_failure=ProviderFailure.MALFORMED_RESPONSE,
                error_message="; ".join(shape)[:400],
                **common,
            )

        return ProviderOutcome(
            succeeded=True,
            output=structured if structured is not None else dict(result),
            evidence=spec.evidence(structured or {}),
            # The catalog's declaration, not the server's. A server-supplied
            # effect would make the comparison against the binding circular.
            observed_effect=spec.side_effect_class,
            **common,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _redirect_attempt(
        target: McpToolTarget, payload: Mapping[str, Any]
    ) -> Optional[str]:
        """Whether the payload tried to name a different tool or server.

        Refused rather than ignored. A caller who passed ``_mcp_tool`` believes
        it did something; telling them it disagreed with the binding is more
        useful than performing the bound tool and letting them wonder.
        """
        declared_tool = payload.get("_mcp_tool")
        if declared_tool is not None and declared_tool != target.tool_name:
            return (
                f"the request names tool {str(declared_tool)[:64]!r} but the "
                f"binding authorizes {target.tool_name!r}; the adapter performs "
                "the bound tool and does not re-resolve"
            )
        declared_server = payload.get("_mcp_server")
        if declared_server is not None and declared_server != target.server.server_id:
            return (
                f"the request names server {str(declared_server)[:64]!r} but the "
                f"binding authorizes {target.server.server_id!r}; there is no "
                "fallback server"
            )
        if payload.get("_mcp_endpoint") is not None:
            return (
                "the request supplies an MCP endpoint; the destination is "
                "deployment configuration and is never request input"
            )
        return None

    def _envelope(
        self,
        request_id: int,
        method: str,
        params: Mapping[str, Any],
        *,
        session: Optional[McpSession] = None,
        idempotency_key: Optional[str] = None,
        idempotency_header: Optional[str] = None,
    ) -> ProviderRequestPlan:
        """One JSON-RPC request, as a transport plan. Deterministic throughout."""
        headers = {
            "accept": "application/json, text/event-stream",
            "mcp-protocol-version": MCP_PREFERRED_PROTOCOL_VERSION,
        }
        if session is not None and session.session_id:
            # Validated at ``McpInitialization`` construction to be printable
            # ASCII within bounds, so echoing it into a header is safe.
            headers["mcp-session-id"] = session.session_id
        if idempotency_key and idempotency_header:
            headers[idempotency_header.lower()] = idempotency_key
        return ProviderRequestPlan(
            method="POST",
            path="/",
            body={
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": dict(params),
            },
            headers=headers,
        )


def _rpc_code(error: Any) -> Optional[int]:
    if isinstance(error, Mapping):
        code = error.get("code")
        if isinstance(code, int) and not isinstance(code, bool):
            return code
    return None


def _rpc_error(error: Any) -> Tuple[ProviderFailure, str]:
    """Classify a JSON-RPC error. Unknown codes stay ambiguous about nothing.

    A protocol error means the *request* was rejected, so the tool did not run —
    which is why every entry here is a definite classification rather than an
    unknown outcome. The uncertainty in MCP lives in the transport, not in a
    server that answered with a well-formed refusal.
    """
    code = _rpc_code(error)
    failure = MCP_ERROR_FAILURES.get(code, ProviderFailure.PROTOCOL_ERROR)
    message = ""
    if isinstance(error, Mapping):
        raw = error.get("message")
        if isinstance(raw, str):
            # Bounded: a server's error text is content somebody else controls
            # and this reaches a log line.
            message = raw[:200]
    return failure, message or f"the server returned JSON-RPC error {code}"


def _first_text(content: Any) -> Optional[str]:
    """The first text block of an MCP content array, bounded.

    A tool's error text is composed by somebody else's server, sometimes from
    input the caller supplied, and it reaches a log line -- so it is truncated
    here rather than wherever it is eventually written.
    """
    if not isinstance(content, list):
        return None
    for item in content[:_MAX_CONTENT_ITEMS]:
        if isinstance(item, Mapping) and item.get("type") == "text":
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()[:_MAX_TEXT_EVIDENCE]
    return None


def _declared_tools(capabilities: Mapping[str, Any]) -> Tuple[str, ...]:
    """Tool names the server mentions in its capabilities, if it mentions any.

    Recorded, never acted on. The MCP ``initialize`` response does not normally
    enumerate tools — that is ``tools/list``, which this adapter deliberately
    never calls — so this is usually empty, and that emptiness is correct.
    """
    tools = capabilities.get("tools")
    if not isinstance(tools, Mapping):
        return ()
    listed = tools.get("names")
    if not isinstance(listed, (list, tuple)):
        return ()
    return tuple(str(name)[:128] for name in listed if isinstance(name, str))
