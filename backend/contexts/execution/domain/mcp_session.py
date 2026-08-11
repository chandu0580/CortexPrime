"""The MCP session: its identity, its life, and what a server's answer is worth.

A server is not a tool, and neither is authority
--------------------------------------------------
An MCP *server* is a provider boundary; an MCP *tool* is a capability
(ADR-033). This module holds the server side — connecting, initializing,
negotiating a protocol version, reading what the server says it can do — and
none of it grants anything.

A server declaring ``dangerous_tool`` in its ``initialize`` response has told us
what it offers. It has not told us what CortexPrime may call, and this module is
built so that distinction cannot be lost: ``McpInitialization`` holds the
server's declaration as *data*, has no method that returns a permission, and is
never consulted when deciding what to invoke. The binding decides that, and the
binding was made before any of this ran.

Sessions are scoped, never shared
-----------------------------------
``McpSessionKey`` is (tenant, provider, environment, principal, credential
fingerprint). Every component of it changes which authority the session speaks
with, so two invocations differing in any one of them get two sessions.

There is deliberately **no global session and no global authenticated client**.
A process-wide MCP client is one tenant's credential answering another tenant's
call, and it is the single easiest way to build a cross-tenant data leak that
looks like a performance optimisation.

The lifecycle exists so failure has a name
--------------------------------------------
Six states, and the transitions between them are enumerated rather than implied.
Without them, "the server did not answer" and "the server answered something we
could not understand" and "we never got as far as asking" all arrive as the same
exception, and an operator is handed one word for three different faults.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Tuple

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionEnvironment
from backend.platform.hashing import compute_digest

__all__ = [
    "MCP_PROTOCOL_VERSIONS",
    "MCP_PREFERRED_PROTOCOL_VERSION",
    "McpSessionState",
    "McpSessionKey",
    "McpSession",
    "McpInitialization",
    "McpSessionRefused",
    "IllegalSessionTransition",
    "MCP_SESSION_TRANSITIONS",
]

#: Protocol revisions this fabric can speak, newest first. An explicit list
#: rather than a floor: MCP revisions are dated strings with no ordering anybody
#: should infer, and ``>=`` over them would be a comparison that happens to work
#: until the day a revision is named differently.
MCP_PROTOCOL_VERSIONS: Tuple[str, ...] = ("2025-06-18", "2025-03-26", "2024-11-05")

MCP_PREFERRED_PROTOCOL_VERSION = MCP_PROTOCOL_VERSIONS[0]

_MAX_SESSION_ID_LENGTH = 256
_MAX_DECLARED_TOOLS = 512


class McpSessionRefused(ContractViolation):
    """A session could not be established, and nothing was invoked.

    Carries a reason code rather than a server message: an MCP server is
    infrastructure somebody else runs, and its error text is caller-influenced
    content that must not become a log line unbounded.
    """

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code
        self.safe_message = message


class IllegalSessionTransition(ContractViolation):
    """A session was moved somewhere its current state does not permit."""

    def __init__(self, *, source: str, target: str) -> None:
        super().__init__(f"an MCP session cannot move from {source} to {target}")
        self.source = source
        self.target = target


class McpSessionState(str, Enum):
    """Where an MCP session is in its life. Six states, and no implicit ones."""

    CONNECTING = "connecting"
    """A transport is being established. Nothing has been said in either
    direction, so nothing has been agreed."""

    INITIALIZING = "initializing"
    """``initialize`` is in flight. The protocol version is not yet agreed,
    which means no tool call may be made — a call sent now would be spoken in a
    dialect nobody confirmed."""

    READY = "ready"
    """Initialized, version agreed, and the only state a tool call is permitted
    from."""

    CLOSING = "closing"
    """Finishing in flight work and accepting nothing new. How a session ends
    without cutting a response in half."""

    CLOSED = "closed"
    """Terminal, and ordinary. The session ended as intended."""

    FAILED = "failed"
    """Terminal, and not ordinary. Distinct from ``CLOSED`` because 'we ended
    it' and 'it broke' lead to different conversations and different repairs."""

    @property
    def permits_tool_call(self) -> bool:
        """Fails closed: exactly one state says yes."""
        return self is McpSessionState.READY

    @property
    def is_terminal(self) -> bool:
        return self in {McpSessionState.CLOSED, McpSessionState.FAILED}


#: Legal moves. No transition leaves a terminal state -- a session that ended
#: comes back as a new session, which forces a new key, a new credential and a
#: new initialization rather than resuming one whose authority may have lapsed.
MCP_SESSION_TRANSITIONS: Mapping[McpSessionState, Tuple[McpSessionState, ...]] = {
    McpSessionState.CONNECTING: (
        McpSessionState.INITIALIZING,
        McpSessionState.FAILED,
        McpSessionState.CLOSED,
    ),
    McpSessionState.INITIALIZING: (
        McpSessionState.READY,
        McpSessionState.FAILED,
        McpSessionState.CLOSING,
    ),
    McpSessionState.READY: (McpSessionState.CLOSING, McpSessionState.FAILED),
    McpSessionState.CLOSING: (McpSessionState.CLOSED, McpSessionState.FAILED),
    McpSessionState.CLOSED: (),
    McpSessionState.FAILED: (),
}


@dataclass(frozen=True)
class McpSessionKey:
    """What makes two MCP sessions the same session. Five things, and all of them.

    Every component changes the authority the session speaks with, so dropping
    any one of them merges two authorities into one channel:

    ``tenant_id``        two tenants sharing a channel is the leak
    ``provider_id``      two servers are two providers
    ``environment``      a development session must never reach production
    ``principal_id``     a session opened as one principal, used as another
    ``credential_fingerprint``  a rotated or re-scoped credential is a new
                         authority, and reusing the channel would keep using
                         the old one after it was replaced
    """

    tenant_id: str
    provider_id: str
    environment: ExecutionEnvironment
    principal_id: str
    credential_fingerprint: Optional[str] = None
    """``None`` only where the server needs no credential. Kept distinct from a
    blank string so 'no credential was required' and 'we do not know which
    credential' cannot be confused."""

    def __post_init__(self) -> None:
        for label in ("tenant_id", "provider_id", "principal_id"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"{label} must be non-blank text; a session key missing it "
                    "would match sessions belonging to somebody else"
                )
        if not isinstance(self.environment, ExecutionEnvironment):
            raise ContractViolation("environment must be an ExecutionEnvironment")
        if self.credential_fingerprint is not None and (
            not isinstance(self.credential_fingerprint, str)
            or not self.credential_fingerprint.strip()
        ):
            raise ContractViolation(
                "credential_fingerprint must be non-blank text when present"
            )

    @property
    def value(self) -> str:
        """A stable, non-secret rendering. The fingerprint is already
        non-reversible (``CredentialMaterial.fingerprint``), so this is safe to
        log — which matters, because it is what an operator greps for."""
        return (
            f"mcp://{self.tenant_id}/{self.environment.value}/{self.provider_id}"
            f"#{self.principal_id}/{self.credential_fingerprint or 'anonymous'}"
        )

    def __str__(self) -> str:
        return self.value

    def belongs_to(self, tenant_id: str) -> bool:
        return self.tenant_id == tenant_id

    def to_dict(self) -> dict:
        return {
            "key": self.value,
            "tenant_id": self.tenant_id,
            "provider_id": self.provider_id,
            "environment": self.environment.value,
            "principal_id": self.principal_id,
            "credential_fingerprint": self.credential_fingerprint,
        }


@dataclass(frozen=True)
class McpInitialization:
    """What the server said about itself. **Data, and never a permission.**

    Every field here is the server's own claim. A server that lists a tool has
    advertised it; a server that omits one has not withdrawn CortexPrime's
    authority to call it, and a server that lists a thousand has granted
    nothing. The binding is authoritative in both directions, and this object
    exists so that the server's account can be *recorded* and *compared* without
    ever being consulted as an authority.

    ``declares`` is the only query it offers, and it deliberately answers a
    question about the server rather than about permission: "does the server
    admit to having this tool", which is useful for explaining a ``not_found``
    and is useless for deciding whether to call one.
    """

    protocol_version: str
    server_name: str
    server_version: str
    session_id: Optional[str] = None
    """The server's own handle for the session, when the transport carries one
    (``Mcp-Session-Id``). Bounded and validated: it is echoed on later requests,
    so an unbounded or control-character-bearing value would be injected into a
    header by the thing that echoes it."""

    capabilities: Mapping[str, Any] = field(default_factory=dict)
    declared_tools: Tuple[str, ...] = ()
    negotiated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if self.protocol_version not in MCP_PROTOCOL_VERSIONS:
            raise McpSessionRefused(
                "mcp_protocol_unsupported",
                f"the server negotiated {self.protocol_version!r}, which this "
                f"fabric does not speak (supported: "
                f"{', '.join(MCP_PROTOCOL_VERSIONS)}). Speaking a protocol we "
                "have not implemented is how a tool call means something else",
            )
        for label in ("server_name", "server_version"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise McpSessionRefused(
                    "mcp_initialization_malformed",
                    f"the server's initialize response has no {label}",
                )
            object.__setattr__(self, label, value.strip()[:128])
        if self.session_id is not None:
            session_id = self.session_id
            if not isinstance(session_id, str) or not session_id.strip():
                raise McpSessionRefused(
                    "mcp_initialization_malformed",
                    "the server returned a blank session id",
                )
            if len(session_id) > _MAX_SESSION_ID_LENGTH:
                raise McpSessionRefused(
                    "mcp_initialization_malformed",
                    "the server returned an implausibly long session id",
                )
            for character in session_id:
                code = ord(character)
                if code < 0x20 or code == 0x7F or code > 0x7E:
                    # This value is echoed back in a header. A control character
                    # here does not corrupt the header, it ends it.
                    raise McpSessionRefused(
                        "mcp_initialization_malformed",
                        "the server's session id contains a character that is "
                        "not safe to echo in a header",
                    )
        if len(self.declared_tools) > _MAX_DECLARED_TOOLS:
            raise McpSessionRefused(
                "mcp_initialization_malformed",
                f"the server declared more than {_MAX_DECLARED_TOOLS} tools; a "
                "declaration that large is a memory cost for information this "
                "fabric does not act on",
            )

    def declares(self, tool_name: str) -> bool:
        """Whether the server admits to having this tool. **Not permission.**

        Useful for explaining why a bound tool returned ``not_found``. Useless
        for deciding whether to call one, and there is nothing here that makes
        it look otherwise.
        """
        return tool_name in self.declared_tools

    def supports(self, capability: str) -> bool:
        """Whether the server advertises a protocol capability, e.g. ``tools``."""
        return bool(self.capabilities.get(capability))

    @property
    def digest(self) -> str:
        """A stable digest of what the server declared.

        Recorded so that a server quietly changing its declaration between two
        invocations is visible after the fact. Not acted on at call time —
        acting on it would make the server's self-description load-bearing.
        """
        return compute_digest(
            {
                "protocol_version": self.protocol_version,
                "server_name": self.server_name,
                "server_version": self.server_version,
                "capabilities": sorted(self.capabilities),
                "declared_tools": sorted(self.declared_tools),
            }
        ).value

    def to_dict(self) -> dict:
        """Safe to record. The session id is deliberately excluded: it is a
        bearer-ish value for the duration of the session, and belongs in the
        session rather than in a log line."""
        return {
            "protocol_version": self.protocol_version,
            "server_name": self.server_name,
            "server_version": self.server_version,
            "capabilities": sorted(self.capabilities),
            "declared_tool_count": len(self.declared_tools),
            "declaration_digest": self.digest,
            "negotiated_at": self.negotiated_at.isoformat(),
        }


@dataclass(frozen=True)
class McpSession:
    """One scoped MCP session. Immutable; every transition returns a new one.

    Immutable for the same reason ``WorkerEntry`` is: something holding a
    session cannot have its state changed underneath it by whoever it was handed
    to, and a tool call made against a ``READY`` session is provably made
    against a session that was ready when the call was built.
    """

    key: McpSessionKey
    state: McpSessionState = McpSessionState.CONNECTING
    initialization: Optional[McpInitialization] = None
    opened_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    """When the authority behind this session lapses. A session cannot outlive
    the invocation window that opened it, so this is set from the authority
    rather than from a session timeout somebody chose."""

    reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.key, McpSessionKey):
            raise ContractViolation("key must be an McpSessionKey")
        if not isinstance(self.state, McpSessionState):
            raise ContractViolation("state must be an McpSessionState")
        for label in ("opened_at", "updated_at"):
            if getattr(self, label).tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")
        if self.expires_at is not None and self.expires_at.tzinfo is None:
            raise ContractViolation("expires_at must be timezone-aware")
        if self.state is McpSessionState.READY and self.initialization is None:
            raise ContractViolation(
                "a session cannot be READY without an initialization; ready "
                "means a protocol version was agreed, and there is nothing here "
                "that agreed one"
            )

    # -- queries -------------------------------------------------------

    @property
    def protocol_version(self) -> Optional[str]:
        return self.initialization.protocol_version if self.initialization else None

    @property
    def session_id(self) -> Optional[str]:
        return self.initialization.session_id if self.initialization else None

    def permits_tool_call_at(self, moment: datetime) -> bool:
        """Ready, and still inside the authority that opened it. Both."""
        if not self.state.permits_tool_call:
            return False
        return self.expires_at is None or moment < self.expires_at

    # -- transitions ---------------------------------------------------

    def _moved(self, target: McpSessionState, *, now: Optional[datetime] = None, **changes: Any) -> "McpSession":
        if target not in MCP_SESSION_TRANSITIONS.get(self.state, ()):
            raise IllegalSessionTransition(
                source=self.state.value, target=target.value
            )
        from dataclasses import replace

        return replace(
            self,
            state=target,
            updated_at=now or datetime.now(timezone.utc),
            **changes,
        )

    def initializing(self, *, now: Optional[datetime] = None) -> "McpSession":
        return self._moved(McpSessionState.INITIALIZING, now=now)

    def ready(
        self, initialization: McpInitialization, *, now: Optional[datetime] = None
    ) -> "McpSession":
        """Record the negotiated protocol and permit tool calls.

        The one transition that widens what the session may do, and it requires
        the initialization to be supplied rather than looked up — a session
        cannot become ready by assertion.
        """
        if not isinstance(initialization, McpInitialization):
            raise ContractViolation(
                "becoming ready requires the negotiated initialization; a "
                "session that became ready without one would be speaking a "
                "protocol version nobody agreed"
            )
        return self._moved(
            McpSessionState.READY, now=now, initialization=initialization, reason=None
        )

    def closing(self, reason: str, *, now: Optional[datetime] = None) -> "McpSession":
        return self._moved(McpSessionState.CLOSING, now=now, reason=reason)

    def closed(self, *, now: Optional[datetime] = None) -> "McpSession":
        return self._moved(McpSessionState.CLOSED, now=now)

    def failed(self, reason: str, *, now: Optional[datetime] = None) -> "McpSession":
        if not isinstance(reason, str) or not reason.strip():
            raise ContractViolation(
                "a failed session requires a stated reason; a failure with no "
                "explanation is one nobody can act on"
            )
        return self._moved(McpSessionState.FAILED, now=now, reason=reason[:400])

    def to_dict(self) -> dict:
        return {
            **self.key.to_dict(),
            "state": self.state.value,
            "protocol_version": self.protocol_version,
            "opened_at": self.opened_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "reason": self.reason,
            "initialization": (
                self.initialization.to_dict() if self.initialization else None
            ),
        }
