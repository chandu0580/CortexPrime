"""What a capability promises: interface, schemas, effects, execution semantics.

This is the part of a capability definition that a digest covers and that an
approval is *about*. Everything here answers "what will happen if this runs",
which is why none of it may change under a registered version.

Deliberately absent
---------------------
**Credentials.** No tokens, keys, secrets, or connection strings. A capability
says *what it can do*, never *how to authenticate as somebody*. Credential
resolution belongs to a later security layer, and putting one here would put
secrets into an object designed to be widely readable, digested, and logged.

**Whether a given workflow may use it.** That is an authorization question about
a request; this is a declaration about an ability. Phase 3.2.3 answers the first
using the second.

Schemas are referenced, not embedded
--------------------------------------
``input_schema_ref``/``output_schema_ref`` name a schema; they do not carry it.
A registry entry that embedded arbitrary third-party JSON Schema would be
unbounded in size and would put untrusted structure inside an object the platform
hashes and shows to everybody. The digest covers the *reference and its digest*,
which is enough to detect a schema changing underneath a registered version.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional

from backend.contracts.connector import IsolationTier
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import EffectSemantics, SideEffectClass

__all__ = [
    "CapabilityInterface",
    "ExecutionMode",
    "CapabilityEnvironment",
    "SchemaRef",
    "CapabilityContract",
]


class CapabilityInterface(str, Enum):
    """The shape of thing that provides this ability.

    Extensible on purpose. The registry branches on nothing here -- it records
    the value so a later resolver can pick an adapter. A registry with a
    provider-specific branch in it stops being generic the moment the second
    provider arrives.
    """

    EXECUTION_WORKER = "execution_worker"
    """Runs work under the execution runtime's lease and reports an outcome."""

    CONNECTOR = "connector"
    """Calls a configured external system (BC-8's existing vocabulary)."""

    MCP_TOOL = "mcp_tool"
    """Exposed over the Model Context Protocol by some server."""

    AGENT = "agent"
    """A model-driven actor that decides its own steps."""

    SKILL = "skill"
    """A packaged procedure invoked by an agent."""

    SERVICE = "service"
    """An internal platform service exposing an ability."""

    @property
    def is_model_driven(self) -> bool:
        """Whether what runs is chosen by a model rather than declared.

        Recorded because it changes what a declaration is worth: an agent's
        effect class is a statement about intent, not a bound on behaviour.
        """
        return self in {CapabilityInterface.AGENT, CapabilityInterface.SKILL}


class ExecutionMode(str, Enum):
    """How an invocation returns its result."""

    SYNCHRONOUS = "synchronous"
    """The call returns the outcome."""

    ASYNCHRONOUS = "asynchronous"
    """The call returns an acceptance; the outcome arrives later. Transport
    success is not business success, and this is where that gap starts."""

    STREAMING = "streaming"
    """Partial results arrive over time."""

    @property
    def result_is_immediate(self) -> bool:
        return self is ExecutionMode.SYNCHRONOUS


class CapabilityEnvironment(str, Enum):
    """Where a capability is entitled to operate.

    Duplicated deliberately from ``intent.domain.scope.Environment``. The two
    contexts may not import each other (Constitution S2) and this vocabulary is
    not published in ``contracts/``. A free-form string was the alternative and
    is worse: it would let ``prod``, ``production`` and ``Production`` become
    three environments. If a third context needs this, promote it to
    ``contracts/`` rather than making a third copy.
    """

    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"

    @property
    def is_live(self) -> bool:
        return self is CapabilityEnvironment.PRODUCTION


@dataclass(frozen=True)
class SchemaRef:
    """A pointer to a schema, plus a digest of the schema it pointed at."""

    name: str
    digest: str
    media_type: str = "application/schema+json"

    def __post_init__(self) -> None:
        for label in ("name", "digest", "media_type"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"schema {label} must be non-blank text; a schema reference "
                    "that cannot be resolved or verified is not a contract"
                )

    def to_dict(self) -> dict:
        return {"name": self.name, "digest": self.digest, "media_type": self.media_type}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "SchemaRef":
        return cls(
            name=data["name"],
            digest=data["digest"],
            media_type=data.get("media_type", "application/schema+json"),
        )


@dataclass(frozen=True)
class CapabilityContract:
    """What running this capability promises. The digested part of a definition."""

    interface: CapabilityInterface
    side_effect_class: SideEffectClass
    effect_semantics: EffectSemantics
    isolation_tier: IsolationTier
    execution_mode: ExecutionMode = ExecutionMode.SYNCHRONOUS

    input_schema: Optional[SchemaRef] = None
    output_schema: Optional[SchemaRef] = None

    required_permissions: tuple = ()
    supported_environments: tuple = ()

    idempotency_supported: bool = False
    retryable: bool = False
    cancellable: bool = False
    compensation_capability: Optional[str] = None
    timeout_seconds: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.interface, CapabilityInterface):
            raise ContractViolation("interface must be a CapabilityInterface")
        if not isinstance(self.side_effect_class, SideEffectClass):
            raise ContractViolation("side_effect_class must be a SideEffectClass")
        if not isinstance(self.effect_semantics, EffectSemantics):
            raise ContractViolation("effect_semantics must be an EffectSemantics")
        if not isinstance(self.isolation_tier, IsolationTier):
            raise ContractViolation("isolation_tier must be an IsolationTier")
        if not isinstance(self.execution_mode, ExecutionMode):
            raise ContractViolation("execution_mode must be an ExecutionMode")

        # Reuses the existing BC-8 rule (ADR-005 / Constitution S6): an
        # under-isolated destructive tool is the configuration that turns a
        # prompt injection into an incident.
        if self.side_effect_class not in self.isolation_tier.minimum_for:
            raise ContractViolation(
                f"isolation tier {self.isolation_tier.value!r} is insufficient for a "
                f"{self.side_effect_class.value!r} capability"
            )

        # The two effect axes must not contradict each other.
        if self.side_effect_class.mutates and self.effect_semantics is EffectSemantics.READ_ONLY:
            raise ContractViolation(
                f"a {self.side_effect_class.value!r} capability cannot declare "
                "read-only semantics; it changes something, and calling it read-only "
                "would let it be repeated freely"
            )
        if not self.side_effect_class.mutates and self.effect_semantics.mutates:
            raise ContractViolation(
                "a read capability cannot declare mutating effect semantics"
            )

        # Claiming idempotency is a claim a caller will act on.
        if (
            self.effect_semantics is EffectSemantics.IDEMPOTENT_WRITE
            and not self.idempotency_supported
        ):
            raise ContractViolation(
                "a capability declaring idempotent-write semantics must support an "
                "idempotency key; without one there is nothing that makes the "
                "second application a no-op, and the claim is unfounded"
            )

        # The central rule, restated at registration: unknown never means safe.
        if self.retryable and not self.effect_semantics.is_repeatable:
            raise ContractViolation(
                f"a capability with {self.effect_semantics.value!r} semantics cannot "
                "declare itself retryable"
                + (
                    ". Effect semantics are UNKNOWN because nothing establishes that "
                    "repeating this is safe -- declare an idempotency key or declare "
                    "it non-retryable, but unknown does not default to safe"
                    if self.effect_semantics is EffectSemantics.UNKNOWN
                    else ""
                )
            )

        if not self.supported_environments:
            raise ContractViolation(
                "a capability must say which environments it may operate in; one "
                "that declares none is either unusable or usable everywhere, and "
                "the second is not something to arrive at by omission"
            )
        for environment in self.supported_environments:
            if not isinstance(environment, CapabilityEnvironment):
                raise ContractViolation(
                    "supported_environments must contain CapabilityEnvironment values"
                )

        if self.timeout_seconds is not None and self.timeout_seconds < 1:
            raise ContractViolation("timeout_seconds must be at least 1")

        for permission in self.required_permissions:
            if not isinstance(permission, str) or not permission.strip():
                raise ContractViolation("required_permissions must be non-blank text")

    @property
    def is_effect_declared(self) -> bool:
        """Whether anyone actually said what repeating this does."""
        return self.effect_semantics.is_declared

    @property
    def supports_production(self) -> bool:
        return CapabilityEnvironment.PRODUCTION in self.supported_environments

    def permits_environment(self, environment: CapabilityEnvironment) -> bool:
        return environment in self.supported_environments

    def digest_payload(self) -> dict:
        """The security-relevant contract, canonically ordered.

        Operational status, counters, health and timestamps are excluded: the
        digest answers "is this the contract that was approved", and a capability
        whose digest changed because a heartbeat arrived would make that question
        unanswerable.
        """
        return {
            "interface": self.interface.value,
            "side_effect_class": self.side_effect_class.value,
            "effect_semantics": self.effect_semantics.value,
            "isolation_tier": self.isolation_tier.value,
            "execution_mode": self.execution_mode.value,
            "input_schema": self.input_schema.to_dict() if self.input_schema else None,
            "output_schema": self.output_schema.to_dict() if self.output_schema else None,
            "required_permissions": sorted(self.required_permissions),
            "supported_environments": sorted(
                e.value for e in self.supported_environments
            ),
            "idempotency_supported": self.idempotency_supported,
            "retryable": self.retryable,
            "cancellable": self.cancellable,
            "compensation_capability": self.compensation_capability,
            "timeout_seconds": self.timeout_seconds,
        }

    def to_dict(self) -> dict:
        return self.digest_payload()

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "CapabilityContract":
        return cls(
            interface=CapabilityInterface(data["interface"]),
            side_effect_class=SideEffectClass(data["side_effect_class"]),
            effect_semantics=EffectSemantics(data["effect_semantics"]),
            isolation_tier=IsolationTier(data["isolation_tier"]),
            execution_mode=ExecutionMode(data["execution_mode"]),
            input_schema=(
                SchemaRef.from_dict(data["input_schema"])
                if data.get("input_schema")
                else None
            ),
            output_schema=(
                SchemaRef.from_dict(data["output_schema"])
                if data.get("output_schema")
                else None
            ),
            required_permissions=tuple(data.get("required_permissions", ())),
            supported_environments=tuple(
                CapabilityEnvironment(e) for e in data.get("supported_environments", ())
            ),
            idempotency_supported=data.get("idempotency_supported", False),
            retryable=data.get("retryable", False),
            cancellable=data.get("cancellable", False),
            compensation_capability=data.get("compensation_capability"),
            timeout_seconds=data.get("timeout_seconds"),
        )
