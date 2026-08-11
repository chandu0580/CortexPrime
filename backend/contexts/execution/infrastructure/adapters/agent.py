"""The agent-as-capability seam. A mechanism, and nothing more.

Why this seam exists at all
-----------------------------
Because the capability contract already says agents are capabilities:
``CapabilityInterface`` carries ``AGENT`` and ``SKILL`` (ADR-032), so a binding
for one can be resolved and authorized today. Without this seam it would reach
execution and find no shape to land in, and the pressure would be to route it
through some other adapter — which would mean a model-driven actor running under
a contract written for a deterministic call.

What is deliberately not here
-------------------------------
No LLM call. No agent loop. No planner. No memory. No reasoning. No tool
selection. No orchestration of any kind. Those are a different concern entirely,
and an execution adapter that grew them would put a model inside the fabric
whose whole value is being deterministic.

The distinction that makes this safe
--------------------------------------
A model may propose an action anywhere else in CortexPrime. It may not
participate in worker selection, compatibility, authorization or binding
validation. This adapter is downstream of every one of those: by the time it is
called, what may run has been decided by field comparison, and the agent's job
is to perform a specific authorized operation — not to decide what to do.

The refusal that Phase 4.3 adds
---------------------------------
ADR-042 §31: *if the agent mechanism cannot guarantee effect boundaries, refuse.*

An agent's declared effect class is a statement about intent, not a bound on
behaviour — ``CapabilityInterface.is_model_driven`` has said so since ADR-032.
For a read-only capability that is tolerable: the worst case is a model that
read more than it needed. For a **mutating** capability it is not, because the
effect check that would catch an over-reach is a detection *after* the write.

So a mutating agent capability requires an invoker that declares
``confines_effects`` — a runtime that can actually stop the actor from exceeding
its authority, not one that reports afterwards. Without one, the invocation is
refused having done nothing. That is a real restriction and it is meant to be:
the alternative is a model performing writes under a contract nobody can
enforce, which would be the least defensible thing in this fabric.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import SideEffectClass
from backend.contracts.provider import ProviderFailure, ProviderRef
from backend.contexts.execution.domain.bound_capability import BoundCapability
from backend.contexts.execution.domain.provider_invocation import ProviderAuthority
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

__all__ = [
    "AgentTarget",
    "AgentInvocation",
    "AgentInvoker",
    "AgentAdapter",
    "UNCONFINED_AGENT_REASON",
]

UNCONFINED_AGENT_REASON = (
    "this agent capability mutates and the attached agent runtime does not "
    "confine effects. An agent's declared effect class states intent, not a "
    "bound on behaviour, so the contract check would detect an over-reach only "
    "after the write. Execution refuses rather than performing a model-driven "
    "mutation under a contract nothing can enforce"
)


@dataclass(frozen=True)
class AgentTarget:
    """Which agent, which operation. Copied from the binding.

    ``agent_id`` is the binding's provider. The agent is a provider of an
    ability, exactly as an MCP server is — and, exactly as with MCP, trusting the
    agent is not the same decision as authorizing each thing it can do.
    """

    agent_id: str
    operation: str
    capability_ref: str
    capability_digest: str

    def __post_init__(self) -> None:
        for label in ("agent_id", "operation", "capability_ref", "capability_digest"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")

    @classmethod
    def from_binding(cls, binding: BoundCapability) -> "AgentTarget":
        return cls(
            agent_id=binding.provider,
            operation=binding.operation,
            capability_ref=binding.capability_ref,
            capability_digest=binding.capability_digest,
        )

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "operation": self.operation,
            "capability_ref": self.capability_ref,
            "capability_digest": self.capability_digest,
        }


@dataclass(frozen=True)
class AgentInvocation:
    """One agent invocation, as an agent runtime receives it.

    ``authorized_side_effect`` bounds what the runtime may permit its actor to
    attempt. Read-only from the runtime's side: the binding remains
    authoritative, and a runtime that widened this would be granting itself
    authority the resolution and authorization steps declined to give.

    Carries **no credential**. An agent runtime that needs to reach a provider
    does so through its own governed capability with its own binding — an agent
    handed this invocation's credential would be an actor holding a secret
    minted for a different action.
    """

    target: AgentTarget
    inputs: Mapping[str, Any] = field(default_factory=dict)
    authorized_side_effect: SideEffectClass = SideEffectClass.READ
    tenant_id: str = ""
    principal_id: str = ""
    action_digest: str = ""
    deadline_seconds: Optional[int] = None
    idempotency_key: Optional[str] = None
    attempt_number: int = 1

    def __post_init__(self) -> None:
        if not isinstance(self.target, AgentTarget):
            raise ContractViolation("target must be an AgentTarget")
        if not isinstance(self.authorized_side_effect, SideEffectClass):
            raise ContractViolation("authorized_side_effect must be a SideEffectClass")
        if self.attempt_number < 1:
            raise ContractViolation("attempt numbers start at 1")
        for label in ("tenant_id", "principal_id", "action_digest"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"{label} must be non-blank text; an agent invocation without "
                    "it cannot be attributed, and an unattributable agent action "
                    "is one nobody can answer for"
                )

    @classmethod
    def from_authority(cls, authority: ProviderAuthority) -> "AgentInvocation":
        return cls(
            target=AgentTarget.from_binding(authority.binding),
            inputs=dict(authority.payload),
            authorized_side_effect=authority.side_effect_class,
            tenant_id=authority.tenant_id,
            principal_id=authority.effective_principal_id,
            action_digest=authority.action_digest,
            deadline_seconds=authority.deadline_seconds,
            idempotency_key=authority.idempotency_key,
            attempt_number=authority.attempt_number,
        )

    def to_dict(self) -> dict:
        """No inputs. Agent input is free text and routinely carries everything."""
        return {
            **self.target.to_dict(),
            "authorized_side_effect": self.authorized_side_effect.value,
            "tenant_id": self.tenant_id,
            "principal_id": self.principal_id,
            "action_digest": self.action_digest,
            "deadline_seconds": self.deadline_seconds,
            "attempt_number": self.attempt_number,
            "idempotency_key_present": self.idempotency_key is not None,
        }


@runtime_checkable
class AgentInvoker(Protocol):
    """The seam an agent runtime attaches to. Nothing implements it here.

    Whatever implements this owns the loop, the model, the memory and the tool
    calls — all of it on the far side of this port, in a concern that is not
    execution. An implementation must not retry, and must report an invocation
    it lost track of as ``ambiguous``: an agent that stopped mid-way may well
    have already performed the write.
    """

    @property
    def confines_effects(self) -> bool:
        """Whether the runtime can *prevent* its actor exceeding the authorized
        effect, rather than report afterwards that it did.

        Declared rather than assumed, and the default anywhere it is absent is
        ``False``. A runtime that answers ``True`` is making a claim about
        sandboxing and tool restriction that somebody has to have built.
        """
        ...

    def invoke(
        self, authority: ProviderAuthority, invocation: AgentInvocation
    ) -> ProviderOutcome: ...


class AgentAdapter(AdapterSeam):
    """Invokes an agent capability. Holds no model client and no loop."""

    WORKER_KIND = WorkerKind.AGENT
    INTERFACE = WorkerInterface.AGENT
    IMPLEMENTATION_VERSION = "1.0.0"

    REQUIRES_CREDENTIAL = False
    """An agent runtime is reached in-process; there is no provider to
    authenticate to. It is stated rather than inherited, because the default is
    to require one and an unstated exemption is how a credential check gets
    quietly skipped for a provider that did need it."""

    def __init__(
        self,
        *,
        implementation: WorkerImplementation,
        provider: ProviderRef,
        invoker: Optional[AgentInvoker] = None,
        preflight: Optional[AdapterPreflight] = None,
        metrics: Optional[Any] = None,
    ) -> None:
        super().__init__(
            implementation=implementation,
            provider=provider,
            invoker=invoker,
            preflight=preflight,
            metrics=metrics,
        )

    @property
    def confines_effects(self) -> bool:
        """Whether the attached runtime confines effects. ``False`` when absent."""
        return bool(getattr(self._invoker, "confines_effects", False))

    def describe(self) -> dict:
        return {
            "adapter": self.adapter.value,
            "agent": self.provider.provider_id,
            "runtime_attached": self.has_transport,
            "confines_effects": self.confines_effects,
        }

    def _perform(
        self,
        context: Any,
        request: WorkerExecutionRequest,
        authority: ProviderAuthority,
    ) -> ProviderOutcome:
        # ADR-042 §31. Checked here rather than at registration because the
        # answer depends on the *binding* -- the same agent may legitimately
        # serve read capabilities and must not serve mutating ones.
        if authority.mutates and not self.confines_effects:
            return ProviderOutcome.refused(
                # Not EFFECT_EXCEEDED: nothing ran, so nothing exceeded
                # anything. The adapter is simply not usable for a binding of
                # this kind, and saying so is a definite, un-retryable answer.
                ProviderFailure.ADAPTER_UNAVAILABLE,
                UNCONFINED_AGENT_REASON,
            )

        outcome = self._invoker.invoke(
            authority, AgentInvocation.from_authority(authority)
        )
        if not isinstance(outcome, ProviderOutcome):
            return ProviderOutcome.unresolved(
                f"the agent runtime returned {type(outcome).__name__}, not a "
                "ProviderOutcome; what it did is unknown"
            )
        if outcome.succeeded and outcome.observed_effect is None:
            # A model-driven actor that reports success without saying what it
            # did has skipped the one check that bounds it. Not treated as a
            # success: the effect comparison is the whole safety story here.
            return ProviderOutcome.unresolved(
                "the agent reported success without declaring what it did; a "
                "model-driven actor's effect is the one thing that must be "
                "stated for the contract check to mean anything"
            )
        return outcome
