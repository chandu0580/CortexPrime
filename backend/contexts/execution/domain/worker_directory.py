"""Worker identity: which *implementation* may perform an authorized ability.

A capability is an authority. A worker is a mechanism.
------------------------------------------------------
Capability identity (BC-8, ADR-032) answers *what ability exists*. Worker
identity answers *what implementation can perform it*. They are related and they
are not the same question, so this module is not a second capability registry and
holds nothing a resolver would consult when choosing an ability.

Nothing here can widen what a binding authorized. A worker entry names a
mechanism and the narrow set of bindings that mechanism is declared fit for; it
cannot name a capability into existence, cannot grant itself an operation, and is
never consulted about whether a principal may act.

Two axes, borrowed deliberately
---------------------------------
``WorkerLifecycle`` and ``WorkerTrust`` mirror the shape ADR-032 chose for
capabilities -- administrative life on one axis, how much the platform vouches on
the other -- because the reasoning that produced it applies unchanged: a worker
being *registered* says somebody described an implementation, and nothing more.

They mirror that shape without sharing its type. Capability trust answers "do we
trust this declared ability?"; worker trust answers "do we trust this
implementation to perform it?". A trusted capability reached through an
unverified adapter is not a trusted execution, and one enum for both would make
that sentence unsayable. Execution requires both sides to be acceptable, checked
against two independent records.

Availability is a third axis, and stays separate
--------------------------------------------------
An enabled, trusted worker that is not running is not disabled and not untrusted
-- it is unavailable, which calls for a different response. Collapsing the three
into ``worker_not_found`` is how an operator spends an incident looking for a
registration that was there all along.

Registration is not enablement
--------------------------------
A newly registered worker is ``REGISTERED``, ``UNVERIFIED`` and ``UNAVAILABLE``.
Three separate deliberate acts stand between recording an implementation and it
being handed real work, and none of them happens as a side effect of the others.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable, Optional

from backend.contracts.connector import CodeTrust, IsolationTier, minimum_isolation
from backend.contracts.errors import ContractViolation
from backend.contracts.execution import (
    EffectSemantics,
    ExecutionEnvironment,
    SideEffectClass,
)
from backend.contexts.execution.domain.errors import ExecutionError
from backend.contexts.execution.domain.identifiers import normalise_worker_id
from backend.contexts.execution.domain.worker import WorkerKind
from backend.contexts.execution.domain.worker_contract import CancellationSupport
from backend.platform.hashing import compute_digest

__all__ = [
    "WorkerLifecycle",
    "WorkerTrust",
    "WorkerAvailability",
    "WorkerScope",
    "WorkerInterface",
    "WorkerImplementation",
    "WorkerEntry",
    "IllegalWorkerTransition",
    "WORKER_LIFECYCLE_TRANSITIONS",
    "WORKER_TRUST_TRANSITIONS",
    "WORKER_IMPLEMENTATION_KIND",
    "WORKER_PROTOCOL_VERSION",
    "is_legal_worker_lifecycle_transition",
    "is_legal_worker_trust_transition",
]

WORKER_IMPLEMENTATION_KIND = "cortexprime.execution.worker_implementation"

WORKER_PROTOCOL_VERSION = "cortexprime.execution.worker/1"
"""The ``ExecutionWorker`` contract of ADR-036: take a ``WorkerExecutionRequest``,
return a ``WorkerExecutionResult``. Versioned because an adapter compiled against
a different request shape would misread the binding, and a misread binding is the
one failure mode this whole layer exists to prevent."""


class IllegalWorkerTransition(ExecutionError):
    """A worker was moved somewhere its current state does not permit."""

    def __init__(self, *, worker_id: str, axis: str, source: str, target: str) -> None:
        super().__init__(
            f"worker {worker_id!r} cannot move {axis} from {source} to {target}"
        )
        self.worker_id = worker_id
        self.axis = axis
        self.source = source
        self.target = target


class WorkerLifecycle(str, Enum):
    """Where a worker implementation is in its administrative life."""

    REGISTERED = "registered"
    """The implementation is recorded and digest-bound. Nobody has checked that
    it does what it claims, and nothing may be handed to it."""

    VALIDATED = "validated"
    """Its declaration has been checked against the adapter it names. Still not
    switched on -- checking and using are two decisions with two records."""

    ENABLED = "enabled"
    """Eligible for selection, subject to trust and availability."""

    DISABLED = "disabled"
    """Switched off, reversibly. The ordinary operational lever."""

    REVOKED = "revoked"
    """Withdrawn permanently. Terminal, with no transition out -- that absence
    *is* the security property. A revoked implementation returns only as a new
    registration, which forces a new digest and a new decision."""

    @property
    def is_terminal(self) -> bool:
        return self is WorkerLifecycle.REVOKED

    @property
    def permits_execution(self) -> bool:
        """Whether lifecycle alone allows selection. Trust still has a vote.

        Deliberately narrower than ``CapabilityStatus.permits_execution``, which
        also admits ``DEPRECATED``. A deprecated *ability* still needs to run
        while callers migrate; there is no equivalent for an implementation --
        superseding one means registering the successor and disabling this.
        """
        return self is WorkerLifecycle.ENABLED


WORKER_LIFECYCLE_TRANSITIONS: dict = {
    WorkerLifecycle.REGISTERED: (
        WorkerLifecycle.VALIDATED,
        WorkerLifecycle.DISABLED,
        WorkerLifecycle.REVOKED,
    ),
    WorkerLifecycle.VALIDATED: (
        WorkerLifecycle.ENABLED,
        WorkerLifecycle.DISABLED,
        WorkerLifecycle.REVOKED,
    ),
    WorkerLifecycle.ENABLED: (WorkerLifecycle.DISABLED, WorkerLifecycle.REVOKED),
    # Back to VALIDATED, never straight to ENABLED: switching an implementation
    # back on goes through the gate it went through the first time.
    WorkerLifecycle.DISABLED: (WorkerLifecycle.VALIDATED, WorkerLifecycle.REVOKED),
    WorkerLifecycle.REVOKED: (),
}


class WorkerTrust(str, Enum):
    """How much the platform vouches for this *implementation*.

    Not capability trust. A capability the platform trusts, performed by an
    adapter it does not, is not a trusted execution -- and the reverse is equally
    true. Both records are read at the execution boundary and either one refuses.
    """

    UNVERIFIED = "unverified"
    """Registered, and nothing more. The default, because assuming otherwise is
    how an unchecked adapter comes to hold production credentials."""

    VERIFIED = "verified"
    """The implementation has been checked against what it declares."""

    TRUSTED = "trusted"
    """Verified, and cleared for consequential work."""

    QUARANTINED = "quarantined"
    """Something is wrong. Withheld without withdrawing the registration, so it
    can be investigated and released rather than re-registered."""

    UNTRUSTED = "untrusted"
    """Judged unfit. Terminal for this implementation version."""

    @property
    def permits_execution(self) -> bool:
        """Fails closed: only two states say yes."""
        return self in {WorkerTrust.VERIFIED, WorkerTrust.TRUSTED}

    @property
    def is_withheld(self) -> bool:
        return self in {WorkerTrust.QUARANTINED, WorkerTrust.UNTRUSTED}


WORKER_TRUST_TRANSITIONS: dict = {
    WorkerTrust.UNVERIFIED: (
        WorkerTrust.VERIFIED,
        WorkerTrust.QUARANTINED,
        WorkerTrust.UNTRUSTED,
    ),
    WorkerTrust.VERIFIED: (
        WorkerTrust.TRUSTED,
        WorkerTrust.QUARANTINED,
        WorkerTrust.UNTRUSTED,
        WorkerTrust.UNVERIFIED,
    ),
    WorkerTrust.TRUSTED: (
        WorkerTrust.VERIFIED,
        WorkerTrust.QUARANTINED,
        WorkerTrust.UNTRUSTED,
    ),
    # Quarantine returns to UNVERIFIED, not to whatever it was: coming out means
    # being checked again, not resuming a trust that was already in doubt.
    WorkerTrust.QUARANTINED: (WorkerTrust.UNVERIFIED, WorkerTrust.UNTRUSTED),
    WorkerTrust.UNTRUSTED: (),
}


class WorkerAvailability(str, Enum):
    """Whether the implementation is actually there right now.

    A third axis because "switched off", "not trusted" and "not running" are
    three different problems with three different fixes, and an operator handed
    one word for all three has been told nothing.

    No polling and no heartbeat infrastructure is introduced here: this is a
    recorded state that something else sets. ``WorkerHealth`` (ADR-029) remains
    what a worker reports about itself; this is what the directory believes.
    """

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    """Registered and expected, but not reachable. Distinct from unhealthy: we
    cannot see it at all rather than seeing it fail."""

    UNHEALTHY = "unhealthy"
    """Reachable and reporting that it is not fit to work."""

    DRAINING = "draining"
    """Finishing what it holds and taking nothing new. How an implementation
    leaves without stranding the work it is running."""

    @property
    def accepts_work(self) -> bool:
        return self is WorkerAvailability.AVAILABLE


class WorkerScope(str, Enum):
    """Who a worker registration belongs to.

    Stated rather than inferred. A directory that guessed would eventually guess
    that a tenant's registration is a platform one, and that registration would
    then be offered another tenant's bindings.
    """

    PLATFORM = "platform"
    """Registered once for the whole platform. Visible to every tenant, and
    writable by none of them."""

    TENANT = "tenant"
    """Registered by and for one tenant. Invisible to every other tenant, and it
    may not take an id a platform worker already holds -- a tenant that could
    shadow a platform worker could redirect platform work into its own adapter."""


class WorkerInterface(str, Enum):
    """The shape of thing an adapter drives.

    Values match ``connectivity.domain.contract.CapabilityInterface`` exactly, so
    the composition root translates by value. The contexts may not import each
    other (S2) and this is the cheapest honest correspondence: a mistranslation
    raises ``ValueError`` at the boundary rather than silently selecting an
    adapter built for a different kind of provider.

    An **MCP server is not an MCP tool.** The server is a provider boundary; the
    tool is the capability (ADR-033). ``MCP_TOOL`` names the tool, and one
    server-level trust decision therefore never authorizes everything that server
    exposes.
    """

    EXECUTION_WORKER = "execution_worker"
    CONNECTOR = "connector"
    MCP_TOOL = "mcp_tool"
    AGENT = "agent"
    SKILL = "skill"
    SERVICE = "service"


def is_legal_worker_lifecycle_transition(
    source: WorkerLifecycle, target: WorkerLifecycle
) -> bool:
    return target in WORKER_LIFECYCLE_TRANSITIONS.get(source, ())


def is_legal_worker_trust_transition(source: WorkerTrust, target: WorkerTrust) -> bool:
    return target in WORKER_TRUST_TRANSITIONS.get(source, ())


def _frozen_text(label: str, values: Iterable[Any]) -> frozenset:
    out = set()
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise ContractViolation(f"{label} entries must be non-blank text")
        out.add(value.strip())
    return frozenset(out)


@dataclass(frozen=True)
class WorkerImplementation:
    """The immutable identity of one worker implementation.

    Everything here is a fact about *what the implementation is* and what it is
    declared fit for. Nothing here is a fact about how it is currently doing --
    lifecycle, trust and availability live on ``WorkerEntry``, and the digest
    below deliberately does not cover them.

    Every constraint is stated positively and none of them has a wildcard. An
    empty ``supported_providers`` is refused rather than read as "any provider":
    the difference between "declared fit for GitHub" and "declared fit for
    whatever turns up" is the whole of this object's value.
    """

    worker_id: str
    worker_kind: WorkerKind
    interface: WorkerInterface

    implementation: str
    """A stable name for the code that runs, e.g. the adapter's dotted path. Not
    parsed and not imported from here -- recorded so an audit answers 'which
    implementation was selected' with something more than an id somebody chose."""

    implementation_version: str
    """Explicit and pinned. ``latest`` is refused: an authoritative execution
    decision that resolves at invocation time is a decision nobody made."""

    isolation: IsolationTier
    """Reused from ``contracts.connector`` rather than restated. What the
    implementation *actually* provides -- claiming ``SEALED`` for a process-local
    adapter would let a destructive capability through a gate that is not there."""

    scope: WorkerScope = WorkerScope.PLATFORM
    tenant_id: Optional[str] = None

    protocol_version: str = WORKER_PROTOCOL_VERSION

    supported_environments: frozenset = field(default_factory=frozenset)
    supported_effects: frozenset = field(default_factory=frozenset)
    supported_providers: frozenset = field(default_factory=frozenset)

    supported_capability_refs: frozenset = field(default_factory=frozenset)
    """Empty means this axis is not narrowed further, *not* 'any capability' --
    ``supported_providers`` is already mandatory, so an empty set here still
    leaves the worker confined to declared providers."""

    supported_operations: frozenset = field(default_factory=frozenset)
    pinned_capability_digests: frozenset = field(default_factory=frozenset)
    """When non-empty, the exact contract digests this implementation was built
    against. A capability whose contract was republished no longer matches, which
    is the point: the adapter was written for a shape that has changed."""

    cancellation: CancellationSupport = CancellationSupport.NONE
    supports_provider_idempotency: bool = False
    """Whether the provider accepts an idempotency key. Advertised, never acted
    on here -- Execution derives the key and owns every retry decision."""

    def __post_init__(self) -> None:
        object.__setattr__(self, "worker_id", normalise_worker_id(self.worker_id))
        if not isinstance(self.worker_kind, WorkerKind):
            raise ContractViolation("worker_kind must be a WorkerKind")
        if not isinstance(self.interface, WorkerInterface):
            raise ContractViolation("interface must be a WorkerInterface")
        if not isinstance(self.isolation, IsolationTier):
            raise ContractViolation("isolation must be an IsolationTier")
        if not isinstance(self.scope, WorkerScope):
            raise ContractViolation("scope must be a WorkerScope")

        for label in ("implementation", "implementation_version", "protocol_version"):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(f"{label} must be non-blank text")
            object.__setattr__(self, label, value.strip())

        if self.implementation_version.lower() in {"latest", "current", "head"}:
            raise ContractViolation(
                f"worker {self.worker_id!r} declares version "
                f"{self.implementation_version!r}; a moving version resolves at "
                "invocation time, so the audit record would name a decision nobody "
                "made. Pin the version"
            )

        if self.scope is WorkerScope.TENANT:
            if not isinstance(self.tenant_id, str) or not self.tenant_id.strip():
                raise ContractViolation(
                    "a tenant-scoped worker must name its tenant; one that does not "
                    "is visible to everybody and owned by nobody"
                )
            object.__setattr__(self, "tenant_id", self.tenant_id.strip())
        elif self.tenant_id is not None:
            raise ContractViolation(
                "a platform-scoped worker must not name a tenant; carrying one would "
                "make a platform registration look tenant-owned to anything reading "
                "the field instead of the scope"
            )

        environments = set(self.supported_environments)
        for environment in environments:
            if not isinstance(environment, ExecutionEnvironment):
                raise ContractViolation(
                    "supported_environments must contain ExecutionEnvironment values"
                )
        if not environments:
            raise ContractViolation(
                f"worker {self.worker_id!r} declares no environment; there is no "
                "wildcard, and a worker entitled to nowhere would either never run "
                "or -- if absence were read as 'anywhere' -- run in production"
            )
        object.__setattr__(self, "supported_environments", frozenset(environments))

        effects = set(self.supported_effects)
        for effect in effects:
            if not isinstance(effect, EffectSemantics):
                raise ContractViolation(
                    "supported_effects must contain EffectSemantics values"
                )
        if not effects:
            raise ContractViolation(
                f"worker {self.worker_id!r} declares no effect semantics; repeat "
                "safety is what the retry rules read, and an implementation that "
                "declares none cannot be matched against a binding that declares one"
            )
        object.__setattr__(self, "supported_effects", frozenset(effects))

        object.__setattr__(
            self, "supported_providers", _frozen_text("supported_providers", self.supported_providers)
        )
        if not self.supported_providers:
            raise ContractViolation(
                f"worker {self.worker_id!r} names no provider; an implementation fit "
                "for 'whatever turns up' is the substitution this layer exists to "
                "prevent"
            )
        object.__setattr__(
            self,
            "supported_capability_refs",
            _frozen_text("supported_capability_refs", self.supported_capability_refs),
        )
        object.__setattr__(
            self,
            "supported_operations",
            _frozen_text("supported_operations", self.supported_operations),
        )
        object.__setattr__(
            self,
            "pinned_capability_digests",
            _frozen_text("pinned_capability_digests", self.pinned_capability_digests),
        )

        if not isinstance(self.cancellation, CancellationSupport):
            raise ContractViolation("cancellation must be a CancellationSupport")
        if not isinstance(self.supports_provider_idempotency, bool):
            raise ContractViolation("supports_provider_idempotency must be a bool")

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    def identity_payload(self) -> dict:
        """What the implementation digest covers.

        Status, trust, availability and every timestamp are absent by design. The
        digest answers *which implementation was selected*, never *is it
        currently enabled* -- so disabling a worker does not change the digest an
        earlier selection recorded, and an audit trail stays comparable across a
        state change.
        """
        return {
            "artifact_kind": WORKER_IMPLEMENTATION_KIND,
            "worker_id": self.worker_id,
            "worker_kind": self.worker_kind.value,
            "interface": self.interface.value,
            "implementation": self.implementation,
            "implementation_version": self.implementation_version,
            "protocol_version": self.protocol_version,
            "isolation": self.isolation.value,
            "scope": self.scope.value,
            "tenant_id": self.tenant_id,
            "supported_environments": sorted(e.value for e in self.supported_environments),
            "supported_effects": sorted(e.value for e in self.supported_effects),
            "supported_providers": sorted(self.supported_providers),
            "supported_capability_refs": sorted(self.supported_capability_refs),
            "supported_operations": sorted(self.supported_operations),
            "pinned_capability_digests": sorted(self.pinned_capability_digests),
            "cancellation": self.cancellation.value,
            "supports_provider_idempotency": self.supports_provider_idempotency,
        }

    @property
    def digest(self) -> str:
        return compute_digest(self.identity_payload()).value

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def visible_to(self, tenant_id: str) -> bool:
        """Whether this registration is one that tenant may be offered.

        Platform workers are visible to everybody; tenant workers to exactly one.
        There is no third answer, and cross-tenant visibility fails closed.
        """
        if self.scope is WorkerScope.PLATFORM:
            return True
        return self.tenant_id == tenant_id

    def permits(self, code_trust: CodeTrust, side_effect: SideEffectClass) -> bool:
        """Whether this worker may run **this code** performing **this effect**.

        GATE 2 (ADR-088). Reads the one matrix rather than restating it: the
        platform already decided what each class of computation requires, and
        this does not get a second opinion.

        Note what ``isolation`` means here. It is what the implementation
        **actually provides**, not what it would prefer to claim -- an in-process
        adapter is not ``CONTAINED`` however it is declared (ADR-059), because
        ``CONTAINED`` requires a separate worker with per-execution credentials.
        This gate cannot detect a false declaration; only honesty upstream of it
        keeps the gate meaningful.
        """
        return self.isolation.satisfies(minimum_isolation(code_trust, side_effect))

    def permits_side_effect(self, side_effect: SideEffectClass) -> bool:
        """Whether this worker may perform that effect **with FIXED code**.

        The pre-ADR-088 signature, kept for callers that only ever ask about
        typed connector operations, and narrowed to that meaning rather than
        left ambiguous. Anything that can host code above ``FIXED`` must call
        :meth:`permits` and say which class.
        """
        return self.permits(CodeTrust.FIXED, side_effect)

    def to_dict(self) -> dict:
        return {**self.identity_payload(), "digest": self.digest}


@dataclass(frozen=True)
class WorkerEntry:
    """One registration: an implementation plus everything governed about it.

    Immutable. Every transition returns a new entry, so a directory that holds
    one of these cannot have its state changed by whoever it handed it to -- and
    a selection made against one is comparable, by digest, against whatever the
    authoritative record says later.
    """

    implementation: WorkerImplementation
    lifecycle: WorkerLifecycle = WorkerLifecycle.REGISTERED
    trust: WorkerTrust = WorkerTrust.UNVERIFIED
    availability: WorkerAvailability = WorkerAvailability.UNAVAILABLE
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: Optional[str] = None
    """Why the entry is in its current state. Required for every withholding
    move, because 'disabled' with no reason is a state nobody can safely undo."""

    def __post_init__(self) -> None:
        if not isinstance(self.implementation, WorkerImplementation):
            raise ContractViolation("implementation must be a WorkerImplementation")
        for label, value, expected in (
            ("lifecycle", self.lifecycle, WorkerLifecycle),
            ("trust", self.trust, WorkerTrust),
            ("availability", self.availability, WorkerAvailability),
        ):
            if not isinstance(value, expected):
                raise ContractViolation(f"{label} must be a {expected.__name__}")
        for label in ("registered_at", "updated_at"):
            if getattr(self, label).tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

    # -- queries -------------------------------------------------------

    @property
    def worker_id(self) -> str:
        return self.implementation.worker_id

    @property
    def worker_kind(self) -> WorkerKind:
        return self.implementation.worker_kind

    @property
    def worker_digest(self) -> str:
        return self.implementation.digest

    @property
    def worker_version(self) -> str:
        return self.implementation.implementation_version

    @property
    def is_executable(self) -> bool:
        """All three axes agree. Any one of them can say no."""
        return (
            self.lifecycle.permits_execution
            and self.trust.permits_execution
            and self.availability.accepts_work
        )

    # -- transitions ---------------------------------------------------

    def _moved(self, *, now: Optional[datetime] = None, **changes: Any) -> "WorkerEntry":
        from dataclasses import replace

        return replace(self, updated_at=now or datetime.now(timezone.utc), **changes)

    def _assert_lifecycle(self, target: WorkerLifecycle) -> None:
        if not is_legal_worker_lifecycle_transition(self.lifecycle, target):
            raise IllegalWorkerTransition(
                worker_id=self.worker_id,
                axis="lifecycle",
                source=self.lifecycle.value,
                target=target.value,
            )

    def validated(self, *, now: Optional[datetime] = None) -> "WorkerEntry":
        self._assert_lifecycle(WorkerLifecycle.VALIDATED)
        return self._moved(lifecycle=WorkerLifecycle.VALIDATED, reason=None, now=now)

    def enabled(self, *, now: Optional[datetime] = None) -> "WorkerEntry":
        """Eligible for selection. Says nothing about trust or availability."""
        self._assert_lifecycle(WorkerLifecycle.ENABLED)
        return self._moved(lifecycle=WorkerLifecycle.ENABLED, reason=None, now=now)

    def disabled(self, reason: str, *, now: Optional[datetime] = None) -> "WorkerEntry":
        if not isinstance(reason, str) or not reason.strip():
            raise ContractViolation(
                "disabling a worker requires a reason; an operator finding it off "
                "with no explanation has to guess whether re-enabling is safe"
            )
        self._assert_lifecycle(WorkerLifecycle.DISABLED)
        return self._moved(lifecycle=WorkerLifecycle.DISABLED, reason=reason, now=now)

    def revoked(self, reason: str, *, now: Optional[datetime] = None) -> "WorkerEntry":
        if not isinstance(reason, str) or not reason.strip():
            raise ContractViolation("revoking a worker requires a reason")
        self._assert_lifecycle(WorkerLifecycle.REVOKED)
        return self._moved(lifecycle=WorkerLifecycle.REVOKED, reason=reason, now=now)

    def with_trust(
        self, trust: WorkerTrust, reason: str, *, now: Optional[datetime] = None
    ) -> "WorkerEntry":
        if not isinstance(trust, WorkerTrust):
            raise ContractViolation("trust must be a WorkerTrust")
        if not isinstance(reason, str) or not reason.strip():
            raise ContractViolation("a trust change requires a stated reason")
        if not is_legal_worker_trust_transition(self.trust, trust):
            raise IllegalWorkerTransition(
                worker_id=self.worker_id,
                axis="trust",
                source=self.trust.value,
                target=trust.value,
            )
        return self._moved(trust=trust, reason=reason, now=now)

    def with_availability(
        self, availability: WorkerAvailability, *, now: Optional[datetime] = None
    ) -> "WorkerEntry":
        """Record what the directory believes about reachability.

        Unconstrained by a transition table on purpose: availability is an
        observation, not a decision, and an observation that had to be legal
        would be an observation somebody had to falsify to record the truth.
        """
        if not isinstance(availability, WorkerAvailability):
            raise ContractViolation("availability must be a WorkerAvailability")
        return self._moved(availability=availability, now=now)

    def to_dict(self) -> dict:
        return {
            "worker_id": self.worker_id,
            "worker_kind": self.worker_kind.value,
            "worker_version": self.worker_version,
            "worker_digest": self.worker_digest,
            "lifecycle": self.lifecycle.value,
            "trust": self.trust.value,
            "availability": self.availability.value,
            "executable": self.is_executable,
            "scope": self.implementation.scope.value,
            "tenant_id": self.implementation.tenant_id,
            "registered_at": self.registered_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "reason": self.reason,
            "implementation": self.implementation.to_dict(),
        }
