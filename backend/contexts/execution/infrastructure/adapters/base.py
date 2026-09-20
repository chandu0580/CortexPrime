"""The shared gate every adapter runs before it touches a provider.

One gate, not one per provider
--------------------------------
Each concrete adapter has its own transport, its own error vocabulary and its
own idea of what "done" means. Everything they have in *common* — checking the
request is theirs, checking the authority is still live, honouring the declared
effect, mapping whatever came back onto the failure taxonomy, and refusing when
anything is missing — lives here, once. The alternative is each provider
re-deriving the ambiguity rules, and the first one to get them slightly wrong
reports a timeout as a failure and a lost mutation gets retried.

An adapter reports; it never concludes
----------------------------------------
``_perform`` returns a ``ProviderOutcome``: what the provider said, in the
provider's own terms. This module turns that into a ``WorkerExecutionResult``,
and Execution decides what the result means. No adapter decides whether to
retry, whether a node failed, or what the run's state becomes.

Authority arrives; it is never manufactured
---------------------------------------------
**Phase 4.3.** Every invocation now requires a ``ProviderAuthority`` — the object
the invocation gateway builds after the whole authority chain agreed. An adapter
called without one refuses, and that refusal is the structural form of ADR-042
§4: there is no path from a route, a service or a test to a provider call that
does not pass the gateway, because the thing the adapter needs can only be
produced there.

The authority is also re-checked here, immediately before anything leaves
(§37). Selection-time state is not enough: between the gateway admitting the
invocation and the socket opening, a binding can expire, a credential can be
revoked and a cancellation can be requested. Re-reading costs a comparison and
closes the window an operator uses to stop something.

Ambiguity survives translation
--------------------------------
The one thing that must not be lost on the way through: a call that stopped
without an answer is ``UNKNOWN_OUTCOME``, never ``FAILURE``. "The socket closed"
is a fact about this side. Whether the far side applied the change is unknown,
and an adapter that reports failure has asserted something it cannot know —
after which the retry rules, reading a definite failure, will happily run the
mutation again.

Effect claims are checked in both directions
----------------------------------------------
An adapter may not report a stronger effect than the binding declared (that is a
capability performing work it was not authorized for), and it may not report
``READ`` for a binding that mutates (that is a write being recorded as a read).
Both become anomalies, and an anomaly is ``UNKNOWN_OUTCOME`` — the change may
well have landed, and saying otherwise would be the same mistake in a nicer tone.

No retry, no credential acquisition, no state
-----------------------------------------------
There is no retry loop here and there will not be one: Execution owns retry,
attempt numbering and ambiguity handling (ADR-031). There is no credential
*acquisition*: the material arrives on the authority, already minted against
this action's digest, and an adapter that fetched its own would put a secret
outside the boundary designed to hold it. Adapters hold no mutable state, so
nothing accumulates across invocations.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, ClassVar, Mapping, Optional, Protocol, Tuple, runtime_checkable

from backend.contracts.errors import ContractViolation
from backend.contracts.execution import SideEffectClass
from backend.contracts.provider import (
    ADAPTER_METRICS,
    AdapterRef,
    ProviderDelivery,
    ProviderFailure,
    ProviderRef,
)
from backend.contexts.execution.domain.bound_capability import BoundCapability
from backend.contexts.execution.domain.failure import FailureClass, FailureRecord
from backend.contexts.execution.domain.provider_invocation import ProviderAuthority
from backend.contexts.execution.domain.worker import (
    WorkerHealth,
    WorkerKind,
    WorkerRegistration,
)
from backend.contexts.execution.domain.worker_contract import (
    CancellationSupport,
    WorkerExecutionRequest,
    WorkerExecutionResult,
    WorkerOutcome,
)
from backend.contexts.execution.domain.worker_directory import (
    WORKER_PROTOCOL_VERSION,
    WorkerImplementation,
    WorkerInterface,
)
from backend.platform.hashing import compute_digest

__all__ = [
    "ProviderOutcome",
    "AdapterSeam",
    "AdapterPreflight",
    "ProviderInvoker",
    "TransportUnavailable",
    "ADAPTER_UNAVAILABLE_REASON",
    "AUTHORITY_REQUIRED_REASON",
    "PROVIDER_FAILURE_CLASSES",
]

log = logging.getLogger(__name__)

ADAPTER_UNAVAILABLE_REASON = (
    "no provider transport is wired behind this adapter seam, so nothing was "
    "sent; there is no default transport and no fallback adapter"
)

AUTHORITY_REQUIRED_REASON = (
    "this adapter was invoked without invocation-gateway authority. An adapter "
    "consumes authority that the gateway established; it cannot manufacture a "
    "tenant, a principal, a binding, an action digest or a credential, so an "
    "invocation arriving without one is refused rather than performed"
)

#: How a provider-neutral failure lands on Phase 3.1's taxonomy. The ambiguous
#: side of this table is the load-bearing part: every entry that could have been
#: applied maps to ``UNKNOWN_OUTCOME``, so the retry rules never read a definite
#: failure for an operation nobody can account for.
PROVIDER_FAILURE_CLASSES: Mapping[ProviderFailure, FailureClass] = {
    ProviderFailure.AUTHENTICATION_FAILURE: FailureClass.AUTHORIZATION_FAILURE,
    ProviderFailure.AUTHORIZATION_FAILURE: FailureClass.AUTHORIZATION_FAILURE,
    ProviderFailure.NOT_FOUND: FailureClass.PERMANENT_FAILURE,
    ProviderFailure.CONFLICT: FailureClass.EXTERNAL_SYSTEM_FAILURE,
    ProviderFailure.VALIDATION_FAILURE: FailureClass.VALIDATION_FAILURE,
    ProviderFailure.PRECONDITION_FAILED: FailureClass.EXTERNAL_SYSTEM_FAILURE,
    ProviderFailure.RATE_LIMITED: FailureClass.TRANSIENT_FAILURE,
    ProviderFailure.UNAVAILABLE: FailureClass.EXTERNAL_SYSTEM_FAILURE,
    ProviderFailure.QUOTA_EXCEEDED: FailureClass.TRANSIENT_FAILURE,
    ProviderFailure.TIMEOUT: FailureClass.TIMEOUT,
    ProviderFailure.CANCELLED: FailureClass.CANCELLATION,
    ProviderFailure.PROTOCOL_ERROR: FailureClass.UNKNOWN_OUTCOME,
    ProviderFailure.MALFORMED_RESPONSE: FailureClass.UNKNOWN_OUTCOME,
    ProviderFailure.RESPONSE_TOO_LARGE: FailureClass.UNKNOWN_OUTCOME,
    ProviderFailure.TRANSPORT_REFUSED: FailureClass.PERMANENT_FAILURE,
    ProviderFailure.CREDENTIAL_REFUSED: FailureClass.PERMANENT_FAILURE,
    ProviderFailure.OPERATION_NOT_SUPPORTED: FailureClass.PERMANENT_FAILURE,
    ProviderFailure.PROVIDER_MISMATCH: FailureClass.PERMANENT_FAILURE,
    ProviderFailure.ADAPTER_UNAVAILABLE: FailureClass.PERMANENT_FAILURE,
    ProviderFailure.CONTRACT_MISMATCH: FailureClass.PERMANENT_FAILURE,
    ProviderFailure.EFFECT_EXCEEDED: FailureClass.UNKNOWN_OUTCOME,
    ProviderFailure.UNKNOWN_OUTCOME: FailureClass.UNKNOWN_OUTCOME,
}


class TransportUnavailable(ContractViolation):
    """No provider transport is attached to this seam.

    Raised only where a caller asked for something that cannot exist. The ``run``
    path does not raise it — it returns a definite ``FAILURE``, because nothing
    left this process and "it did not happen" is a claim that is true.
    """


@runtime_checkable
class ProviderInvoker(Protocol):
    """The transport port a concrete adapter attaches to.

    Each seam narrows this to its own target and outcome types. Kept to a single
    method on purpose: a port with a ``connect``, a ``login`` and a ``session``
    invites an adapter to own a lifecycle, and a lifecycle is where credentials
    and retries end up living.
    """

    def invoke(self, authority: ProviderAuthority, request: Any) -> "ProviderOutcome": ...


@runtime_checkable
class AdapterPreflight(Protocol):
    """The last authoritative re-read before bytes leave. Implemented at the root.

    ADR-042 §37. The worker runtime already re-read the directory entry when it
    admitted the invocation; this runs *inside* the adapter, at the last
    instant, over whatever the deployment considers authoritative — the worker
    entry, the adapter's own enablement, the connection policy.

    Returns refusal reasons; empty means proceed. **Absence is not a bypass**:
    an adapter with no preflight still runs every check in ``_authority_stale``,
    which is the set that can be answered without asking anybody.
    """

    def refusals(self, authority: ProviderAuthority, *, now: datetime) -> Tuple[str, ...]: ...


@dataclass(frozen=True)
class ProviderOutcome:
    """What a provider said, before it means anything.

    Deliberately not a ``WorkerExecutionResult``. An adapter author fills this in
    with facts they actually have; the translation into outcome semantics,
    failure classes and ambiguity happens in ``AdapterSeam``, once, under rules
    they cannot accidentally reinterpret.
    """

    succeeded: bool = False
    ambiguous: bool = False
    """The call did not complete and this side cannot say whether the far side
    applied it. Takes precedence over ``succeeded`` — an outcome that is both is
    an outcome nobody knows, which is what ambiguity means."""

    timed_out: bool = False
    cancelled: bool = False

    delivery: ProviderDelivery = ProviderDelivery.UNKNOWN
    """Whether the operation reached the provider. Defaults to ``UNKNOWN``
    because certainty is the thing being claimed, and an adapter that forgot to
    say should not be read as having said 'nothing was sent'."""

    output: Optional[Mapping[str, Any]] = None
    """Digested, never carried into the result. Provider results are unbounded
    and can contain anything, including the caller's own data coming back."""

    evidence: Mapping[str, Any] = field(default_factory=dict)
    """The small, declared, non-sensitive fields worth keeping — an issue
    number, a resource id. Bounded by the operation's declaration, so an adapter
    cannot widen it at runtime."""

    observed_effect: Optional[SideEffectClass] = None
    provider_failure: Optional[ProviderFailure] = None
    """The neutral classification. Preferred over ``failure_class``: it is the
    vocabulary recovery reads, and leaving it ``None`` on a non-success is
    treated as ``UNKNOWN_OUTCOME`` rather than as a definite failure."""

    error_code: Optional[str] = None
    error_message: Optional[str] = None
    failure_class: Optional[FailureClass] = None
    """Set only where an adapter genuinely knows better than the table above.
    Left ``None`` is the ordinary case and is safe."""

    retry_after_seconds: Optional[float] = None
    """What the provider said about when to come back. **A fact, never an
    instruction.** Nothing in this fabric sleeps on it; Execution's recovery
    decides whether another attempt is safe at all (ADR-042 §25, §58)."""

    provider_request_id: Optional[str] = None
    """The provider's own correlation handle, where it publishes a non-secret
    one. What an operator quotes in a support ticket."""

    response_digest: Optional[str] = None
    status_code: Optional[int] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)
    """Non-sensitive provider facts — status codes, request ids, rate-limit
    hints. Reaches audit, so never a token, a header, or a payload."""

    def __post_init__(self) -> None:
        if self.succeeded and (self.ambiguous or self.timed_out or self.cancelled):
            raise ContractViolation(
                "a provider outcome cannot be both successful and unresolved; "
                "reporting both leaves whoever reads it to decide which was true"
            )
        if self.succeeded and self.provider_failure is not None:
            raise ContractViolation(
                "a successful provider outcome cannot carry a failure "
                "classification"
            )
        if not isinstance(self.delivery, ProviderDelivery):
            raise ContractViolation("delivery must be a ProviderDelivery")
        if self.succeeded and self.delivery is not ProviderDelivery.DELIVERED:
            raise ContractViolation(
                "a provider outcome cannot be successful without having been "
                "delivered; success is a claim about what the provider did, and "
                "it cannot have done anything it did not receive"
            )

    @property
    def resolved_failure(self) -> ProviderFailure:
        """The classification to act on. Conservative when nobody said."""
        if self.provider_failure is not None:
            return self.provider_failure
        if self.timed_out:
            return ProviderFailure.TIMEOUT
        if self.cancelled:
            return ProviderFailure.CANCELLED
        return ProviderFailure.UNKNOWN_OUTCOME

    @property
    def is_unresolved(self) -> bool:
        """Whether nobody can say what the provider did."""
        if self.succeeded:
            return False
        return (
            self.ambiguous
            or self.timed_out
            or self.delivery is ProviderDelivery.UNKNOWN
            or self.resolved_failure.is_ambiguous
        )

    # -- construction ----------------------------------------------------

    @classmethod
    def refused(
        cls, failure: ProviderFailure, message: str, **fields: Any
    ) -> "ProviderOutcome":
        """A refusal raised before anything was transmitted.

        ``NOT_ATTEMPTED`` only where the failure can be shown to precede
        transmission; anything else stays ``UNKNOWN``, because a refusal raised
        after a socket opened may have been preceded by bytes.
        """
        return cls(
            provider_failure=failure,
            error_message=message,
            delivery=(
                ProviderDelivery.NOT_ATTEMPTED
                if failure.is_definitely_not_applied
                else ProviderDelivery.UNKNOWN
            ),
            **fields,
        )

    @classmethod
    def unresolved(cls, message: str, **fields: Any) -> "ProviderOutcome":
        """The safe answer when nobody can say. Always available."""
        return cls(
            ambiguous=True,
            provider_failure=ProviderFailure.UNKNOWN_OUTCOME,
            error_message=message,
            delivery=ProviderDelivery.UNKNOWN,
            **fields,
        )


class AdapterSeam:
    """Base for every concrete provider adapter. Implements ``ExecutionWorker``.

    Subclasses declare what they are, which provider they serve, and implement
    ``_perform``. They do not override ``run``: the gate below is the part that
    must be identical everywhere, and a provider author who could replace it
    would eventually replace the ambiguity rule with something more convenient.
    """

    WORKER_KIND: ClassVar[WorkerKind]
    INTERFACE: ClassVar[WorkerInterface]
    IMPLEMENTATION_VERSION: ClassVar[str] = "0.1.0"
    PROTOCOL_VERSION: ClassVar[str] = WORKER_PROTOCOL_VERSION
    CANCELLATION: ClassVar[CancellationSupport] = CancellationSupport.NONE

    REQUIRES_CREDENTIAL: ClassVar[bool] = True
    """Whether this adapter refuses without credential material.

    ``True`` by default and overridden only where a provider genuinely needs no
    authentication. Defaulting the other way would make a wiring mistake — a
    credential adapter that was never registered — look like an anonymous
    provider call that happens to fail at the far end.
    """

    CONSUMES_PROVIDER_AUTHORITY: ClassVar[bool] = True
    """Read by ``WorkerRuntime`` to decide whether to thread the authority down.
    A marker rather than a signature probe: exception-driven feature detection
    would turn a wiring mistake into an ambiguous outcome."""

    def __init__(
        self,
        *,
        implementation: WorkerImplementation,
        provider: ProviderRef,
        invoker: Optional[Any] = None,
        preflight: Optional[AdapterPreflight] = None,
        metrics: Optional[Any] = None,
    ) -> None:
        if not isinstance(implementation, WorkerImplementation):
            raise ContractViolation("implementation must be a WorkerImplementation")
        if not isinstance(provider, ProviderRef):
            raise ContractViolation(
                "an adapter must name the provider it serves; one that serves "
                "'whatever turns up' is the substitution this layer exists to "
                "prevent"
            )
        if implementation.worker_kind is not type(self).WORKER_KIND:
            raise ContractViolation(
                f"{type(self).__name__} runs {type(self).WORKER_KIND.value} work but "
                f"was registered as {implementation.worker_kind.value}; an adapter "
                "wired under the wrong kind would be selected for work it cannot do"
            )
        if implementation.interface is not type(self).INTERFACE:
            raise ContractViolation(
                f"{type(self).__name__} drives {type(self).INTERFACE.value} providers "
                f"but was registered as {implementation.interface.value}"
            )
        if implementation.protocol_version != type(self).PROTOCOL_VERSION:
            raise ContractViolation(
                f"{type(self).__name__} speaks {type(self).PROTOCOL_VERSION} but was "
                f"registered as {implementation.protocol_version}"
            )
        if provider.provider_id not in implementation.supported_providers:
            # The registration is what worker selection reads. An adapter
            # serving a provider its registration does not list would be
            # selected for one provider and would address another.
            raise ContractViolation(
                f"{type(self).__name__} serves {provider.provider_id!r} but its "
                f"registration declares "
                f"{', '.join(sorted(implementation.supported_providers))}"
            )
        self._implementation = implementation
        self._provider = provider
        self._invoker = invoker
        self._preflight = preflight
        self._metrics = metrics

    # ------------------------------------------------------------------
    # Identity
    # ------------------------------------------------------------------

    @property
    def implementation(self) -> WorkerImplementation:
        return self._implementation

    @property
    def provider(self) -> ProviderRef:
        return self._provider

    @property
    def adapter(self) -> AdapterRef:
        """This adapter's own identity, distinct from the worker's.

        Derived from the registration rather than stored separately, so the two
        cannot drift: a rebuilt implementation changes the worker digest and the
        adapter version together.
        """
        return AdapterRef(
            adapter_id=type(self).__name__,
            provider_id=self._provider.provider_id,
            version=self._implementation.implementation_version,
        )

    @property
    def has_transport(self) -> bool:
        return self._invoker is not None

    def registration(self) -> WorkerRegistration:
        """What this adapter offers, in the ADR-029 vocabulary the pool reads."""
        return WorkerRegistration.create(
            self._implementation.worker_id,
            [self._implementation.worker_kind],
            labels=(
                f"interface={self._implementation.interface.value}",
                f"provider={self._provider.provider_id}",
                f"version={self._implementation.implementation_version}",
                f"isolation={self._implementation.isolation.value}",
            ),
        )

    def heartbeat(self, context: Any, worker_id: str) -> WorkerHealth:
        """How this adapter is. Honest about having nothing behind it.

        ``LOST`` rather than ``READY`` while no transport is wired: a seam that
        reported itself ready would be offered work it cannot perform, and the
        node would burn an attempt discovering that.

        **Deliberately not a provider health probe** (ADR-042 §59). It reports
        what this process knows about itself and contacts nobody — a probe on
        every heartbeat would multiply provider traffic by the fleet size, and a
        provider being reachable is not authorization anyway.
        """
        return WorkerHealth.READY if self.has_transport else WorkerHealth.LOST

    def cancel(self, context: Any, execution_id: str, node_id: str) -> bool:
        """Stop work in flight. ``False`` unless the provider confirms it stopped.

        The default is ``False`` and subclasses should keep it unless their
        provider genuinely confirms cancellation. Returning ``True`` on the
        strength of having *sent* a cancel is the lie that turns a still-running
        mutation into a node the runtime believes is finished.
        """
        return False

    def supports_operation(self, operation: str) -> bool:
        """Whether this adapter declares the operation. Exact match, always.

        Overridden by catalog-driven adapters. The base answer is ``True``
        because a seam with no catalog has no narrower statement to make; every
        such adapter still refuses anything the *binding* does not authorize,
        which is the check that cannot be skipped.
        """
        return True

    # ------------------------------------------------------------------
    # The gate
    # ------------------------------------------------------------------

    def run(
        self,
        context: Any,
        request: WorkerExecutionRequest,
        *,
        authority: Optional[ProviderAuthority] = None,
    ) -> WorkerExecutionResult:
        """Perform the bound operation, once. Never overridden."""
        started = datetime.now(timezone.utc)

        if not isinstance(request, WorkerExecutionRequest):
            raise ContractViolation(
                "an adapter is handed a WorkerExecutionRequest; anything else has "
                "not been through the gate that decides what may run"
            )
        binding = request.binding

        # The request was routed here by kind. Checking again is cheap and closes
        # the case where an adapter is wired into the wrong directory entry.
        if request.worker_kind is not type(self).WORKER_KIND:
            return self._refused(
                request,
                started,
                FailureClass.VALIDATION_FAILURE,
                f"this adapter runs {type(self).WORKER_KIND.value} work; the request "
                f"names {request.worker_kind.value}",
                provider_failure=ProviderFailure.VALIDATION_FAILURE,
            )

        # -- authority. ADR-042 §4: no gateway, no provider call --------
        if authority is None:
            self._count("adapter.refused", None, reason="authority_missing")
            return self._refused(
                request,
                started,
                FailureClass.PERMANENT_FAILURE,
                AUTHORITY_REQUIRED_REASON,
                provider_failure=ProviderFailure.ADAPTER_UNAVAILABLE,
            )
        if not isinstance(authority, ProviderAuthority):
            return self._refused(
                request,
                started,
                FailureClass.PERMANENT_FAILURE,
                "the authority supplied is not a ProviderAuthority; an adapter "
                "acts on the gateway's own artifact or on nothing",
                provider_failure=ProviderFailure.ADAPTER_UNAVAILABLE,
            )
        mismatch = self._authority_disagrees(request, authority)
        if mismatch:
            # The authority describes a different invocation than the request.
            # One of them belongs to another run, possibly another tenant, and
            # guessing which would be the whole breach.
            self._count("adapter.refused", authority, reason="authority_mismatch")
            return self._refused(
                request,
                started,
                FailureClass.PERMANENT_FAILURE,
                mismatch,
                provider_failure=ProviderFailure.PROVIDER_MISMATCH,
            )

        self._count("adapter.invocation", authority)

        # -- TOCTOU. Everything re-read at the last instant (§37) -------
        stale = self._authority_stale(authority, now=started)
        if stale:
            # The first classification, in the order the checks are written --
            # fixed so that a request wrong in three ways always reports the
            # same one, and two identical requests never look like two problems.
            first = stale[0][0]
            self._count("adapter.refused", authority, reason=first.value)
            return self._refused(
                request,
                started,
                (
                    FailureClass.CANCELLATION
                    if authority.cancelled
                    else FailureClass.PERMANENT_FAILURE
                ),
                "; ".join(reason for _, reason in stale)[:400],
                provider_failure=first,
            )
        if self._preflight is not None:
            try:
                refusals = self._preflight.refusals(authority, now=started)
            except Exception as exc:  # noqa: BLE001 - unverifiable is unusable
                return self._refused(
                    request,
                    started,
                    FailureClass.PERMANENT_FAILURE,
                    f"the adapter's authority could not be revalidated "
                    f"({type(exc).__name__}); nothing was sent",
                    provider_failure=ProviderFailure.ADAPTER_UNAVAILABLE,
                )
            if refusals:
                self._count("adapter.refused", authority, reason="preflight")
                return self._refused(
                    request,
                    started,
                    FailureClass.PERMANENT_FAILURE,
                    "; ".join(str(r) for r in refusals)[:400],
                    provider_failure=ProviderFailure.ADAPTER_UNAVAILABLE,
                )

        if self._invoker is None:
            # Nothing was sent, so FAILURE is a claim that is true. Reporting
            # UNKNOWN here would make an unwired seam look like a lost mutation
            # and block retry on a node that never left the building.
            self._count("adapter.refused", authority, reason="adapter_unavailable")
            return self._refused(
                request,
                started,
                FailureClass.PERMANENT_FAILURE,
                ADAPTER_UNAVAILABLE_REASON,
                provider_failure=ProviderFailure.ADAPTER_UNAVAILABLE,
            )

        if request.deadline_seconds is not None and request.deadline_seconds < 1:
            return self._refused(
                request,
                started,
                FailureClass.VALIDATION_FAILURE,
                "the request carries a non-positive deadline",
                provider_failure=ProviderFailure.VALIDATION_FAILURE,
            )

        try:
            outcome = self._perform(context, request, authority)
        except Exception as exc:  # noqa: BLE001 - classified, never leaked
            # Never ``str(exc)`` unguarded from an HTTP client: its exceptions
            # routinely carry the request they were making, headers included.
            from backend.platform.credentials import safe_exception_text

            log.warning(
                "adapter %s raised against %s",
                type(self).__name__,
                self._provider.provider_id,
                exc_info=False,
            )
            return WorkerExecutionResult(
                outcome=WorkerOutcome.UNKNOWN_OUTCOME,
                binding_id=binding.binding_id,
                attempt_id=str(request.attempt_id),
                started_at=started,
                completed_at=datetime.now(timezone.utc),
                failure=FailureRecord(
                    failure_class=FailureClass.UNKNOWN_OUTCOME,
                    reason=(
                        f"{safe_exception_text(exc)}"[:400]
                        + " -- the adapter raised without saying whether the "
                        "operation reached the provider"
                    ),
                    source=f"adapter:{type(self).__name__}",
                ),
                detail=self._identity_detail(authority),
            )

        if not isinstance(outcome, ProviderOutcome):
            return WorkerExecutionResult.unknown(
                binding_id=binding.binding_id,
                attempt_id=str(request.attempt_id),
                started_at=started,
                reason=(
                    f"the adapter returned {type(outcome).__name__}, not a "
                    "ProviderOutcome; what it did is unknown"
                ),
                detail=self._identity_detail(authority),
            )

        return self._translate(request, authority, outcome, started)

    # ------------------------------------------------------------------
    # Authority checks
    # ------------------------------------------------------------------

    @staticmethod
    def _authority_disagrees(
        request: WorkerExecutionRequest, authority: ProviderAuthority
    ) -> Optional[str]:
        """Whether the authority is about the invocation in hand. Every field."""
        pairs = (
            ("tenant", request.tenant_id, authority.tenant_id),
            (
                "principal",
                request.principal.principal_id,
                authority.principal.principal_id,
            ),
            ("execution", str(request.execution_id), authority.execution_id),
            ("node", request.node_id, authority.node_id),
            ("attempt", str(request.attempt_id), authority.attempt_id),
            ("binding", request.binding.binding_id, authority.binding.binding_id),
            (
                "binding digest",
                request.binding.binding_digest,
                authority.binding.binding_digest,
            ),
            ("operation", request.binding.operation, authority.operation),
        )
        differing = [label for label, left, right in pairs if left != right]
        if not differing:
            return None
        return (
            "the authority and the request disagree on "
            + ", ".join(differing)
            + "; one of them describes another invocation and this adapter will "
            "not choose between them"
        )

    def _authority_stale(
        self, authority: ProviderAuthority, *, now: datetime
    ) -> Tuple[Tuple[ProviderFailure, str], ...]:
        """Everything that must still hold, checked at the last possible moment.

        Deliberately answerable without asking anybody: these are the checks that
        cannot fail because a collaborator was unavailable, so they run whether
        or not a preflight port is wired.

        Each problem is returned with its classification rather than as bare
        text, so a refusal raised on this side reaches recovery in the same
        vocabulary a provider's own refusal would.
        """
        problems: list = []

        if authority.cancelled:
            reason = (authority.cancellation.reason if authority.cancellation else None)
            problems.append(
                (
                    ProviderFailure.CANCELLED,
                    f"the invocation was cancelled before it was sent: {reason}",
                )
            )
        if not authority.binding.is_live_at(now):
            problems.append(
                (
                    ProviderFailure.TRANSPORT_REFUSED,
                    "the binding expired before the provider was contacted; "
                    "expiry is never extended at the point of use",
                )
            )
        if (
            authority.authority_expires_at is not None
            and now >= authority.authority_expires_at
        ):
            problems.append(
                (
                    ProviderFailure.TRANSPORT_REFUSED,
                    "the authority window closed before the provider was contacted",
                )
            )
        if authority.remaining_seconds(now) <= 0:
            problems.append(
                (
                    ProviderFailure.TRANSPORT_REFUSED,
                    "no authority window remains; a provider call started now "
                    "would outlive the permission for it",
                )
            )
        if not self._provider.matches(authority.binding.provider):
            problems.append(
                (
                    ProviderFailure.PROVIDER_MISMATCH,
                    f"this adapter serves {self._provider.provider_id!r} but the "
                    f"binding names {authority.binding.provider!r}; there is no "
                    "fallback provider and no substitution",
                )
            )
        if not self.supports_operation(authority.operation):
            problems.append(
                (
                    ProviderFailure.OPERATION_NOT_SUPPORTED,
                    f"this adapter declares no operation {authority.operation!r}",
                )
            )
        if type(self).REQUIRES_CREDENTIAL:
            grant = authority.credential_grant
            if grant is None:
                problems.append(
                    (
                        ProviderFailure.CREDENTIAL_REFUSED,
                        "no credential was issued for this action and this "
                        "adapter requires one; an adapter does not read the "
                        "environment, a global store, or an inbound "
                        "Authorization header",
                    )
                )
            elif not grant.is_live_at(now):
                problems.append(
                    (
                        ProviderFailure.CREDENTIAL_REFUSED,
                        "the credential issued for this action is no longer live",
                    )
                )
            elif grant.action_digest != authority.action_digest:
                problems.append(
                    (
                        ProviderFailure.CREDENTIAL_REFUSED,
                        "the credential was minted for a different action than "
                        "the one about to run",
                    )
                )
        return tuple(problems)

    # ------------------------------------------------------------------
    # Translation
    # ------------------------------------------------------------------

    def _identity_detail(self, authority: Optional[ProviderAuthority]) -> dict:
        detail = {
            "adapter": type(self).__name__,
            "adapter_ref": self.adapter.value,
            "provider_ref": self._provider.value,
            "worker_id": self._implementation.worker_id,
            "worker_version": self._implementation.implementation_version,
            "interface": self._implementation.interface.value,
            "transport_attached": self.has_transport,
        }
        if authority is not None:
            detail.update(
                {
                    "operation": authority.operation,
                    "action_digest": authority.action_digest,
                    "selection_id": authority.selection_id,
                }
            )
        return detail

    def _translate(
        self,
        request: WorkerExecutionRequest,
        authority: ProviderAuthority,
        outcome: ProviderOutcome,
        started: datetime,
    ) -> WorkerExecutionResult:
        binding = request.binding
        completed = datetime.now(timezone.utc)
        failure = outcome.resolved_failure

        detail = {
            **self._identity_detail(authority),
            "provider_delivery": outcome.delivery.value,
            **{f"provider_{k}": v for k, v in dict(outcome.metadata).items()},
        }
        if outcome.status_code is not None:
            detail["provider_status"] = outcome.status_code
        if outcome.error_code:
            detail["provider_error_code"] = outcome.error_code
        if outcome.provider_request_id:
            detail["provider_request_id"] = outcome.provider_request_id
        if outcome.retry_after_seconds is not None:
            # A fact, carried for recovery to read. Nothing here waits on it.
            detail["provider_retry_after_seconds"] = outcome.retry_after_seconds
        if outcome.evidence:
            detail["provider_evidence"] = dict(outcome.evidence)
        if not outcome.succeeded:
            detail["provider_failure"] = failure.value
            detail["security_relevant"] = failure.is_security_relevant

        anomaly = self._effect_anomaly(outcome, binding)
        if anomaly:
            # Not a failure and not a success: the provider did something other
            # than what the binding authorized, and whether it landed is unknown.
            self._count("adapter.failure", authority, reason="effect_anomaly")
            self._count("adapter.effect_anomaly", authority)
            return WorkerExecutionResult.unknown(
                binding_id=binding.binding_id,
                attempt_id=str(request.attempt_id),
                started_at=started,
                reason=anomaly,
                completed_at=completed,
                detail={
                    **detail,
                    "effect_anomaly": True,
                    "provider_failure": ProviderFailure.EFFECT_EXCEEDED.value,
                },
            )

        if outcome.succeeded:
            self._count("adapter.success", authority)
            return WorkerExecutionResult(
                outcome=WorkerOutcome.SUCCESS,
                binding_id=binding.binding_id,
                attempt_id=str(request.attempt_id),
                started_at=started,
                completed_at=completed,
                result_digest=(
                    outcome.response_digest
                    or (
                        compute_digest(dict(outcome.output)).value
                        if outcome.output is not None
                        else None
                    )
                ),
                observed_effect=outcome.observed_effect,
                detail=detail,
                cancellation_support=type(self).CANCELLATION,
            )

        self._count("adapter.failure", authority, reason=failure.value)
        metric = failure.metric
        if metric:
            self._count(metric, authority)

        # -- cancellation, which is only cancellation when it is proved -
        if outcome.cancelled or failure is ProviderFailure.CANCELLED:
            proved = type(self).CANCELLATION.proves_stopped
            return self._result(
                request,
                started,
                completed,
                detail,
                outcome,
                worker_outcome=(
                    WorkerOutcome.CANCELLATION if proved else WorkerOutcome.UNKNOWN_OUTCOME
                ),
                failure_class=(
                    FailureClass.CANCELLATION if proved else FailureClass.UNKNOWN_OUTCOME
                ),
                default_reason=(
                    "cancelled and confirmed stopped"
                    if proved
                    else "a stop was requested; whether the work stopped is unknown"
                ),
            )

        # -- timeout is a fact about us, never about the far side -------
        if outcome.timed_out or failure is ProviderFailure.TIMEOUT:
            return self._result(
                request,
                started,
                completed,
                detail,
                outcome,
                worker_outcome=WorkerOutcome.TIMEOUT,
                failure_class=FailureClass.TIMEOUT,
                default_reason=(
                    "the provider stopped responding; whether it applied the "
                    "change is unknown"
                ),
            )

        failure_class = outcome.failure_class or PROVIDER_FAILURE_CLASSES.get(
            failure, FailureClass.UNKNOWN_OUTCOME
        )
        unresolved = outcome.is_unresolved or failure_class.is_ambiguous
        return self._result(
            request,
            started,
            completed,
            detail,
            outcome,
            worker_outcome=(
                WorkerOutcome.UNKNOWN_OUTCOME if unresolved else WorkerOutcome.FAILURE
            ),
            failure_class=(
                FailureClass.UNKNOWN_OUTCOME
                if unresolved and not failure_class.is_ambiguous
                else failure_class
            ),
            default_reason="the provider refused the operation",
        )

    def _result(
        self,
        request: WorkerExecutionRequest,
        started: datetime,
        completed: datetime,
        detail: Mapping[str, Any],
        outcome: ProviderOutcome,
        *,
        worker_outcome: WorkerOutcome,
        failure_class: FailureClass,
        default_reason: str,
    ) -> WorkerExecutionResult:
        return WorkerExecutionResult(
            outcome=worker_outcome,
            binding_id=request.binding.binding_id,
            attempt_id=str(request.attempt_id),
            started_at=started,
            completed_at=completed,
            failure=FailureRecord(
                failure_class=failure_class,
                reason=(outcome.error_message or default_reason)[:500],
                occurred_at=completed,
                source=f"adapter:{type(self).__name__}",
                # Phase 11.1-K: the provider's own Retry-After, carried to the
                # retry policy on the failure it decides from.
                detail=({"provider_retry_after_seconds": outcome.retry_after_seconds}
                        if outcome.retry_after_seconds is not None else {}),
            ),
            observed_effect=outcome.observed_effect,
            detail=dict(detail),
            cancellation_support=type(self).CANCELLATION,
        )

    @staticmethod
    def _effect_anomaly(
        outcome: ProviderOutcome, binding: BoundCapability
    ) -> Optional[str]:
        """Whether the reported effect contradicts what was bound. Both ways.

        Over-claiming is checked again by ``WorkerRuntime``; it is checked here
        too because an adapter is the last place the provider's own account is
        available, and catching it here means the reason names the provider.

        Under-claiming is checked *only* here: a mutating binding reported as a
        ``READ`` would be recorded as a read, and a read is retried freely.
        """
        observed = outcome.observed_effect
        if observed is None:
            return None
        order = {
            SideEffectClass.READ: 0,
            SideEffectClass.REVERSIBLE_WRITE: 1,
            SideEffectClass.IRREVERSIBLE_WRITE: 2,
            SideEffectClass.DESTRUCTIVE: 3,
        }
        if order[observed] > order[binding.side_effect_class]:
            return (
                f"the adapter reports a {observed.value} effect but the bound "
                f"capability declares {binding.side_effect_class.value}; the "
                "operation exceeded what was authorized"
            )
        if binding.mutates and observed is SideEffectClass.READ:
            return (
                f"the adapter reports a read but the bound capability declares "
                f"{binding.side_effect_class.value}; recording a mutation as a read "
                "would make it freely repeatable. The binding is authoritative"
            )
        return None

    def _refused(
        self,
        request: WorkerExecutionRequest,
        started: datetime,
        failure_class: FailureClass,
        reason: str,
        *,
        provider_failure: ProviderFailure = ProviderFailure.ADAPTER_UNAVAILABLE,
    ) -> WorkerExecutionResult:
        """A refusal before anything was sent, classified the same way a provider
        answer would be.

        ``provider_failure`` is carried even though no provider was contacted, so
        that recovery reads one vocabulary rather than two: an operator looking
        at ``provider_failure`` should not have to know whether the refusal came
        from this side or the far side to interpret it.
        """
        return WorkerExecutionResult.failed(
            binding_id=request.binding.binding_id,
            attempt_id=str(request.attempt_id),
            started_at=started,
            failure=FailureRecord(
                failure_class=failure_class,
                reason=reason,
                source=f"adapter:{type(self).__name__}",
            ),
            detail={
                **self._identity_detail(None),
                "provider_delivery": ProviderDelivery.NOT_ATTEMPTED.value,
                "provider_failure": provider_failure.value,
                "security_relevant": provider_failure.is_security_relevant,
            },
        )

    # ------------------------------------------------------------------
    # Measurement
    # ------------------------------------------------------------------

    def _count(
        self,
        name: str,
        authority: Optional[ProviderAuthority],
        **extra: str,
    ) -> None:
        """Labels carry tenant, provider, adapter and environment. Nothing else.

        No operation payload, no credential reference, no URL, no capability
        reference — a capability ref is high-cardinality and identifies one
        tenant's ability, which as a metric dimension turns a dashboard into an
        inventory of what each tenant can do.
        """
        if self._metrics is None or name not in ADAPTER_METRICS:
            return
        try:
            self._metrics.increment(
                name,
                labels={
                    "tenant": authority.tenant_id if authority else "unknown",
                    "provider": self._provider.provider_id,
                    "adapter": type(self).__name__,
                    "environment": (
                        authority.environment.value if authority else "unknown"
                    ),
                    **extra,
                },
            )
        except Exception:  # noqa: BLE001 - measurement never changes an outcome
            log.debug("adapter metric failed", exc_info=False)

    # ------------------------------------------------------------------
    # The provider call
    # ------------------------------------------------------------------

    def _perform(
        self,
        context: Any,
        request: WorkerExecutionRequest,
        authority: ProviderAuthority,
    ) -> ProviderOutcome:
        """Make the provider call. The only thing a subclass implements.

        Called with a transport confirmed attached, a request already gated, a
        binding already validated, and an authority already re-checked. It has
        one job, and one attempt.
        """
        raise NotImplementedError(
            f"{type(self).__name__} defines an adapter seam and performs no work"
        )
