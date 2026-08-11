"""The invocation request, the refusal vocabulary, and the canonical action digest.

What this module is for
-------------------------
By Phase 3.3.2 the platform can say, separately: this capability exists and is
trusted; this principal was authorized; this binding was made; this worker was
selected. Each of those is a fact recorded at a different moment by a different
component.

Nothing yet checks that they still *agree with each other* at the instant work is
about to happen. This module carries the request that asserts they do, and the
vocabulary for saying exactly which one did not.

References, not copies
------------------------
``InvocationRequest`` carries ids and digests, never upstream aggregates. A
request that embedded the binding would let a caller present a binding of its own
construction; one that carries `binding_digest` can only *name* a binding, and
naming one that does not match is a refusal.

The same reasoning that makes ``BoundCapability`` unmintable applies here: every
identifying field is required, every digest is opaque to this context, and there
is no constructor path that produces authority from nothing.

Immutable, and structurally so
--------------------------------
There is no ``set_capability``, no ``change_worker``, no ``rebind``, no
``change_tenant`` and no ``change_operation``. Not discouraged — absent. A request
whose target could change after it was checked would be checked against one
action and performed as another, which is the whole class of bug this phase
exists to make unrepresentable.

``capability_ref`` is one token, deliberately
-----------------------------------------------
The directive asks for ``capability_id`` and ``capability_version`` as separate
fields. They are carried as the single rendered ``capability_ref``
(``namespace.provider.capability@version``) because ADR-036 established that
Execution never parses that string — splitting it here would require exactly the
parsing that decision forbade. Comparing the whole token enforces both clauses at
once and cannot drift between them: there is no state where the id matches and
the version does not.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping, Optional, Protocol, runtime_checkable

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import ExecutionEnvironment
from backend.contracts.identity import PrincipalRef
from backend.contexts.execution.domain.errors import ExecutionError
from backend.contexts.execution.domain.identifiers import AttemptId, ExecutionId
from backend.platform.hashing import compute_digest

__all__ = [
    "Clock",
    "SystemClock",
    "FrozenClock",
    "InvocationRefusal",
    "InvocationRefused",
    "InvocationRequest",
    "AuthorityWindow",
    "INVOCATION_ARTIFACT_KIND",
    "ACTION_DIGEST_KIND",
    "canonical_action_digest",
]

INVOCATION_ARTIFACT_KIND = "cortexprime.execution.invocation_request"
ACTION_DIGEST_KIND = "cortexprime.execution.action"


# ----------------------------------------------------------------------
# Time
# ----------------------------------------------------------------------


@runtime_checkable
class Clock(Protocol):
    """The one source of now for the gateway.

    Every expiry in this phase — binding, authorization, approval, lease,
    deadline — is compared against a single reading. Scattering
    ``datetime.now()`` through the checks would let a request pass the binding
    check at one instant and the approval check at another, and the window
    between them is a window where a revocation lands and is not seen.

    It also makes the gate testable without sleeping, which is why an expiry test
    that has to sleep is a test nobody runs.
    """

    def now(self) -> datetime: ...


class SystemClock:
    """The wall clock, in UTC. The only implementation used in production."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


class FrozenClock:
    """A clock that does not move. For reasoning about a single instant."""

    def __init__(self, moment: datetime) -> None:
        if moment.tzinfo is None:
            raise ContractViolation("a frozen clock needs a timezone-aware moment")
        self._moment = moment

    def now(self) -> datetime:
        return self._moment


# ----------------------------------------------------------------------
# Refusals
# ----------------------------------------------------------------------


class InvocationRefusal(str, Enum):
    """Why an invocation was refused. A denial is a fact, not an absence.

    Every value is machine-readable and safe to return to the caller. None of
    them names an internal URL, a provider credential, or an exception trace —
    a refusal that leaks infrastructure detail turns the security boundary into
    a reconnaissance surface.

    Retryability is a *fact about the cause*, reported here and acted on by
    Execution's recovery policy (ADR-031). The gateway never retries.
    """

    # -- identity and tenancy ------------------------------------------
    IDENTITY_MISSING = "identity_missing"
    PRINCIPAL_MISMATCH = "principal_mismatch"
    DELEGATION_NOT_AUTHORIZED = "delegation_not_authorized"
    """On-behalf-of execution was attempted and the authorization decision does
    not sanction it, sanctions a different principal, or says nothing.

    **Declared in Phase 4.1 and first raised in Phase 4.4.** Until then the
    delegated principal travelled through the whole chain and was compared only
    against the authenticated context -- so 'the actor is who they say' was
    checked and 'the actor may act for that principal' never was."""

    TENANT_MISMATCH = "tenant_mismatch"
    TENANT_UNKNOWN = "tenant_unknown"

    # -- authorization --------------------------------------------------
    AUTHORIZATION_UNAVAILABLE = "authorization_unavailable"
    AUTHORIZATION_MISSING = "authorization_missing"
    AUTHORIZATION_DENIED = "authorization_denied"
    AUTHORIZATION_EXPIRED = "authorization_expired"
    AUTHORIZATION_MISMATCH = "authorization_mismatch"
    POLICY_VERSION_CHANGED = "policy_version_changed"
    OBLIGATION_UNSATISFIED = "obligation_unsatisfied"

    # -- approval --------------------------------------------------------
    APPROVAL_REQUIRED = "approval_required"
    APPROVAL_MISSING = "approval_missing"
    APPROVAL_EXPIRED = "approval_expired"
    APPROVAL_MISMATCH = "approval_mismatch"

    # -- capability and binding -------------------------------------------
    BINDING_UNVERIFIABLE = "binding_unverifiable"
    BINDING_INVALID = "binding_invalid"
    BINDING_EXPIRED = "binding_expired"
    BINDING_MISMATCH = "binding_mismatch"
    CAPABILITY_MISMATCH = "capability_mismatch"
    CAPABILITY_REVOKED = "capability_revoked"
    CAPABILITY_DISABLED = "capability_disabled"
    OPERATION_MISMATCH = "operation_mismatch"
    ENVIRONMENT_MISMATCH = "environment_mismatch"
    ENVIRONMENT_UNKNOWN = "environment_unknown"

    # -- effect ------------------------------------------------------------
    EFFECT_UNDECLARED = "effect_undeclared"
    EFFECT_MISMATCH = "effect_mismatch"

    # -- worker -------------------------------------------------------------
    WORKER_UNAVAILABLE = "worker_unavailable"
    WORKER_DISABLED = "worker_disabled"
    WORKER_REVOKED = "worker_revoked"
    WORKER_UNTRUSTED = "worker_untrusted"
    WORKER_DIGEST_MISMATCH = "worker_digest_mismatch"
    WORKER_SELECTION_MISMATCH = "worker_selection_mismatch"
    WORKER_AMBIGUOUS = "worker_ambiguous"

    # -- input ---------------------------------------------------------------
    INPUT_INVALID = "input_invalid"
    INPUT_VALIDATION_UNAVAILABLE = "input_validation_unavailable"
    PAYLOAD_DIGEST_MISMATCH = "payload_digest_mismatch"

    # -- execution -------------------------------------------------------------
    LEASE_INVALID = "lease_invalid"
    LEASE_UNVERIFIABLE = "lease_unverifiable"
    DEADLINE_EXPIRED = "deadline_expired"
    EXECUTION_MISMATCH = "execution_mismatch"
    ATTEMPT_MISMATCH = "attempt_mismatch"

    # -- resources ---------------------------------------------------------------
    RATE_LIMITED = "rate_limited"

    # -- credentials ----------------------------------------------------------------
    CREDENTIAL_UNAVAILABLE = "credential_unavailable"

    # -- results -------------------------------------------------------------------
    RESULT_INVALID = "result_invalid"
    RESULT_FOREIGN = "result_foreign"

    # -- wiring --------------------------------------------------------------------
    GATEWAY_MISCONFIGURED = "gateway_misconfigured"

    @property
    def is_retryable(self) -> bool:
        """Whether another attempt could plausibly succeed without a decision.

        Deliberately narrow. A mismatch between two authority artifacts will not
        resolve itself by being asked again, and marking one retryable would turn
        a security refusal into a retry loop against a boundary that keeps saying
        no.

        Recovery still decides. This is the gateway reporting what it knows about
        the cause, not an instruction.
        """
        return self in {
            InvocationRefusal.WORKER_UNAVAILABLE,
            InvocationRefusal.AUTHORIZATION_UNAVAILABLE,
            InvocationRefusal.BINDING_UNVERIFIABLE,
            InvocationRefusal.LEASE_UNVERIFIABLE,
            InvocationRefusal.RATE_LIMITED,
            InvocationRefusal.CREDENTIAL_UNAVAILABLE,
        }

    @property
    def is_security_relevant(self) -> bool:
        """Whether this refusal belongs in a security review rather than an ops one.

        A tenant mismatch is somebody presenting another tenant's authority. A
        worker being briefly unavailable is a Tuesday. Recording them at the same
        weight is how the first gets lost among the second.
        """
        return self in {
            InvocationRefusal.PRINCIPAL_MISMATCH,
            InvocationRefusal.DELEGATION_NOT_AUTHORIZED,
            InvocationRefusal.TENANT_MISMATCH,
            InvocationRefusal.AUTHORIZATION_DENIED,
            InvocationRefusal.AUTHORIZATION_MISMATCH,
            InvocationRefusal.APPROVAL_MISSING,
            InvocationRefusal.APPROVAL_MISMATCH,
            InvocationRefusal.BINDING_MISMATCH,
            InvocationRefusal.CAPABILITY_MISMATCH,
            InvocationRefusal.CAPABILITY_REVOKED,
            InvocationRefusal.OPERATION_MISMATCH,
            InvocationRefusal.ENVIRONMENT_MISMATCH,
            InvocationRefusal.WORKER_DIGEST_MISMATCH,
            InvocationRefusal.WORKER_REVOKED,
            InvocationRefusal.WORKER_UNTRUSTED,
            InvocationRefusal.PAYLOAD_DIGEST_MISMATCH,
            InvocationRefusal.RESULT_FOREIGN,
        }


class InvocationRefused(ExecutionError):
    """The gateway declined. No worker was invoked.

    Carries a machine-readable code, a reason safe to show a caller, the
    correlation id, and the digests that are safe to disclose. It carries no
    credential, no internal URL, no provider hostname and no traceback.
    """

    def __init__(
        self,
        refusal: InvocationRefusal,
        message: str,
        *,
        correlation_id: Optional[str] = None,
        detail: Optional[Mapping[str, Any]] = None,
        reasons: tuple = (),
    ) -> None:
        super().__init__(f"{refusal.value}: {message}")
        self.refusal = refusal
        self.reason_code = refusal.value
        self.safe_message = message
        self.correlation_id = correlation_id
        self.detail = dict(detail or {})
        self.reasons = tuple(reasons)

    @property
    def retryable(self) -> bool:
        return self.refusal.is_retryable

    def to_dict(self) -> dict:
        return {
            "refusal": self.refusal.value,
            "reason": self.safe_message,
            "retryable": self.retryable,
            "security_relevant": self.refusal.is_security_relevant,
            "correlation_id": self.correlation_id,
            "reasons": list(self.reasons),
            **self.detail,
        }


# ----------------------------------------------------------------------
# The authority window
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class AuthorityWindow:
    """How long every authority behind this action still holds. The earliest wins.

    Four independent clocks govern one action: the binding expires, the
    authorization expires, the approval expires, and the execution has a
    deadline. Work may proceed only while *all four* are live, so the effective
    window is the minimum — and taking the minimum is the only combination that
    cannot be widened by adding another authority.

    There is no renewal and no extension. An authority that could be extended at
    the moment of use is an authority with no expiry at all.
    """

    binding_expires_at: datetime
    authorization_expires_at: Optional[datetime] = None
    approval_expires_at: Optional[datetime] = None
    deadline_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        for label in (
            "binding_expires_at",
            "authorization_expires_at",
            "approval_expires_at",
            "deadline_at",
        ):
            value = getattr(self, label)
            if value is not None and value.tzinfo is None:
                raise ContractViolation(f"{label} must be timezone-aware")

    @property
    def effective_expiry(self) -> datetime:
        candidates = [
            c
            for c in (
                self.binding_expires_at,
                self.authorization_expires_at,
                self.approval_expires_at,
                self.deadline_at,
            )
            if c is not None
        ]
        return min(candidates)

    @property
    def binding_expiry_source(self) -> str:
        """Which authority actually limits this action. What an operator asks first."""
        earliest = self.effective_expiry
        for label, value in (
            ("deadline", self.deadline_at),
            ("approval", self.approval_expires_at),
            ("authorization", self.authorization_expires_at),
            ("binding", self.binding_expires_at),
        ):
            if value == earliest:
                return label
        return "binding"

    def remaining_seconds(self, now: datetime) -> int:
        """Whole seconds of authority left. Floored, never rounded up.

        Rounding up would hand a worker a deadline that outlives the authority
        permitting it -- a call still running after its approval expired.
        """
        return int((self.effective_expiry - now).total_seconds())

    def is_live_at(self, now: datetime) -> bool:
        return now < self.effective_expiry

    def to_dict(self) -> dict:
        return {
            "binding_expires_at": self.binding_expires_at.isoformat(),
            "authorization_expires_at": (
                self.authorization_expires_at.isoformat()
                if self.authorization_expires_at
                else None
            ),
            "approval_expires_at": (
                self.approval_expires_at.isoformat() if self.approval_expires_at else None
            ),
            "deadline_at": self.deadline_at.isoformat() if self.deadline_at else None,
            "effective_expiry": self.effective_expiry.isoformat(),
            "limited_by": self.binding_expiry_source,
        }


# ----------------------------------------------------------------------
# The canonical action digest
# ----------------------------------------------------------------------


def canonical_action_digest(
    *,
    capability_ref: str,
    capability_digest: str,
    operation: str,
    tenant_id: str,
    principal_id: str,
    environment: ExecutionEnvironment,
    binding_digest: str,
    policy_version: Optional[str],
    payload: Mapping[str, Any],
) -> str:
    """One digest that binds the concrete action. Reuses platform hashing.

    Covers *what will happen to whom, under whose authority*: the capability and
    its contract, the operation, the tenant, the principal, the environment, the
    binding, the policy version, and the validated input.

    Deliberately excludes timestamps, worker health, availability, attempt number
    and any other volatile metadata. A digest that changed between an approval and
    the execution of the very thing approved would make approval unenforceable —
    and one that included the attempt number would make each retry a different
    action, which is exactly backwards.

    Canonicalization is the platform's (``canonical_bytes`` sorts keys and orders
    structures), so Python dict ordering cannot determine what was authorized. Two
    semantically identical payloads produce one digest; that is verified, not
    assumed.
    """
    return compute_digest(
        {
            "artifact_kind": ACTION_DIGEST_KIND,
            "capability_ref": capability_ref,
            "capability_digest": capability_digest,
            "operation": operation,
            "tenant_id": tenant_id,
            "principal_id": principal_id,
            "environment": environment.value,
            "binding_digest": binding_digest,
            "policy_version": policy_version,
            "payload": dict(payload),
        }
    ).value


# ----------------------------------------------------------------------
# The request
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class InvocationRequest:
    """The assertion that every authority artifact still names one action.

    Constructed by the governed dispatch path, never by a caller off the network.
    Every field is required except the genuinely optional ones, and none of them
    can be changed after construction.
    """

    execution_id: ExecutionId
    attempt_id: AttemptId
    attempt_number: int
    node_id: str

    tenant_id: str
    principal: PrincipalRef

    capability_ref: str
    """``namespace.provider.capability@version`` as one indivisible token. See the
    module docstring: comparing it enforces both the id and the version clause,
    and cannot drift between them."""

    capability_digest: str

    operation: str
    """The **provider** operation: the concrete action the adapter will perform,
    keyed into the provider's operation catalog (``repository.get_repository``).

    This is the one the action digest covers, because the action digest exists to
    say *what will actually happen*. A governance verb in that digest would let
    two different concrete actions produce the same digest."""

    environment: ExecutionEnvironment

    binding_id: str
    binding_digest: str

    worker_selection_id: str
    worker_id: str
    worker_digest: str

    payload: Mapping[str, Any] = field(default_factory=dict)
    """The caller's input, **unvalidated at this point**. The gateway validates
    it and only then digests it — digesting first would bind whatever arrived."""

    governance_operation: Optional[str] = None
    """The **governance** verb the authorization decided on (``invoke``).

    A closed vocabulary (``CapabilityOperation``), and deliberately a separate
    field. Before Phase 5.5 one field carried both meanings, and whichever reader
    lost got a value it could not parse: ``CapabilityOperation(
    'repository.get_repository')`` raises, and ``catalog.get('invoke')`` returns
    nothing. Naming them separately is what makes both independently checkable.

    Optional only so that a request built before this field existed still
    constructs; the gateway refuses when it is absent, so absence is not a
    bypass."""

    lease_holder_id: Optional[str] = None
    """Which **execution participant** holds the node lease this request runs under.

    Not the worker. ADR-036 §9 is explicit -- "Execution owns lease acquisition,
    heartbeat, expiry and reclaim; a worker **never acquires its own lease**" --
    and ``worker_runtime`` says the same at its own lease check. The lease
    answers *who may produce this node's result*; ``worker_id`` answers *which
    implementation performs the provider call*. They are different questions and
    they have different answers: the dispatcher holds the lease, the connector
    does the work.

    A separate field because the gateway previously compared the aggregate's
    lease holder against the selected worker, which is a comparison between two
    vocabularies -- so it refused every invocation, exactly as comparing a
    governance verb against a provider operation did.

    Optional only so a request built before this field existed still constructs.
    The gateway refuses when it is absent, so absence is not a bypass."""

    declared_action_digest: Optional[str] = None
    """What the caller believes the action digest is. Optional; when present it
    must equal what the gateway computes, which is how a payload swapped between
    approval and invocation is caught."""

    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    causation_id: Optional[str] = None
    deadline_at: Optional[datetime] = None
    execution_key: Optional[str] = None
    idempotency_key: Optional[str] = None
    """Execution's already-derived key (ADR-031). Passed through, never minted
    here — a second key for one logical operation is a second operation."""

    on_behalf_of: Optional[PrincipalRef] = None
    """The original requester when the actor is acting for somebody else. Kept
    distinct from ``principal`` rather than flattened: collapsing them loses which
    of the two a decision was actually made about."""

    requested_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        if not isinstance(self.execution_id, ExecutionId):
            raise ContractViolation("execution_id must be an ExecutionId")
        if not isinstance(self.attempt_id, AttemptId):
            raise ContractViolation("attempt_id must be an AttemptId")
        if not isinstance(self.principal, PrincipalRef):
            raise ContractViolation("principal must be a PrincipalRef")
        if self.on_behalf_of is not None and not isinstance(
            self.on_behalf_of, PrincipalRef
        ):
            raise ContractViolation("on_behalf_of must be a PrincipalRef when present")
        if not isinstance(self.environment, ExecutionEnvironment):
            raise ContractViolation(
                "environment must be an ExecutionEnvironment; an unstated or "
                "free-form environment is not a wildcard and cannot be compared "
                "against what a binding and a worker were entitled to"
            )
        if self.attempt_number < 1:
            raise ContractViolation("attempt numbers start at 1")
        for label in (
            "node_id",
            "tenant_id",
            "capability_ref",
            "capability_digest",
            "operation",
            "binding_id",
            "binding_digest",
            "worker_selection_id",
            "worker_id",
            "worker_digest",
        ):
            value = getattr(self, label)
            if not isinstance(value, str) or not value.strip():
                raise ContractViolation(
                    f"{label} must be non-blank text; a request missing it names an "
                    "authority nobody can check, and an uncheckable claim is not one"
                )
        if self.deadline_at is not None and self.deadline_at.tzinfo is None:
            raise ContractViolation("deadline_at must be timezone-aware")
        if self.requested_at.tzinfo is None:
            raise ContractViolation("requested_at must be timezone-aware")

    # -- queries -------------------------------------------------------

    @property
    def principal_id(self) -> str:
        return self.principal.principal_id

    @property
    def actor_chain(self) -> tuple:
        """Actor, then the principal on whose behalf it acts. Never flattened."""
        if self.on_behalf_of is None:
            return (self.principal.principal_id,)
        return (self.principal.principal_id, self.on_behalf_of.principal_id)

    def action_digest(
        self, *, policy_version: Optional[str], payload: Mapping[str, Any]
    ) -> str:
        """The canonical digest for this action over an explicitly given payload.

        The payload is a parameter rather than read from ``self`` so the caller
        must pass the *validated* one. Reading it from the request would make it
        effortless to digest the unvalidated input, and effortless is how that
        happens.
        """
        return canonical_action_digest(
            capability_ref=self.capability_ref,
            capability_digest=self.capability_digest,
            operation=self.operation,
            tenant_id=self.tenant_id,
            principal_id=self.principal_id,
            environment=self.environment,
            binding_digest=self.binding_digest,
            policy_version=policy_version,
            payload=payload,
        )

    def to_dict(self) -> dict:
        """No payload. Input carries customer data and this reaches audit."""
        return {
            "artifact_kind": INVOCATION_ARTIFACT_KIND,
            "execution_id": str(self.execution_id),
            "attempt_id": str(self.attempt_id),
            "attempt_number": self.attempt_number,
            "node_id": self.node_id,
            "tenant_id": self.tenant_id,
            "principal_id": self.principal_id,
            "on_behalf_of": (
                self.on_behalf_of.principal_id if self.on_behalf_of else None
            ),
            "capability_ref": self.capability_ref,
            "capability_digest": self.capability_digest,
            "lease_holder_id": self.lease_holder_id,
            "provider_operation": self.operation,
            "governance_operation": self.governance_operation,
            "environment": self.environment.value,
            "binding_id": self.binding_id,
            "binding_digest": self.binding_digest,
            "worker_selection_id": self.worker_selection_id,
            "worker_id": self.worker_id,
            "worker_digest": self.worker_digest,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "causation_id": self.causation_id,
            "deadline_at": self.deadline_at.isoformat() if self.deadline_at else None,
            "requested_at": self.requested_at.isoformat(),
        }
